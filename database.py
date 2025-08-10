# database.py - Native PostgreSQL implementation
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
                money INTEGER DEFAULT 500,
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
                skill_points INTEGER DEFAULT 5,
                location_status TEXT DEFAULT 'docked',
                current_ship_id INTEGER,
                engineering INTEGER DEFAULT 5,
                navigation INTEGER DEFAULT 5,
                combat INTEGER DEFAULT 5,
                medical INTEGER DEFAULT 5,
                defense INTEGER DEFAULT 0,
                ship_id BIGINT,
                group_id BIGINT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_home_id BIGINT,
                alignment TEXT DEFAULT 'neutral',
                login_time TIMESTAMP,
                active_ship_id BIGINT,
                image_url TEXT,
                auto_rename BIGINT DEFAULT 0,
                guild_id BIGINT
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
                time_paused_at TIMESTAMP,
                is_manually_paused BOOLEAN DEFAULT false
            )''',
            
            # Locations table
            '''CREATE TABLE IF NOT EXISTS locations (
                location_id SERIAL PRIMARY KEY,
                channel_id BIGINT UNIQUE,
                name TEXT NOT NULL,
                location_type TEXT NOT NULL,
                description TEXT,
                x_coordinate REAL DEFAULT 0,
                y_coordinate REAL DEFAULT 0,
                z_coordinate REAL DEFAULT 0,
                wealth_level INTEGER DEFAULT 1,
                population INTEGER DEFAULT 100,
                system_name TEXT,
                faction TEXT DEFAULT 'Independent',
                faction_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                has_medical BOOLEAN DEFAULT false,
                has_repair BOOLEAN DEFAULT false,
                has_fuel BOOLEAN DEFAULT false,
                has_market BOOLEAN DEFAULT false,
                has_shipyard BOOLEAN DEFAULT false,
                has_jobs BOOLEAN DEFAULT true,
                has_shops BOOLEAN DEFAULT true,
                channel_last_active TIMESTAMP,
                last_event TIMESTAMP,
                orbital_id INTEGER,
                npc_count INTEGER DEFAULT 0,
                is_hidden BOOLEAN DEFAULT false
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
            
            # Corridors table
            '''CREATE TABLE IF NOT EXISTS corridors (
                corridor_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                origin_location INTEGER NOT NULL,
                destination_location INTEGER NOT NULL,
                travel_time INTEGER DEFAULT 300,
                fuel_cost INTEGER DEFAULT 20,
                is_bidirectional BOOLEAN DEFAULT true,
                requires_ship BOOLEAN DEFAULT false,
                danger_level INTEGER DEFAULT 1,
                corridor_type TEXT DEFAULT 'ungated',
                is_active BOOLEAN DEFAULT true,
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
                job_status TEXT DEFAULT 'available',
                difficulty_level INTEGER DEFAULT 1,
                danger_level INTEGER DEFAULT 1,
                duration_minutes INTEGER DEFAULT 15,
                required_skill TEXT,
                min_skill_level INTEGER DEFAULT 0,
                karma_change INTEGER DEFAULT 0,
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
                corridor_id INTEGER,
                temp_channel_id BIGINT,
                start_time TIMESTAMP DEFAULT NOW(),
                estimated_arrival TIMESTAMP,
                status TEXT DEFAULT 'in_progress',
                session_type TEXT DEFAULT 'individual',
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (origin_location) REFERENCES locations (location_id),
                FOREIGN KEY (destination_location) REFERENCES locations (location_id),
                FOREIGN KEY (corridor_id) REFERENCES corridors (corridor_id)
            )''',
            
            # Repeaters table
            '''CREATE TABLE IF NOT EXISTS repeaters (
                repeater_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                receive_range INTEGER DEFAULT 3,
                transmit_range INTEGER DEFAULT 3,
                is_active BOOLEAN DEFAULT TRUE,
                installed_by BIGINT,
                installed_at TIMESTAMP DEFAULT NOW(),
                last_maintenance TIMESTAMP DEFAULT NOW(),
                power_level INTEGER DEFAULT 100,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (installed_by) REFERENCES characters (user_id)
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
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(player1_id, player2_id, cooldown_type)
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
            
            # Server configuration
            '''CREATE TABLE IF NOT EXISTS server_config (
                guild_id BIGINT PRIMARY KEY,
                colony_category_id BIGINT,
                station_category_id BIGINT,
                outpost_category_id BIGINT,
                gate_category_id BIGINT,
                transit_category_id BIGINT,
                ship_interiors_category_id BIGINT,
                residences_category_id BIGINT,
                galactic_updates_channel_id BIGINT,
                status_voice_channel_id BIGINT,
                max_location_channels INTEGER DEFAULT 50,
                channel_timeout_hours INTEGER DEFAULT 48,
                auto_cleanup_enabled BOOLEAN DEFAULT true,
                setup_completed BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )''',
            
            # Ambient events tracking table
            '''CREATE TABLE IF NOT EXISTS ambient_event_tracking (
                location_id INTEGER PRIMARY KEY,
                last_ambient_event TIMESTAMP DEFAULT NOW(),
                total_events_generated INTEGER DEFAULT 0,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Endgame config table
            '''CREATE TABLE IF NOT EXISTS endgame_config (
                config_id SERIAL PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                length_minutes INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT true
            )''',
            
            # Endgame evacuations table
            '''CREATE TABLE IF NOT EXISTS endgame_evacuations (
                evacuation_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL UNIQUE,
                evacuation_deadline TIMESTAMP NOT NULL,
                warned_at TIMESTAMP NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Location homes table
            '''CREATE TABLE IF NOT EXISTS location_homes (
                home_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                home_type TEXT NOT NULL,
                home_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                owner_id BIGINT,
                purchase_date TIMESTAMP,
                is_available BOOLEAN DEFAULT true,
                interior_description TEXT,
                activities TEXT,
                value_modifier REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
            )''',
            
            # Home interiors table
            '''CREATE TABLE IF NOT EXISTS home_interiors (
                interior_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL UNIQUE,
                channel_id BIGINT,
                last_activity TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes (home_id)
            )''',
            
            # Home recovery tracking table
            '''CREATE TABLE IF NOT EXISTS home_recovery_tracking (
                tracking_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                home_id INTEGER NOT NULL,
                entered_at TIMESTAMP DEFAULT NOW(),
                last_recovery TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES characters(user_id),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id)
            )''',
            
            # Job tracking table
            '''CREATE TABLE IF NOT EXISTS job_tracking (
                tracking_id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                start_location INTEGER NOT NULL,
                required_duration REAL NOT NULL,
                time_at_location REAL DEFAULT 0.0,
                last_location_check TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (job_id) REFERENCES jobs (job_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (start_location) REFERENCES locations (location_id),
                UNIQUE(job_id, user_id)
            )''',
            
            # Guild location channels table
            '''CREATE TABLE IF NOT EXISTS guild_location_channels (
                channel_mapping_id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                channel_id BIGINT NOT NULL,
                channel_last_active TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(guild_id, location_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Character identity table
            '''CREATE TABLE IF NOT EXISTS character_identity (
                user_id BIGINT PRIMARY KEY,
                birth_month INTEGER NOT NULL,
                birth_day INTEGER NOT NULL,
                birth_year INTEGER NOT NULL,
                age INTEGER NOT NULL,
                biography TEXT,
                birthplace_id INTEGER,
                id_scrubbed BOOLEAN DEFAULT false,
                scrubbed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (birthplace_id) REFERENCES locations (location_id)
            )''',
            
            # Home income table
            '''CREATE TABLE IF NOT EXISTS home_income (
                income_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL UNIQUE,
                accumulated_income INTEGER DEFAULT 0,
                last_collected TIMESTAMP DEFAULT NOW(),
                last_calculated TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id)
            )''',
            
            # AFK warnings table
            '''CREATE TABLE IF NOT EXISTS afk_warnings (
                warning_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                warning_time TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT true,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            
            # Service cooldowns table
            '''CREATE TABLE IF NOT EXISTS service_cooldowns (
                user_id BIGINT NOT NULL,
                service_type TEXT NOT NULL,
                location_id INTEGER NOT NULL,
                last_used TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (user_id, service_type, location_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Character equipment table
            '''CREATE TABLE IF NOT EXISTS character_equipment (
                equipment_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                slot_name TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                equipped_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(user_id, slot_name)
            )''',
            
            # Active stat modifiers table
            '''CREATE TABLE IF NOT EXISTS active_stat_modifiers (
                modifier_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                modifier_type TEXT NOT NULL,
                stat_name TEXT NOT NULL,
                modifier_value INTEGER NOT NULL,
                source_type TEXT NOT NULL CHECK(source_type IN ('equipment', 'consumable')),
                source_item_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            
            # Active beacons table
            '''CREATE TABLE IF NOT EXISTS active_beacons (
                beacon_id SERIAL PRIMARY KEY,
                beacon_type TEXT NOT NULL,
                user_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                message_content TEXT NOT NULL,
                transmissions_sent INTEGER DEFAULT 0,
                max_transmissions INTEGER DEFAULT 3,
                interval_minutes INTEGER DEFAULT 20,
                next_transmission TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                is_active BOOLEAN DEFAULT true,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Corridor events table
            '''CREATE TABLE IF NOT EXISTS corridor_events (
                event_id SERIAL PRIMARY KEY,
                transit_channel_id BIGINT NOT NULL,
                event_type TEXT NOT NULL,
                severity INTEGER DEFAULT 1,
                triggered_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                affected_users TEXT,
                responses TEXT
            )''',
            
            # Game panels table
            '''CREATE TABLE IF NOT EXISTS game_panels (
                panel_id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL UNIQUE,
                created_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(guild_id, channel_id)
            )''',
            
            # Home customizations table
            '''CREATE TABLE IF NOT EXISTS home_customizations (
                customization_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL UNIQUE,
                wall_color TEXT DEFAULT 'Beige',
                floor_type TEXT DEFAULT 'Standard Tile',
                lighting_style TEXT DEFAULT 'Standard',
                furniture_style TEXT DEFAULT 'Basic',
                ambiance TEXT DEFAULT 'Cozy',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id)
            )''',
            
            # Home storage table
            '''CREATE TABLE IF NOT EXISTS home_storage (
                storage_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                value INTEGER DEFAULT 0,
                stored_by BIGINT NOT NULL,
                stored_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                FOREIGN KEY (stored_by) REFERENCES characters(user_id)
            )''',
            
            # Home upgrades table
            '''CREATE TABLE IF NOT EXISTS home_upgrades (
                upgrade_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                upgrade_name TEXT NOT NULL,
                daily_income INTEGER DEFAULT 0,
                purchase_price INTEGER NOT NULL,
                purchased_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id)
            )''',
            
            # Home market listings table
            '''CREATE TABLE IF NOT EXISTS home_market_listings (
                listing_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL UNIQUE,
                seller_id BIGINT NOT NULL,
                asking_price INTEGER NOT NULL,
                original_price INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT true,
                listed_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                FOREIGN KEY (seller_id) REFERENCES characters(user_id)
            )''',
            
            # Home invitations table
            '''CREATE TABLE IF NOT EXISTS home_invitations (
                invitation_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL,
                inviter_id BIGINT NOT NULL,
                invitee_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (home_id) REFERENCES location_homes(home_id),
                FOREIGN KEY (inviter_id) REFERENCES characters(user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters(user_id),
                FOREIGN KEY (location_id) REFERENCES locations(location_id)
            )''',
            
            # Ship invitations table
            '''CREATE TABLE IF NOT EXISTS ship_invitations (
                invitation_id SERIAL PRIMARY KEY,
                ship_id INTEGER NOT NULL,
                inviter_id BIGINT NOT NULL,
                invitee_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (ship_id) REFERENCES ships(ship_id),
                FOREIGN KEY (inviter_id) REFERENCES characters(user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters(user_id),
                FOREIGN KEY (location_id) REFERENCES locations(location_id)
            )''',
            
            # Character reputation table
            '''CREATE TABLE IF NOT EXISTS character_reputation (
                reputation_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                reputation INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(user_id, location_id)
            )''',
            
            # Travel micro events table
            '''CREATE TABLE IF NOT EXISTS travel_micro_events (
                event_id SERIAL PRIMARY KEY,
                travel_session_id INTEGER,
                transit_channel_id BIGINT,
                user_id BIGINT NOT NULL,
                event_type TEXT NOT NULL,
                corridor_id INTEGER,
                triggered_at TIMESTAMP DEFAULT NOW(),
                responded BOOLEAN DEFAULT false,
                skill_used TEXT,
                roll_result INTEGER,
                difficulty INTEGER,
                success BOOLEAN,
                xp_awarded INTEGER DEFAULT 0,
                damage_taken INTEGER DEFAULT 0,
                damage_type TEXT,
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (travel_session_id) REFERENCES travel_sessions (session_id),
                FOREIGN KEY (corridor_id) REFERENCES corridors (corridor_id)
            )''',
            
            # Location ownership table
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
                FOREIGN KEY (group_id) REFERENCES groups (group_id)
            )''',
            
            # Active location effects table
            '''CREATE TABLE IF NOT EXISTS active_location_effects (
                effect_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value TEXT NOT NULL,
                source_event TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Combat states table for NPC combat system
            '''CREATE TABLE IF NOT EXISTS combat_states (
                combat_id SERIAL PRIMARY KEY,
                player_id BIGINT NOT NULL,
                target_npc_id BIGINT,
                target_npc_type TEXT,
                combat_type TEXT,
                location_id INTEGER,
                last_action_time TIMESTAMP DEFAULT NOW(),
                next_npc_action_time TIMESTAMP,
                player_can_act_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (player_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # NPC respawn queue table
            '''CREATE TABLE IF NOT EXISTS npc_respawn_queue (
                respawn_id SERIAL PRIMARY KEY,
                original_npc_id BIGINT,
                location_id INTEGER,
                scheduled_respawn_time TIMESTAMP,
                npc_data TEXT,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # PvP combat states table
            '''CREATE TABLE IF NOT EXISTS pvp_combat_states (
                combat_id SERIAL PRIMARY KEY,
                attacker_id BIGINT NOT NULL,
                defender_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                combat_type TEXT NOT NULL CHECK(combat_type IN ('ground', 'space')),
                created_at TIMESTAMP DEFAULT NOW(),
                last_action_time TIMESTAMP DEFAULT NOW(),
                attacker_can_act_time TIMESTAMP,
                defender_can_act_time TIMESTAMP,
                current_turn TEXT DEFAULT 'attacker' CHECK(current_turn IN ('attacker', 'defender')),
                FOREIGN KEY (attacker_id) REFERENCES characters (user_id),
                FOREIGN KEY (defender_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Static NPCs table
            '''CREATE TABLE IF NOT EXISTS static_npcs (
                npc_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                occupation TEXT,
                personality TEXT,
                trade_specialty TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                alignment TEXT DEFAULT 'neutral' CHECK(alignment IN ('loyal', 'neutral', 'bandit')),
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                combat_rating INTEGER DEFAULT 5,
                credits INTEGER DEFAULT 100,
                last_interaction TIMESTAMP,
                is_alive BOOLEAN DEFAULT true,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Dynamic NPCs table  
            '''CREATE TABLE IF NOT EXISTS dynamic_npcs (
                npc_id SERIAL PRIMARY KEY,
                name TEXT,
                callsign TEXT UNIQUE,
                age BIGINT,
                ship_name TEXT,
                ship_type TEXT,
                current_location INTEGER,
                destination_location INTEGER,
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
            
            # Combat encounters table
            '''CREATE TABLE IF NOT EXISTS combat_encounters (
                encounter_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                encounter_type TEXT NOT NULL,
                difficulty_level INTEGER DEFAULT 1,
                enemy_name TEXT,
                enemy_hp INTEGER DEFAULT 100,
                enemy_max_hp INTEGER DEFAULT 100,
                enemy_combat_rating INTEGER DEFAULT 5,
                loot_table TEXT,
                experience_reward INTEGER DEFAULT 10,
                money_reward INTEGER DEFAULT 50,
                created_at TIMESTAMP DEFAULT NOW(),
                is_active BOOLEAN DEFAULT true,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # NPC inventory table
            '''CREATE TABLE IF NOT EXISTS npc_inventory (
                inventory_id SERIAL PRIMARY KEY,
                npc_id BIGINT NOT NULL,
                npc_type TEXT NOT NULL CHECK(npc_type IN ('static', 'dynamic')),
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                item_type TEXT DEFAULT 'misc',
                trade_value INTEGER DEFAULT 10,
                UNIQUE(npc_id, npc_type, item_name)
            )''',
            
            # News queue table for galactic news system
            '''CREATE TABLE IF NOT EXISTS news_queue (
                news_id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                news_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location_id INTEGER,
                event_data TEXT,
                scheduled_delivery TIMESTAMP NOT NULL,
                delay_hours REAL DEFAULT 0,
                is_delivered BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
        ]
        
        # Execute schema creation
        for statement in schema_statements:
            try:
                self.execute_query(statement)
            except Exception as e:
                print(f"⚠️ Error creating table: {e}")
                continue
        
        # Add missing columns for existing databases
        column_migrations = [
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS location_status TEXT DEFAULT \'docked\'',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_ship_id INTEGER',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_location INTEGER',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_home_id BIGINT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS ship_id BIGINT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS group_id BIGINT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS status TEXT DEFAULT \'active\'',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS alignment TEXT DEFAULT \'neutral\'',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS login_time TIMESTAMP',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS active_ship_id BIGINT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS image_url TEXT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS auto_rename BIGINT DEFAULT 0',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS guild_id BIGINT',
            # Corridor table columns
            'ALTER TABLE corridors ADD COLUMN IF NOT EXISTS fuel_cost INTEGER DEFAULT 20',
            'ALTER TABLE corridors ADD COLUMN IF NOT EXISTS corridor_type TEXT DEFAULT \'ungated\'',
            'ALTER TABLE corridors ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true',
            # Jobs table columns
            'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_status TEXT DEFAULT \'available\'',
            'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS danger_level INTEGER DEFAULT 1',
            'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 15',
            'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS required_skill TEXT',
            'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS min_skill_level INTEGER DEFAULT 0',
            'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS karma_change INTEGER DEFAULT 0',
            # Locations table columns
            'ALTER TABLE locations ADD COLUMN IF NOT EXISTS has_jobs BOOLEAN DEFAULT true',
            'ALTER TABLE locations ADD COLUMN IF NOT EXISTS has_shops BOOLEAN DEFAULT true',
            'ALTER TABLE locations ADD COLUMN IF NOT EXISTS x_coordinate REAL DEFAULT 0',
            'ALTER TABLE locations ADD COLUMN IF NOT EXISTS y_coordinate REAL DEFAULT 0',
            'ALTER TABLE locations ADD COLUMN IF NOT EXISTS system_name TEXT',
            'ALTER TABLE locations ADD COLUMN IF NOT EXISTS faction TEXT DEFAULT \'Independent\'',
            # Travel sessions table columns
            'ALTER TABLE travel_sessions ADD COLUMN IF NOT EXISTS corridor_id INTEGER',
            'ALTER TABLE travel_sessions ADD COLUMN IF NOT EXISTS temp_channel_id BIGINT',
            'ALTER TABLE travel_sessions ADD COLUMN IF NOT EXISTS last_event_time TIMESTAMP',
            'ALTER TABLE travel_sessions ADD COLUMN IF NOT EXISTS end_time TIMESTAMP',
            # Galaxy info table columns for time system PostgreSQL migration
            'ALTER TABLE galaxy_info ADD COLUMN IF NOT EXISTS time_paused_at TIMESTAMP',
            'ALTER TABLE galaxy_info ADD COLUMN IF NOT EXISTS is_manually_paused BOOLEAN DEFAULT false',
            'ALTER TABLE galaxy_info ADD COLUMN IF NOT EXISTS last_shift_check TEXT',
            'ALTER TABLE galaxy_info ADD COLUMN IF NOT EXISTS current_shift TEXT',
        ]
        
        for migration_sql in column_migrations:
            try:
                self.execute_query(migration_sql)
            except Exception as e:
                # Ignore column addition errors (they might already exist)
                pass
        
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
            'CREATE INDEX IF NOT EXISTS idx_travel_sessions_corridor ON travel_sessions(corridor_id)',
            'CREATE INDEX IF NOT EXISTS idx_travel_micro_events_user ON travel_micro_events(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_travel_micro_events_session ON travel_micro_events(travel_session_id)',
            'CREATE INDEX IF NOT EXISTS idx_pvp_cooldowns_expires ON pvp_cooldowns(expires_at)',
            'CREATE INDEX IF NOT EXISTS idx_repeaters_location ON repeaters(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_repeaters_active ON repeaters(is_active) WHERE is_active = true',
            'CREATE INDEX IF NOT EXISTS idx_news_queue_delivery ON news_queue(scheduled_delivery) WHERE is_delivered = false',
            'CREATE INDEX IF NOT EXISTS idx_news_queue_guild ON news_queue(guild_id)',
            'CREATE INDEX IF NOT EXISTS idx_news_queue_location ON news_queue(location_id)',
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

    def execute_read_query(self, query, params=None, fetch='all'):
        """Execute a read-only query without acquiring the main lock"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            conn = None
            try:
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
                        # Keep as RealDictRow for dictionary access
                        if result:
                            result = dict(result) if hasattr(result, 'keys') else result
                    elif fetch == 'all':
                        result = cursor.fetchall()
                        # Convert list of RealDictRows to list of dictionaries
                        if result:
                            result = [dict(row) if hasattr(row, 'keys') else row for row in result]
                    
                    return result
                    
                except Exception as e:
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
                    print(f"❌ Database read error after {max_retries} attempts: {e}")
                    raise

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

    # Transaction methods for compatibility with existing code
    def begin_transaction(self):
        """Begin a transaction and return connection for manual management"""
        if self._shutdown:
            raise RuntimeError("Database is shutting down")
        
        try:
            conn = self.get_connection()
            conn.autocommit = False  # Ensure we're in transaction mode
            return conn
        except Exception as e:
            print(f"❌ Error beginning transaction: {e}")
            raise

    def execute_in_transaction(self, conn, query, params=None, fetch=None):
        """Execute a query within an existing transaction"""
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
            elif fetch == 'lastrowid':
                result = cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
            elif fetch is None:
                result = cursor.rowcount
            
            cursor.close()
            return result
            
        except Exception as e:
            print(f"❌ Database error during transaction: {e}\nQuery: {query}\nParams: {params}")
            raise

    def executemany_in_transaction(self, conn, query, params_list):
        """Execute a bulk query within an existing transaction"""
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            cursor.close()
        except Exception as e:
            print(f"❌ Database error during executemany: {e}\nQuery: {query}")
            raise

    def commit_transaction(self, conn):
        """Commit transaction and clean up connection"""
        try:
            conn.commit()
        except Exception as e:
            print(f"❌ Error committing transaction: {e}")
            raise
        finally:
            self._close_connection(conn)

    def rollback_transaction(self, conn):
        """Rollback transaction and clean up connection"""
        try:
            conn.rollback()
        except Exception as e:
            print(f"❌ Error rolling back transaction: {e}")
        finally:
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
    
    def get_active_location_effects(self, location_id: int):
        """Get all active effects for a location"""
        # First clean up expired effects
        self.execute_query(
            "DELETE FROM active_location_effects WHERE expires_at < NOW()",
            ()
        )
        
        # Return active effects
        return self.execute_query(
            """SELECT effect_type, effect_value, source_event, created_at, expires_at 
               FROM active_location_effects 
               WHERE location_id = %s AND (expires_at IS NULL OR expires_at > NOW())""",
            (location_id,),
            fetch='all'
        )

    def cleanup_expired_effects(self):
        """Remove all expired effects"""
        result = self.execute_query(
            "DELETE FROM active_location_effects WHERE expires_at < NOW()",
            ()
        )
        return result

    def add_location_effect(self, location_id: int, effect_type: str, effect_value: str, source_event: str, duration_hours: int = 24):
        """Add an active effect to a location (replaces existing effect of same type)"""
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        # Remove existing effects of the same type at this location to prevent stacking
        self.execute_query(
            "DELETE FROM active_location_effects WHERE location_id = %s AND effect_type = %s",
            (location_id, effect_type)
        )
        
        # Add the new effect
        self.execute_query(
            """INSERT INTO active_location_effects 
               (location_id, effect_type, effect_value, source_event, created_at, expires_at)
               VALUES (%s, %s, %s, %s, NOW(), %s)""",
            (location_id, effect_type, effect_value, source_event, expires_at)
        )

    def remove_location_effects(self, location_id: int, effect_type: str = None):
        """Remove effects from a location, optionally filtered by type"""
        if effect_type:
            self.execute_query(
                "DELETE FROM active_location_effects WHERE location_id = %s AND effect_type = %s",
                (location_id, effect_type)
            )
        else:
            self.execute_query(
                "DELETE FROM active_location_effects WHERE location_id = %s",
                (location_id,)
            )

    def check_integrity(self):
        """Check database integrity - compatibility method"""
        try:
            # Simple query to check if database is responsive
            result = self.execute_query("SELECT 1", fetch='one')
            return result is not None
        except Exception as e:
            print(f"❌ Database integrity check failed: {e}")
            return False