# database.py - Fixed version with proper shutdown handling and WAL mode
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
import atexit
import time

class Database:
    def __init__(self, db_path="beta2.db"):
        self.db_path = db_path
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
            print("✅ Database WAL mode enabled and optimized")
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
        """Execute a single query with automatic connection management"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
            
        max_retries = 3
        retry_delay = 0.5  # Start with longer delay
        
        for attempt in range(max_retries):
            try:
                with self.lock:
                    conn = self.get_connection()
                    try:
                        cursor = conn.cursor()
                        
                        # Support bulk inserts with executemany
                        if many and params:
                            cursor.executemany(query, params)
                        elif params:
                            cursor.execute(query, params or [])
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
                    except sqlite3.Error as e:
                        conn.rollback()
                        if attempt < max_retries - 1 and "database is locked" in str(e):
                            print(f"⚠️ Database locked on attempt {attempt + 1}, retrying...")
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        raise e
                    finally:
                        self._close_connection(conn)
            except Exception as e:
                if attempt < max_retries - 1 and "database is locked" in str(e):
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                print(f"❌ Database error: {e}")
                print(f"Query: {query}")
                if not many:
                    print(f"Params: {params}")
                else:
                    print(f"Params: {len(params) if params else 0} rows")
                raise e

    def begin_transaction(self):
        """Begin a transaction with proper connection tracking"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        # Try to acquire lock with timeout
        acquired = self.lock.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Could not acquire database lock for transaction")
        
        try:
            conn = self.get_connection()
            # Use IMMEDIATE to lock the database right away
            conn.execute("BEGIN IMMEDIATE")
            return conn
        except:
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
            self._close_connection(conn)
            
    def execute_in_transaction(self, conn, query, params=None, fetch=None):
        """Execute a query within an existing transaction"""
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or [])

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
                engineering INTEGER DEFAULT 10,
                navigation INTEGER DEFAULT 10,
                combat INTEGER DEFAULT 10,
                medical INTEGER DEFAULT 10,
                current_location INTEGER,
                ship_id INTEGER,
                group_id INTEGER,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            # Add current home tracking to characters table
            '''ALTER TABLE characters ADD COLUMN current_home_id INTEGER''',
            '''ALTER TABLE location_ownership ADD COLUMN faction_id INTEGER REFERENCES factions(faction_id)''',
            # Add home invitations table
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
                is_active BOOLEAN DEFAULT 1,
                is_generated BOOLEAN DEFAULT 0,
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
                FOREIGN KEY (group_id) REFERENCES groups (group_id)
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
            # NPC job completions tracking
            '''CREATE TABLE IF NOT EXISTS npc_job_completions (
                completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_job_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (npc_job_id) REFERENCES npc_jobs (npc_job_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
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
            '''ALTER TABLE jobs ADD COLUMN unloading_started_at DATETIME;''',
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