# In database.py, replace the init_database method with this corrected version:
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

class Database:
    def __init__(self, db_path="thequietend.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path, timeout=30.0)
    
    def execute_query(self, query, params=None, fetch=None):
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
                else:
                    result = None
                
                conn.commit()
                return result
            except sqlite3.Error as e:
                conn.rollback()
                print(f"❌ Database error: {e}")
                print(f"Query: {query}")
                print(f"Params: {params}")
                raise e
            except Exception as e:
                conn.rollback()
                print(f"❌ Unexpected error in database operation: {e}")
                print(f"Query: {query}")
                print(f"Params: {params}")
                raise e
            finally:
                conn.close()
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # Corridors table (unchanged)
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
            
            # Groups table (unchanged)
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
            
            # Jobs table (unchanged)
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
                destination_location_id INTEGER, -- ADD THIS LINE
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (taken_by) REFERENCES characters (user_id),
                FOREIGN KEY (destination_location_id) REFERENCES locations (location_id) -- ADD THIS LINE for foreign key
            )''',
            
            # Inventory table (unchanged)
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
            
            # Travel sessions table (unchanged)
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
            
            # Shop items table (unchanged)
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
            
            # Server configuration table - ADD radio_channel_id field
            '''CREATE TABLE IF NOT EXISTS server_config (
                guild_id INTEGER PRIMARY KEY,
                colony_category_id INTEGER,
                station_category_id INTEGER,
                outpost_category_id INTEGER,
                gate_category_id INTEGER,
                transit_category_id INTEGER,
                ship_interiors_category_id INTEGER,
                max_location_channels INTEGER DEFAULT 50,
                channel_timeout_hours INTEGER DEFAULT 48,
                auto_cleanup_enabled BOOLEAN DEFAULT 1,
                setup_completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # Galaxy generation settings (unchanged)
            '''CREATE TABLE IF NOT EXISTS galaxy_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # Radio repeaters table - NEW
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
            # Add this table creation query to the queries list in init_database method
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

            # Add location items table for item system
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

            # Combat encounters table
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

            # Character experience and leveling
            '''CREATE TABLE IF NOT EXISTS character_experience (
                user_id INTEGER PRIMARY KEY,
                total_exp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                skill_points INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',

            # Ship upgrades and customization
            '''CREATE TABLE IF NOT EXISTS ship_upgrades (
                upgrade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ship_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                upgrade_name TEXT NOT NULL,
                bonus_value INTEGER DEFAULT 0,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',

            # Group ships
            '''CREATE TABLE IF NOT EXISTS group_ships (
                group_id INTEGER PRIMARY KEY,
                ship_id INTEGER NOT NULL,
                captain_id INTEGER,
                crew_positions TEXT,
                FOREIGN KEY (group_id) REFERENCES groups (group_id),
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id),
                FOREIGN KEY (captain_id) REFERENCES characters (user_id)
            )''',
            # Job tracking table - FIXED version
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
            # Group invites table
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

            # Group vote sessions table
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

            # Group votes table
            '''CREATE TABLE IF NOT EXISTS group_votes (
                vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vote_value TEXT NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES group_vote_sessions (session_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            # Add location status to characters (docked vs in-space)
            '''ALTER TABLE characters ADD COLUMN location_status TEXT DEFAULT 'docked' ''',

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
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
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
                FOREIGN KEY (current_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id)
            )''',

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
            )'''
        ]
        
        for q in queries:
            try:
                # we only care about running it once; IF NOT EXISTS handles tables,
                # but ALTER TABLE will throw if the column is already there
                self.execute_query(q)
            except sqlite3.OperationalError as e:
                # skip errors like "duplicate column name" or syntax issues
                print(f"⚠️ Skipping database init query (already exists?): {e}")
            except Exception as e:
                # log any other unexpected errors but keep going
                print(f"❌ Error running init query: {e}")
