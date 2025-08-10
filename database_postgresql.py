# database_postgresql.py - Native PostgreSQL implementation
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
        
        self.init_database()
        
        # Register cleanup on exit
        atexit.register(self.cleanup)

    def init_database(self):
        """Initialize database with native PostgreSQL schema"""
        print("🔄 Initializing PostgreSQL database schema...")
        
        # Core PostgreSQL schema
        schema_statements = [
            # Characters table
            '''CREATE TABLE IF NOT EXISTS characters (
                user_id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                callsign TEXT,
                appearance TEXT,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                current_location INTEGER,
                current_home_id BIGINT,
                money INTEGER DEFAULT 1000,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                is_logged_in BOOLEAN DEFAULT false,
                last_activity TIMESTAMP DEFAULT NOW(),
                birth_location TEXT,
                faction_id INTEGER,
                current_ship INTEGER,
                reputation INTEGER DEFAULT 0,
                combat_modifier INTEGER DEFAULT 0,
                can_act_time TIMESTAMP,
                ship_storage_limit INTEGER DEFAULT 5,
                skill_points INTEGER DEFAULT 0,
                is_alive BOOLEAN DEFAULT true
            )''',
            
            # Galaxy info table
            '''CREATE TABLE IF NOT EXISTS galaxy_info (
                galaxy_id INTEGER PRIMARY KEY DEFAULT 1,
                name TEXT NOT NULL DEFAULT 'Unknown Galaxy',
                start_date TEXT NOT NULL DEFAULT '2751-01-01',
                created_at TIMESTAMP DEFAULT NOW(),
                time_scale_factor REAL DEFAULT 4.0,
                time_started_at TIMESTAMP,
                current_ingame_time TEXT,
                is_time_paused BOOLEAN DEFAULT false,
                paused_at TIMESTAMP,
                last_shift_check TEXT,
                current_shift TEXT
            )''',
            
            # Locations table
            '''CREATE TABLE IF NOT EXISTS locations (
<<<<<<< HEAD
                location_id BIGSERIAL PRIMARY KEY,
=======
                location_id SERIAL PRIMARY KEY,
>>>>>>> 855b8fa61f9f3a2ee4597deb88499136b96c0f15
                channel_id BIGINT UNIQUE,
                name TEXT NOT NULL,
                location_type TEXT NOT NULL,
                description TEXT,
                x_coordinate REAL DEFAULT 0,
                y_coordinate REAL DEFAULT 0,
                z_coordinate REAL DEFAULT 0,
                wealth_level INTEGER DEFAULT 1,
                population INTEGER DEFAULT 100,
                faction_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                has_medical BOOLEAN DEFAULT false,
                has_repair BOOLEAN DEFAULT false,
                has_fuel BOOLEAN DEFAULT false,
                has_market BOOLEAN DEFAULT false,
                has_shipyard BOOLEAN DEFAULT false,
                channel_last_active TIMESTAMP,
                last_event TIMESTAMP,
                orbital_id INTEGER,
                npc_count INTEGER DEFAULT 0,
                is_hidden BOOLEAN DEFAULT false,
                is_derelict BOOLEAN DEFAULT false
            )''',
            
            # Ships table
            '''CREATE TABLE IF NOT EXISTS ships (
                ship_id SERIAL PRIMARY KEY,
                owner_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                ship_type TEXT DEFAULT 'Basic Hauler',
                fuel_capacity INTEGER DEFAULT 100,
                fuel_level INTEGER DEFAULT 100,
                max_cargo INTEGER DEFAULT 50,
                armor INTEGER DEFAULT 100,
                max_armor INTEGER DEFAULT 100,
                location_id INTEGER,
                docked_at INTEGER,
                is_active BOOLEAN DEFAULT true,
                last_maintenance TIMESTAMP DEFAULT NOW(),
                exterior_description TEXT,
                interior_description TEXT,
                channel_id BIGINT
            )''',
            
            # Ship activities table
            '''CREATE TABLE IF NOT EXISTS ship_activities (
                activity_id SERIAL PRIMARY KEY,
                ship_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',
            
            # Corridors table
            '''CREATE TABLE IF NOT EXISTS corridors (
                corridor_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                origin_location INTEGER NOT NULL,
                destination_location INTEGER NOT NULL,
                travel_time INTEGER DEFAULT 300,
                is_bidirectional BOOLEAN DEFAULT true,
                requires_ship BOOLEAN DEFAULT false,
                danger_level INTEGER DEFAULT 1,
                last_shift TIMESTAMP,
                FOREIGN KEY (origin_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id)
            )''',
            
            # Jobs table
            '''CREATE TABLE IF NOT EXISTS jobs (
                job_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                reward_money INTEGER DEFAULT 100,
                reward_items TEXT,
                is_taken BOOLEAN DEFAULT false,
                taken_by BIGINT,
                taken_at TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                job_type TEXT DEFAULT 'standard',
                difficulty_level INTEGER DEFAULT 1,
                required_reputation INTEGER DEFAULT 0,
                destination_location_id INTEGER,
                item_requirements TEXT,
                group_size_min INTEGER DEFAULT 1,
                group_size_max INTEGER DEFAULT 1,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (taken_by) REFERENCES characters (user_id)
            )''',
            
            # Character inventory table
            '''CREATE TABLE IF NOT EXISTS character_inventory (
                inventory_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                item_type TEXT DEFAULT 'misc',
                metadata TEXT,
                acquired_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(user_id, item_name)
            )''',
            
            # Shop items table
            '''CREATE TABLE IF NOT EXISTS shop_items (
                item_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock_quantity INTEGER DEFAULT -1,
                description TEXT,
                expires_at TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Shop refresh tracking
            '''CREATE TABLE IF NOT EXISTS shop_refresh (
                location_id INTEGER PRIMARY KEY,
                last_refreshed TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Galaxy settings
            '''CREATE TABLE IF NOT EXISTS galaxy_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )''',
            
            # Search cooldowns
            '''CREATE TABLE IF NOT EXISTS search_cooldowns (
                user_id BIGINT PRIMARY KEY,
                last_search_time TIMESTAMP,
                location_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Travel sessions
            '''CREATE TABLE IF NOT EXISTS travel_sessions (
                session_id SERIAL PRIMARY KEY,
                group_id INTEGER,
                user_id BIGINT,
                origin_location INTEGER NOT NULL,
                destination_location INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT NOW(),
                estimated_arrival TIMESTAMP,
                status TEXT DEFAULT 'in_progress',
                session_type TEXT DEFAULT 'individual',
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (origin_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id)
            )''',
            
            # Groups table
            '''CREATE TABLE IF NOT EXISTS groups (
                group_id SERIAL PRIMARY KEY,
                name TEXT,
                leader_id BIGINT NOT NULL,
                current_location INTEGER,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                group_type TEXT DEFAULT 'temporary',
                max_members INTEGER DEFAULT 8,
                invite_code TEXT UNIQUE,
                FOREIGN KEY (leader_id) REFERENCES characters (user_id),
                FOREIGN KEY (current_location) REFERENCES locations (location_id)
            )''',
            
            # PvP opt-outs
            '''CREATE TABLE IF NOT EXISTS pvp_opt_outs (
                user_id BIGINT PRIMARY KEY,
                opted_out BOOLEAN DEFAULT false,
                updated_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            
            # Pending robberies for PvP combat system
            '''CREATE TABLE IF NOT EXISTS pending_robberies (
                robbery_id SERIAL PRIMARY KEY,
                robber_id BIGINT NOT NULL,
                victim_id BIGINT NOT NULL,
                location_id BIGINT NOT NULL,
                message_id BIGINT,
                channel_id BIGINT,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (robber_id) REFERENCES characters (user_id),
                FOREIGN KEY (victim_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Faction system tables
            '''CREATE TABLE IF NOT EXISTS factions (
                faction_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                emoji TEXT NOT NULL,
                description TEXT,
                leader_id BIGINT NOT NULL,
                is_public BOOLEAN DEFAULT false,
                bank_balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (leader_id) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS faction_members (
                member_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                joined_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS faction_invites (
                invite_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                inviter_id BIGINT NOT NULL,
                invitee_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (inviter_id) REFERENCES characters (user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS faction_sales_tax (
                tax_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                tax_percentage INTEGER DEFAULT 0,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(location_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS faction_payouts (
                payout_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                collected BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS location_ownership (
                ownership_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL UNIQUE,
                owner_id BIGINT,
                group_id INTEGER,
                faction_id INTEGER,
                purchase_price INTEGER DEFAULT 0,
                ownership_type TEXT DEFAULT 'individual',
                custom_name TEXT,
                custom_description TEXT,
                docking_fee INTEGER DEFAULT 0,
                purchased_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id),
                FOREIGN KEY (group_id) REFERENCES groups (group_id),
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id)
            )''',
            
            # Combat cooldowns
            '''CREATE TABLE IF NOT EXISTS pvp_cooldowns (
                cooldown_id SERIAL PRIMARY KEY,
                player1_id BIGINT NOT NULL,
                player2_id BIGINT NOT NULL,
                cooldown_type TEXT NOT NULL CHECK(cooldown_type IN ('flee', 'robbery')),
                expires_at TIMESTAMP NOT NULL,
                location_id INTEGER,
                FOREIGN KEY (player1_id) REFERENCES characters (user_id),
                FOREIGN KEY (player2_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Server configuration
            '''CREATE TABLE IF NOT EXISTS server_config (
                guild_id BIGINT PRIMARY KEY,
                colony_category_id BIGINT,
                station_category_id BIGINT,
                outpost_category_id BIGINT,
                gate_category_id BIGINT,
                ship_category_id BIGINT,
                home_category_id BIGINT,
                general_channel_id BIGINT,
                newbie_help_channel_id BIGINT,
                bot_updates_channel_id BIGINT,
                alerts_channel_id BIGINT
            )''',
            
            # Location logs table
            '''CREATE TABLE IF NOT EXISTS location_logs (
                log_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                author_id BIGINT NOT NULL,
                author_name TEXT NOT NULL,
                message TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT NOW(),
                is_generated BOOLEAN DEFAULT false,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (author_id) REFERENCES characters (user_id)
            )''',
            
            # Quest system tables
            '''CREATE TABLE IF NOT EXISTS quests (
                quest_id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                start_location_id INTEGER NOT NULL,
                reward_money INTEGER DEFAULT 0,
                reward_items TEXT DEFAULT '[]',
                reward_experience INTEGER DEFAULT 0,
                created_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                is_active BOOLEAN DEFAULT true,
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
                objective_id SERIAL PRIMARY KEY,
                quest_id INTEGER NOT NULL,
                objective_order INTEGER NOT NULL,
                objective_type TEXT NOT NULL CHECK(objective_type IN ('travel', 'obtain_item', 'deliver_item', 'sell_item', 'earn_money', 'visit_location', 'talk_to_npc')),
                target_location_id INTEGER,
                target_item TEXT,
                target_quantity INTEGER DEFAULT 1,
                target_amount INTEGER DEFAULT 0,
                description TEXT NOT NULL,
                is_optional BOOLEAN DEFAULT false,
                FOREIGN KEY (quest_id) REFERENCES quests (quest_id) ON DELETE CASCADE,
                FOREIGN KEY (target_location_id) REFERENCES locations (location_id),
                UNIQUE(quest_id, objective_order)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS quest_progress (
                progress_id SERIAL PRIMARY KEY,
                quest_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                current_objective INTEGER DEFAULT 1,
                started_at TIMESTAMP DEFAULT NOW(),
                objectives_completed TEXT DEFAULT '[]',
                quest_status TEXT DEFAULT 'active' CHECK(quest_status IN ('active', 'completed', 'failed', 'abandoned')),
                completion_data TEXT DEFAULT '{}',
                FOREIGN KEY (quest_id) REFERENCES quests (quest_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(quest_id, user_id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS quest_completions (
                completion_id SERIAL PRIMARY KEY,
                quest_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                completed_at TIMESTAMP DEFAULT NOW(),
                reward_received TEXT DEFAULT '{}',
                completion_time_minutes INTEGER,
                FOREIGN KEY (quest_id) REFERENCES quests (quest_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            
            # Combat states table
            '''CREATE TABLE IF NOT EXISTS combat_states (
                combat_id BIGINT PRIMARY KEY,
                player_id BIGINT,
                target_npc_id BIGINT,
                target_npc_type TEXT,
                combat_type TEXT,
                location_id BIGINT,
                last_action_time TIMESTAMP DEFAULT NOW(),
                next_npc_action_time TIMESTAMP,
                player_can_act_time TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (player_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # NPC respawn queue table
            '''CREATE TABLE IF NOT EXISTS npc_respawn_queue (
                respawn_id BIGINT PRIMARY KEY,
                original_npc_id BIGINT,
                location_id BIGINT,
                scheduled_respawn_time TIMESTAMP,
                npc_data TEXT,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # News queue table
            '''CREATE TABLE IF NOT EXISTS news_queue (
                news_id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                news_type TEXT,
                title TEXT,
                description TEXT,
                location_id BIGINT,
                event_data TEXT,
                scheduled_delivery TIMESTAMP,
                delay_hours REAL DEFAULT 0,
                is_delivered BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT NOW()
            )''',
            
            # Dynamic NPCs table
            '''CREATE TABLE IF NOT EXISTS dynamic_npcs (
                npc_id SERIAL PRIMARY KEY,
                name TEXT,
                callsign TEXT UNIQUE,
                age BIGINT,
                ship_name TEXT,
                ship_type TEXT,
                current_location BIGINT,
                destination_location BIGINT,
                travel_start_time TIMESTAMP,
                travel_duration BIGINT,
                last_radio_message TIMESTAMP,
                last_location_action TIMESTAMP,
                credits BIGINT DEFAULT 0,
                is_alive BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                alignment TEXT DEFAULT 'neutral',
                hp BIGINT DEFAULT 100,
                max_hp BIGINT DEFAULT 100,
                combat_rating BIGINT DEFAULT 5,
                ship_hull BIGINT DEFAULT 100,
                max_ship_hull BIGINT DEFAULT 100,
                FOREIGN KEY (current_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id)
            )''',
        ]
        
        # Execute schema creation
        for i, statement in enumerate(schema_statements):
            try:
                self.execute_query(statement)
                # Extract table name from statement for better logging
                table_name = "unknown"
                if "CREATE TABLE" in statement:
                    parts = statement.split()
                    if "EXISTS" in statement:
                        table_name = parts[parts.index("EXISTS") + 1]
                    else:
                        table_name = parts[parts.index("TABLE") + 1]
                print(f"✅ Created table: {table_name}")
            except Exception as e:
                # Extract table name for better error reporting
                table_name = "unknown"
                if "CREATE TABLE" in statement:
                    parts = statement.split()
                    if "EXISTS" in statement:
                        table_name = parts[parts.index("EXISTS") + 1]
                    else:
                        table_name = parts[parts.index("TABLE") + 1]
                print(f"❌ Error creating table {table_name}: {e}")
                continue
        
        # Create indexes for performance
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_characters_location ON characters(current_location)',
            'CREATE INDEX IF NOT EXISTS idx_characters_logged_in ON characters(is_logged_in) WHERE is_logged_in = true',
            'CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_taken) WHERE is_taken = false',
            'CREATE INDEX IF NOT EXISTS idx_jobs_expires ON jobs(expires_at)',
            'CREATE INDEX IF NOT EXISTS idx_inventory_user ON character_inventory(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_shop_items_location ON shop_items(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_travel_sessions_user ON travel_sessions(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_pvp_cooldowns_expires ON pvp_cooldowns(expires_at)',
            # Faction-related indexes
            'CREATE INDEX IF NOT EXISTS idx_faction_members_user ON faction_members(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_faction_members_faction ON faction_members(faction_id)',
            'CREATE INDEX IF NOT EXISTS idx_faction_invites_invitee ON faction_invites(invitee_id)',
            'CREATE INDEX IF NOT EXISTS idx_faction_invites_expires ON faction_invites(expires_at)',
            'CREATE INDEX IF NOT EXISTS idx_faction_payouts_user ON faction_payouts(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_faction_payouts_collected ON faction_payouts(collected) WHERE collected = false',
            'CREATE INDEX IF NOT EXISTS idx_location_ownership_location ON location_ownership(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_location_ownership_faction ON location_ownership(faction_id)',
            # Location logs indexes
            'CREATE INDEX IF NOT EXISTS idx_location_logs_location ON location_logs(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_location_logs_posted_at ON location_logs(posted_at)',
            # Quest system indexes
            'CREATE INDEX IF NOT EXISTS idx_quests_start_location ON quests(start_location_id)',
            'CREATE INDEX IF NOT EXISTS idx_quests_active ON quests(is_active) WHERE is_active = true',
            'CREATE INDEX IF NOT EXISTS idx_quests_created_by ON quests(created_by)',
            'CREATE INDEX IF NOT EXISTS idx_quest_objectives_quest ON quest_objectives(quest_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_objectives_order ON quest_objectives(quest_id, objective_order)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_user ON quest_progress(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_quest ON quest_progress(quest_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_status ON quest_progress(quest_status)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_active ON quest_progress(user_id, quest_status) WHERE quest_status = \'active\'',
            'CREATE INDEX IF NOT EXISTS idx_quest_completions_user ON quest_completions(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_completions_quest ON quest_completions(quest_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_completions_completed_at ON quest_completions(completed_at)',
            # Ship activities indexes
            'CREATE INDEX IF NOT EXISTS idx_ship_activities_ship ON ship_activities(ship_id)',
            'CREATE INDEX IF NOT EXISTS idx_ship_activities_active ON ship_activities(ship_id, is_active) WHERE is_active = true',
        ]
        
        for index_sql in indexes:
            try:
                self.execute_query(index_sql)
            except Exception as e:
                # Ignore index creation errors (they might already exist)
                pass
        
        print("✅ PostgreSQL database schema initialized")

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
            return conn
        except Exception as e:
            print(f"❌ Error getting connection from pool: {e}")
            raise

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

    def execute_query(self, query, params=None, fetch=None, many=False):
        """Execute a native PostgreSQL query"""
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
                            
                            if params:
                                cursor.execute(query, params)
                            else:
                                cursor.execute(query)
                            
                            # Handle different fetch types
                            result = None
                            if fetch == 'one':
                                result = cursor.fetchone()
                                # Convert RealDictRow to tuple for backwards compatibility
                                if result:
                                    result = tuple(result.values()) if hasattr(result, 'values') else result
                            elif fetch == 'all':
                                result = cursor.fetchall()
                                # Convert list of RealDictRows to list of tuples
                                if result:
                                    result = [tuple(row.values()) if hasattr(row, 'values') else row for row in result]
                            elif fetch is None:
                                result = cursor.rowcount
                            
                            conn.commit()
                            return result
                            
                        except Exception as e:
                            conn.rollback()
                            raise
                        finally:
                            if cursor:
                                cursor.close()
                            self._close_connection(conn)
                            
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    print(f"❌ Database error after {max_retries} attempts: {e}")
                    raise

    def execute_transaction(self, operations):
        """Execute multiple operations in a single transaction"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        with self.lock:
            conn = self.get_connection()
            cursor = None
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
                
            except Exception as e:
                conn.rollback()
                print(f"❌ Transaction failed: {e}")
                raise
            finally:
                if cursor:
                    cursor.close()
                self._close_connection(conn)

    # Compatibility methods for existing code
    def get_galaxy_setting(self, setting_name, default_value=None):
        """Get a galaxy setting value"""
        result = self.execute_query(
            "SELECT setting_value FROM galaxy_settings WHERE setting_name = %s",
            (setting_name,),
            fetch='one'
        )
        return result[0] if result else default_value

    def set_galaxy_setting(self, setting_name, setting_value):
        """Set a galaxy setting value using PostgreSQL UPSERT"""
        self.execute_query(
            """INSERT INTO galaxy_settings (setting_name, setting_value, updated_at)
               VALUES (%s, %s, NOW())
               ON CONFLICT (setting_name) 
               DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = NOW()""",
            (setting_name, setting_value)
        )

    def character_exists(self, user_id):
        """Check if a character exists"""
        result = self.execute_query(
            "SELECT 1 FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        return result is not None

    def get_character_location(self, user_id):
        """Get character's current location"""
        result = self.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        return result[0] if result else None