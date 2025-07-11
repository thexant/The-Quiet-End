# config.py
"""
Configuration settings for the Discord RPG Bot
Modify these values to customize your server experience
"""

# Bot Configuration
BOT_CONFIG = {
    'token': 'YOUR_BOT_TOKEN',  # REPLACE WITH YOUR ACTUAL TOKEN OR USE ENVIRONMENT VARIABLE
    'command_prefix': '!',           # Prefix for text commands (slash commands don't use this)
    'description': 'A 27th century space RPG bot',
    'activity_name': 'in the void of space',  # Bot status message
}

# Galaxy Generation Settings
GALAXY_CONFIG = {
    'default_locations': 50,         # Default number of locations to generate
    'galaxy_radius': 100.0,          # Size of the galaxy map
    'location_distribution': {       # Percentage of each location type
        'colony': 0.40,              # 40% colonies
        'space_station': 0.25,       # 25% space stations
        'outpost': 0.25,             # 25% outposts
        'gate': 0.10                 # 10% gates
    },
    'corridor_connections': {        # Corridor generation settings
        'min_connections': 2,        # Minimum connections per location
        'max_connections': 4,        # Maximum connections per location
        'connection_bias': {         # Higher chance to connect to these types
            'gate': 0.9,
            'space_station': 0.9,
            'colony': 0.7,
            'outpost': 0.4
        }
    }
}

# Game Balance Settings
GAME_BALANCE = {
    'starting_credits': 500,         # Credits new characters start with
    'starting_fuel': 100,            # Starting ship fuel
    'fuel_efficiency_range': (3, 8), # Ship fuel efficiency range
    'wealth_effects': {              # How location wealth affects prices
        'poor_price_multiplier': 1.5,   # Poor locations charge 150% normal
        'rich_price_multiplier': 0.8,   # Rich locations charge 80% normal
        'sell_price_base': 0.6,         # Base sell price (60% of item value)
        'wealth_sell_bonus': 0.02       # +2% sell price per wealth level
    },
    'job_settings': {
        'max_jobs_per_location': 8,  # Maximum jobs at any location
        'job_generation_chance': 0.75, # 70% chance to generate job every cycle
        'job_expiry_hours': (4, 12), # Jobs expire between 4-12 hours
        'skill_improvement_chance': 0.2 # 20% chance to gain skill from jobs
    }
}

# Event System Settings
EVENT_CONFIG = {
    'corridor_management': {
        'check_interval_hours': 6,   # How often to check for corridor events
        'base_shift_chance': 5,      # 5% base chance of shift per check
        'base_collapse_chance': 0.5, # 0.5% base chance of collapse
        'time_multiplier_max': 3     # Maximum time-based multiplier
    },
    'random_events': {
        'check_interval_hours': 2,   # How often to generate random events
        'event_chance': 0.1,         # 10% chance per location per check
        'wealth_effect_multiplier': 1.5 # How much wealth affects event types
    },
    'cleanup_tasks': {
        'interval_hours': 1,         # How often cleanup runs
        'expire_jobs_days': 1,       # Remove completed jobs after 1 day
        'expire_sessions_days': 1    # Remove old travel sessions after 1 day
    }
}

# Travel System Settings
TRAVEL_CONFIG = {
    'base_travel_time': 300,         # Base travel time in seconds (3 minutes)
    'fuel_cost_multiplier': 15,      # Travel time / 15 = fuel cost
    'danger_levels': 5,              # Maximum danger level for corridors
    'emergency_exit': {
        'base_survival_chance': 80,  # 80% base survival chance
        'danger_penalty': 15,        # -15% per danger level
        'min_survival_chance': 20    # Minimum 20% survival chance
    },
    'transit_channels': {
        'progress_updates': [0.25, 0.5, 0.75],  # Progress points for updates
        'event_chance_multiplier': 0.1,  # Danger level * 0.1 = event chance
        'cleanup_delay': 30          # Seconds before deleting transit channel
    }
}

# Channel Management Settings
CHANNEL_CONFIG = {
    'max_location_channels': 50,     # Default max active location channels
    'channel_timeout_hours': 48,     # Hours before unused channels are deleted
    'cleanup_interval_hours': 6,     # How often to run cleanup
    'auto_cleanup_enabled': True,    # Enable automatic cleanup
    'category_names': {              # Category names for organization
        'colony': '🏭 COLONIES',
        'space_station': '🛰️ SPACE STATIONS',
        'outpost': '🛤️ OUTPOSTS', 
        'gate': '🚪 GATES',
        'transit': '🚀 IN TRANSIT'
    },
    'batch_cleanup_size': 5          # How many channels to clean up at once
}

# Discord Settings
DISCORD_CONFIG = {
    'embed_colors': {
        'success': 0x00ff00,         # Green
        'error': 0xff0000,           # Red
        'warning': 0xff9900,         # Orange
        'info': 0x4169E1,            # Royal Blue
        'character': 0x0099ff,       # Light Blue
        'travel': 0xff6600,          # Orange-Red
        'economy': 0xffd700,         # Gold
        'group': 0x9932cc,           # Purple
        'admin': 0xff0000            # Red
    },
    'pagination': {
        'items_per_page': 10,        # Items to show per page in lists
        'max_fields_per_embed': 25   # Discord's limit
    },
    'timeouts': {
        'button_timeout': 300,       # 5 minutes for button interactions
        'modal_timeout': 300,        # 5 minutes for modal responses
        'vote_timeout': 300          # 5 minutes for group votes
    }
}

# Database Settings
DATABASE_CONFIG = {
    'db_path': 'rpg_game.db',        # SQLite database file path
    'connection_timeout': 30.0,      # Database connection timeout
    'backup_interval_hours': 24,     # How often to backup database (if implemented)
    'vacuum_interval_days': 7        # How often to optimize database (if implemented)
}

# Admin Settings
ADMIN_CONFIG = {
    'notification_channels': [],     # Channel IDs to notify of major events
    'auto_generate_on_empty': True,  # Auto-generate galaxy if no locations exist
    'require_admin_for_creation': True, # Require admin perms for manual creation
    'max_manual_locations': 200,     # Maximum manually created locations
    'backup_on_major_changes': True  # Backup database on major admin actions
}

# Add this section to config.py

# Event System Configuration
EVENT_CONFIG = {
    'base_event_frequency': 0.25,     # Base chance per 15-minute check
    'travel_event_frequency': 0.15,   # Base chance for travel events
    'galaxy_event_frequency': 0.05,   # Base chance for galaxy-wide events
    'min_event_spacing_minutes': 30,  # Minimum time between events at same location
    'event_timeout_seconds': 300,     # How long interactive events stay active
    'max_concurrent_events': 3,       # Maximum events per location
    
    # Event weights by location type
    'location_event_weights': {
        'colony': 1.2,
        'space_station': 1.3,
        'outpost': 0.9,
        'gate': 0.8
    },
    
    # Wealth modifiers for events
    'wealth_modifiers': {
        'poor_event_increase': 1.4,    # Poor locations get more negative events
        'rich_event_decrease': 0.7,    # Rich locations get fewer negative events
        'wealth_threshold_poor': 3,
        'wealth_threshold_rich': 7
    }
}