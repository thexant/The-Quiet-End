import aiosqlite
import logging

DATABASE_FILE = "game.db"

class Database:
    def __init__(self, db_file=DATABASE_FILE):
        self.db_file = db_file
        self.conn = None

    async def initialize(self):
        """Initializes the database connection and creates tables if they don't exist."""
        await self._create_tables()
        await self._migrate_schema()
        logging.info("Database initialized successfully.")

    async def _get_connection(self):
        return await aiosqlite.connect(self.db_file)

    async def execute_query(self, query, params=None):
        """Executes a query that modifies the database (INSERT, UPDATE, DELETE)."""
        async with await self._get_connection() as db:
            await db.execute(query, params or ())
            await db.commit()

    async def fetch_one(self, query, params=None):
        """Fetches a single row from the database."""
        async with await self._get_connection() as db:
            async with db.execute(query, params or ()) as cursor:
                return await cursor.fetchone()

    async def fetch_all(self, query, params=None):
        """Fetches all rows from the database."""
        async with await self._get_connection() as db:
            async with db.execute(query, params or ()) as cursor:
                return await cursor.fetchall()

    async def _create_tables(self):
        """Creates all necessary tables if they don't already exist."""
        async with await self._get_connection() as db:
            # All CREATE TABLE statements are executed here
            await db.execute('''
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, name TEXT, location_id INTEGER,
                    ship_id INTEGER, credits INTEGER, reputation INTEGER, health INTEGER, stamina INTEGER,
                    last_action_time REAL, FOREIGN KEY (location_id) REFERENCES locations(id),
                    FOREIGN KEY (ship_id) REFERENCES ships(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS ships (
                    id INTEGER PRIMARY KEY, owner_id INTEGER, name TEXT, fuel INTEGER, max_fuel INTEGER,
                    cargo_capacity INTEGER, health INTEGER, max_health INTEGER, location_id INTEGER,
                    last_used_time REAL, FOREIGN KEY (owner_id) REFERENCES characters(id),
                    FOREIGN KEY (location_id) REFERENCES locations(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY, character_id INTEGER, ship_id INTEGER, item_name TEXT, quantity INTEGER,
                    FOREIGN KEY (character_id) REFERENCES characters(id), FOREIGN KEY (ship_id) REFERENCES ships(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS locations (
                    id INTEGER PRIMARY KEY, name TEXT UNIQUE, type TEXT, x INTEGER, y INTEGER, z INTEGER,
                    economy_type TEXT, government_type TEXT, security_level INTEGER, description TEXT, population INTEGER)
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS market (
                    id INTEGER PRIMARY KEY, location_id INTEGER, item_name TEXT, quantity INTEGER,
                    buy_price INTEGER, sell_price INTEGER, FOREIGN KEY (location_id) REFERENCES locations(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS factions (
                    id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT, reputation INTEGER)
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY, character_id INTEGER, skill_name TEXT, skill_level INTEGER,
                    FOREIGN KEY (character_id) REFERENCES characters(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, location_id INTEGER NOT NULL, title TEXT NOT NULL,
                    description TEXT NOT NULL, reward_money INTEGER NOT NULL, required_skill TEXT,
                    min_skill_level INTEGER, danger_level INTEGER, duration_minutes INTEGER, expires_at DATETIME,
                    is_taken BOOLEAN DEFAULT 0, taken_by INTEGER, job_status TEXT DEFAULT 'available',
                    destination_location_id INTEGER, FOREIGN KEY (location_id) REFERENCES locations(id),
                    FOREIGN KEY (taken_by) REFERENCES characters(id),
                    FOREIGN KEY (destination_location_id) REFERENCES locations(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS character_jobs (
                    character_id INTEGER, job_id INTEGER, status TEXT, assigned_at DATETIME,
                    PRIMARY KEY (character_id, job_id), FOREIGN KEY (character_id) REFERENCES characters(id),
                    FOREIGN KEY (job_id) REFERENCES jobs(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS travel_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, ship_id INTEGER,
                    start_location_id INTEGER, end_location_id INTEGER, departure_time DATETIME,
                    arrival_time DATETIME, fuel_consumed INTEGER, status TEXT,
                    FOREIGN KEY (character_id) REFERENCES characters(id), FOREIGN KEY (ship_id) REFERENCES ships(id),
                    FOREIGN KEY (start_location_id) REFERENCES locations(id),
                    FOREIGN KEY (end_location_id) REFERENCES locations(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS npcs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, npc_type TEXT NOT NULL,
                    location_id INTEGER, ship_id INTEGER, dialogue_file TEXT, faction_id INTEGER,
                    is_hostile BOOLEAN DEFAULT 0, health INTEGER, shield INTEGER, attack_power INTEGER,
                    FOREIGN KEY (location_id) REFERENCES locations(id), FOREIGN KEY (ship_id) REFERENCES ships(id),
                    FOREIGN KEY (faction_id) REFERENCES factions(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_reputation (
                    character_id INTEGER NOT NULL, faction_id INTEGER NOT NULL, reputation_level INTEGER NOT NULL,
                    PRIMARY KEY (character_id, faction_id), FOREIGN KEY (character_id) REFERENCES characters(id),
                    FOREIGN KEY (faction_id) REFERENCES factions(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS location_ownership (
                    location_id INTEGER PRIMARY KEY, owner_id INTEGER, owner_type TEXT, acquired_at DATETIME,
                    FOREIGN KEY (location_id) REFERENCES locations(id))
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sub_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, parent_location_id INTEGER NOT NULL, name TEXT NOT NULL,
                    description TEXT, sub_type TEXT, FOREIGN KEY (parent_location_id) REFERENCES locations(id))
            ''')
            await db.commit()

    async def _migrate_schema(self):
        """Applies schema migrations to an existing database."""
        async with await self._get_connection() as db:
            try:
                cursor = await db.execute("PRAGMA table_info(jobs)")
                columns = [row[1] for row in await cursor.fetchall()]
                if 'destination_location_id' not in columns:
                    await db.execute("ALTER TABLE jobs ADD COLUMN destination_location_id INTEGER REFERENCES locations(id)")
                    await db.commit()
                    logging.info("Successfully migrated jobs table: Added destination_location_id column.")
            except Exception as e:
                logging.error(f"Error during schema migration for jobs table: {e}")