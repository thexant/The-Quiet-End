# utils/history_generator.py
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from utils.npc_data import generate_npc_name
import asyncio
import gc

class HistoryGenerator:
    """Generates galactic history events for locations and notable figures"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Historical event templates
        self.event_templates = {
            'colony': [
                "{figure} led the first colonial expedition to establish {location}",
                "{figure} discovered rich mineral deposits beneath {location}, sparking a settlement boom",
                "{figure} negotiated crucial trade agreements that made {location} a commercial hub",
                "{figure} defended {location} against pirate raids, becoming a local hero",
                "{figure} established the first agricultural domes on {location}",
                "{figure} founded the medical research facility that put {location} on the galactic map",
                "{figure} organized the great exodus that populated {location} during the resource wars",
                "{figure} built the first industrial complex on {location}, transforming the economy",
                "{figure} established diplomatic relations between {location} and neighboring systems",
                "{figure} led relief efforts during the great famine that devastated {location}"
            ],
            'space_station': [
                "{figure} designed and oversaw the construction of {location}",
                "{figure} served as the first station commander of {location}, establishing operational protocols",
                "{figure} negotiated the strategic placement of {location} along major trade routes",
                "{figure} led the engineering team that solved critical life support failures at {location}",
                "{figure} established {location} as a neutral meeting point for warring factions",
                "{figure} developed the unique modular design that makes {location} easily expandable",
                "{figure} coordinated the massive logistics operation to supply {location} during construction",
                "{figure} prevented a catastrophic reactor meltdown at {location}, saving thousands of lives",
                "{figure} established the first diplomatic embassy aboard {location}",
                "{figure} transformed {location} from a simple waystation into a thriving commercial hub"
            ],
            'outpost': [
                "{figure} established {location} as a critical monitoring post for early warning systems",
                "{figure} discovered the strategic importance of {location}'s position in the galactic grid",
                "{figure} led the skeleton crew that maintained {location} during the dark years",
                "{figure} upgraded {location} from a basic relay into a sophisticated outpost",
                "{figure} defended {location} single-handedly against a bandit assault",
                "{figure} established the communication protocols that made {location} a vital relay hub",
                "{figure} survived alone at {location} for six months when supply lines were cut",
                "{figure} solved the technical mysteries that plagued {location}'s original construction",
                "{figure} coordinated search and rescue operations from {location}, saving countless lives",
                "{figure} transformed {location} from a forgotten relay into a crucial navigation beacon"
            ],
            'gate': [
                "{figure} pioneered the corridor transit technology that powers {location}",
                "{figure} established the safety protocols that govern {location}'s operations",
                "{figure} led the construction of {location}, connecting distant regions of the galaxy",
                "{figure} solved the quantum instabilities that initially plagued {location}",
                "{figure} established {location} as the primary gateway to the outer rim territories",
                "{figure} coordinated the massive engineering project to stabilize {location}'s corridor matrix",
                "{figure} developed the traffic control systems that manage {location}'s heavy transit volume",
                "{figure} led the emergency repairs that saved {location} after a cascade failure",
                "{figure} negotiated the treaties that established {location} as neutral territory",
                "{figure} designed the unique architecture that makes {location} both functional and magnificent"
            ]
        }
        
        # General galactic events not tied to specific locations
        self.general_events = [
            "The Great Expansion began, marking humanity's spread across the galaxy",
            "The Resource Wars erupted across multiple systems, reshaping galactic politics",
            "The first successful corridor jump was achieved, revolutionizing interstellar travel",
            "The Galactic Trade Commission was established, standardizing commerce",
            "The Pirate Wars reached their peak, with major battles in the outer rim",
            "The Great Silence occurred when all long-range communications failed for six months",
            "The Discovery of the Ancient Artifacts sparked new technological development",
            "The Unity Accords were signed, establishing peace between major factions",
            "The Great Migration saw millions flee the core worlds for frontier territories",
            "The Technological Renaissance transformed daily life across human space"
        ]
        
        # Event types for variety
        self.event_types = [
            'founding', 'discovery', 'conflict', 'diplomacy', 'disaster', 
            'innovation', 'trade', 'exploration', 'heroism', 'tragedy'
        ]

    async def generate_galaxy_history(self, start_year: int, current_date: str) -> int:
        """Generate comprehensive galactic history using chunked transactions to prevent hangs"""
        print("📚 Generating galactic history with chunked processing...")
        print(f"🔧 DEBUG: Starting history generation for start_year={start_year}, current_date={current_date}")
        
        try:
            # Clear existing history first in a separate transaction
            await self._clear_existing_history()
            
            # Get all locations for processing
            locations = await self._get_locations_for_history()
            if not locations:
                print("⚠️ No locations found for history generation.")
                return await self._generate_general_history_only(start_year, current_date)
            
            # Process locations in smaller chunks to prevent database hangs
            chunk_size = 15  # Process 15 locations per transaction (reduced from 25)
            total_events = 0
            
            print(f"📚 Processing {len(locations)} locations in chunks of {chunk_size}")
            
            for i in range(0, len(locations), chunk_size):
                chunk = locations[i:i + chunk_size]
                chunk_events = await self._process_location_chunk(chunk, start_year, current_date, i)
                total_events += chunk_events
                
                # Progress reporting
                progress = min(100, ((i + chunk_size) / len(locations)) * 100)
                print(f"    History progress: {progress:.0f}% ({i + len(chunk)}/{len(locations)})")
                
                # Longer pause between chunks for better database safety
                await asyncio.sleep(0.1)
            
            # Generate general galactic events in a separate transaction
            general_events = await self._generate_general_history_chunked(start_year, current_date)
            total_events += general_events
            
            # Memory cleanup after intensive history generation
            gc.collect()
            print("🧩 Memory cleanup completed after history generation")
            
            print(f"📚 Generated {total_events} historical events using chunked processing")
            return total_events
            
        except Exception as e:
            print(f"❌ Error generating galactic history: {e}")
            import traceback
            print(f"❌ DEBUG: Full error traceback:\n{traceback.format_exc()}")
            raise e
    
    async def _clear_existing_history(self):
        """Clear existing history in a separate transaction"""
        print("🔧 DEBUG: Clearing existing galactic history...")
        max_retries = 5
        for attempt in range(max_retries):
            conn = None
            try:
                if attempt > 0:
                    await asyncio.sleep(0.5 + attempt * 0.5)  # More aggressive exponential backoff
                
                conn = self.db.begin_transaction()
                self.db.execute_in_transaction(conn, "DELETE FROM galactic_history")
                self.db.commit_transaction(conn)
                conn = None
                print("🔧 DEBUG: Existing history cleared successfully")
                return
            except Exception as e:
                if conn:
                    try:
                        self.db.rollback_transaction(conn)
                    except Exception as cleanup_error:
                        print(f"⚠️ Error during connection cleanup: {cleanup_error}")
                    finally:
                        conn = None
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"🔧 Database locked during history clear, retry {attempt + 1}/{max_retries}")
                    continue
                raise e
    
    async def _get_locations_for_history(self):
        """Get all locations for history generation with retry logic"""
        max_retries = 5
        for attempt in range(max_retries):
            conn = None
            try:
                if attempt > 0:
                    await asyncio.sleep(0.5 + attempt * 0.5)  # More aggressive exponential backoff
                
                conn = self.db.begin_transaction()
                try:
                    locations = self.db.execute_in_transaction(conn,
                        "SELECT location_id, name, location_type, establishment_date FROM locations WHERE is_generated = 1",
                        fetch='all'
                    )
                    self.db.commit_transaction(conn)
                    conn = None
                    
                    if locations and len(locations) > 150:
                        locations = random.sample(locations, 150)
                        print(f"📚 Limited history generation to 150 locations (out of {len(locations)} total)")
                    
                    print(f"🔧 Found {len(locations) if locations else 0} locations for history generation")
                    return locations
                    
                except Exception as e:
                    if conn:
                        self.db.rollback_transaction(conn)
                        conn = None
                    if "no such column: establishment_date" in str(e):
                        print("⚠️ establishment_date column missing, setting defaults...")
                        # Try again with simpler query using read-only operation
                        locations = self.db.execute_query(
                            "SELECT location_id, name, location_type, '01-01-2750' as establishment_date FROM locations WHERE is_generated = 1",
                            fetch='all'
                        )
                        if locations and len(locations) > 150:
                            locations = random.sample(locations, 150)
                        return locations
                    raise e
                    
            except Exception as e:
                if conn:
                    try:
                        self.db.rollback_transaction(conn)
                    except Exception as cleanup_error:
                        print(f"⚠️ Error during connection cleanup: {cleanup_error}")
                    finally:
                        conn = None
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"🔧 Database locked getting locations, retry {attempt + 1}/{max_retries}")
                    continue
                raise e
    
    async def _process_location_chunk(self, locations_chunk, start_year: int, current_date: str, chunk_index: int):
        """Process a chunk of locations in a single transaction"""
        max_retries = 5
        for attempt in range(max_retries):
            conn = None
            try:
                if attempt > 0:
                    await asyncio.sleep(0.5 + attempt * 0.5)  # More aggressive exponential backoff
                
                conn = self.db.begin_transaction()
                
                try:
                    current_date_obj = datetime.strptime(current_date, '%Y-%m-%d')
                    total_events = 0
                    
                    # Pre-fetch NPCs for this chunk
                    location_ids = [loc[0] for loc in locations_chunk]
                    placeholders = ','.join(['?' for _ in location_ids])
                    npc_query = f"SELECT location_id, name FROM static_npcs WHERE location_id IN ({placeholders})"
                    all_npcs_list = self.db.execute_in_transaction(conn, npc_query, location_ids, fetch='all')
                    
                    # Group NPCs by location
                    npcs_by_location = {}
                    for loc_id, npc_name in all_npcs_list:
                        if loc_id not in npcs_by_location:
                            npcs_by_location[loc_id] = []
                        npcs_by_location[loc_id].append(npc_name)
                    
                    # Process each location in this chunk
                    query = '''INSERT INTO galactic_history 
                               (location_id, event_title, event_description, historical_figure, event_date, event_type)
                               VALUES (?, ?, ?, ?, ?, ?)'''
                    
                    all_events = []
                    for location_id, name, location_type, establishment_date in locations_chunk:
                        existing_npcs = npcs_by_location.get(location_id, [])
                        num_events = random.randint(2, 3)  # Further reduced events per location for safety
                        
                        location_events = await self._prepare_location_history_data_optimized(
                            conn, location_id, name, location_type, establishment_date, 
                            start_year, current_date_obj, existing_npcs, num_events
                        )
                        all_events.extend(location_events)
                        total_events += len(location_events)
                    
                    # Insert all events for this chunk
                    if all_events:
                        self.db.executemany_in_transaction(conn, query, all_events)
                    
                    self.db.commit_transaction(conn)
                    conn = None
                    return total_events
                    
                except Exception as e:
                    if conn:
                        self.db.rollback_transaction(conn)
                        conn = None
                    raise e
                    
            except Exception as e:
                if conn:
                    try:
                        self.db.rollback_transaction(conn)
                    except Exception as cleanup_error:
                        print(f"⚠️ Error during connection cleanup: {cleanup_error}")
                    finally:
                        conn = None
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"🔧 Database locked processing chunk {chunk_index}, retry {attempt + 1}/{max_retries}")
                    continue
                print(f"❌ Error processing location chunk {chunk_index}: {e}")
                return 0  # Return 0 events for failed chunk but don't crash
    
    async def _generate_general_history_chunked(self, start_year: int, current_date: str):
        """Generate general galactic events in a separate transaction"""
        max_retries = 5
        for attempt in range(max_retries):
            conn = None
            try:
                if attempt > 0:
                    await asyncio.sleep(0.5 + attempt * 0.5)  # More aggressive exponential backoff
                
                conn = self.db.begin_transaction()
                
                try:
                    current_date_obj = datetime.strptime(current_date, '%Y-%m-%d')
                    general_events = await self._prepare_general_history_data_optimized(start_year, current_date_obj, 10)
                    
                    if general_events:
                        query = '''INSERT INTO galactic_history 
                                   (location_id, event_title, event_description, historical_figure, event_date, event_type)
                                   VALUES (?, ?, ?, ?, ?, ?)'''
                        self.db.executemany_in_transaction(conn, query, general_events)
                    
                    self.db.commit_transaction(conn)
                    conn = None
                    print(f"📚 Generated {len(general_events)} general galactic events")
                    return len(general_events)
                    
                except Exception as e:
                    if conn:
                        self.db.rollback_transaction(conn)
                        conn = None
                    raise e
                    
            except Exception as e:
                if conn:
                    try:
                        self.db.rollback_transaction(conn)
                    except Exception as cleanup_error:
                        print(f"⚠️ Error during connection cleanup: {cleanup_error}")
                    finally:
                        conn = None
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"🔧 Database locked generating general history, retry {attempt + 1}/{max_retries}")
                    continue
                print(f"❌ Error generating general history: {e}")
                return 0  # Return 0 events but don't crash
    
    async def _generate_general_history_only(self, start_year: int, current_date: str):
        """Generate only general galactic events when no locations exist"""
        print("📚 Generating general galactic events only (no locations available)")
        return await self._generate_general_history_chunked(start_year, current_date)
            
    async def _prepare_location_history_data(self, conn, location_id: int, location_name: str, 
                                           location_type: str, establishment_date: str, 
                                           start_year: int, current_date: datetime) -> List[Tuple]:
        """Prepare location history data for bulk insert (returns list of tuples)"""
        history_events = []
        
        # Get NPCs from this location for historical figures using the transaction connection
        npcs = self.db.execute_in_transaction(conn,
            "SELECT name FROM static_npcs WHERE location_id = ? LIMIT 5",
            (location_id,),
            fetch='all'
        )
        
        # Create a pool of historical figures (existing NPCs + generated names)
        historical_figures = [npc[0] for npc in npcs] if npcs else []
        
        # Generate additional historical figures if needed
        while len(historical_figures) < 10:
            first_name, last_name = generate_npc_name()
            historical_figures.append(f"{first_name} {last_name}")
        
        # Parse establishment date with flexible format handling
        try:
            if establishment_date and establishment_date.strip():
                # Handle DD-MM-YYYY format (from galaxy generation)
                if '-' in establishment_date:
                    parts = establishment_date.split('-')
                    if len(parts) == 3:
                        # Could be DD-MM-YYYY or YYYY-MM-DD
                        if len(parts[0]) == 4:  # YYYY-MM-DD
                            est_date = datetime.strptime(establishment_date, '%Y-%m-%d')
                        else:  # DD-MM-YYYY
                            est_date = datetime.strptime(establishment_date, '%d-%m-%Y')
                    else:
                        raise ValueError("Invalid date format")
                else:
                    raise ValueError("No separator found")
            else:
                # No valid establishment date
                est_date = datetime(start_year - random.randint(1, 10), 
                                   random.randint(1, 12), 
                                   random.randint(1, 28))
        except (ValueError, TypeError, AttributeError):
            # Any parsing failure gets a fallback date
            est_date = datetime(start_year - random.randint(1, 10), 
                               random.randint(1, 12), 
                               random.randint(1, 28))
        
        # Generate 10 events between establishment and current date
        for _ in range(10):
            # Random date between establishment and current date
            time_span = current_date - est_date
            random_days = random.randint(0, time_span.days)
            event_date = est_date + timedelta(days=random_days)
            
            # Choose event template and figure
            templates = self.event_templates.get(location_type, self.event_templates['outpost'])
            event_template = random.choice(templates)
            figure = random.choice(historical_figures)
            
            # Format the event
            event_description = event_template.format(figure=figure, location=location_name)
            event_title = self._generate_event_title(event_description)
            event_type = random.choice(self.event_types)
            
            # Add to bulk insert list
            history_events.append((
                location_id, event_title, event_description, figure, 
                event_date.strftime('%Y-%m-%d'), event_type
            ))
        
        return history_events

    async def _prepare_general_history_data(self, start_year: int, current_date: datetime) -> List[Tuple]:
        """Prepare general galactic history data for bulk insert (returns list of tuples)"""
        history_events = []
        start_date = datetime(start_year - 350, 1, 1)  # Start 20 years before galaxy start
        
        # Generate 15 general galactic events
        for _ in range(25):
            # Random date between early history and current date
            time_span = current_date - start_date
            random_days = random.randint(0, time_span.days)
            event_date = start_date + timedelta(days=random_days)
            
            # Choose general event
            event_description = random.choice(self.general_events)
            event_title = self._generate_event_title(event_description)
            
            # Generate a historical figure for some events
            figure = None
            if random.random() < 0.6:  # 60% chance of having a notable figure
                first_name, last_name = generate_npc_name()
                figure = f"{first_name} {last_name}"
                
                # Add figure to some descriptions
                if "began" in event_description or "established" in event_description:
                    event_description = f"{figure} initiated what became known as: {event_description}"
            
            # Add to bulk insert list
            history_events.append((
                None, event_title, event_description, figure, 
                event_date.strftime('%Y-%m-%d'), 'general'
            ))
        
        return history_events
    async def _generate_location_history(self, location_id: int, location_name: str, 
                                       location_type: str, establishment_date: str, 
                                       start_year: int, current_date: datetime) -> int:
        """Generate 10 historical events for a specific location"""
        events_created = 0
        
        # Get NPCs from this location for historical figures
        npcs = self.db.execute_query(
            "SELECT name FROM static_npcs WHERE location_id = ? LIMIT 5",
            (location_id,),
            fetch='all'
        )
        
        # Create a pool of historical figures (existing NPCs + generated names)
        historical_figures = [npc[0] for npc in npcs] if npcs else []
        
        # Generate additional historical figures if needed
        while len(historical_figures) < 10:
            first_name, last_name = generate_npc_name()
            historical_figures.append(f"{first_name} {last_name}")
        
        # Parse establishment date with flexible format handling
        try:
            if establishment_date and establishment_date.strip():
                # Handle DD-MM-YYYY format (from galaxy generation)
                if '-' in establishment_date:
                    parts = establishment_date.split('-')
                    if len(parts) == 3:
                        # Could be DD-MM-YYYY or YYYY-MM-DD
                        if len(parts[0]) == 4:  # YYYY-MM-DD
                            est_date = datetime.strptime(establishment_date, '%Y-%m-%d')
                        else:  # DD-MM-YYYY
                            est_date = datetime.strptime(establishment_date, '%d-%m-%Y')
                    else:
                        raise ValueError("Invalid date format")
                else:
                    raise ValueError("No separator found")
            else:
                # No valid establishment date
                est_date = datetime(start_year - random.randint(1, 10), 
                                   random.randint(1, 12), 
                                   random.randint(1, 28))
        except (ValueError, TypeError, AttributeError):
            # Any parsing failure gets a fallback date
            est_date = datetime(start_year - random.randint(1, 10), 
                               random.randint(1, 12), 
                               random.randint(1, 28))
        
        # Generate 10 events between establishment and current date
        for _ in range(10):
            # Random date between establishment and current date
            time_span = current_date - est_date
            random_days = random.randint(0, time_span.days)
            event_date = est_date + timedelta(days=random_days)
            
            # Choose event template and figure
            templates = self.event_templates.get(location_type, self.event_templates['outpost'])
            event_template = random.choice(templates)
            figure = random.choice(historical_figures)
            
            # Format the event
            event_description = event_template.format(figure=figure, location=location_name)
            event_title = self._generate_event_title(event_description)
            event_type = random.choice(self.event_types)
            
            # Store in database
            self.db.execute_query(
                '''INSERT INTO galactic_history 
                   (location_id, event_title, event_description, historical_figure, event_date, event_type)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (location_id, event_title, event_description, figure, 
                 event_date.strftime('%Y-%m-%d'), event_type)
            )
            
            events_created += 1
        
        return events_created

    async def _generate_general_history(self, start_year: int, current_date: datetime) -> int:
        """Generate general galactic events not tied to specific locations"""
        events_created = 0
        start_date = datetime(start_year - 350, 1, 1)  # Start 20 years before galaxy start
        
        # Generate 15 general galactic events
        for _ in range(15):
            # Random date between early history and current date
            time_span = current_date - start_date
            random_days = random.randint(0, time_span.days)
            event_date = start_date + timedelta(days=random_days)
            
            # Choose general event
            event_description = random.choice(self.general_events)
            event_title = self._generate_event_title(event_description)
            
            # Generate a historical figure for some events
            figure = None
            if random.random() < 0.6:  # 60% chance of having a notable figure
                first_name, last_name = generate_npc_name()
                figure = f"{first_name} {last_name}"
                
                # Add figure to some descriptions
                if "began" in event_description or "established" in event_description:
                    event_description = f"{figure} initiated what became known as: {event_description}"
            
            # Store in database
            self.db.execute_query(
                '''INSERT INTO galactic_history 
                   (location_id, event_title, event_description, historical_figure, event_date, event_type)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (None, event_title, event_description, figure, 
                 event_date.strftime('%Y-%m-%d'), 'general')
            )
            
            events_created += 1
        
        return events_created

    def _generate_event_title(self, description: str) -> str:
        """Generate a short title from an event description"""
        # Extract key words and create a title
        words = description.split()
        
        # Common title patterns
        if "established" in description.lower():
            return "Foundation Event"
        elif "defended" in description.lower() or "battle" in description.lower():
            return "Defensive Action"
        elif "discovered" in description.lower():
            return "Discovery"
        elif "negotiated" in description.lower() or "treaty" in description.lower():
            return "Diplomatic Achievement"
        elif "built" in description.lower() or "constructed" in description.lower():
            return "Construction Project"
        elif "led" in description.lower():
            return "Leadership Initiative"
        elif "saved" in description.lower() or "rescue" in description.lower():
            return "Heroic Action"
        else:
            return "Historical Event"
    async def _prepare_location_history_data_optimized(self, conn, location_id: int, location_name: str, 
                                                     location_type: str, establishment_date: str, 
                                                     start_year: int, current_date: datetime, 
                                                     existing_npcs: List[str], num_events: int) -> List[Tuple]:
        """Optimized location history data preparation with pre-fetched NPCs"""
        history_events = []
        
        # Use existing NPCs or generate minimal figures
        historical_figures = existing_npcs[:5] if existing_npcs else []
        
        # Generate fewer additional figures (3-5 instead of 10)
        while len(historical_figures) < 5:
            first_name, last_name = generate_npc_name()
            historical_figures.append(f"{first_name} {last_name}")
        
        # Yield to prevent blocking the event loop
        await asyncio.sleep(0)
        
        # Parse establishment date (reuse existing logic but simplified)
        try:
            if establishment_date and establishment_date.strip() and '-' in establishment_date:
                parts = establishment_date.split('-')
                if len(parts) == 3:
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        est_date = datetime.strptime(establishment_date, '%Y-%m-%d')
                    else:  # DD-MM-YYYY
                        est_date = datetime.strptime(establishment_date, '%d-%m-%Y')
                else:
                    raise ValueError("Invalid format")
            else:
                raise ValueError("No valid date")
        except:
            # Fallback date
            est_date = datetime(start_year - random.randint(1, 10), 
                               random.randint(1, 12), 
                               random.randint(1, 28))
        
        # Generate fewer events per location
        templates = self.event_templates.get(location_type, self.event_templates['outpost'])
        for _ in range(num_events):
            # Random date between establishment and current date
            time_span = current_date - est_date
            if time_span.days > 0:
                random_days = random.randint(0, time_span.days)
                event_date = est_date + timedelta(days=random_days)
            else:
                event_date = est_date
            
            # Choose event template and figure
            event_template = random.choice(templates)
            figure = random.choice(historical_figures)
            
            # Format the event
            event_description = event_template.format(figure=figure, location=location_name)
            event_title = self._generate_event_title(event_description)
            event_type = random.choice(self.event_types)
            
            # Add to bulk insert list
            history_events.append((
                location_id, event_title, event_description, figure, 
                event_date.strftime('%Y-%m-%d'), event_type
            ))
            
            # Yield control more frequently during event generation
            if _ % 1 == 0:  # Every event
                await asyncio.sleep(0)
        
        return history_events

    async def _prepare_general_history_data_optimized(self, start_year: int, current_date: datetime, num_events: int) -> List[Tuple]:
        """Optimized general galactic history data preparation"""
        history_events = []
        start_date = datetime(start_year - 100, 1, 1)  # Reduced history span
        
        # Generate fewer general galactic events
        for i in range(num_events):
            # Random date between early history and current date
            time_span = current_date - start_date
            random_days = random.randint(0, time_span.days)
            event_date = start_date + timedelta(days=random_days)
            
            # Choose general event
            event_description = random.choice(self.general_events)
            event_title = self._generate_event_title(event_description)
            
            # Generate a historical figure for some events
            figure = None
            if random.random() < 0.4:  # Reduced from 60% to 40%
                first_name, last_name = generate_npc_name()
                figure = f"{first_name} {last_name}"
                
                # Add figure to some descriptions
                if "began" in event_description or "established" in event_description:
                    event_description = f"{figure} initiated what became known as: {event_description}"
            
            # Add to bulk insert list
            history_events.append((
                None, event_title, event_description, figure, 
                event_date.strftime('%Y-%m-%d'), 'general'
            ))
            
            # Yield control every few events
            if i % 3 == 0:
                await asyncio.sleep(0)
        
        return history_events
    async def get_random_history_event(self, location_id: int = None) -> Dict:
        """Get a random historical event, optionally filtered by location"""
        if location_id:
            # Get event from specific location or general events
            event = self.db.execute_query(
                '''SELECT event_title, event_description, historical_figure, event_date, event_type
                   FROM galactic_history 
                   WHERE location_id = ? OR location_id IS NULL
                   ORDER BY RANDOM() LIMIT 1''',
                (location_id,),
                fetch='one'
            )
        else:
            # Get any historical event
            event = self.db.execute_query(
                '''SELECT event_title, event_description, historical_figure, event_date, event_type
                   FROM galactic_history 
                   ORDER BY RANDOM() LIMIT 1''',
                fetch='one'
            )
        
        if event:
            return {
                'title': event[0],
                'description': event[1],
                'figure': event[2],
                'date': event[3],
                'type': event[4]
            }
        
        return None