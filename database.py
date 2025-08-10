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
        self.validate_schema()
        
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
                name TEXT,
                callsign TEXT,
                appearance TEXT,
                hp BIGINT DEFAULT 100,
                max_hp BIGINT DEFAULT 100,
                money BIGINT DEFAULT 500,
                engineering BIGINT DEFAULT 5,
                navigation BIGINT DEFAULT 5,
                combat BIGINT DEFAULT 5,
                medical BIGINT DEFAULT 5,
                current_location BIGINT,
                ship_id BIGINT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_home_id BIGINT,
                alignment TEXT DEFAULT 'neutral',
                location_status TEXT DEFAULT 'docked',
                experience BIGINT DEFAULT 0,
                level BIGINT DEFAULT 1,
                skill_points BIGINT DEFAULT 5,
                is_logged_in BOOLEAN DEFAULT false,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                login_time TIMESTAMP,
                current_ship_id BIGINT,
                active_ship_id BIGINT,
                image_url TEXT,
                auto_rename BIGINT DEFAULT 0,
                defense BIGINT DEFAULT 0,
                guild_id BIGINT,
                discord_id BIGINT
            )''',
            
            # Galaxy info table
            '''CREATE TABLE IF NOT EXISTS galaxy_info (
                galaxy_id BIGINT PRIMARY KEY DEFAULT 1,
                name TEXT DEFAULT 'Unknown Galaxy',
                start_date TEXT DEFAULT '2751-01-01',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                time_scale_factor REAL DEFAULT 4.0,
                time_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_time_paused BOOLEAN DEFAULT false,
                time_paused_at TIMESTAMP,
                current_ingame_time TIMESTAMP,
                last_shift_check TEXT,
                current_shift TEXT,
                is_manually_paused BOOLEAN DEFAULT false
            )''',
            
            # Locations table
            '''CREATE TABLE IF NOT EXISTS locations (
                location_id SERIAL PRIMARY KEY,
                channel_id BIGINT,
                name TEXT,
                location_type TEXT,
                description TEXT,
                wealth_level BIGINT DEFAULT 5,
                population BIGINT DEFAULT 100,
                system_name TEXT,
                has_jobs BOOLEAN DEFAULT true,
                has_shops BOOLEAN DEFAULT true,
                has_medical BOOLEAN DEFAULT true,
                has_repairs BOOLEAN DEFAULT true,
                has_fuel BOOLEAN DEFAULT true,
                has_upgrades BOOLEAN DEFAULT false,
                is_generated BOOLEAN DEFAULT false,
                is_derelict BOOLEAN DEFAULT false,
                gate_status TEXT DEFAULT 'active',
                original_location_id BIGINT,
                relocated_to_id BIGINT,
                channel_last_active TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                faction TEXT DEFAULT 'Independent',
                has_federal_supplies BOOLEAN DEFAULT false,
                establishment_date TEXT,
                established_date TEXT,
                has_black_market BOOLEAN DEFAULT false,
                generated_income BIGINT DEFAULT 0,
                has_shipyard BOOLEAN DEFAULT false,
                reconnection_eta TIMESTAMP,
                abandoned_since TIMESTAMP,
                x_coordinate REAL DEFAULT 0,
                y_coordinate REAL DEFAULT 0
            )''',
            
            # Ships table
            '''CREATE TABLE IF NOT EXISTS ships (
                ship_id SERIAL PRIMARY KEY,
                owner_id BIGINT,
                name TEXT,
                ship_type TEXT DEFAULT 'Basic Hauler',
                fuel_capacity BIGINT DEFAULT 100,
                current_fuel BIGINT DEFAULT 100,
                fuel_efficiency BIGINT DEFAULT 5,
                combat_rating BIGINT DEFAULT 10,
                hull_integrity BIGINT DEFAULT 100,
                max_hull BIGINT DEFAULT 100,
                cargo_capacity BIGINT DEFAULT 50,
                cargo_used BIGINT DEFAULT 0,
                ship_hp BIGINT DEFAULT 50,
                max_ship_hp BIGINT DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ship_class TEXT DEFAULT 'civilian',
                upgrade_slots BIGINT DEFAULT 3,
                used_upgrade_slots BIGINT DEFAULT 0,
                exterior_description TEXT,
                interior_description TEXT,
                channel_id BIGINT,
                docked_at_location BIGINT,
                tier BIGINT DEFAULT 1,
                condition_rating BIGINT DEFAULT 100,
                engine_level BIGINT DEFAULT 1,
                hull_level BIGINT DEFAULT 1,
                systems_level BIGINT DEFAULT 1,
                special_mods TEXT DEFAULT '[]',
                market_value BIGINT DEFAULT 10000,
                max_upgrade_slots BIGINT DEFAULT 3,
                speed_rating BIGINT DEFAULT 5
            )''',
            
            # Ship customization table
            '''CREATE TABLE IF NOT EXISTS ship_customization (
                ship_id BIGINT PRIMARY KEY,
                paint_job TEXT DEFAULT 'Default',
                decals TEXT DEFAULT 'None',
                interior_style TEXT DEFAULT 'Standard',
                name_plate TEXT DEFAULT 'Standard',
                FOREIGN KEY (ship_id) REFERENCES ships (ship_id)
            )''',
            
            # Player ships junction table for ship ownership and storage
            '''CREATE TABLE IF NOT EXISTS player_ships (
                ship_storage_id SERIAL PRIMARY KEY,
                owner_id BIGINT,
                ship_id BIGINT,
                is_active BOOLEAN DEFAULT false,
                stored_at_shipyard BIGINT,
                acquired_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # Corridors table
            '''CREATE TABLE IF NOT EXISTS corridors (
                corridor_id SERIAL PRIMARY KEY,
                name TEXT,
                origin_location BIGINT,
                destination_location BIGINT,
                travel_time BIGINT DEFAULT 300,
                fuel_cost BIGINT DEFAULT 20,
                danger_level BIGINT DEFAULT 3,
                is_active BOOLEAN DEFAULT true,
                is_generated BOOLEAN DEFAULT false,
                last_shift TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_shift TIMESTAMP,
                is_bidirectional BOOLEAN DEFAULT true,
                corridor_type TEXT DEFAULT 'ungated'
            )''',
            
            # Jobs table
            '''CREATE TABLE IF NOT EXISTS jobs (
                job_id SERIAL PRIMARY KEY,
                location_id BIGINT,
                title TEXT,
                description TEXT,
                reward_money BIGINT DEFAULT 100,
                required_skill TEXT,
                min_skill_level BIGINT DEFAULT 0,
                danger_level BIGINT DEFAULT 1,
                duration_minutes BIGINT DEFAULT 60,
                is_taken BOOLEAN DEFAULT false,
                taken_by BIGINT,
                taken_at TIMESTAMP,
                expires_at TIMESTAMP,
                job_status TEXT DEFAULT 'available',
                destination_location_id BIGINT,
                karma_change BIGINT DEFAULT 0,
                unloading_started_at TIMESTAMP WITH TIME ZONE
            )''',
            
            # Character inventory table (renamed to 'inventory' to match bot code)
            '''CREATE TABLE IF NOT EXISTS inventory (
                item_id SERIAL PRIMARY KEY,
                owner_id BIGINT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT DEFAULT 'misc',
                quantity INTEGER DEFAULT 1,
                description TEXT,
                value INTEGER DEFAULT 0,
                metadata TEXT,
                equippable BOOLEAN DEFAULT false,
                equipment_slot TEXT,
                stat_modifiers TEXT,
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
            )''',
            
            # Shop items table
            '''CREATE TABLE IF NOT EXISTS shop_items (
                item_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock INTEGER DEFAULT -1,
                description TEXT,
                expires_at TIMESTAMP,
                sold_by_player BOOLEAN DEFAULT false,
                metadata TEXT,
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
                owner_id BIGINT,
                repeater_type TEXT DEFAULT 'standard',
                receive_range INTEGER DEFAULT 3,
                transmit_range INTEGER DEFAULT 3,
                is_active BOOLEAN DEFAULT TRUE,
                deployed_at TIMESTAMP DEFAULT NOW(),
                installed_by BIGINT,
                installed_at TIMESTAMP DEFAULT NOW(),
                last_maintenance TIMESTAMP DEFAULT NOW(),
                power_level INTEGER DEFAULT 100,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id),
                FOREIGN KEY (installed_by) REFERENCES characters (user_id)
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
                location_id INTEGER NOT NULL,
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
            
            # Black markets table
            '''CREATE TABLE IF NOT EXISTS black_markets (
                market_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                market_type TEXT DEFAULT 'underground',
                reputation_required INTEGER DEFAULT 0,
                is_hidden BOOLEAN DEFAULT true,
                discovered_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Black market items table
            '''CREATE TABLE IF NOT EXISTS black_market_items (
                item_id SERIAL PRIMARY KEY,
                market_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock INTEGER DEFAULT 1,
                max_stock INTEGER DEFAULT 1,
                refresh_rate INTEGER DEFAULT 60,
                last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                item_description TEXT,
                FOREIGN KEY (market_id) REFERENCES black_markets (market_id)
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
                faction_id INTEGER,
                purchase_price INTEGER DEFAULT 0,
                ownership_type TEXT DEFAULT 'individual',
                custom_name TEXT,
                custom_description TEXT,
                docking_fee INTEGER DEFAULT 0,
                purchased_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (owner_id) REFERENCES characters (user_id)
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
            
            # Location economy table for supply/demand tracking
            '''CREATE TABLE IF NOT EXISTS location_economy (
                economy_id SERIAL PRIMARY KEY,
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
            
            # Economic events table for economic news system
            '''CREATE TABLE IF NOT EXISTS economic_events (
                event_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                item_category TEXT,
                item_name TEXT,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Sub-locations table for location subdivisions
            '''CREATE TABLE IF NOT EXISTS sub_locations (
                sub_location_id SERIAL PRIMARY KEY,
                parent_location_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sub_type TEXT,
                description TEXT,
                thread_id BIGINT,
                channel_id BIGINT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_location_id) REFERENCES locations (location_id)
            )''',
            
            # Home activities table
            '''CREATE TABLE IF NOT EXISTS home_activities (
                activity_id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL,
                activity_type TEXT,
                activity_name TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (home_id) REFERENCES location_homes (home_id)
            )''',
            
            # Ship activities table
            '''CREATE TABLE IF NOT EXISTS ship_activities (
                activity_id SERIAL PRIMARY KEY,
                ship_id BIGINT,
                activity_type TEXT,
                activity_name TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ship_id) REFERENCES ships(ship_id)
            )''',
            
            # Location logs table for location history
            '''CREATE TABLE IF NOT EXISTS location_logs (
                log_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                author_id BIGINT,
                author_name TEXT,
                message TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_generated BOOLEAN DEFAULT false,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Location items table
            '''CREATE TABLE IF NOT EXISTS location_items (
                item_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT,
                quantity INTEGER DEFAULT 1,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Location storage table
            '''CREATE TABLE IF NOT EXISTS location_storage (
                storage_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT,
                quantity INTEGER DEFAULT 1,
                stored_by BIGINT,
                stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (stored_by) REFERENCES characters (user_id)
            )''',
            
            # Location income log table
            '''CREATE TABLE IF NOT EXISTS location_income_log (
                income_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                income_amount INTEGER NOT NULL,
                income_source TEXT,
                collected_by BIGINT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (collected_by) REFERENCES characters (user_id)
            )''',
            
            # Location access control table
            '''CREATE TABLE IF NOT EXISTS location_access_control (
                access_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                access_level TEXT DEFAULT 'visitor',
                granted_by BIGINT,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (granted_by) REFERENCES characters (user_id),
                UNIQUE(location_id, user_id)
            )''',
            
            # Location upgrades table
            '''CREATE TABLE IF NOT EXISTS location_upgrades (
                upgrade_id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                upgrade_name TEXT NOT NULL,
                upgrade_level INTEGER DEFAULT 1,
                purchased_by BIGINT,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (purchased_by) REFERENCES characters (user_id)
            )''',
            
            # NPC trade inventory table
            '''CREATE TABLE IF NOT EXISTS npc_trade_inventory (
                trade_item_id SERIAL PRIMARY KEY,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT DEFAULT 'misc',
                quantity INTEGER DEFAULT 1,
                price_credits INTEGER DEFAULT 10,
                trade_for_item TEXT,
                trade_quantity_required INTEGER DEFAULT 1,
                rarity TEXT DEFAULT 'common',
                description TEXT,
                metadata TEXT,
                is_available BOOLEAN DEFAULT true,
                restocks_at TIMESTAMP,
                UNIQUE(npc_id, npc_type, item_name)
            )''',
            
            # NPC jobs table
            '''CREATE TABLE IF NOT EXISTS npc_jobs (
                job_id SERIAL PRIMARY KEY,
                npc_id INTEGER NOT NULL,
                npc_type TEXT NOT NULL,
                job_title TEXT NOT NULL,
                job_description TEXT,
                reward_money INTEGER DEFAULT 100,
                reward_items TEXT,
                required_skill TEXT,
                min_skill_level INTEGER DEFAULT 0,
                danger_level INTEGER DEFAULT 0,
                duration_minutes INTEGER DEFAULT 30,
                is_available BOOLEAN DEFAULT true,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # NPC job completions table
            '''CREATE TABLE IF NOT EXISTS npc_job_completions (
                completion_id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL,
                completed_by BIGINT NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES npc_jobs (job_id),
                FOREIGN KEY (completed_by) REFERENCES characters (user_id)
            )''',
            
            # Galactic history table
            '''CREATE TABLE IF NOT EXISTS galactic_history (
                history_id SERIAL PRIMARY KEY,
                location_id INTEGER,
                event_title TEXT,
                event_description TEXT NOT NULL,
                historical_figure TEXT,
                event_date TEXT,
                event_type TEXT NOT NULL,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
            
            # Factions table
            '''CREATE TABLE IF NOT EXISTS factions (
                faction_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                emoji TEXT NOT NULL,
                description TEXT,
                leader_id BIGINT NOT NULL,
                is_public BOOLEAN DEFAULT false,
                bank_balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (leader_id) REFERENCES characters (user_id)
            )''',
            
            # Faction members table
            '''CREATE TABLE IF NOT EXISTS faction_members (
                member_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                UNIQUE(user_id)
            )''',
            
            # Faction invites table
            '''CREATE TABLE IF NOT EXISTS faction_invites (
                invite_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                inviter_id BIGINT NOT NULL,
                invitee_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (inviter_id) REFERENCES characters (user_id),
                FOREIGN KEY (invitee_id) REFERENCES characters (user_id)
            )''',
            
            # Faction sales tax table
            '''CREATE TABLE IF NOT EXISTS faction_sales_tax (
                tax_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                tax_percentage INTEGER DEFAULT 0,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                UNIQUE(location_id)
            )''',
            
            # Faction payouts table
            '''CREATE TABLE IF NOT EXISTS faction_payouts (
                payout_id SERIAL PRIMARY KEY,
                faction_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                collected BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faction_id) REFERENCES factions (faction_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id)
            )''',
            
            # User location panels table
            '''CREATE TABLE IF NOT EXISTS user_location_panels (
                user_id BIGINT NOT NULL,
                location_id INTEGER NOT NULL,
                message_id BIGINT,
                channel_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, location_id),
                FOREIGN KEY (user_id) REFERENCES characters (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            )''',
        ]
        
        # Execute schema creation
        print(f"📋 Executing {len(schema_statements)} schema statements...")
        failed_tables = []
        for i, statement in enumerate(schema_statements):
            try:
                # Extract table name for logging
                table_name = None
                if 'CREATE TABLE' in statement:
                    table_name = statement.split('CREATE TABLE IF NOT EXISTS ')[1].split(' ')[0].split('(')[0]
                    print(f"  [{i+1}/{len(schema_statements)}] Creating table {table_name}...")
                
                result = self.execute_query(statement)
                
                if table_name:
                    # Verify the table was created - need to fetch the result
                    verify_result = self.execute_query(
                        "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
                        (table_name,),
                        fetch='one'  # Explicitly fetch one row
                    )
                    # Check if table exists
                    table_exists = False
                    if verify_result:
                        if isinstance(verify_result, dict) and verify_result.get('count', 0) > 0:
                            table_exists = True
                        elif isinstance(verify_result, (tuple, list)) and verify_result[0] > 0:
                            table_exists = True
                    
                    if table_exists:
                        print(f"     ✓ Table {table_name} created successfully")
                    else:
                        print(f"     ✗ Table {table_name} was not created!")
                        failed_tables.append(table_name)
                        
            except Exception as e:
                print(f"❌ Error on statement {i}: {e}")
                # Log the first 200 chars of the statement for debugging
                print(f"   Statement preview: {statement[:200]}...")
                if table_name:
                    failed_tables.append(table_name)
                # For critical tables, don't continue
                if table_name in ['characters', 'inventory', 'locations']:
                    print(f"🛑 CRITICAL: Failed to create essential table '{table_name}'. Cannot continue.")
                    raise Exception(f"Failed to create critical table '{table_name}': {e}")
        
        # Add missing columns for existing databases
        column_migrations = [
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS discord_id BIGINT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS location_status TEXT DEFAULT \'docked\'',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_ship_id INTEGER',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_location INTEGER',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_home_id BIGINT',
            'ALTER TABLE characters ADD COLUMN IF NOT EXISTS ship_id BIGINT',
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
            'ALTER TABLE corridors ADD COLUMN IF NOT EXISTS is_generated BOOLEAN DEFAULT false',
            'ALTER TABLE corridors ADD COLUMN IF NOT EXISTS next_shift TIMESTAMP',
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
            
            # Drop duplicate coordinate columns if they exist (already migrated)
            'ALTER TABLE locations DROP COLUMN IF EXISTS x_coord',
            'ALTER TABLE locations DROP COLUMN IF EXISTS y_coord',
            
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
            # Shop items table columns
            'ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS sold_by_player BOOLEAN DEFAULT false',
            'ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS metadata TEXT',
            # Clean up redundant stock_quantity column (use stock instead)
            'ALTER TABLE shop_items DROP COLUMN IF EXISTS stock_quantity',
            
            # Fix data type mismatches for foreign keys
            'ALTER TABLE pending_robberies ALTER COLUMN location_id TYPE INTEGER USING location_id::INTEGER',
            'ALTER TABLE black_markets ALTER COLUMN location_id TYPE INTEGER USING location_id::INTEGER',
            'ALTER TABLE black_markets ALTER COLUMN reputation_required TYPE INTEGER USING reputation_required::INTEGER',
            'ALTER TABLE black_market_items ALTER COLUMN market_id TYPE INTEGER USING market_id::INTEGER',
            'ALTER TABLE black_market_items ALTER COLUMN price TYPE INTEGER USING price::INTEGER',
            
            # Add missing columns to repeaters table
            'ALTER TABLE repeaters ADD COLUMN IF NOT EXISTS owner_id BIGINT',
            'ALTER TABLE repeaters ADD COLUMN IF NOT EXISTS repeater_type TEXT DEFAULT \'standard\'',
            'ALTER TABLE repeaters ADD COLUMN IF NOT EXISTS deployed_at TIMESTAMP DEFAULT NOW()',
            
            # Add missing columns to galactic_history table
            'ALTER TABLE galactic_history ADD COLUMN IF NOT EXISTS event_title TEXT',
            'ALTER TABLE galactic_history ADD COLUMN IF NOT EXISTS historical_figure TEXT',
            'ALTER TABLE galactic_history ADD COLUMN IF NOT EXISTS event_date TEXT',
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
            'CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(owner_id)',
            'CREATE INDEX IF NOT EXISTS idx_inventory_item_name ON inventory(item_name)',
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
            # Quest system indexes
            'CREATE INDEX IF NOT EXISTS idx_quests_location ON quests(start_location_id)',
            'CREATE INDEX IF NOT EXISTS idx_quests_active ON quests(is_active) WHERE is_active = true',
            'CREATE INDEX IF NOT EXISTS idx_quest_objectives_quest ON quest_objectives(quest_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_objectives_order ON quest_objectives(quest_id, objective_order)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_user ON quest_progress(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_quest ON quest_progress(quest_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_status ON quest_progress(quest_status)',
            'CREATE INDEX IF NOT EXISTS idx_quest_progress_active ON quest_progress(user_id, quest_status) WHERE quest_status = \'active\'',
            'CREATE INDEX IF NOT EXISTS idx_quest_completions_user ON quest_completions(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_quest_completions_quest ON quest_completions(quest_id)',
            # Economy table indexes
            'CREATE INDEX IF NOT EXISTS idx_location_economy_location ON location_economy(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_location_economy_expires ON location_economy(expires_at)',
            'CREATE INDEX IF NOT EXISTS idx_location_economy_item ON location_economy(location_id, item_category, item_name)',
            'CREATE INDEX IF NOT EXISTS idx_economic_events_location ON economic_events(location_id)',
            'CREATE INDEX IF NOT EXISTS idx_economic_events_type ON economic_events(event_type)',
            # Ship activities indexes
            'CREATE INDEX IF NOT EXISTS idx_ship_activities_ship ON ship_activities(ship_id)',
            'CREATE INDEX IF NOT EXISTS idx_ship_activities_active ON ship_activities(ship_id, is_active) WHERE is_active = true',
        ]
        
        for index_sql in indexes:
            try:
                # Remove CONCURRENTLY if present and execute without transaction locks
                clean_sql = index_sql.replace('CONCURRENTLY ', '')
                self._create_index_without_transaction(clean_sql)
            except Exception as e:
                # Ignore index creation errors (they might already exist)
                print(f"Index creation note: {e}")
                pass
        
        # Verify critical tables exist
        critical_tables = ['characters', 'inventory', 'locations']
        print("\n🔍 Verifying critical tables...")
        for table in critical_tables:
            try:
                # Use a simpler query that just counts the table - with fetch='one'
                result = self.execute_query(
                    "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
                    (table,),
                    fetch='one'  # Make sure we fetch the result
                )
                # Check if result exists and has the expected structure
                if result:
                    if isinstance(result, dict):
                        exists = result.get('count', 0) > 0
                    elif isinstance(result, (tuple, list)):
                        exists = result[0] > 0 if len(result) > 0 else False
                    else:
                        # Unexpected result type
                        print(f"  ⚠️ Unexpected result type for table '{table}': {type(result)} = {result}")
                        exists = False
                    
                    if exists:
                        print(f"  ✅ Table '{table}' verified")
                    else:
                        print(f"  ❌ CRITICAL: Table '{table}' does not exist!")
                else:
                    print(f"  ❌ Could not verify table '{table}' - no result returned")
            except Exception as e:
                print(f"  ⚠️ Error verifying table '{table}': {e}")
        
        print("\n✅ PostgreSQL database schema initialized")

    def _create_index_without_transaction(self, index_sql):
        """Create index outside of transaction to avoid CONCURRENTLY issues"""
        conn = None
        try:
            conn = self.get_connection()
            conn.autocommit = True  # Enable autocommit to avoid transaction blocks
            cursor = conn.cursor()
            cursor.execute(index_sql)
            cursor.close()
        except Exception as e:
            # If index already exists or other issue, that's fine
            pass
        finally:
            if conn:
                conn.autocommit = False  # Reset to default
                self._close_connection(conn)

    def validate_schema(self):
        """Validate critical schema elements exist"""
        print("🔍 Validating database schema...")
        
        critical_validations = [
            ("shop_items table exists", "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'shop_items'"),
            ("sold_by_player column exists", "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'shop_items' AND column_name = 'sold_by_player'"),
            ("locations table exists", "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'locations'"),
            ("black_markets table exists", "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'black_markets'"),
            ("location_id foreign key exists", "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_name = 'black_markets' AND constraint_name = 'black_markets_location_id_fkey'"),
        ]
        
        validation_errors = []
        for validation_name, query in critical_validations:
            try:
                result = self.execute_query(query, fetch='one')
                if result and result[0] > 0:
                    print(f"  ✅ {validation_name}")
                else:
                    error_msg = f"❌ {validation_name} - FAILED"
                    print(error_msg)
                    validation_errors.append(error_msg)
            except Exception as e:
                error_msg = f"❌ {validation_name} - ERROR: {e}"
                print(error_msg)
                validation_errors.append(error_msg)
        
        if validation_errors:
            print(f"⚠️ Schema validation found {len(validation_errors)} issues:")
            for error in validation_errors:
                print(f"  {error}")
        else:
            print("✅ Database schema validation completed successfully")

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
                # PostgreSQL doesn't support cursor.lastrowid reliably
                # This is a fallback for legacy code - prefer using RETURNING in your SQL
                print("⚠️ WARNING: Using lastrowid with PostgreSQL is unreliable. Use 'RETURNING id' in your SQL instead.")
                result = cursor.lastrowid if hasattr(cursor, 'lastrowid') else 0
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