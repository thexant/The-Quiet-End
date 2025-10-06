# database.py - Fixed version with proper shutdown handling and WAL mode
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
import atexit
import time
from config import DATABASE_CONFIG

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DATABASE_CONFIG['db_path']
        self.lock = threading.Lock()
        self._shutdown = False
        self._active_connections = set()
        self._connection_lock = threading.Lock()
        
        # Enable WAL mode and optimize settings
        self._setup_database()
        self.init_database()
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def _setup_database(self):
        """Setup database with WAL mode and optimizations"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            # Increase cache size for better performance
            conn.execute("PRAGMA cache_size=10000")
            # Synchronous mode - NORMAL is safe with WAL
            conn.execute("PRAGMA synchronous=NORMAL")
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys=ON")
            # Increase timeout
            conn.execute("PRAGMA busy_timeout=30000")
            conn.commit()
            print("[OK] Database WAL mode enabled and optimized")
        finally:
            conn.close()
    
    def cleanup(self):
        """Cleanup all connections on shutdown"""
        print("🔄 Database cleanup starting...")
        self._shutdown = True
        
        # Set a deadline for cleanup
        import time
        deadline = time.time() + 10  # 10 second maximum
        
        # Wait for active connections to finish
        while self._active_connections and time.time() < deadline:
            active_count = len(self._active_connections)
            if active_count > 0:
                print(f"⏳ Waiting for {active_count} database connection(s) to close...")
            time.sleep(0.1)
        
        # Force close any remaining connections
        with self._connection_lock:
            for conn in list(self._active_connections):
                try:
                    # Try to rollback any pending transactions
                    conn.rollback()
                    conn.close()
                except:
                    pass
            self._active_connections.clear()
        
        # Checkpoint the WAL file multiple times to ensure it's fully written
        checkpoint_attempts = 3
        for attempt in range(checkpoint_attempts):
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
                print(f"✅ Database WAL checkpoint {attempt + 1}/{checkpoint_attempts} completed")
                time.sleep(0.2)  # Small delay between checkpoints
            except Exception as e:
                print(f"⚠️ WAL checkpoint attempt {attempt + 1} failed: {e}")
        
        # Final integrity check
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] == 'ok':
                print("✅ Database integrity verified")
            else:
                print("⚠️ Database integrity check failed")
        except Exception as e:
            print(f"⚠️ Could not verify database integrity: {e}")
        
        print("✅ Database cleanup completed")
    
    def force_close_transactions(self):
        """Force close all pending transactions - emergency use only"""
        print("⚠️ Force closing all database transactions...")
        with self._connection_lock:
            for conn in list(self._active_connections):
                try:
                    # Set a very short timeout to force failure
                    conn.execute("PRAGMA busy_timeout=100")
                    conn.rollback()
                    conn.close()
                except:
                    # Force close even if rollback fails
                    try:
                        conn.close()
                    except:
                        pass
        self._active_connections.clear()
        
    def get_connection(self):
        """Get a database connection with proper tracking"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        # Use a much longer timeout for better reliability
        conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        
        # Track active connections
        with self._connection_lock:
            self._active_connections.add(conn)
        
        return conn
    
    def _close_connection(self, conn):
        """Safely close a connection and remove from tracking"""
        with self._connection_lock:
            if conn in self._active_connections:
                self._active_connections.remove(conn)
        try:
            conn.close()
        except:
            pass
    
    def get_active_connection_count(self):
        """Get the current number of active connections for monitoring"""
        with self._connection_lock:
            return len(self._active_connections)
    
    def cleanup_stale_connections(self):
        """Force cleanup of any stale connections - emergency measure"""
        with self._connection_lock:
            stale_connections = list(self._active_connections)
            for conn in stale_connections:
                try:
                    conn.close()
                    self._active_connections.discard(conn)
                    print(f"🧹 Cleaned up stale connection")
                except:
                    pass
            if stale_connections:
                print(f"🧹 Cleaned up {len(stale_connections)} stale connections")
            
    def execute_read_query(self, query, params=None, fetch='all'):
        """Execute a read-only query without acquiring the main lock"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        # Don't use the main lock for read operations
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
        finally:
            self._close_connection(conn)
            
    def execute_query(self, query, params=None, fetch=None, many=False):
        """Execute a single query with automatic connection management and reduced lock time"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
            
        max_retries = 3
        retry_delay = 0.1  # Reduced retry delay for faster recovery
        
        for attempt in range(max_retries):
            try:
                # Use shorter lock duration by preparing everything first
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
                            self._close_connection(conn)  # FIX: Properly close connection
                else:
                    # Single operations with minimal lock time
                    with self.lock:
                        conn = self.get_connection()
                        try:
                            cursor = conn.cursor()
                            
                            if params:
                                cursor.execute(query, params)
                            else:
                                cursor.execute(query)
                            
                            if fetch == 'one':
                                result = cursor.fetchone()
                            elif fetch == 'all':
                                result = cursor.fetchall()
                            elif fetch == 'lastrowid':
                                result = cursor.lastrowid
                            else:
                                result = None
                            
                            conn.commit()
                            return result
                        finally:
                            cursor.close()
                            self._close_connection(conn)  # FIX: Properly close connection
                
            except sqlite3.Error as e:
                if attempt < max_retries - 1 and "database is locked" in str(e):
                    print(f"⚠️ Database locked on attempt {attempt + 1}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    print(f"❌ Database error after {attempt + 1} attempts: {e}")
                    raise
            except Exception as e:
                print(f"❌ Unexpected database error: {e}")
                print(f"Query: {query}")
                if not many:
                    print(f"Params: {params}")
                else:
                    print(f"Params: {len(params) if params else 0} rows")
                raise
    
    def bulk_execute(self, operations: list):
        """Execute multiple operations in a single transaction to reduce lock time"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with self.lock:
                    conn = self.get_connection()
                    try:
                        cursor = conn.cursor()
                        
                        # Execute all operations in a single transaction
                        for query, params in operations:
                            if params:
                                cursor.execute(query, params)
                            else:
                                cursor.execute(query)
                        
                        conn.commit()
                        return True
                    finally:
                        cursor.close()
                        self._close_connection(conn)  # FIX: Properly close connection
                        
            except sqlite3.Error as e:
                if attempt < max_retries - 1 and "database is locked" in str(e):
                    print(f"⚠️ Database locked during bulk operation on attempt {attempt + 1}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    print(f"❌ Bulk operation failed after {attempt + 1} attempts: {e}")
                    raise
            except Exception as e:
                print(f"❌ Unexpected error during bulk operation: {e}")
                raise
        
        return False

    def begin_transaction(self):
        """Begin a transaction with proper connection tracking and verification"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        # Check connection pool health before acquiring lock (with bypass for urgent operations)
        try:
            self._verify_connection_pool_health()
        except Exception as e:
            print(f"⚠️ Connection pool health check failed, continuing anyway: {e}")
        
        print("🔧 DB DEBUG: Attempting to acquire database lock...")
        # Try to acquire lock with timeout
        acquired = self.lock.acquire(timeout=30)
        if not acquired:
            print("🔧 DB DEBUG: Failed to acquire database lock after 30s timeout")
            raise RuntimeError("Could not acquire database lock for transaction")
        
        print("🔧 DB DEBUG: Database lock acquired, getting connection...")
        try:
            conn = self.get_connection()
            # Light verification - just ensure connection works
            try:
                self._verify_connection_state(conn)
            except Exception as e:
                print(f"⚠️ Connection verification failed, continuing anyway: {e}")
                # Don't block the transaction if verification fails
            
            print("🔧 DB DEBUG: Connection verified, starting IMMEDIATE transaction...")
            # Use IMMEDIATE to lock the database right away
            conn.execute("BEGIN IMMEDIATE")
            print("🔧 DB DEBUG: Transaction started successfully")
            return conn
        except Exception as e:
            print(f"🔧 DB DEBUG: Failed to begin transaction: {e}")
            # If we fail to begin transaction, release the lock
            self.lock.release()
            raise
            
    def execute_bulk_read_queries(self, queries_and_params):
        """Execute multiple read-only queries in a single connection to reduce overhead"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        results = []
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for query, params, fetch_type in queries_and_params:
                cursor.execute(query, params or [])
                
                if fetch_type == 'one':
                    results.append(cursor.fetchone())
                elif fetch_type == 'all':
                    results.append(cursor.fetchall())
                else:
                    results.append(None)
            return results
        finally:
            cursor.close()  # FIX: Close cursor too
            self._close_connection(conn)
            
    def execute_in_transaction(self, conn, query, params=None, fetch=None):
        """Execute a query within an existing transaction"""
        try:
            cursor = conn.cursor()
            # Log DELETE and INSERT statements for debugging
            if query.strip().upper().startswith(('DELETE', 'INSERT')):
                query_type = query.split()[0].upper()
                if 'DELETE' in query.upper():
                    # Extract table name from DELETE FROM table_name
                    from_match = query.upper().find(' FROM ')
                    if from_match > 0:
                        table_part = query[from_match + 6:].split()[0]  # Get first word after FROM
                        print(f"🔧 DB DEBUG: Executing {query_type} FROM {table_part}")
                elif 'INSERT' in query.upper():
                    # Extract table name from INSERT INTO table_name
                    into_match = query.upper().find(' INTO ')
                    if into_match > 0:
                        table_part = query[into_match + 6:].split()[0]  # Get first word after INTO
                        print(f"🔧 DB DEBUG: Executing {query_type} INTO {table_part}")
            
            import time
            start_time = time.time()
            cursor.execute(query, params or [])
            execution_time = time.time() - start_time
            
            if execution_time > 1.0:  # Log slow queries
                print(f"🔧 DB DEBUG: Slow query ({execution_time:.2f}s): {query[:100]}...")

            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            elif fetch == 'lastrowid':
                return cursor.lastrowid
            return None
        except sqlite3.Error as e:
            print(f"❌ Database error during transaction: {e}\nQuery: {query}\nParams: {params}")
            raise e

    def executemany_in_transaction(self, conn, query, params_list):
        """Execute a bulk query within an existing transaction"""
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
        except sqlite3.Error as e:
            print(f"❌ Database error during executemany: {e}\nQuery: {query}")
            raise e

    def commit_transaction(self, conn):
        """Commit transaction and clean up"""
        try:
            conn.commit()
        finally:
            self._close_connection(conn)
            if self.lock.locked():
                self.lock.release()

    def rollback_transaction(self, conn):
        """Rollback transaction and clean up"""
        try:
            conn.rollback()
        finally:
            self._close_connection(conn)
            if self.lock.locked():
                self.lock.release()
    
    def _verify_connection_pool_health(self):
        """Verify connection pool is not exhausted and clean up stale connections"""
        try:
            # Quick check with timeout protection
            with self._connection_lock:
                active_count = len(self._active_connections)
                
                # Only do expensive cleanup if we have many connections
                if active_count > 15:  # Increased threshold to be less aggressive
                    print(f"⚠️ High number of active connections: {active_count}, cleaning up...")
                    # Only clean up obviously stale connections to avoid hanging
                    stale_connections = []
                    checked_count = 0
                    
                    for conn in list(self._active_connections):
                        # Limit how many connections we test to avoid hanging
                        if checked_count >= 5:
                            break
                        checked_count += 1
                        
                        try:
                            # Quick test with timeout-like behavior
                            cursor = conn.cursor()
                            cursor.execute("SELECT 1")
                            cursor.fetchone()
                        except:
                            # Connection is stale, mark for removal
                            stale_connections.append(conn)
                    
                    # Remove stale connections
                    for conn in stale_connections:
                        try:
                            self._active_connections.discard(conn)
                            conn.close()
                        except:
                            pass
                    
                    if stale_connections:
                        print(f"🔧 Cleaned up {len(stale_connections)} stale connections")
                
        except Exception as e:
            print(f"⚠️ Error during connection pool health check (skipping): {e}")
            # Don't let health check failures block the main operation
    
    def _verify_connection_state(self, conn):
        """Verify a connection is in a usable state"""
        try:
            # Just test basic functionality - don't mess with transactions
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if not result or result[0] != 1:
                raise RuntimeError("Connection failed basic functionality test")
            
        except Exception as e:
            print(f"❌ Connection state verification failed: {e}")
            raise RuntimeError(f"Connection is not in a usable state: {e}")
    
    def get_active_connection_count(self):
        """Get the current number of active connections"""
        with self._connection_lock:
            return len(self._active_connections)
    
    def check_integrity(self):
        """Check database integrity"""
        try:
            result = self.execute_query("PRAGMA integrity_check", fetch='one')
            return result[0] == 'ok' if result else False
        except:
            return False
    
    def vacuum_database(self):
        """Vacuum the database to optimize storage"""
        try:
            # Cannot vacuum within a transaction
            conn = self.get_connection()
            try:
                conn.execute("VACUUM")
                print("✅ Database vacuumed successfully")
            finally:
                self._close_connection(conn)
        except Exception as e:
            print(f"❌ Failed to vacuum database: {e}")
                
    def init_database(self):
        """Initialize all database tables"""
        queries = [
            # Characters table - ADD callsign field
            '''CREATE TABLE IF NOT EXISTS characters (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                callsign TEXT,
                appearance TEXT,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                money INTEGER DEFAULT 500,
                engineering INTEGER DEFAULT 5,
                navigation INTEGER DEFAULT 5,
                combat INTEGER DEFAULT 5,
                medical INTEGER DEFAULT 5,
                current_location INTEGER,
                ship_id INTEGER,
                group_id INTEGER,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_home_id INTEGER,
                defense INTEGER DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS ship_customization (
                ship_id INTEGER PRIMARY KEY,
                paint_job TEXT DEFAULT 'Default',
                decals TEXT DEFAULT 'None',
                interior_style TEXT DEFAULT 'Standard',
                name_plate TEXT DEFAULT 'Standard',
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS home_invitations (
                invitation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes (home_id),
                FOREIGN KEY (inviter_id) REFERENCES characters (user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            '''ALTER TABLE ships ADD COLUMN tier INTEGER DEFAULT 1''',
            '''ALTER TABLE ships ADD COLUMN condition_rating INTEGER DEFAULT 100''',
            '''ALTER TABLE ships ADD COLUMN engine_level INTEGER DEFAULT 1''',
            '''ALTER TABLE ships ADD COLUMN hull_level INTEGER DEFAULT 1''',
            '''ALTER TABLE ships ADD COLUMN systems_level INTEGER DEFAULT 1''',
            '''ALTER TABLE ships ADD COLUMN special_mods TEXT DEFAULT '[]' ''',
            '''ALTER TABLE ships ADD COLUMN market_value INTEGER DEFAULT 10000''',
            '''ALTER TABLE ships ADD COLUMN max_upgrade_slots INTEGER DEFAULT 3''',
            '''ALTER TABLE ships ADD COLUMN speed_rating INTEGER DEFAULT 5''',
            '''CREATE TABLE IF NOT EXISTS galaxy_info (
                galaxy_id INTEGER PRIMARY KEY DEFAULT 1,
                name TEXT NOT NULL DEFAULT 'Unknown Galaxy',
                start_date TEXT NOT NULL DEFAULT '2751-01-01',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                time_scale_factor REAL DEFAULT 4.0,
                time_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_time_paused BOOLEAN DEFAULT 0,
                time_paused_at TIMESTAMP,
                current_ingame_time TIMESTAMP
            )''',

            '''CREATE TABLE IF NOT EXISTS endgame_config (
                config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                length_minutes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )''',

            '''CREATE TABLE IF NOT EXISTS endgame_evacuations (
                evacuation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                evacuation_deadline TEXT NOT NULL,
                warned_at TEXT NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            '''ALTER TABLE locations ADD COLUMN faction TEXT DEFAULT 'Independent' ''',
            # Character birth and identity info
            '''CREATE TABLE IF NOT EXISTS character_identity (
                user_id INTEGER PRIMARY KEY,
                birth_month INTEGER NOT NULL,
                birth_day INTEGER NOT NULL,
                birth_year INTEGER NOT NULL,
                age INTEGER NOT NULL,
                biography TEXT,
                birthplace_id INTEGER,
                id_scrubbed BOOLEAN DEFAULT 0,
                scrubbed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (birthplace_id) REFERENCES locations (location_id)
            )''',
            '''ALTER TABLE galaxy_info ADD COLUMN last_shift_check TEXT''',
            '''ALTER TABLE galaxy_info ADD COLUMN current_shift TEXT''',
            '''ALTER TABLE galaxy_info ADD COLUMN is_manually_paused BOOLEAN DEFAULT 0''',
            # Character reputation system
            '''CREATE TABLE IF NOT EXISTS character_reputation (
                reputation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                reputation INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(user_id, location_id)
            )''',
            # Add federal supplies flag to locations  
            '''ALTER TABLE locations ADD COLUMN has_federal_supplies BOOLEAN DEFAULT 0''',
            # Combat states table - tracks active fights
            '''CREATE TABLE IF NOT EXISTS combat_states (
                combat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                target_npc_id INTEGER NOT NULL,
                target_npc_type TEXT NOT NULL CHECK(target_npc_type IN ('static', 'dynamic')),
                combat_type TEXT NOT NULL CHECK(combat_type IN ('ground', 'space')),
                location_id INTEGER NOT NULL,
                last_action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_npc_action_time TIMESTAMP,
                player_can_act_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS location_homes (
                home_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                home_type TEXT NOT NULL,
                home_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                owner_id INTEGER,
                purchase_date TIMESTAMP,
                is_available BOOLEAN DEFAULT 1,
                interior_description TEXT,
                activities TEXT,
                value_modifier REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS home_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes (home_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS home_interiors (
                interior_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                channel_id INTEGER,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes (home_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS home_market_listings (
                listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                asking_price INTEGER NOT NULL,
                original_price INTEGER NOT NULL,
                listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (home_id) REFERENCES location_homes (home_id),
                FOREIGN KEY (seller_id) REFERENCES characters (user_id)
            )''',
            # NPC respawn tracking for static NPCs
            '''CREATE TABLE IF NOT EXISTS npc_respawn_queue (
                respawn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_npc_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                scheduled_respawn_time TIMESTAMP NOT NULL,
                npc_data TEXT NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Sub-locations within main locations
            '''CREATE TABLE IF NOT EXISTS sub_locations (
                sub_location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_location_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sub_type TEXT NOT NULL,
                description TEXT,
                thread_id INTEGER,
                channel_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_location_id) REFERENCES locations (location_id)
            )''',
            # Supply and demand economy tracking
            '''CREATE TABLE IF NOT EXISTS location_economy (
                economy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                item_category TEXT,
                item_name TEXT,
                status TEXT NOT NULL CHECK(status IN ('in_demand', 'surplus', 'normal')),
                price_modifier REAL DEFAULT 1.0,
                stock_modifier REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(location_id, item_category, item_name)
            )''',

            # Economic news events
            '''CREATE TABLE IF NOT EXISTS economic_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                item_category TEXT,
                item_name TEXT,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Black market information
            '''CREATE TABLE IF NOT EXISTS black_markets (
                market_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                market_type TEXT DEFAULT 'underground',
                reputation_required INTEGER DEFAULT 0,
                is_hidden BOOLEAN DEFAULT 1,
                discovered_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Add this to the queries list in init_database()
            '''CREATE TABLE IF NOT EXISTS logbook_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                logbook_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_id INTEGER NOT NULL,
                entry_title TEXT NOT NULL,
                entry_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ingame_date TEXT NOT NULL
            )''',
            # Black market items
            '''CREATE TABLE IF NOT EXISTS black_market_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock INTEGER DEFAULT -1,
                description TEXT,
                legality TEXT DEFAULT 'illegal',
                FOREIGN KEY (market_id) REFERENCES black_markets (market_id)
            )''',
            # Ships table (unchanged)
            '''CREATE TABLE IF NOT EXISTS ships (
                ship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                ship_type TEXT DEFAULT 'Basic Hauler',
                fuel_capacity INTEGER DEFAULT 100,
                current_fuel INTEGER DEFAULT 100,
                fuel_efficiency INTEGER DEFAULT 5,
                combat_rating INTEGER DEFAULT 10,
                hull_integrity INTEGER DEFAULT 100,
                max_hull INTEGER DEFAULT 100,
                cargo_capacity INTEGER DEFAULT 50,
                cargo_used INTEGER DEFAULT 0,
                ship_hp INTEGER DEFAULT 50,
                max_ship_hp INTEGER DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
            )''',
            
            # Locations table (unchanged)
            '''CREATE TABLE IF NOT EXISTS locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                location_type TEXT NOT NULL,
                description TEXT,
                wealth_level INTEGER DEFAULT 5,
                population INTEGER DEFAULT 100,
                x_coord REAL DEFAULT 0,
                y_coord REAL DEFAULT 0,
                system_name TEXT,
                has_jobs BOOLEAN DEFAULT 1,
                has_shops BOOLEAN DEFAULT 1,
                has_medical BOOLEAN DEFAULT 1,
                has_repairs BOOLEAN DEFAULT 1,
                has_fuel BOOLEAN DEFAULT 1,
                has_upgrades BOOLEAN DEFAULT 0,
                is_generated BOOLEAN DEFAULT 0,
                is_derelict BOOLEAN DEFAULT 0,
                gate_status TEXT DEFAULT 'active',
                reconnection_eta TIMESTAMP,
                abandoned_since TIMESTAMP,
                original_location_id INTEGER,
                relocated_to_id INTEGER,
                channel_last_active TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                faction TEXT DEFAULT 'Independent',
                has_federal_supplies BOOLEAN DEFAULT 0,
                establishment_date TEXT,
                established_date TEXT,
                has_black_market BOOLEAN DEFAULT 0,
                generated_income INTEGER DEFAULT 0,
                has_shipyard BOOLEAN DEFAULT 0
            )''',
            
            '''CREATE TABLE IF NOT EXISTS corridors (
                corridor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                origin_location INTEGER NOT NULL,
                destination_location INTEGER NOT NULL,
                travel_time INTEGER DEFAULT 300,
                fuel_cost INTEGER DEFAULT 20,
                danger_level INTEGER DEFAULT 3,
                corridor_type TEXT DEFAULT 'ungated',
                is_active BOOLEAN DEFAULT 1,
                is_generated BOOLEAN DEFAULT 0,
                is_bidirectional BOOLEAN DEFAULT 1,
                last_shift TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_shift TIMESTAMP,
                FOREIGN KEY (origin_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                leader_id INTEGER NOT NULL,
                current_location INTEGER,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (leader_id) REFERENCES characters (user_id),
                FOREIGN KEY (current_location) REFERENCES locations (location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                reward_money INTEGER DEFAULT 100,
                required_skill TEXT,
                min_skill_level INTEGER DEFAULT 0,
                danger_level INTEGER DEFAULT 1,
                duration_minutes INTEGER DEFAULT 60,
                is_taken BOOLEAN DEFAULT 0,
                taken_by INTEGER,
                taken_at TIMESTAMP,
                expires_at TIMESTAMP,
                job_status TEXT DEFAULT 'available',
                destination_location_id INTEGER,
                karma_change INTEGER DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location_id) REFERENCES locations (location_id),
                FOREIGN KEY (taken_by) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS inventory (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                description TEXT,
                value INTEGER DEFAULT 0,
                metadata TEXT,
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS travel_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                origin_location INTEGER NOT NULL,
                destination_location INTEGER NOT NULL,
                corridor_id INTEGER NOT NULL,
                temp_channel_id INTEGER,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'traveling',
                last_event_time TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (group_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (origin_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id),
                FOREIGN KEY (corridor_id) REFERENCES corridors (corridor_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS shop_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock INTEGER DEFAULT -1,
                description TEXT,
                metadata TEXT,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS shop_refresh (
                location_id INTEGER PRIMARY KEY,
                last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS server_config (
                guild_id INTEGER PRIMARY KEY,
                colony_category_id INTEGER,
                station_category_id INTEGER,
                outpost_category_id INTEGER,
                gate_category_id INTEGER,
                transit_category_id INTEGER,
                ship_interiors_category_id INTEGER,
                residences_category_id INTEGER,
                max_location_channels INTEGER DEFAULT 50,
                channel_timeout_hours INTEGER DEFAULT 48,
                auto_cleanup_enabled BOOLEAN DEFAULT 1,
                setup_completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS galaxy_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS repeaters (
                repeater_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                owner_id INTEGER,
                repeater_type TEXT DEFAULT 'built_in',
                receive_range INTEGER DEFAULT 10,
                transmit_range INTEGER DEFAULT 5,
                is_active BOOLEAN DEFAULT 1,
                deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS corridor_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transit_channel_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                severity INTEGER DEFAULT 1,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                affected_users TEXT,
                responses TEXT
            )''',
            # Add these to your database.py init_database() queries list:
            
            '''CREATE TABLE IF NOT EXISTS pvp_opt_outs (
                user_id INTEGER PRIMARY KEY,
                opted_out BOOLEAN DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',


            '''CREATE TABLE IF NOT EXISTS pvp_combat_states (
                combat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER NOT NULL,
                defender_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                combat_type TEXT NOT NULL CHECK(combat_type IN ('ground', 'space')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attacker_can_act_time TIMESTAMP,
                defender_can_act_time TIMESTAMP,
                current_turn TEXT DEFAULT 'attacker' CHECK(current_turn IN ('attacker', 'defender')),
                FOREIGN KEY (attacker_id) REFERENCES characters (user_id),
                FOREIGN KEY (defender_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS pvp_cooldowns (
                cooldown_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                cooldown_type TEXT NOT NULL CHECK(cooldown_type IN ('flee', 'robbery')),
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player1_id) REFERENCES characters (user_id),
                FOREIGN KEY (player2_id) REFERENCES characters (user_id),
                UNIQUE(player1_id, player2_id, cooldown_type)
            )''',

            '''CREATE TABLE IF NOT EXISTS pending_robberies (
                robbery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                robber_id INTEGER NOT NULL,
                victim_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                message_id INTEGER,
                channel_id INTEGER,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (robber_id) REFERENCES characters (user_id),
                FOREIGN KEY (victim_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS character_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                item_type TEXT DEFAULT 'misc',
                acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(user_id, item_name)
            )''',

            # Add alignment column to characters
            '''ALTER TABLE characters ADD COLUMN alignment TEXT DEFAULT 'neutral' ''',

            # Add alignment column to characters if it doesn't exist
            '''ALTER TABLE characters ADD COLUMN alignment TEXT DEFAULT 'neutral' CHECK(alignment IN ('loyal', 'neutral', 'bandit'))''',
            
            '''CREATE TABLE IF NOT EXISTS location_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                description TEXT,
                value INTEGER DEFAULT 0,
                dropped_by INTEGER,
                dropped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (dropped_by) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS home_storage (
                storage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                description TEXT,
                value INTEGER DEFAULT 0,
                stored_by INTEGER NOT NULL,
                stored_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                FOREIGN KEY (stored_by) REFERENCES characters(user_id)
            )''',
            
            
            '''ALTER TABLE location_homes ADD COLUMN storage_capacity INTEGER DEFAULT 50''',
            
            '''CREATE TABLE IF NOT EXISTS home_upgrades (
                upgrade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                upgrade_name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                daily_income INTEGER DEFAULT 0,
                purchase_price INTEGER NOT NULL,
                purchased_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                UNIQUE(home_id, upgrade_type)
            )''',

            '''CREATE TABLE IF NOT EXISTS home_income (
                income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                accumulated_income INTEGER DEFAULT 0,
                last_collected DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                UNIQUE(home_id)
            )''',
            
            
            '''CREATE TABLE IF NOT EXISTS location_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                message TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_generated BOOLEAN DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (author_id) REFERENCES characters (user_id)
            )''',
            
            
            '''CREATE TABLE IF NOT EXISTS home_recovery_tracking (
                tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                home_id INTEGER NOT NULL,
                entered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_recovery DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters(user_id),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                UNIQUE(user_id)
            )''',
            
            
            '''CREATE TABLE IF NOT EXISTS home_customizations (
                customization_id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_id INTEGER NOT NULL,
                wall_color TEXT DEFAULT 'Beige',
                floor_type TEXT DEFAULT 'Standard Tile',
                lighting_style TEXT DEFAULT 'Standard',
                furniture_style TEXT DEFAULT 'Basic',
                ambiance TEXT DEFAULT 'Cozy',
                custom_description TEXT,
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                UNIQUE(home_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS combat_encounters (
                encounter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                participants TEXT NOT NULL,
                encounter_type TEXT NOT NULL,
                location_id INTEGER,
                status TEXT DEFAULT 'active',
                initiative_order TEXT,
                current_turn INTEGER DEFAULT 0,
                channel_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS character_experience (
                user_id INTEGER PRIMARY KEY,
                total_exp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                skill_points INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS ship_upgrades (
                upgrade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ship_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                upgrade_name TEXT NOT NULL,
                bonus_value INTEGER DEFAULT 0,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',
            
           
            '''CREATE TABLE IF NOT EXISTS factions (
                faction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                emoji TEXT NOT NULL,
                description TEXT,
                leader_id INTEGER NOT NULL,
                is_public BOOLEAN DEFAULT 0,
                bank_balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (leader_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS faction_members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS faction_invites (
                invite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (inviter_id) REFERENCES characters (user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS faction_sales_tax (
                tax_id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                tax_percentage INTEGER DEFAULT 0,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(location_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS faction_payouts (
                payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                collected BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            '''ALTER TABLE location_ownership ADD COLUMN faction_id INTEGER REFERENCES factions(faction_id)''',
            
            
            
            '''CREATE TABLE IF NOT EXISTS group_ships (
                group_id INTEGER PRIMARY KEY,
                ship_id INTEGER NOT NULL,
                captain_id INTEGER,
                crew_positions TEXT,
                FOREIGN KEY (group_id) REFERENCES groups (group_id),
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id),
                FOREIGN KEY (captain_id) REFERENCES characters (user_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS job_tracking (
                tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                start_location INTEGER NOT NULL,
                required_duration REAL NOT NULL,
                time_at_location REAL DEFAULT 0.0,
                last_location_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (job_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (start_location) REFERENCES locations (location_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS group_invites (
                invite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (group_id),
                FOREIGN KEY (inviter_id) REFERENCES characters (user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS group_vote_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                vote_data TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (group_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS group_votes (
                vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vote_value TEXT NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES group_vote_sessions (session_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            '''ALTER TABLE characters ADD COLUMN location_status TEXT DEFAULT 'docked' ''',
            '''CREATE TABLE IF NOT EXISTS user_location_panels (
                user_id INTEGER,
                location_id INTEGER,
                message_id INTEGER,
                channel_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, location_id)
            )''',
            # Add experience fields to characters
            '''ALTER TABLE characters ADD COLUMN experience INTEGER DEFAULT 0''',
            '''ALTER TABLE characters ADD COLUMN level INTEGER DEFAULT 1''',
            '''ALTER TABLE characters ADD COLUMN skill_points INTEGER DEFAULT 5''',

            # Add ship customization fields
            '''ALTER TABLE ships ADD COLUMN ship_class TEXT DEFAULT 'civilian' ''',
            '''ALTER TABLE ships ADD COLUMN upgrade_slots INTEGER DEFAULT 3''',
            '''ALTER TABLE ships ADD COLUMN used_upgrade_slots INTEGER DEFAULT 0''',
            '''ALTER TABLE server_config ADD COLUMN pvp_enabled BOOLEAN DEFAULT 0''',
            '''ALTER TABLE server_config ADD COLUMN combat_channel_id INTEGER''',
            '''ALTER TABLE server_config ADD COLUMN ship_interiors_category_id INTEGER''',
            #JOB STATUS
            '''ALTER TABLE jobs ADD COLUMN job_status TEXT DEFAULT 'available' ''',
            # Add establishment date to locations
            '''ALTER TABLE locations ADD COLUMN established_date TEXT''',

            # Add black market flag to locations
            '''ALTER TABLE locations ADD COLUMN has_black_market BOOLEAN DEFAULT 0''',
            # Login/logout system columns
            '''ALTER TABLE characters ADD COLUMN is_logged_in BOOLEAN DEFAULT 0''',
            '''ALTER TABLE characters ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP''',
            '''ALTER TABLE characters ADD COLUMN login_time TIMESTAMP''',

            # AFK warning system
            '''CREATE TABLE IF NOT EXISTS afk_warnings (
                warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                warning_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS search_cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_search_time TIMESTAMP,
                location_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Ship interior data
            '''ALTER TABLE ships ADD COLUMN exterior_description TEXT''',
            '''ALTER TABLE ships ADD COLUMN interior_description TEXT''',
            '''ALTER TABLE ships ADD COLUMN channel_id INTEGER''',

            # Character location inside a ship
            '''ALTER TABLE characters ADD COLUMN current_ship_id INTEGER''',
            # Add ship docking location tracking
            '''ALTER TABLE ships ADD COLUMN docked_at_location INTEGER''',
            # Ship ownership and storage system
            '''ALTER TABLE characters ADD COLUMN active_ship_id INTEGER''',
            '''CREATE TABLE IF NOT EXISTS player_ships (
                ship_storage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                ship_id INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                stored_at_shipyard INTEGER,
                acquired_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES characters (user_id),
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id),
                FOREIGN KEY (stored_at_shipyard) REFERENCES locations (location_id)
            )''',

            # Add shipyard service to locations
            '''ALTER TABLE locations ADD COLUMN has_shipyard BOOLEAN DEFAULT 0''',
            
            '''ALTER TABLE locations ADD COLUMN generated_income INTEGER DEFAULT 0''',

            # Track ship description additions
            '''CREATE TABLE IF NOT EXISTS ship_customizations (
                customization_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ship_id INTEGER NOT NULL,
                customization_type TEXT NOT NULL,
                addition_text TEXT NOT NULL,
                added_by INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cost_paid INTEGER DEFAULT 0,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id),
                FOREIGN KEY (added_by) REFERENCES characters (user_id)
            )''',
            # Add galactic updates channel to server config
            '''ALTER TABLE server_config ADD COLUMN galactic_updates_channel_id INTEGER''',

            # Add news queue table for delayed news delivery
            '''CREATE TABLE IF NOT EXISTS news_queue (
                news_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                news_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location_id INTEGER,
                event_data TEXT,
                scheduled_delivery TIMESTAMP NOT NULL,
                delay_hours REAL DEFAULT 0,
                is_delivered BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Location ownership system tables
            '''CREATE TABLE IF NOT EXISTS location_ownership (
                ownership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL UNIQUE,
                owner_id INTEGER,
                group_id INTEGER,
                faction_id INTEGER,
                docking_fee INTEGER DEFAULT 0,
                purchase_price INTEGER NOT NULL,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ownership_type TEXT DEFAULT 'individual',
                custom_name TEXT,
                custom_description TEXT,
                last_upkeep_payment TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                upkeep_due_date TIMESTAMP,
                total_invested INTEGER DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id),
                FOREIGN KEY (group_id) REFERENCES groups (group_id),
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id)
            )''',
            
            '''ALTER TABLE location_ownership ADD COLUMN docking_fee INTEGER DEFAULT 0''',
            
            '''CREATE TABLE IF NOT EXISTS location_upgrades (
                upgrade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                upgrade_level INTEGER DEFAULT 1,
                cost INTEGER NOT NULL,
                upgrade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS location_access_control (
                control_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                user_id INTEGER,
                group_id INTEGER,
                access_type TEXT DEFAULT 'allowed',
                fee_amount INTEGER DEFAULT 0,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (group_id) REFERENCES groups (group_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS location_income_log (
                income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                income_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                source_user_id INTEGER,
                generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                collected BOOLEAN DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (source_user_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS location_storage (
                storage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                stored_by INTEGER NOT NULL,
                stored_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (stored_by) REFERENCES characters (user_id)
            )''',
                        # Static NPCs tied to locations
            '''CREATE TABLE IF NOT EXISTS static_npcs (
                npc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                occupation TEXT,
                personality TEXT,
                trade_specialty TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alignment TEXT DEFAULT 'neutral' CHECK(alignment IN ('loyal', 'neutral', 'bandit')),
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                combat_rating INTEGER DEFAULT 5,
                is_alive BOOLEAN DEFAULT 1,
                credits INTEGER DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Admin Game Panel
            '''CREATE TABLE IF NOT EXISTS game_panels (
                panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, channel_id)
            )''',
            # Dynamic NPCs that move around the galaxy
            '''CREATE TABLE IF NOT EXISTS dynamic_npcs (
                npc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                callsign TEXT UNIQUE NOT NULL,
                age INTEGER NOT NULL,
                ship_name TEXT NOT NULL,
                ship_type TEXT NOT NULL,
                current_location INTEGER,
                destination_location INTEGER,
                travel_start_time TIMESTAMP,
                travel_duration INTEGER,
                last_radio_message TIMESTAMP,
                last_location_action TIMESTAMP,
                credits INTEGER DEFAULT 0,
                is_alive BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alignment TEXT DEFAULT 'neutral' CHECK(alignment IN ('loyal', 'neutral', 'bandit')),
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                combat_rating INTEGER DEFAULT 5,
                ship_hull INTEGER DEFAULT 100,
                max_ship_hull INTEGER DEFAULT 100,
                FOREIGN KEY (current_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id)
            )''',
            '''ALTER TABLE server_config ADD COLUMN status_voice_channel_id INTEGER''',
            '''ALTER TABLE server_config ADD COLUMN tqe_role_id INTEGER''',
            # NPC inventory for trading
            '''CREATE TABLE IF NOT EXISTS npc_inventory (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                price INTEGER NOT NULL,
                description TEXT,
                rarity TEXT DEFAULT 'common',
                FOREIGN KEY (npc_id) REFERENCES static_npcs (npc_id)
            )''',
                        # NPC-offered jobs table
            '''CREATE TABLE IF NOT EXISTS npc_jobs (
                npc_job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                job_title TEXT NOT NULL,
                job_description TEXT NOT NULL,
                reward_money INTEGER NOT NULL,
                reward_items TEXT,
                required_skill TEXT,
                min_skill_level INTEGER DEFAULT 0,
                danger_level INTEGER DEFAULT 1,
                duration_minutes INTEGER DEFAULT 60,
                requirements TEXT,
                is_available BOOLEAN DEFAULT 1,
                max_completions INTEGER DEFAULT -1,
                current_completions INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (npc_id) REFERENCES static_npcs (npc_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS galactic_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER,
                event_title TEXT NOT NULL,
                event_description TEXT NOT NULL,
                historical_figure TEXT,
                event_date TEXT NOT NULL,
                event_type TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Performance indexes for galactic_history table
            '''CREATE INDEX IF NOT EXISTS idx_galactic_history_location_id ON galactic_history (location_id)''',
            '''CREATE INDEX IF NOT EXISTS idx_galactic_history_event_date ON galactic_history (event_date)''',
            '''CREATE INDEX IF NOT EXISTS idx_galactic_history_location_date ON galactic_history (location_id, event_date)''',
            # NPC job completions tracking
            '''CREATE TABLE IF NOT EXISTS npc_job_completions (
                completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_job_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (npc_job_id) REFERENCES npc_jobs (npc_job_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS npc_relationships (
                relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                relationship_score INTEGER DEFAULT 0,
                married BOOLEAN DEFAULT 0,
                married_at TIMESTAMP,
                UNIQUE(npc_id, npc_type, user_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS npc_job_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                npc_job_id INTEGER,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (npc_job_id) REFERENCES npc_jobs (npc_job_id),
                FOREIGN KEY (job_id) REFERENCES jobs (job_id)
            )''',

            # Enhanced NPC inventory for trading
            '''CREATE TABLE IF NOT EXISTS npc_trade_inventory (
                trade_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                price_credits INTEGER,
                trade_for_item TEXT,
                trade_quantity_required INTEGER DEFAULT 1,
                rarity TEXT DEFAULT 'common',
                description TEXT,
                metadata TEXT,
                is_available BOOLEAN DEFAULT 1,
                restocks_at TIMESTAMP,
                FOREIGN KEY (npc_id) REFERENCES static_npcs (npc_id)
            )''',
            # Add character image URL support
            '''ALTER TABLE characters ADD COLUMN image_url TEXT''',
            '''CREATE UNIQUE INDEX IF NOT EXISTS idx_galaxy_singleton ON galaxy_info (galaxy_id)''',
            '''CREATE TABLE IF NOT EXISTS active_beacons (
                beacon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                beacon_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                message_content TEXT NOT NULL,
                transmissions_sent INTEGER DEFAULT 0,
                max_transmissions INTEGER DEFAULT 3,
                interval_minutes INTEGER DEFAULT 20,
                next_transmission TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS ship_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ship_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',
            '''ALTER TABLE characters ADD COLUMN auto_rename INTEGER DEFAULT 0 NOT NULL''',
            '''ALTER TABLE black_market_items ADD COLUMN stock INTEGER DEFAULT 1''',

            '''ALTER TABLE shop_items ADD COLUMN metadata TEXT DEFAULT NULL''',
            '''ALTER TABLE shop_items ADD COLUMN sold_by_player BOOLEAN DEFAULT FALSE''',
            '''ALTER TABLE jobs ADD COLUMN unloading_started_at DATETIME;''',
            '''ALTER TABLE travel_sessions ADD COLUMN last_event_time TIMESTAMP''',
            '''ALTER TABLE corridors ADD COLUMN is_bidirectional BOOLEAN DEFAULT 1''',
            '''ALTER TABLE corridors ADD COLUMN corridor_type TEXT DEFAULT 'ungated' ''',
            '''CREATE TABLE IF NOT EXISTS federal_supply_items (
                supply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock INTEGER DEFAULT -1,
                description TEXT,
                clearance_level INTEGER DEFAULT 1,
                requires_id BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS federal_access (
                access_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                access_level INTEGER DEFAULT 1,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (granted_by) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS federal_reputation (
                user_id INTEGER PRIMARY KEY,
                reputation_points INTEGER DEFAULT 0,
                loyalty_level TEXT DEFAULT 'neutral' CHECK(loyalty_level IN ('traitor', 'suspect', 'neutral', 'trusted', 'exemplary')),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            '''CREATE TABLE IF NOT EXISTS federal_services (
                service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                service_type TEXT NOT NULL CHECK(service_type IN ('id_verification', 'permit_issuance', 'loyalty_certification', 'security_clearance', 'military_contracts')),
                service_name TEXT NOT NULL,
                cost INTEGER NOT NULL,
                requirements TEXT,
                is_available BOOLEAN DEFAULT 1,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Service cooldowns for sub-location services
            '''CREATE TABLE IF NOT EXISTS service_cooldowns (
                user_id INTEGER NOT NULL,
                service_type TEXT NOT NULL,
                location_id INTEGER NOT NULL,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, service_type, location_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            # Travel micro-events tracking
            '''CREATE TABLE IF NOT EXISTS travel_micro_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                travel_session_id INTEGER,
                transit_channel_id INTEGER,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                corridor_id INTEGER,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded BOOLEAN DEFAULT 0,
                skill_used TEXT,
                roll_result INTEGER,
                difficulty INTEGER,
                success BOOLEAN,
                xp_awarded INTEGER DEFAULT 0,
                damage_taken INTEGER DEFAULT 0,
                damage_type TEXT,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (corridor_id) REFERENCES corridors (corridor_id)
            )''',
            
            # Ship interior system tables
            '''CREATE TABLE IF NOT EXISTS ship_interiors (
                ship_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS ship_invitations (
                invitation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ship_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id),
                FOREIGN KEY (inviter_id) REFERENCES characters (user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Shipyard inventory system for persistent ship stock
            '''CREATE TABLE IF NOT EXISTS shipyard_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                ship_name TEXT NOT NULL,
                ship_type TEXT NOT NULL,
                ship_class TEXT NOT NULL,
                tier INTEGER NOT NULL,
                price INTEGER NOT NULL,
                cargo_capacity INTEGER NOT NULL,
                speed_rating INTEGER NOT NULL,
                combat_rating INTEGER NOT NULL,
                fuel_efficiency INTEGER NOT NULL,
                special_features TEXT,
                is_player_sold BOOLEAN DEFAULT 0,
                original_owner_id INTEGER,
                condition_rating INTEGER DEFAULT 100,
                market_value INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (original_owner_id) REFERENCES characters (user_id)
            )''',
            
            # Ship exchange system tables
            '''CREATE TABLE IF NOT EXISTS ship_exchange_listings (
                listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ship_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                listed_at_location INTEGER NOT NULL,
                asking_price INTEGER DEFAULT 0,
                desired_ship_types TEXT DEFAULT '[]',
                listing_description TEXT,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id),
                FOREIGN KEY (listed_at_location) REFERENCES locations (location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS ship_exchange_offers (
                offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                offerer_id INTEGER NOT NULL,
                offered_ship_id INTEGER NOT NULL,
                credits_adjustment INTEGER DEFAULT 0,
                offer_message TEXT,
                offer_expires_at TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'declined', 'expired')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES ship_exchange_listings (listing_id),
                FOREIGN KEY (offerer_id) REFERENCES characters (user_id),
                FOREIGN KEY (offered_ship_id) REFERENCES ships (ship_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS ship_exchange_history (
                exchange_id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_listing_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                seller_ship_id INTEGER NOT NULL,
                buyer_ship_id INTEGER NOT NULL,
                credits_exchanged INTEGER DEFAULT 0,
                exchange_location INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES characters (user_id),
                FOREIGN KEY (buyer_id) REFERENCES characters (user_id),
                FOREIGN KEY (exchange_location) REFERENCES locations (location_id)
            )''',
            
            # Ambient events tracking table
            '''CREATE TABLE IF NOT EXISTS ambient_event_tracking (
                location_id INTEGER PRIMARY KEY,
                last_ambient_event TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_events_generated INTEGER DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Active location effects from events
            '''CREATE TABLE IF NOT EXISTS active_location_effects (
                effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value TEXT NOT NULL,
                source_event TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Add reconnection_eta field for moving gates
            '''ALTER TABLE locations ADD COLUMN reconnection_eta TIMESTAMP''',
            
            # Add abandoned_since field for tracking abandoned gate duration
            '''ALTER TABLE locations ADD COLUMN abandoned_since TIMESTAMP''',
            
            # Quest system tables
            '''CREATE TABLE IF NOT EXISTS quests (
                quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                start_location_id INTEGER NOT NULL,
                reward_money INTEGER DEFAULT 0,
                reward_items TEXT DEFAULT '[]',
                reward_experience INTEGER DEFAULT 0,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                max_completions INTEGER DEFAULT -1,
                current_completions INTEGER DEFAULT 0,
                required_level INTEGER DEFAULT 1,
                required_items TEXT DEFAULT '[]',
                estimated_duration TEXT,
                danger_level INTEGER DEFAULT 1,
                FOREIGN KEY (start_location_id) REFERENCES locations (location_id),
                FOREIGN KEY (created_by) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS quest_objectives (
                objective_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_id INTEGER NOT NULL,
                objective_order INTEGER NOT NULL,
                objective_type TEXT NOT NULL CHECK(objective_type IN ('travel', 'obtain_item', 'deliver_item', 'sell_item', 'earn_money', 'visit_location', 'talk_to_npc')),
                target_location_id INTEGER,
                target_item TEXT,
                target_quantity INTEGER DEFAULT 1,
                target_amount INTEGER DEFAULT 0,
                target_npc_id INTEGER,
                description TEXT NOT NULL,
                is_optional BOOLEAN DEFAULT 0,
                FOREIGN KEY (quest_id) REFERENCES quests (quest_id) ON DELETE CASCADE,
                FOREIGN KEY (target_location_id) REFERENCES locations (location_id),
                UNIQUE(quest_id, objective_order)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS quest_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                current_objective INTEGER DEFAULT 1,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                objectives_completed TEXT DEFAULT '[]',
                quest_status TEXT DEFAULT 'active' CHECK(quest_status IN ('active', 'completed', 'failed', 'abandoned')),
                completion_data TEXT DEFAULT '{}',
                FOREIGN KEY (quest_id) REFERENCES quests (quest_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(quest_id, user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS quest_completions (
                completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reward_received TEXT DEFAULT '{}',
                completion_time_minutes INTEGER,
                FOREIGN KEY (quest_id) REFERENCES quests (quest_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            # Equipment system tables
            '''CREATE TABLE IF NOT EXISTS character_equipment (
                equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                slot_name TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                equipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (item_id) REFERENCES inventory (item_id),
                UNIQUE(user_id, slot_name)
            )''',

            '''CREATE TABLE IF NOT EXISTS active_stat_modifiers (
                modifier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                modifier_type TEXT NOT NULL,
                stat_name TEXT NOT NULL,
                modifier_value INTEGER NOT NULL,
                source_type TEXT NOT NULL CHECK(source_type IN ('equipment', 'consumable')),
                source_item_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            # Add equipment properties to inventory
            '''ALTER TABLE inventory ADD COLUMN equippable BOOLEAN DEFAULT 0''',
            '''ALTER TABLE inventory ADD COLUMN equipment_slot TEXT''',
            '''ALTER TABLE inventory ADD COLUMN stat_modifiers TEXT''',
            
            # Add defense stat to characters
            '''ALTER TABLE characters ADD COLUMN defense INTEGER DEFAULT 0''',
            
            # Add guild tracking for characters
            '''ALTER TABLE characters ADD COLUMN guild_id INTEGER''',
            
            # Create per-guild location channel tracking table
            '''CREATE TABLE IF NOT EXISTS guild_location_channels (
                channel_mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                channel_last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, location_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )'''
        ]
        
        for q in queries:
            try:
                # we only care about running it once; IF NOT EXISTS handles tables,
                # but ALTER TABLE will throw if the column is already there
                self.execute_query(q)
            except sqlite3.OperationalError as e:
                # skip errors like "duplicate column name" or syntax issues
                if "duplicate column name" in str(e) or "already exists" in str(e):
                    pass
                else:
                    print(f"⚠️ Skipping database init query (already exists?): {e}")
            except Exception as e:
                # log any other unexpected errors but keep going
                print(f"❌ Error running init query: {e}")
        self._add_faction_column_safely()
        self._classify_existing_corridors()

    # Effect management methods
    def add_location_effect(self, location_id: int, effect_type: str, effect_value: str, source_event: str, duration_hours: int = 24):
        """Add an active effect to a location (replaces existing effect of same type)"""
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        # Remove existing effects of the same type at this location to prevent stacking
        self.execute_query(
            "DELETE FROM active_location_effects WHERE location_id = ? AND effect_type = ?",
            (location_id, effect_type)
        )
        
        self.execute_query(
            """INSERT INTO active_location_effects 
               (location_id, effect_type, effect_value, source_event, expires_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (location_id, effect_type, str(effect_value), source_event, expires_at)
        )

    def get_active_location_effects(self, location_id: int):
        """Get all active effects for a location"""
        from datetime import datetime
        # First clean up expired effects
        self.execute_query(
            "DELETE FROM active_location_effects WHERE expires_at < ?",
            (datetime.now(),)
        )
        
        # Return active effects
        return self.execute_query(
            """SELECT effect_type, effect_value, source_event, created_at, expires_at 
               FROM active_location_effects 
               WHERE location_id = ? AND (expires_at IS NULL OR expires_at > ?)""",
            (location_id, datetime.now()),
            fetch='all'
        )

    def remove_location_effects(self, location_id: int, effect_type: str = None):
        """Remove effects from a location, optionally filtered by type"""
        if effect_type:
            self.execute_query(
                "DELETE FROM active_location_effects WHERE location_id = ? AND effect_type = ?",
                (location_id, effect_type)
            )
        else:
            self.execute_query(
                "DELETE FROM active_location_effects WHERE location_id = ?",
                (location_id,)
            )

    def cleanup_expired_effects(self):
        """Remove all expired effects"""
        from datetime import datetime
        result = self.execute_query(
            "DELETE FROM active_location_effects WHERE expires_at < ?",
            (datetime.now(),)
        )
        return result


    def _add_faction_column_safely(self):
        """Safely add faction column to locations table if it doesn't exist"""
        try:
            # Check if faction column exists
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(locations)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'faction' not in columns:
                cursor.execute("ALTER TABLE locations ADD COLUMN faction TEXT DEFAULT 'Independent'")
                conn.commit()
                print("✅ Added faction column to locations table")
            
            self._close_connection(conn)
        except Exception as e:
            print(f"❌ Error adding faction column: {e}")

    def _classify_existing_corridors(self):
        """Classify existing corridors with proper corridor_type values"""
        try:
            # Check if corridor_type column exists
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(corridors)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'corridor_type' not in columns:
                print("⚠️ corridor_type column not found - migration will handle this")
                self._close_connection(conn)
                return
            
            # Check ALL corridors for classification (including fixing misclassified ones)
            cursor.execute("SELECT COUNT(*) FROM corridors")
            total_count = cursor.fetchone()[0]
            
            print(f"🔄 Validating classification of {total_count} corridors...")
            
            # Get all corridors with location and system information
            cursor.execute("""
                SELECT c.corridor_id, c.name, c.origin_location, c.destination_location,
                       o.location_type as origin_type, d.location_type as dest_type,
                       o.system_name as origin_system, d.system_name as dest_system,
                       c.corridor_type as current_type
                FROM corridors c
                JOIN locations o ON c.origin_location = o.location_id
                JOIN locations d ON c.destination_location = d.location_id
            """)
            
            all_corridors = cursor.fetchall()
            
            # Batch update corridors by type (track changes)
            updates = {'gated': [], 'ungated': [], 'local_space': []}
            corrections = 0
            
            for corridor_id, name, origin_id, dest_id, origin_type, dest_type, origin_system, dest_system, current_type in all_corridors:
                # Use improved classification logic with system information
                same_system = origin_system == dest_system
                
                # Local space routes (name-based detection or same system connections)
                if any(keyword in name.lower() for keyword in ['local space', 'approach', 'arrival', 'departure']):
                    correct_type = 'local_space'
                # Major location ↔ Gate connections must ALWAYS be local_space if in same system
                elif (origin_type in ['colony', 'space_station', 'outpost'] and dest_type == 'gate') or \
                     (origin_type == 'gate' and dest_type in ['colony', 'space_station', 'outpost']):
                    if same_system:
                        correct_type = 'local_space'  # Major location to local gate = local space ONLY
                    else:
                        correct_type = 'ungated'  # Major location to distant gate = ungated
                # Gate to gate connections
                elif origin_type == 'gate' and dest_type == 'gate':
                    if same_system:
                        correct_type = 'local_space'  # Gates in same system = local space
                    else:
                        correct_type = 'gated'  # Gates in different systems = gated corridor
                # Major location to major location connections
                else:
                    correct_type = 'ungated'  # Major location to major location = ungated
                
                # Only update if the type needs to be corrected
                if current_type != correct_type:
                    updates[correct_type].append(corridor_id)
                    corrections += 1
            
            # Execute batch updates only for corridors that need correction
            for corridor_type, corridor_ids in updates.items():
                if corridor_ids:
                    placeholders = ','.join(['?' for _ in corridor_ids])
                    cursor.execute(f"""
                        UPDATE corridors SET corridor_type = ? 
                        WHERE corridor_id IN ({placeholders})
                    """, [corridor_type] + corridor_ids)
                    print(f"  ✅ Corrected {len(corridor_ids)} corridors to '{corridor_type}'")
            
            conn.commit()
            self._close_connection(conn)
            
            if corrections > 0:
                print(f"✅ Fixed {corrections} misclassified corridors out of {total_count} total")
            else:
                print(f"✅ All {total_count} corridors already correctly classified")
            
        except Exception as e:
            print(f"❌ Error classifying corridors: {e}")
            if 'conn' in locals():
                self._close_connection(conn)
    
    def get_galaxy_setting(self, setting_name: str, default_value: str = None) -> str:
        """Get a galaxy setting value"""
        try:
            result = self.execute_query(
                "SELECT setting_value FROM galaxy_settings WHERE setting_name = ?",
                (setting_name,),
                fetch='one'
            )
            return result[0] if result else default_value
        except Exception as e:
            print(f"Error getting galaxy setting {setting_name}: {e}")
            return default_value
    
    def set_galaxy_setting(self, setting_name: str, setting_value: str):
        """Set a galaxy setting value"""
        try:
            self.execute_query(
                """INSERT OR REPLACE INTO galaxy_settings (setting_name, setting_value, updated_at)
                   VALUES (?, ?, datetime('now'))""",
                (setting_name, setting_value)
            )
        except Exception as e:
            print(f"Error setting galaxy setting {setting_name}: {e}")
    
    # Ship Exchange Helper Methods
    def cleanup_expired_ship_listings(self):
        """Remove expired ship exchange listings and offers"""
        try:
            # Deactivate expired listings
            self.execute_query(
                "UPDATE ship_exchange_listings SET is_active = 0 WHERE expires_at < datetime('now') AND is_active = 1"
            )
            
            # Mark expired offers
            self.execute_query(
                "UPDATE ship_exchange_offers SET status = 'expired' WHERE offer_expires_at < datetime('now') AND status = 'pending'"
            )
            
            print("✅ Cleaned up expired ship exchange listings and offers")
        except Exception as e:
            print(f"❌ Error cleaning up expired ship exchange data: {e}")
    
    def get_ship_exchange_stats(self, location_id: int = None):
        """Get statistics about ship exchange activity"""
        try:
            if location_id:
                # Stats for specific location
                active_listings = self.execute_query(
                    "SELECT COUNT(*) FROM ship_exchange_listings WHERE listed_at_location = ? AND is_active = 1 AND expires_at > datetime('now')",
                    (location_id,),
                    fetch='one'
                )[0]
                
                pending_offers = self.execute_query(
                    '''SELECT COUNT(*) FROM ship_exchange_offers seo
                       JOIN ship_exchange_listings sel ON seo.listing_id = sel.listing_id
                       WHERE sel.listed_at_location = ? AND seo.status = 'pending' ''',
                    (location_id,),
                    fetch='one'
                )[0]
                
                completed_exchanges = self.execute_query(
                    "SELECT COUNT(*) FROM ship_exchange_history WHERE exchange_location = ?",
                    (location_id,),
                    fetch='one'
                )[0]
                
                return {
                    'active_listings': active_listings,
                    'pending_offers': pending_offers,
                    'completed_exchanges': completed_exchanges
                }
            else:
                # Global stats
                active_listings = self.execute_query(
                    "SELECT COUNT(*) FROM ship_exchange_listings WHERE is_active = 1 AND expires_at > datetime('now')",
                    fetch='one'
                )[0]
                
                pending_offers = self.execute_query(
                    "SELECT COUNT(*) FROM ship_exchange_offers WHERE status = 'pending'",
                    fetch='one'
                )[0]
                
                completed_exchanges = self.execute_query(
                    "SELECT COUNT(*) FROM ship_exchange_history",
                    fetch='one'
                )[0]
                
                return {
                    'active_listings': active_listings,
                    'pending_offers': pending_offers,
                    'completed_exchanges': completed_exchanges
                }
                
        except Exception as e:
            print(f"❌ Error getting ship exchange stats: {e}")
            return {'active_listings': 0, 'pending_offers': 0, 'completed_exchanges': 0}
    
    def get_user_ship_exchange_activity(self, user_id: int):
        """Get a user's ship exchange activity summary"""
        try:
            # Active listings
            active_listings = self.execute_query(
                '''SELECT COUNT(*) FROM ship_exchange_listings 
                   WHERE owner_id = ? AND is_active = 1 AND expires_at > datetime('now') ''',
                (user_id,),
                fetch='one'
            )[0]
            
            # Pending offers made
            offers_made = self.execute_query(
                "SELECT COUNT(*) FROM ship_exchange_offers WHERE offerer_id = ? AND status = 'pending'",
                (user_id,),
                fetch='one'
            )[0]
            
            # Pending offers received
            offers_received = self.execute_query(
                '''SELECT COUNT(*) FROM ship_exchange_offers seo
                   JOIN ship_exchange_listings sel ON seo.listing_id = sel.listing_id
                   WHERE sel.owner_id = ? AND seo.status = 'pending' ''',
                (user_id,),
                fetch='one'
            )[0]
            
            # Completed exchanges (as seller)
            exchanges_sold = self.execute_query(
                "SELECT COUNT(*) FROM ship_exchange_history WHERE seller_id = ?",
                (user_id,),
                fetch='one'
            )[0]
            
            # Completed exchanges (as buyer)
            exchanges_bought = self.execute_query(
                "SELECT COUNT(*) FROM ship_exchange_history WHERE buyer_id = ?",
                (user_id,),
                fetch='one'
            )[0]
            
            return {
                'active_listings': active_listings,
                'offers_made': offers_made,
                'offers_received': offers_received,
                'exchanges_sold': exchanges_sold,
                'exchanges_bought': exchanges_bought
            }
            
        except Exception as e:
            print(f"❌ Error getting user ship exchange activity: {e}")
            return {'active_listings': 0, 'offers_made': 0, 'offers_received': 0, 'exchanges_sold': 0, 'exchanges_bought': 0}
    
    # Shipyard Inventory Management Methods
    def get_shipyard_inventory(self, location_id: int) -> List[Dict]:
        """Get all ships in a shipyard's inventory"""
        try:
            result = self.execute_query(
                """SELECT inventory_id, ship_name, ship_type, ship_class, tier, price,
                          cargo_capacity, speed_rating, combat_rating, fuel_efficiency,
                          special_features, is_player_sold, original_owner_id,
                          condition_rating, market_value, added_at
                   FROM shipyard_inventory 
                   WHERE location_id = ?
                   ORDER BY is_player_sold ASC, tier ASC, price ASC""",
                (location_id,),
                fetch='all'
            )
            
            ships = []
            for row in result:
                ships.append({
                    'inventory_id': row[0],
                    'name': row[1],
                    'type': row[2],
                    'class': row[3],
                    'tier': row[4],
                    'price': row[5],
                    'cargo_capacity': row[6],
                    'speed_rating': row[7],
                    'combat_rating': row[8],
                    'fuel_efficiency': row[9],
                    'special_features': row[10],
                    'is_player_sold': bool(row[11]),
                    'original_owner_id': row[12],
                    'condition_rating': row[13],
                    'market_value': row[14],
                    'added_at': row[15]
                })
            return ships
        except Exception as e:
            print(f"Error getting shipyard inventory: {e}")
            return []
    
    def add_ship_to_inventory(self, location_id: int, ship_data: Dict, is_player_sold: bool = False, original_owner_id: int = None):
        """Add a ship to shipyard inventory"""
        try:
            self.execute_query(
                """INSERT INTO shipyard_inventory 
                   (location_id, ship_name, ship_type, ship_class, tier, price,
                    cargo_capacity, speed_rating, combat_rating, fuel_efficiency,
                    special_features, is_player_sold, original_owner_id,
                    condition_rating, market_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    location_id,
                    ship_data['name'],
                    ship_data['type'],
                    ship_data['class'],
                    ship_data['tier'],
                    ship_data['price'],
                    ship_data['cargo_capacity'],
                    ship_data['speed_rating'],
                    ship_data['combat_rating'],
                    ship_data['fuel_efficiency'],
                    ship_data.get('special_features'),
                    is_player_sold,
                    original_owner_id,
                    ship_data.get('condition_rating', 100),
                    ship_data.get('market_value', ship_data['price'])
                )
            )
        except Exception as e:
            print(f"Error adding ship to inventory: {e}")
    
    def remove_ship_from_inventory(self, inventory_id: int):
        """Remove a ship from shipyard inventory (when purchased)"""
        try:
            self.execute_query(
                "DELETE FROM shipyard_inventory WHERE inventory_id = ?",
                (inventory_id,)
            )
        except Exception as e:
            print(f"Error removing ship from inventory: {e}")
    
    def refresh_shipyard_inventory(self, location_id: int, new_ships: List[Dict]):
        """Refresh shipyard inventory, keeping player-sold ships"""
        try:
            # Remove only non-player-sold ships
            self.execute_query(
                "DELETE FROM shipyard_inventory WHERE location_id = ? AND is_player_sold = 0",
                (location_id,)
            )
            
            # Add new ships
            for ship in new_ships:
                self.add_ship_to_inventory(location_id, ship, is_player_sold=False)
                
            # Update last refresh time for all ships at this location
            self.execute_query(
                "UPDATE shipyard_inventory SET last_refresh = datetime('now') WHERE location_id = ?",
                (location_id,)
            )
        except Exception as e:
            print(f"Error refreshing shipyard inventory: {e}")
    
    def check_inventory_refresh_needed(self, location_id: int, refresh_hours: int = 12) -> bool:
        """Check if shipyard inventory needs refreshing"""
        try:
            result = self.execute_query(
                """SELECT last_refresh FROM shipyard_inventory 
                   WHERE location_id = ? 
                   ORDER BY last_refresh DESC LIMIT 1""",
                (location_id,),
                fetch='one'
            )
            
            if not result:
                return True  # No inventory yet, needs refresh
            
            last_refresh = result[0]
            # Check if refresh_hours have passed since last refresh
            check_result = self.execute_query(
                """SELECT datetime('now') > datetime(?, '+{} hours')""".format(refresh_hours),
                (last_refresh,),
                fetch='one'
            )
            
            return bool(check_result[0]) if check_result else True
        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True