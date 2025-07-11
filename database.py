import aiosqlite
import logging

DATABASE_FILE = "game.db"

class Database:
    def __init__(self, db_file=DATABASE_FILE):
        self.db_file = db_file

    async def initialize(self):
        """Initializes the database connection and creates tables if they don't exist."""
        await self._create_tables()
        await self._migrate_schema()
        logging.info("Database initialized successfully.")

    async def _get_connection(self):
        """Creates a new database connection each time"""
        return aiosqlite.connect(self.db_file)

    async def execute_query(self, query, params=None, fetch=None):
        """Executes a query and optionally fetches results."""
        async with aiosqlite.connect(self.db_file) as db:
            if fetch == 'one':
                async with db.execute(query, params or ()) as cursor:
                    return await cursor.fetchone()
            elif fetch == 'all':
                async with db.execute(query, params or ()) as cursor:
                    return await cursor.fetchall()
            else:
                # For INSERT, UPDATE, DELETE operations
                await db.execute(query, params or ())
                await db.commit()
                return db.lastrowid if query.strip().upper().startswith('INSERT') else None

    async def fetch_one(self, query, params=None):
        """Fetches a single row from the database."""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(query, params or ()) as cursor:
                return await cursor.fetchone()

    async def fetch_all(self, query, params=None):
        """Fetches all rows from the database."""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(query, params or ()) as cursor:
                return await cursor.fetchall()

    async def _create_tables(self):
        """Creates all necessary tables if they don't already exist."""
        async with aiosqlite.connect(self.db_file) as db:
            # Characters table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY, 
                    user_id INTEGER UNIQUE, 
                    name TEXT, 
                    callsign TEXT,
                    appearance TEXT,
                    image_url TEXT,
                    current_location INTEGER,
                    ship_id INTEGER, 
                    active_ship_id INTEGER,
                    credits INTEGER DEFAULT 1000, 
                    reputation INTEGER DEFAULT 0, 
                    health INTEGER DEFAULT 100, 
                    stamina INTEGER DEFAULT 100,
                    engineering INTEGER DEFAULT 10,
                    navigation INTEGER DEFAULT 10,
                    combat INTEGER DEFAULT 10,
                    medical INTEGER DEFAULT 10,
                    is_logged_in BOOLEAN DEFAULT 0,
                    login_time TIMESTAMP,
                    last_activity TIMESTAMP,
                    last_action_time REAL, 
                    FOREIGN KEY (current_location) REFERENCES locations(location_id),
                    FOREIGN KEY (ship_id) REFERENCES ships(ship_id),
                    FOREIGN KEY (active_ship_id) REFERENCES ships(ship_id)
                )
            ''')
            
            # Character identity table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS character_identity (
                    user_id INTEGER PRIMARY KEY,
                    birth_month INTEGER,
                    birth_day INTEGER,
                    birth_year INTEGER,
                    age INTEGER,
                    biography TEXT,
                    birthplace_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES characters(user_id),
                    FOREIGN KEY (birthplace_id) REFERENCES locations(location_id)
                )
            ''')
            
            # Ships table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS ships (
                    ship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER, 
                    name TEXT, 
                    ship_type TEXT DEFAULT 'Civilian Transport',
                    exterior_description TEXT,
                    interior_description TEXT,
                    fuel INTEGER DEFAULT 100, 
                    max_fuel INTEGER DEFAULT 100,
                    cargo_capacity INTEGER DEFAULT 50, 
                    health INTEGER DEFAULT 100, 
                    max_health INTEGER DEFAULT 100, 
                    current_location INTEGER,
                    last_used_time REAL, 
                    FOREIGN KEY (owner_id) REFERENCES characters(user_id),
                    FOREIGN KEY (current_location) REFERENCES locations(location_id)
                )
            ''')
            
            # Player ships junction table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_ships (
                    owner_id INTEGER,
                    ship_id INTEGER,
                    is_active BOOLEAN DEFAULT 0,
                    PRIMARY KEY (owner_id, ship_id),
                    FOREIGN KEY (owner_id) REFERENCES characters(user_id),
                    FOREIGN KEY (ship_id) REFERENCES ships(ship_id)
                )
            ''')
            
            # Inventory table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER, 
                    ship_id INTEGER, 
                    item_name TEXT, 
                    item_type TEXT,
                    quantity INTEGER DEFAULT 1,
                    description TEXT,
                    value INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (owner_id) REFERENCES characters(user_id), 
                    FOREIGN KEY (ship_id) REFERENCES ships(ship_id)
                )
            ''')
            
            # Locations table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS locations (
                    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE, 
                    location_type TEXT, 
                    x INTEGER, 
                    y INTEGER, 
                    z INTEGER,
                    economy_type TEXT, 
                    government_type TEXT, 
                    security_level INTEGER, 
                    description TEXT, 
                    population INTEGER,
                    wealth_level INTEGER DEFAULT 1,
                    generated_income INTEGER DEFAULT 0
                )
            ''')
            
            # Corridors table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS corridors (
                    corridor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin_location INTEGER,
                    destination_location INTEGER,
                    corridor_type TEXT,
                    travel_time INTEGER,
                    fuel_cost INTEGER,
                    danger_level INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT 1,
                    description TEXT,
                    FOREIGN KEY (origin_location) REFERENCES locations(location_id),
                    FOREIGN KEY (destination_location) REFERENCES locations(location_id)
                )
            ''')
            
            # Market table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS market (
                    market_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER, 
                    item_name TEXT, 
                    quantity INTEGER DEFAULT 0,
                    buy_price INTEGER, 
                    sell_price INTEGER, 
                    FOREIGN KEY (location_id) REFERENCES locations(location_id)
                )
            ''')
            
            # Factions table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS factions (
                    faction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE, 
                    description TEXT, 
                    reputation INTEGER DEFAULT 0
                )
            ''')
            
            # Skills table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS skills (
                    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER, 
                    skill_name TEXT, 
                    skill_level INTEGER DEFAULT 1,
                    FOREIGN KEY (character_id) REFERENCES characters(user_id)
                )
            ''')
            
            # Jobs table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    location_id INTEGER NOT NULL, 
                    title TEXT NOT NULL,
                    description TEXT NOT NULL, 
                    reward_money INTEGER NOT NULL, 
                    required_skill TEXT,
                    min_skill_level INTEGER, 
                    danger_level INTEGER DEFAULT 1, 
                    duration_minutes INTEGER DEFAULT 30, 
                    expires_at DATETIME,
                    is_taken BOOLEAN DEFAULT 0, 
                    taken_by INTEGER, 
                    job_status TEXT DEFAULT 'available',
                    difficulty TEXT DEFAULT 'easy',
                    FOREIGN KEY (location_id) REFERENCES locations(location_id),
                    FOREIGN KEY (taken_by) REFERENCES characters(user_id)
                )
            ''')
            
            # Job tracking table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS job_tracking (
                    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    user_id INTEGER,
                    start_location INTEGER,
                    required_duration INTEGER,
                    time_at_location REAL DEFAULT 0,
                    last_location_check DATETIME,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                    FOREIGN KEY (user_id) REFERENCES characters(user_id),
                    FOREIGN KEY (start_location) REFERENCES locations(location_id)
                )
            ''')
            
            await db.commit()

    async def _migrate_schema(self):
        """Handle any database schema migrations"""
        try:
            # Check if we need to add any missing columns
            async with aiosqlite.connect(self.db_file) as db:
                # Add any schema updates here as needed
                # Example: Add new columns if they don't exist
                try:
                    await db.execute('ALTER TABLE characters ADD COLUMN is_logged_in BOOLEAN DEFAULT 0')
                    await db.commit()
                except:
                    pass  # Column already exists
                
                try:
                    await db.execute('ALTER TABLE characters ADD COLUMN login_time TIMESTAMP')
                    await db.commit()
                except:
                    pass  # Column already exists
                
                try:
                    await db.execute('ALTER TABLE characters ADD COLUMN last_activity TIMESTAMP')
                    await db.commit()
                except:
                    pass  # Column already exists
                    
        except Exception as e:
            logging.warning(f"Schema migration warning: {e}")