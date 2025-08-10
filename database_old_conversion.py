# database_postgresql.py - PostgreSQL version
import psycopg2
import psycopg2.extras
from psycopg2 import pool
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
import atexit
import time
import os

class Database:
    def __init__(self, db_url=None):
        # PostgreSQL connection string
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://thequietend_user:thequietend_pass@localhost/thequietend_db?host=/tmp')
        self.db_path = "postgresql://thequietend_db"  # Compatibility attribute for old SQLite code
        self.lock = threading.Lock()
        self._shutdown = False
        
        # Create connection pool
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                1, 20,  # min and max connections
                self.db_url,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            print("[OK] PostgreSQL connection pool created")
        except Exception as e:
            print(f"❌ Failed to create connection pool: {e}")
            raise
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def _convert_sqlite_to_postgresql(self, query):
        """Convert SQLite syntax to PostgreSQL syntax"""
        import re
        
        # Replace AUTOINCREMENT with SERIAL PRIMARY KEY
        query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        
        # Convert parameter placeholders from ? to %s
        query = query.replace('?', '%s')
        
        # Convert boolean comparisons 
        # Handle various boolean column patterns
        boolean_patterns = [
            (r'\bis_logged_in\s*=\s*1\b', 'is_logged_in = true'),
            (r'\bis_logged_in\s*=\s*0\b', 'is_logged_in = false'),
            (r'\bhas_jobs\s*=\s*1\b', 'has_jobs = true'),
            (r'\bhas_jobs\s*=\s*0\b', 'has_jobs = false'),
            (r'\bis_active\s*=\s*1\b', 'is_active = true'),
            (r'\bis_active\s*=\s*0\b', 'is_active = false'),
            (r'\bis_delivered\s*=\s*1\b', 'is_delivered = true'),
            (r'\bis_delivered\s*=\s*0\b', 'is_delivered = false'),
            (r'\bis_claimed\s*=\s*1\b', 'is_claimed = true'),
            (r'\bis_claimed\s*=\s*0\b', 'is_claimed = false'),
            (r'\bis_completed\s*=\s*1\b', 'is_completed = true'),
            (r'\bis_completed\s*=\s*0\b', 'is_completed = false'),
            (r'\bis_alive\s*=\s*1\b', 'is_alive = true'),
            (r'\bis_alive\s*=\s*0\b', 'is_alive = false'),
            (r'\bis_taken\s*=\s*1\b', 'is_taken = true'),
            (r'\bis_taken\s*=\s*0\b', 'is_taken = false'),
            (r'\bis_public\s*=\s*1\b', 'is_public = true'),
            (r'\bis_public\s*=\s*0\b', 'is_public = false'),
            (r'\bis_open\s*=\s*1\b', 'is_open = true'),
            (r'\bis_open\s*=\s*0\b', 'is_open = false'),
        ]
        
        for pattern, replacement in boolean_patterns:
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
        
        # Convert SQLite datetime functions to PostgreSQL
        datetime_patterns = [
            (r'\bdatetime\(\'now\'\)', 'NOW()'),
            (r'\bdatetime\(\"now\"\)', 'NOW()'),
            (r'\bdatetime\([^)]+\)', 'NOW()'),  # Generic datetime() function conversion
            (r'\bSTRFTIME\(\'%s\',\s*\'now\'\)', 'EXTRACT(EPOCH FROM NOW())::INTEGER'),
            (r'\bJULIANDAY\(\'now\'\)', 'EXTRACT(EPOCH FROM NOW())/86400.0 + 2440587.5'),
        ]
        
        for pattern, replacement in datetime_patterns:
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
        
        return query
    
    def _convert_result_format(self, result, fetch_type):
        """Convert PostgreSQL dict-like results to tuple-like for backwards compatibility"""
        if not result:
            return result
            
        if fetch_type == 'one':
            if hasattr(result, 'keys'):  # dict-like object
                # Preserve the original column order from the SELECT statement
                # RealDictCursor preserves column order
                return tuple(result.values()) if result else None
            return result
        elif fetch_type == 'all':
            if result and hasattr(result[0], 'keys'):  # list of dict-like objects
                # For all results, preserve the column order consistently
                return [tuple(row.values()) if row else None for row in result]
            return result
        
        return result
    
    def cleanup(self):
        """Cleanup all connections on shutdown"""
        print("🔄 Database cleanup starting...")
        self._shutdown = True
        
        # Close connection pool
        try:
            if hasattr(self, 'connection_pool') and self.connection_pool:
                self.connection_pool.closeall()
                print("✅ Connection pool closed")
        except Exception as e:
            print(f"⚠️ Error closing connection pool: {e}")
        
        print("✅ Database cleanup completed")
    
    def get_connection(self):
        """Get a database connection from the pool"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        try:
            conn = self.connection_pool.getconn()
            # Test the connection
            if conn.closed:
                # Connection is closed, try to get a new one
                self.connection_pool.putconn(conn, close=True)
                conn = self.connection_pool.getconn()
            return conn
        except Exception as e:
            print(f"❌ Error getting connection from pool: {e}")
            # Try to recreate the connection pool
            try:
                self.connection_pool.closeall()
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    1, 20,
                    self.db_url,
                    cursor_factory=psycopg2.extras.RealDictCursor
                )
                return self.connection_pool.getconn()
            except:
                raise e
    
    def _close_connection(self, conn):
        """Return a connection to the pool"""
        try:
            self.connection_pool.putconn(conn)
        except Exception as e:
            print(f"⚠️ Error returning connection to pool: {e}")
            try:
                conn.close()
            except:
                pass
    
    def execute_read_query(self, query, params=None, fetch='all'):
        """Execute a read-only query"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            
            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            else:
                return None
        except Exception as e:
            print(f"❌ Read query error: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            raise
        finally:
            self._close_connection(conn)
    
    def execute_query(self, query, params=None, fetch=None, many=False):
        """Execute a single query with automatic connection management"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
            
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            conn = None
            try:
                if many and params:
                    # Bulk operations
                    with self.lock:
                        conn = self.get_connection()
                        try:
                            cursor = conn.cursor()
                            cursor.executemany(query, params)
                            conn.commit()
                            return cursor.rowcount if fetch is None else None
                        finally:
                            cursor.close()
                            self._close_connection(conn)
                else:
                    # Single operations
                    with self.lock:
                        conn = self.get_connection()
                        cursor = None
                        try:
                            cursor = conn.cursor()
                            
                            # Convert SQLite syntax to PostgreSQL
                            converted_query = self._convert_sqlite_to_postgresql(query)
                            
                            if params:
                                cursor.execute(converted_query, params)
                            else:
                                cursor.execute(converted_query)
                            
                            if fetch == 'one':
                                result = cursor.fetchone()
                            elif fetch == 'all':
                                result = cursor.fetchall()
                            elif fetch == 'lastrowid':
                                # PostgreSQL doesn't have lastrowid, use RETURNING clause or sequence
                                result = None
                            else:
                                result = cursor.rowcount
                            
                            conn.commit()
                            
                            # Convert PostgreSQL dict-like results to tuple-like for backwards compatibility
                            if result and fetch in ['one', 'all']:
                                result = self._convert_result_format(result, fetch)
                            
                            return result
                        finally:
                            if cursor:
                                cursor.close()
                            self._close_connection(conn)
                            
            except psycopg2.Error as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Database error on attempt {attempt + 1}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))
                    if conn:
                        try:
                            conn.rollback()
                            self._close_connection(conn)
                        except:
                            pass
                    continue
                else:
                    print(f"❌ Database error after {attempt + 1} attempts: {e}")
                    if conn:
                        try:
                            conn.rollback()
                            self._close_connection(conn)
                        except:
                            pass
                    raise
            except Exception as e:
                print(f"❌ Unexpected database error: {e}")
                print(f"Query: {query}")
                if not many:
                    print(f"Params: {params}")
                else:
                    print(f"Params: {len(params) if params else 0} rows")
                if conn:
                    try:
                        conn.rollback()
                        self._close_connection(conn)
                    except:
                        pass
                raise
    
    def bulk_execute(self, operations: list):
        """Execute multiple operations in a single transaction"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            conn = None
            try:
                with self.lock:
                    conn = self.get_connection()
                    cursor = None
                    try:
                        cursor = conn.cursor()
                        
                        # Execute all operations in a single transaction
                        for query, params in operations:
                            converted_query = self._convert_sqlite_to_postgresql(query)
                            if params:
                                cursor.execute(converted_query, params)
                            else:
                                cursor.execute(converted_query)
                        
                        conn.commit()
                        return True
                    finally:
                        if cursor:
                            cursor.close()
                        self._close_connection(conn)
                        
            except psycopg2.Error as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Database error during bulk operation on attempt {attempt + 1}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))
                    if conn:
                        try:
                            conn.rollback()
                            self._close_connection(conn)
                        except:
                            pass
                    continue
                else:
                    print(f"❌ Bulk operation failed after {attempt + 1} attempts: {e}")
                    if conn:
                        try:
                            conn.rollback()
                            self._close_connection(conn)
                        except:
                            pass
                    raise
            except Exception as e:
                print(f"❌ Unexpected error during bulk operation: {e}")
                if conn:
                    try:
                        conn.rollback()
                        self._close_connection(conn)
                    except:
                        pass
                raise
        
        return False

    def begin_transaction(self):
        """Begin a transaction and return connection and cursor"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        return conn, cursor
    
    def commit_transaction(self, conn, cursor):
        """Commit a transaction"""
        try:
            conn.commit()
        finally:
            cursor.close()
            self._close_connection(conn)
    
    def rollback_transaction(self, conn, cursor):
        """Rollback a transaction"""
        try:
            conn.rollback()
        finally:
            cursor.close()
            self._close_connection(conn)

    # Add placeholder methods that might be used by the bot but aren't essential for PostgreSQL
    def init_database(self):
        """Database is already initialized by pgloader"""
        pass
    
    def check_database_integrity(self):
        """Check database integrity"""
        try:
            result = self.execute_read_query("SELECT 1", fetch='one')
            return bool(result)
        except:
            return False
    
    def check_integrity(self):
        """Alias for check_database_integrity for compatibility"""
        return self.check_database_integrity()
    
    def vacuum_database(self):
        """PostgreSQL equivalent - analyze tables for statistics"""
        try:
            self.execute_query("ANALYZE;")
            print("✅ Database analyzed successfully")
        except Exception as e:
            print(f"❌ Failed to analyze database: {e}")