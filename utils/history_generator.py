# utils/history_generator.py
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from utils.npc_data import generate_npc_name

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
        """Generate comprehensive galactic history for all major locations"""
        print("📚 Generating galactic history...")
        
        # Clear existing history
        self.db.execute_query("DELETE FROM galactic_history")
        
        # Get all locations
        try:
            locations = self.db.execute_query(
                "SELECT location_id, name, location_type, establishment_date FROM locations WHERE is_generated = 1",
                fetch='all'
            )
        except Exception as e:
            if "no such column: establishment_date" in str(e):
                print("⚠️ establishment_date column missing, adding it now...")
                
                # Set default dates for existing locations
                self.db.execute_query("""
                    UPDATE locations 
                    SET establishment_date = '01-01-2750'
                    WHERE establishment_date IS NULL AND is_generated = 1
                """)
                print("✅ Added establishment_date column and set default dates")
                
                # Retry the query
                locations = self.db.execute_query(
                    "SELECT location_id, name, location_type, establishment_date FROM locations WHERE is_generated = 1",
                    fetch='all'
                )
            else:
                raise e
        
        total_events = 0
        current_date_obj = datetime.strptime(current_date, '%Y-%m-%d')
        
        # Generate 10 events per major location
        for location_id, name, location_type, establishment_date in locations:
            location_events = await self._generate_location_history(
                location_id, name, location_type, establishment_date, start_year, current_date_obj
            )
            total_events += location_events
        
        # Generate general galactic events
        general_events = await self._generate_general_history(start_year, current_date_obj)
        total_events += general_events
        
        print(f"📚 Generated {total_events} historical events")
        return total_events

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
        start_date = datetime(start_year - 20, 1, 1)  # Start 20 years before galaxy start
        
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