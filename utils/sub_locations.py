# utils/sub_locations.py
import discord
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from discord import app_commands
from discord.ext import commands
import random
from utils.leave_button import UniversalLeaveView

class SubLocationManager:
    """Manages sub-locations within main locations using Discord threads"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_threads = {}  # Track active sub-location threads
        
        # Sub-location types and their properties
        self.sub_location_types = {
            'bar': {
                'name': 'The Bar',
                'description': 'A dimly lit establishment where travelers gather to drink and exchange stories.',
                'icon': '🍺',
                'location_types': ['colony', 'space_station', 'outpost']
            },
            'medbay': {
                'name': 'Medical Bay',
                'description': 'Sterile medical facility offering treatment and health services.',
                'icon': '⚕️',
                'location_types': ['colony', 'space_station']
            },
            'engineering': {
                'name': 'Engineering Deck',
                'description': 'Technical area with ship repair and maintenance facilities.',
                'icon': '🔧',
                'location_types': ['space_station', 'outpost']
            },
            'security': {
                'name': 'Security Office',
                'description': 'Fortified area housing security personnel and holding cells.',
                'icon': '🛡️',
                'location_types': ['colony', 'space_station']
            },
            'observatory': {
                'name': 'Observatory',
                'description': 'High-tech facility for stellar observation and navigation data.',
                'icon': '🔭',
                'location_types': ['space_station', 'colony']
            },
            'lounge': {
                'name': 'Common Lounge',
                'description': 'Comfortable social area for relaxation and conversation.',
                'icon': '🛋️',
                'location_types': ['space_station', 'colony', 'outpost']
            },
            'market': {
                'name': 'Market District',
                'description': 'Bustling commercial area with shops and vendors.',
                'icon': '🛒',
                'location_types': ['colony', 'space_station']
            },
            'admin': {
                'name': 'Administration',
                'description': 'Bureaucratic offices handling official business and permits.',
                'icon': '📋',
                'location_types': ['colony', 'space_station']
            },
            'dormitory': {
                'name': 'Dormitory',
                'icon': '🛏️',
                'description': 'Living quarters for personnel.',
                'location_types': ['space_station', 'colony'],
                'min_wealth': 1
            },
            'research': {
                'name': 'Research Lab',
                'icon': '🔬',
                'description': 'Cutting-edge scientific workspaces.',
                'location_types': ['space_station', 'colony'],
                'min_wealth': 5
            },
            'hydroponics': {
                'name': 'Hydroponics Bay',
                'icon': '🌱',
                'description': 'Food production and botanical research.',
                'location_types': ['space_station', 'colony'],
                'min_wealth': 2
            },
            'recreation': {
                'name': 'Recreation Deck',
                'icon': '🎮',
                'description': 'Leisure and fitness facilities.',
                'location_types': ['space_station', 'colony'],
                'min_wealth': 3
            },
            'communications': {
                'name': 'Comm Center',
                'icon': '📡',
                'description': 'Long-range comms and sensor array.',
                'location_types': ['space_station', 'outpost'],
                'min_wealth': 1
            },
            'cafeteria': {
                'name': 'Cafeteria',
                'icon': '🍽️',
                'description': 'Food service and social hub.',
                'location_types': ['space_station', 'colony', 'outpost'],
                'min_wealth': 0
            },
            # Gate-specific sub-locations (truck stop/roadside stop themed)
            'gate_control': {
                'name': 'Gate Control Center',
                'description': 'Central operations hub managing corridor traffic and gate systems.',
                'icon': '🎛️',
                'location_types': ['gate']
            },
            'truck_stop': {
                'name': 'Traveler Services',
                'description': 'Rest area with amenities for long-haul corridor travelers.',
                'icon': '🛻',
                'location_types': ['gate']
            },
            'checkpoint': {
                'name': 'Security Checkpoint',
                'description': 'Mandatory screening facility for corridor transit authorization.',
                'icon': '🛂',
                'location_types': ['gate']
            },
            'fuel_depot': {
                'name': 'Fuel Depot',
                'description': 'High-capacity refueling station for corridor-traveling vessels.',
                'icon': '⛽',
                'location_types': ['gate']
            },
            'transit_lounge': {
                'name': 'Transit Lounge',
                'description': 'Comfortable waiting area for travelers between corridor connections.',
                'icon': '🛋️',
                'location_types': ['gate']
            },
            'gate_mechanic': {
                'name': 'Gate Mechanics Bay',
                'description': 'Specialized repair facility for pre-corridor system checks.',
                'icon': '⚙️',
                'location_types': ['gate']
            },
            # Derelict-themed sub-locations
            'abandoned_quarters': {
                'name': 'Abandoned Quarters',
                'description': 'Empty living spaces left behind by former inhabitants.',
                'icon': '🏚️',
                'location_types': ['colony', 'space_station', 'outpost'],
                'derelict_only': True
            },
            'emergency_shelter': {
                'name': 'Emergency Shelter',
                'description': 'Basic survival facility still functioning on backup power.',
                'icon': '🆘',
                'location_types': ['colony', 'space_station', 'outpost'],
                'derelict_only': True
            },
            'salvage_yard': {
                'name': 'Salvage Yard',
                'description': 'Area filled with scavenged equipment and spare parts.',
                'icon': '🔧',
                'location_types': ['colony', 'space_station', 'outpost'],
                'derelict_only': True
            },
            'power_core': {
                'name': 'Failing Power Core',
                'description': 'Critical systems barely maintaining life support functions.',
                'icon': '⚡',
                'location_types': ['space_station', 'outpost'],
                'derelict_only': True
            },
            'scavenger_den': {
                'name': 'Scavenger Den',
                'description': 'Makeshift living area used by those who remain.',
                'icon': '🦝',
                'location_types': ['colony', 'space_station', 'outpost'],
                'derelict_only': True
            },
            'historical_archive': {
                'name': 'Historical Archive',
                'description': 'Repository of galactic history and important records from across human space.',
                'icon': '📚',
                'location_types': ['colony', 'space_station'],
                'min_wealth': 4
            },
            # New Gate sub-locations
            'cargo_inspection': {
                'name': 'Cargo Inspection Bay',
                'description': 'Mandatory freight verification and customs scanning for corridor transit.',
                'icon': '⚖️',
                'location_types': ['gate']
            },
            'vessel_wash': {
                'name': 'Hull Cleaning Bay',
                'description': 'Automated decontamination facility removing space debris and radiation.',
                'icon': '🧽',
                'location_types': ['gate']
            },
            'pilot_quarters': {
                'name': 'Pilot Rest Quarters',
                'description': 'Basic sleeping pods for exhausted freight haulers and long-haul pilots.',
                'icon': '🛌',
                'location_types': ['gate']
            },
            'freight_depot': {
                'name': 'Freight Storage Depot',
                'description': 'Temporary cargo storage awaiting corridor transport connections.',
                'icon': '📦',
                'location_types': ['gate']
            },
            'component_shop': {
                'name': 'Ship Components Shop',
                'description': 'Essential spare parts and emergency supplies for corridor voyages.',
                'icon': '🔩',
                'location_types': ['gate']
            },
            'travel_cafe': {
                'name': 'Transit Café',
                'description': 'Quick-serve eatery offering hot meals and caffeine to weary travelers.',
                'icon': '☕',
                'location_types': ['gate']
            },
            'family_area': {
                'name': 'Family Rest Area',
                'description': 'Quiet space with amenities for traveling families and children.',
                'icon': '👶',
                'location_types': ['gate']
            },
            'passenger_pods': {
                'name': 'Sleep Pods',
                'description': 'Private rest capsules for passengers on extended corridor journeys.',
                'icon': '🛏️',
                'location_types': ['gate']
            },
            'entertainment_lounge': {
                'name': 'Entertainment Hub',
                'description': 'Holo-games, music, and virtual reality for passenger entertainment.',
                'icon': '🎮',
                'location_types': ['gate']
            },
            'travel_services': {
                'name': 'Travel Services Desk',
                'description': 'Booking assistance, route planning, and passenger coordination.',
                'icon': '🎫',
                'location_types': ['gate']
            },
            # New Outpost sub-locations
            'survey_lab': {
                'name': 'Survey Laboratory',
                'description': 'Geological analysis station for mineral and resource assessment.',
                'icon': '🔬',
                'location_types': ['outpost']
            },
            'core_storage': {
                'name': 'Core Sample Storage',
                'description': 'Climate-controlled vault storing planetary drilling samples.',
                'icon': '🗃️',
                'location_types': ['outpost']
            },
            'mining_control': {
                'name': 'Mining Operations Control',
                'description': 'Remote operation center for automated mining equipment.',
                'icon': '⛏️',
                'location_types': ['outpost']
            },
            'refinery_module': {
                'name': 'Mineral Processing Unit',
                'description': 'Compact refinery for basic ore processing and purification.',
                'icon': '🏭',
                'location_types': ['outpost']
            },
            'sensor_array': {
                'name': 'Sensor Array Control',
                'description': 'Command center for long-range detection and monitoring systems.',
                'icon': '📊',
                'location_types': ['outpost']
            },
            'beacon_control': {
                'name': 'Navigation Beacon Control',
                'description': 'Maintenance station for critical navigation infrastructure.',
                'icon': '🚨',
                'location_types': ['outpost']
            },
            'weather_station': {
                'name': 'Environmental Monitoring',
                'description': 'Atmospheric and radiation tracking for planetary conditions.',
                'icon': '🌡️',
                'location_types': ['outpost']
            },
            'supply_depot': {
                'name': 'Supply Cache',
                'description': 'Emergency provisions and equipment for extended operations.',
                'icon': '📦',
                'location_types': ['outpost']
            },
            'drone_bay': {
                'name': 'Drone Operations Bay',
                'description': 'Launch and maintenance facility for survey and work drones.',
                'icon': '🤖',
                'location_types': ['outpost']
            },
            'isolation_ward': {
                'name': 'Isolation Quarantine',
                'description': 'Medical containment for unknown pathogens or contamination.',
                'icon': '☣️',
                'location_types': ['outpost']
            },
            # New Space Station/Colony sub-locations
            'manufacturing_bay': {
                'name': 'Manufacturing Bay',
                'description': 'Automated production facility for ships, components, and equipment.',
                'icon': '🏭',
                'location_types': ['space_station', 'colony'],
                'min_wealth': 3
            },
            'fusion_reactor': {
                'name': 'Fusion Reactor Core',
                'description': 'Primary power generation facility maintaining station operations.',
                'icon': '⚛️',
                'location_types': ['space_station'],
                'min_wealth': 2
            },
            'cargo_bay': {
                'name': 'Primary Cargo Bay',
                'description': 'Massive storage facility for bulk goods and freight operations.',
                'icon': '📦',
                'location_types': ['space_station', 'colony']
            },
            'recycling_center': {
                'name': 'Recycling Center',
                'description': 'Waste processing and material reclamation facility.',
                'icon': '♻️',
                'location_types': ['space_station', 'colony']
            },
            'chapel': {
                'name': 'Interfaith Chapel',
                'description': 'Quiet spiritual space serving multiple religious traditions.',
                'icon': '🕊️',
                'location_types': ['space_station', 'colony'],
                'min_wealth': 2
            },
            'art_gallery': {
                'name': 'Cultural Gallery',
                'description': 'Exhibition space showcasing local and galactic artwork.',
                'icon': '🎨',
                'location_types': ['colony', 'space_station'],
                'min_wealth': 4
            },
            'theater': {
                'name': 'Performance Theater',
                'description': 'Entertainment venue for live shows and community events.',
                'icon': '🎭',
                'location_types': ['colony'],
                'min_wealth': 5
            },
            'plaza': {
                'name': 'Central Plaza',
                'description': 'Open gathering space for markets, events, and social interaction.',
                'icon': '🏛️',
                'location_types': ['colony'],
                'min_wealth': 3
            },
            'customs_office': {
                'name': 'Customs Office',
                'description': 'Import/export processing and trade regulation enforcement.',
                'icon': '🛃',
                'location_types': ['space_station'],
                'min_wealth': 2
            },
            'immigration_office': {
                'name': 'Immigration Services',
                'description': 'Residency permits, citizenship processing, and population registry.',
                'icon': '🎫',
                'location_types': ['colony'],
                'min_wealth': 3
            },
            'casino': {
                'name': 'Casino',
                'description': "Gambling establishment with slots, card games, and dice tables.",
                'icon': '🎰',
                'location_types': ['colony', 'space_station'],
                'min_wealth': 6
            },
        }
    
    async def get_available_sub_locations(self, parent_location_id: int) -> List[Dict]:
        """Return the persistent sub-locations for this parent location"""
        stored_subs = self.db.execute_query(
            '''SELECT sub_type, name, description, thread_id 
               FROM sub_locations 
               WHERE parent_location_id = ? AND is_active = 1''',
            (parent_location_id,),
            fetch='all'
        )
        
        available = []
        for sub_type, name, description, thread_id in stored_subs:
            thread_exists = bool(thread_id)
            icon = self.sub_location_types.get(sub_type, {}).get('icon', '🏢')
            
            available.append({
                'type': sub_type,
                'name': name,
                'icon': icon,
                'description': description,
                'exists': thread_exists
            })
        
        return available

    async def create_sub_location(self, guild: discord.Guild, location_channel: discord.TextChannel, 
                                 location_id: int, sub_type: str, user: discord.Member) -> Optional[discord.Thread]:
        """Create a new sub-location thread"""
        sub_data = self.sub_location_types.get(sub_type)
        if not sub_data:
            return None
        
        # Check if sub-location already exists
        existing = self.db.execute_query(
            "SELECT thread_id FROM sub_locations WHERE parent_location_id = ? AND sub_type = ? AND is_active = 1",
            (location_id, sub_type),
            fetch='one'
        )
        
        if existing and existing[0]:
            thread = guild.get_thread(existing[0])
            if thread:
                try:
                    await thread.add_user(user)
                except Exception as e:
                    print(f"Failed to add user to existing sub-location thread: {e}")
                return thread
            else:
                # Thread was deleted, clear the record
                self.db.execute_query(
                    "UPDATE sub_locations SET thread_id = NULL WHERE parent_location_id = ? AND sub_type = ?",
                    (location_id, sub_type)
                )
        
        try:
            # Create a public thread
            thread_name = f"{sub_data['icon']} {sub_data['name']}"
            thread = await location_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=60,  # 1 hour
                reason=f"Sub-location created by {user.name}"
            )
            
            # Update database with new thread ID
            self.db.execute_query(
                '''UPDATE sub_locations SET thread_id = ?
                   WHERE parent_location_id = ? AND sub_type = ?''',
                (thread.id, location_id, sub_type)
            )
            
            # Send welcome message
            await self._send_sub_location_welcome(thread, sub_data, location_id)
            
            # Add the user to the thread
            await thread.add_user(user)

            # Track for cleanup
            self.active_threads[thread.id] = {
                'location_id': location_id,
                'sub_type': sub_type,
                'created_at': datetime.now()
            }
            
            print(f"🏢 Created sub-location thread: {thread_name}")
            return thread
            
        except Exception as e:
            print(f"❌ Failed to create sub-location thread: {e}")
            return None
    
    async def _send_sub_location_welcome(self, thread: discord.Thread, sub_data: Dict, location_id: int):
        """Send welcome message to sub-location thread with interactive services"""
        location_info = self.db.execute_query(
            "SELECT name, location_type, wealth_level FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return
        
        location_name, location_type, wealth_level = location_info
        
        embed = discord.Embed(
            title=f"{sub_data['icon']} {sub_data['name']}",
            description=f"**{location_name}** - {sub_data['description']}",
            color=0x6a5acd
        )
        
        # Add sub-location specific features
        features = []
        
        if sub_data['name'] == 'The Bar':
            features.extend([
                "🍺 Order drinks and socialize",
                "🗣️ Listen to local gossip and rumors",
                "🎲 Play games with other travelers",
                "💬 Share stories and experiences"
            ])
        elif sub_data['name'] == 'Medical Bay':
            features.extend([
                "⚕️ Receive medical treatment",
                "💊 Purchase medical supplies",
                "🩺 Health checkups and diagnostics",
                "🧬 Advanced medical procedures"
            ])
        elif sub_data['name'] == 'Engineering Deck':
            features.extend([
                "🔧 Ship repairs and maintenance",
                "⚙️ Technical consultations",
                "🛠️ Equipment modifications",
                "📊 System diagnostics"
            ])
        elif sub_data['name'] == 'Security Office':
            features.extend([
                "🛡️ Report incidents and crimes",
                "📋 Official permits and licenses",
                "👮 Law enforcement services",
                "🔒 Secure communications"
            ])
        elif sub_data['name'] == 'Observatory':
            features.extend([
                "🔭 Stellar observation",
                "🗺️ Navigation charts",
                "📡 Deep space monitoring",
                "🌌 Astronomical research"
            ])
        elif sub_data['name'] == 'Common Lounge':
            features.extend([
                "🛋️ Relaxation and rest",
                "📺 News and entertainment",
                "☕ Refreshments available",
                "🤝 Social gatherings"
            ])
        elif sub_data['name'] == 'Market District':
            features.extend([
                "🛒 Shopping and commerce",
                "💰 Buy and sell goods",
                "📈 Price information",
                "🏪 Specialty vendors"
            ])
        elif sub_data['name'] == 'Administration':
            features.extend([
                "📋 Official documentation",
                "🗂️ Record keeping",
                "📝 Permit applications",
                "🏛️ Government services"
            ])
        elif sub_data['name'] == 'Historical Archive':
            features.extend([
                "📚 Browse historical records and archives",
                "📖 Research galactic history and events", 
                "👤 Learn about notable historical figures",
                "📝 Access official records and documentation"
            ])
        if features:
            embed.add_field(
                name="Available Services",
                value="\n".join(features),
                inline=False
            )
        
        # Add atmosphere description based on wealth level
        if wealth_level >= 8:
            atmosphere = "Pristine and well-maintained with premium amenities."
        elif wealth_level >= 5:
            atmosphere = "Clean and functional with standard facilities."
        elif wealth_level >= 3:
            atmosphere = "Basic but serviceable with essential amenities."
        else:
            atmosphere = "Worn and weathered but still operational."
        
        embed.add_field(
            name="🏢 Atmosphere",
            value=atmosphere,
            inline=False
        )
        
        embed.add_field(
            name="🎮 Interactive Services",
            value="Use the buttons below to interact with the available services in this area.",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Thread Info",
            value="This thread will auto-archive after 1 hour of inactivity. Use it to roleplay and interact with this specific area.\n Use `/area leave` or the 'Leave' button to leave this area.",
            inline=False
        )
        
        # Determine sub_type for view creation
        sub_type = None
        
        # First try exact match
        for key, props in self.sub_location_types.items():
            if props['name'] == sub_data['name']:
                sub_type = key
                break
        
        # If no exact match, try case-insensitive match
        if not sub_type:
            for key, props in self.sub_location_types.items():
                if props['name'].lower() == sub_data['name'].lower():
                    sub_type = key
                    break
        
        # If still no match, try using the sub_type from database directly
        if not sub_type:
            # Get sub_type from database
            stored_sub_type = self.db.execute_query(
                "SELECT sub_type FROM sub_locations WHERE sub_location_id = ?",
                (sub_data['sub_location_id'],),
                fetch='one'
            )
            if stored_sub_type:
                sub_type = stored_sub_type[0]
                print(f"🔍 Retrieved sub_type '{sub_type}' from database for {sub_data['name']}")
        
        try:
            # Send initial message
            await thread.send(embed=embed)
            
            # Send buttons in a separate message
            if sub_type:
                view = SubLocationServiceView(sub_type, location_id, self.bot)
                
                # Add universal leave button to the view
                leave_view = UniversalLeaveView(self.bot)
                # Transfer the leave button to the main view
                for item in leave_view.children:
                    view.add_item(item)
                
                if len(view.children) > 0:  # Check if buttons were actually added
                    button_embed = discord.Embed(
                        title="🔧 Available Services",
                        description="Click the buttons below to use the services available in this area:",
                        color=0x00ff88
                    )
                    await thread.send(embed=button_embed, view=view)
                    print(f"🏢 Sub-location welcome sent with {len(view.children)} buttons for {sub_data['name']} (type: {sub_type})")
                else:
                    print(f"⚠️ No buttons were added for sub_type '{sub_type}'")
            else:
                # Even if no sub_type, still add the leave button
                leave_view = UniversalLeaveView(self.bot)
                button_embed = discord.Embed(
                    title="🔧 Available Services",
                    description="Click the button below to leave this area:",
                    color=0x00ff88
                )
                await thread.send(embed=button_embed, view=leave_view)
                print(f"⚠️ No sub_type found for {sub_data['name']}, but leave button added")
                
        except Exception as e:
            print(f"❌ Failed to send sub-location welcome: {e}")
            import traceback
            traceback.print_exc()
    
    async def cleanup_inactive_threads(self):
        """Clean up inactive sub-location threads"""
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        inactive_threads = self.db.execute_query(
            '''SELECT sl.sub_location_id, sl.thread_id, sl.parent_location_id, sl.sub_type
               FROM sub_locations sl
               WHERE sl.is_active = 1 AND sl.last_active < ?''',
            (cutoff_time,),
            fetch='all'
        )
        
        for sub_id, thread_id, location_id, sub_type in inactive_threads:
            self.db.execute_query(
                "UPDATE sub_locations SET is_active = 0 WHERE sub_location_id = ?",
                (sub_id,)
            )
            
            if thread_id in self.active_threads:
                del self.active_threads[thread_id]
    
    async def get_sub_location_occupants(self, sub_location_id: int) -> List[int]:
        """Get list of user IDs currently in a sub-location"""
        # Placeholder - in a real implementation, track active users in threads
        return []

    async def generate_persistent_sub_locations(self, parent_location_id: int, location_type: str, wealth_level: int, is_derelict: bool = False) -> int:
        """Generate and store persistent sub-locations for a location during galaxy generation"""
        # Clear any existing sub-locations
        self.db.execute_query(
            "DELETE FROM sub_locations WHERE parent_location_id = ?",
            (parent_location_id,)
        )
        
        # Handle derelict locations
        if is_derelict:
            candidates = []
            for key, props in self.sub_location_types.items():
                if props.get('derelict_only', False) and location_type in props['location_types']:
                    candidates.append((key, props))
            
            if not candidates:
                return 0
            
            max_count = min(len(candidates), random.randint(0, 2))
            if max_count == 0:
                return 0
            
            selected = random.sample(candidates, max_count)
            
            created_count = 0
            for sub_type, props in selected:
                self.db.execute_query(
                    '''INSERT INTO sub_locations 
                       (parent_location_id, name, sub_type, description, is_active)
                       VALUES (?, ?, ?, ?, 1)''',
                    (parent_location_id, props['name'], sub_type, props['description'])
                )
                created_count += 1
            
            return created_count
        
        # Normal location handling
        candidates = []
        for key, props in self.sub_location_types.items():
            if props.get('derelict_only', False):
                continue
            if location_type not in props['location_types']:
                continue
            if props.get('min_wealth', 0) > wealth_level:
                continue
            candidates.append((key, props))
        
        if not candidates:
            return 0
        
        # Determine how many sub-locations this location should have
        if location_type == 'space_station':
            base_count = 3 if wealth_level >= 7 else 2 if wealth_level >= 4 else 1
            max_count = min(len(candidates), base_count + random.randint(0, 2))
        elif location_type == 'colony':
            base_count = 4 if wealth_level >= 6 else 3 if wealth_level >= 3 else 2
            max_count = min(len(candidates), base_count + random.randint(0, 1))
        elif location_type == 'outpost':
            max_count = min(len(candidates), 
                random.randint(2, 3) if wealth_level >= 8 else
                2 if wealth_level >= 4 else 
                random.randint(0, 1))
        else:  # gate
            base_count = 3 if wealth_level >= 7 else 2 if wealth_level >= 3 else 2
            max_count = min(len(candidates), base_count + random.randint(0, 2))
        
        if max_count == 0:
            return 0
        
        selected = random.sample(candidates, max_count)
        
        created_count = 0
        for sub_type, props in selected:
            self.db.execute_query(
                '''INSERT INTO sub_locations 
                   (parent_location_id, name, sub_type, description, is_active)
                   VALUES (?, ?, ?, ?, 1)''',
                (parent_location_id, props['name'], sub_type, props['description'])
            )
            created_count += 1
        
        return created_count
    async def get_persistent_sub_locations_data(self, parent_location_id: int, location_type: str, wealth_level: int, is_derelict: bool = False) -> List[Tuple]:
        """Return persistent sub-location data as tuples for bulk insertion during galaxy generation"""
        
        sub_locations_data = []
        
        # Handle derelict locations
        if is_derelict:
            candidates = []
            for key, props in self.sub_location_types.items():
                if props.get('derelict_only', False) and location_type in props['location_types']:
                    candidates.append((key, props))
            
            if not candidates:
                return sub_locations_data
            
            max_count = min(len(candidates), random.randint(0, 2))
            if max_count == 0:
                return sub_locations_data
            
            selected = random.sample(candidates, max_count)
            
            for sub_type, props in selected:
                sub_locations_data.append((
                    parent_location_id,
                    props['name'],
                    sub_type,
                    props['description']
                ))
            
            return sub_locations_data
        
        # Normal location handling
        candidates = []
        for key, props in self.sub_location_types.items():
            if props.get('derelict_only', False):
                continue
            if location_type not in props['location_types']:
                continue
            if props.get('min_wealth', 0) > wealth_level:
                continue
            candidates.append((key, props))
        
        if not candidates:
            return sub_locations_data
        
        # Determine how many sub-locations this location should have
        if location_type == 'space_station':
            base_count = 3 if wealth_level >= 7 else 2 if wealth_level >= 4 else 1
            max_count = min(len(candidates), base_count + random.randint(0, 2))
        elif location_type == 'colony':
            base_count = 4 if wealth_level >= 6 else 3 if wealth_level >= 3 else 2
            max_count = min(len(candidates), base_count + random.randint(0, 1))
        elif location_type == 'outpost':
            max_count = min(len(candidates), 
                random.randint(2, 3) if wealth_level >= 8 else
                2 if wealth_level >= 4 else 
                random.randint(0, 1))
        else:  # gate
            base_count = 3 if wealth_level >= 7 else 2 if wealth_level >= 3 else 2
            max_count = min(len(candidates), base_count + random.randint(0, 2))
        
        if max_count == 0:
            return sub_locations_data
        
        selected = random.sample(candidates, max_count)
        
        for sub_type, props in selected:
            sub_locations_data.append((
                parent_location_id,
                props['name'],
                sub_type,
                props['description']
            ))
        
        return sub_locations_data

class SubLocationServiceView(discord.ui.View):
    """Interactive view for sub-location services"""
    
    def __init__(self, sub_type: str, location_id: int, bot):
        super().__init__(timeout=1800)  # 30 minute timeout
        self.sub_type = sub_type
        self.location_id = location_id
        self.bot = bot
        self.db = bot.db
        
        # Add buttons based on sub-location type
        self._add_service_buttons()
        print(f"🔧 Created SubLocationServiceView for {sub_type} with {len(self.children)} buttons")
        
    def _add_service_buttons(self):
        """Add service buttons based on sub-location type"""
        self.clear_items()
        
        if self.sub_type == 'bar':
            self.add_item(SubLocationButton(
                label="Order Drink", 
                emoji="🍺", 
                style=discord.ButtonStyle.primary,
                service_type="order_drink"
            ))
            self.add_item(SubLocationButton(
                label="Listen to Gossip", 
                emoji="👂", 
                style=discord.ButtonStyle.secondary,
                service_type="listen_gossip"
            ))
            self.add_item(SubLocationButton(
                label="Play Cards", 
                emoji="🎲", 
                style=discord.ButtonStyle.secondary,
                service_type="play_cards"
            ))
            
        elif self.sub_type == 'medbay':
            self.add_item(SubLocationButton(
                label="Get Treatment", 
                emoji="⚕️", 
                style=discord.ButtonStyle.success,
                service_type="medical_treatment"
            ))
            self.add_item(SubLocationButton(
                label="Buy Medical Supplies", 
                emoji="💊", 
                style=discord.ButtonStyle.primary,
                service_type="buy_medical"
            ))
            self.add_item(SubLocationButton(
                label="Health Checkup", 
                emoji="🩺", 
                style=discord.ButtonStyle.secondary,
                service_type="health_checkup"
            ))
            
        elif self.sub_type == 'engineering':
            self.add_item(SubLocationButton(
                label="Repair Ship", 
                emoji="🔧", 
                style=discord.ButtonStyle.success,
                service_type="repair_ship"
            ))
            self.add_item(SubLocationButton(
                label="Ship Diagnostics", 
                emoji="📊", 
                style=discord.ButtonStyle.secondary,
                service_type="ship_diagnostics"
            ))
            self.add_item(SubLocationButton(
                label="Equipment Mods", 
                emoji="⚙️", 
                style=discord.ButtonStyle.primary,
                service_type="equipment_mods"
            ))
            
        elif self.sub_type == 'observatory':
            self.add_item(SubLocationButton(
                label="Stellar Charts", 
                emoji="🗺️", 
                style=discord.ButtonStyle.success,
                service_type="stellar_charts"
            ))
            self.add_item(SubLocationButton(
                label="Deep Space Scan", 
                emoji="📡", 
                style=discord.ButtonStyle.secondary,
                service_type="deep_space_scan"
            ))
            self.add_item(SubLocationButton(
                label="Navigation Data", 
                emoji="🧭", 
                style=discord.ButtonStyle.primary,
                service_type="navigation_data"
            ))
            
        elif self.sub_type == 'lounge':
            self.add_item(SubLocationButton(
                label="Relax", 
                emoji="🛋️", 
                style=discord.ButtonStyle.secondary,
                service_type="relax"
            ))
            self.add_item(SubLocationButton(
                label="Watch News", 
                emoji="📺", 
                style=discord.ButtonStyle.secondary,
                service_type="watch_news"
            ))
            self.add_item(SubLocationButton(
                label="Get Refreshments", 
                emoji="☕", 
                style=discord.ButtonStyle.primary,
                service_type="refreshments"
            ))
            
        elif self.sub_type == 'market':
            self.add_item(SubLocationButton(
                label="Browse Shops", 
                emoji="🛒", 
                style=discord.ButtonStyle.primary,
                service_type="browse_shops"
            ))
            self.add_item(SubLocationButton(
                label="Check Prices", 
                emoji="📈", 
                style=discord.ButtonStyle.secondary,
                service_type="check_prices"
            ))
            self.add_item(SubLocationButton(
                label="Specialty Vendors", 
                emoji="🏪", 
                style=discord.ButtonStyle.primary,
                service_type="specialty_vendors"
            ))
            
        elif self.sub_type == 'admin':
            self.add_item(SubLocationButton(
                label="Change Name", 
                emoji="👤", 
                style=discord.ButtonStyle.primary,
                service_type="change_name"
            ))
            self.add_item(SubLocationButton(
                label="Change D.O.B.", 
                emoji="🎂", 
                style=discord.ButtonStyle.primary,
                service_type="change_dob"
            ))
            self.add_item(SubLocationButton(
                label="Change Description", 
                emoji="📝", 
                style=discord.ButtonStyle.secondary,
                service_type="change_description"
            ))
            self.add_item(SubLocationButton(
                label="Change Bio", 
                emoji="📖", 
                style=discord.ButtonStyle.secondary,
                service_type="change_bio"
            ))
            self.add_item(SubLocationButton(
                label="Apply for Permits", 
                emoji="📜", 
                style=discord.ButtonStyle.secondary,
                service_type="apply_permits"
            ))
            self.add_item(SubLocationButton(
                label="Take ID Photo", 
                emoji="📸", 
                style=discord.ButtonStyle.primary,
                service_type="take_id_photo"
            ))
            
        elif self.sub_type == 'security':
            self.add_item(SubLocationButton(
                label="Report Incident", 
                emoji="🚨", 
                style=discord.ButtonStyle.danger,
                service_type="report_incident"
            ))
            self.add_item(SubLocationButton(
                label="Security Consultation", 
                emoji="🛡️", 
                style=discord.ButtonStyle.secondary,
                service_type="security_consult"
            ))
            self.add_item(SubLocationButton(
                label="Information Desk", 
                emoji="ℹ️", 
                style=discord.ButtonStyle.primary,
                service_type="info_desk"
            ))
            self.add_item(SubLocationButton(
                label="File Complaint", 
                emoji="📝", 
                style=discord.ButtonStyle.secondary,
                service_type="file_complaint"
            ))

        elif self.sub_type == 'gate_control':
            self.add_item(SubLocationButton(
                label="Check Traffic", 
                emoji="📊", 
                style=discord.ButtonStyle.secondary,
                service_type="check_traffic"
            ))
            self.add_item(SubLocationButton(
                label="Corridor Status", 
                emoji="🌌", 
                style=discord.ButtonStyle.primary,
                service_type="corridor_status"
            ))
            
        elif self.sub_type == 'truck_stop':
            self.add_item(SubLocationButton(
                label="Rest & Recuperate", 
                emoji="😴", 
                style=discord.ButtonStyle.success,
                service_type="rest_recuperate"
            ))
            self.add_item(SubLocationButton(
                label="Traveler Info", 
                emoji="🗺️", 
                style=discord.ButtonStyle.secondary,
                service_type="travel_info"
            ))
            
        elif self.sub_type == 'checkpoint':
            self.add_item(SubLocationButton(
                label="Security Scan", 
                emoji="🔍", 
                style=discord.ButtonStyle.primary,
                service_type="security_scan"
            ))
            self.add_item(SubLocationButton(
                label="Transit Papers", 
                emoji="📄", 
                style=discord.ButtonStyle.secondary,
                service_type="transit_papers"
            ))
            
        elif self.sub_type == 'fuel_depot':
            self.add_item(SubLocationButton(
                label="Priority Refuel", 
                emoji="⛽", 
                style=discord.ButtonStyle.success,
                service_type="priority_refuel"
            ))
            self.add_item(SubLocationButton(
                label="Fuel Quality Check", 
                emoji="🧪", 
                style=discord.ButtonStyle.secondary,
                service_type="fuel_quality"
            ))
            
        elif self.sub_type == 'gate_mechanic':
            self.add_item(SubLocationButton(
                label="Pre-Transit Check", 
                emoji="🔧", 
                style=discord.ButtonStyle.primary,
                service_type="pre_transit_check"
            ))
            self.add_item(SubLocationButton(
                label="Emergency Repairs", 
                emoji="🚨", 
                style=discord.ButtonStyle.danger,
                service_type="emergency_repairs"
            ))
            
        elif self.sub_type == 'dormitory':
            self.add_item(SubLocationButton(
                label="Rest in Quarters", 
                emoji="🛏️", 
                style=discord.ButtonStyle.success,
                service_type="rest_quarters"
            ))
            self.add_item(SubLocationButton(
                label="Use Facilities", 
                emoji="🚿", 
                style=discord.ButtonStyle.secondary,
                service_type="use_facilities"
            ))
            self.add_item(SubLocationButton(
                label="Check Amenities", 
                emoji="🏠", 
                style=discord.ButtonStyle.secondary,
                service_type="check_amenities"
            ))
            
        elif self.sub_type == 'research':
            self.add_item(SubLocationButton(
                label="Browse Research", 
                emoji="🔬", 
                style=discord.ButtonStyle.primary,
                service_type="browse_research"
            ))
            self.add_item(SubLocationButton(
                label="Use Equipment", 
                emoji="⚗️", 
                style=discord.ButtonStyle.secondary,
                service_type="use_equipment"
            ))
            self.add_item(SubLocationButton(
                label="Review Data", 
                emoji="📊", 
                style=discord.ButtonStyle.secondary,
                service_type="review_data"
            ))
            self.add_item(SubLocationButton(
                label="Collaborate", 
                emoji="🤝", 
                style=discord.ButtonStyle.primary,
                service_type="collaborate"
            ))
            
        elif self.sub_type == 'hydroponics':
            self.add_item(SubLocationButton(
                label="Tour Gardens", 
                emoji="🌱", 
                style=discord.ButtonStyle.success,
                service_type="tour_gardens"
            ))
            self.add_item(SubLocationButton(
                label="Market Information", 
                emoji="📊", 
                style=discord.ButtonStyle.primary,
                service_type="market_info"
            ))
            self.add_item(SubLocationButton(
                label="Learn Techniques", 
                emoji="📚", 
                style=discord.ButtonStyle.secondary,
                service_type="learn_techniques"
            ))
            
        elif self.sub_type == 'recreation':
            self.add_item(SubLocationButton(
                label="Play Games", 
                emoji="🎮", 
                style=discord.ButtonStyle.primary,
                service_type="play_games"
            ))
            self.add_item(SubLocationButton(
                label="Exercise", 
                emoji="🏋️", 
                style=discord.ButtonStyle.success,
                service_type="exercise"
            ))
            self.add_item(SubLocationButton(
                label="Join Activity", 
                emoji="🏓", 
                style=discord.ButtonStyle.secondary,
                service_type="join_activity"
            ))
            self.add_item(SubLocationButton(
                label="Relax & Unwind", 
                emoji="😌", 
                style=discord.ButtonStyle.secondary,
                service_type="relax_unwind"
            ))
            
        elif self.sub_type == 'communications':
            self.add_item(SubLocationButton(
                label="Send Message (10-25 credits)", 
                emoji="📡", 
                style=discord.ButtonStyle.primary,
                service_type="send_message"
            ))
            self.add_item(SubLocationButton(
                label="Check Signals", 
                emoji="📻", 
                style=discord.ButtonStyle.secondary,
                service_type="check_signals"
            ))
            self.add_item(SubLocationButton(
                label="Monitor Channels", 
                emoji="🎧", 
                style=discord.ButtonStyle.secondary,
                service_type="monitor_channels"
            ))
            
        elif self.sub_type == 'cafeteria':
            self.add_item(SubLocationButton(
                label="Order Meal", 
                emoji="🍽️", 
                style=discord.ButtonStyle.primary,
                service_type="order_meal"
            ))
            self.add_item(SubLocationButton(
                label="Check Menu", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="check_menu"
            ))
            self.add_item(SubLocationButton(
                label="Socialize", 
                emoji="👥", 
                style=discord.ButtonStyle.secondary,
                service_type="socialize"
            ))
            
        elif self.sub_type == 'transit_lounge':
            self.add_item(SubLocationButton(
                label="Wait Comfortably", 
                emoji="🛋️", 
                style=discord.ButtonStyle.success,
                service_type="wait_comfortably"
            ))
            self.add_item(SubLocationButton(
                label="Check Schedules", 
                emoji="⏱️", 
                style=discord.ButtonStyle.secondary,
                service_type="check_schedules"
            ))
            self.add_item(SubLocationButton(
                label="Get Travel Info", 
                emoji="🗺️", 
                style=discord.ButtonStyle.primary,
                service_type="travel_info"
            ))
        
        elif self.sub_type == 'historical_archive':
            self.add_item(SubLocationButton(
                label="Browse Archives", 
                emoji="📚", 
                style=discord.ButtonStyle.primary,
                service_type="browse_archives"
            ))
            self.add_item(SubLocationButton(
                label="Research Records", 
                emoji="📖", 
                style=discord.ButtonStyle.secondary,
                service_type="research_records"
            ))
            self.add_item(SubLocationButton(
                label="Study Historical Figures", 
                emoji="👤", 
                style=discord.ButtonStyle.secondary,
                service_type="study_figures"
            ))  
        # Outpost sub-location services
        elif self.sub_type == 'survey_lab':
            self.add_item(SubLocationButton(
                label="Review Samples", 
                emoji="🔬", 
                style=discord.ButtonStyle.primary,
                service_type="review_samples"
            ))
            self.add_item(SubLocationButton(
                label="Data Analysis", 
                emoji="📊", 
                style=discord.ButtonStyle.secondary,
                service_type="data_analysis"
            ))
            self.add_item(SubLocationButton(
                label="Equipment Check", 
                emoji="⚗️", 
                style=discord.ButtonStyle.secondary,
                service_type="equipment_check"
            ))
        elif self.sub_type == 'core_storage':
            self.add_item(SubLocationButton(
                label="Sample Catalog", 
                emoji="📂", 
                style=discord.ButtonStyle.primary,
                service_type="sample_catalog"
            ))
            self.add_item(SubLocationButton(
                label="Access Records", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="access_records"
            ))
            self.add_item(SubLocationButton(
                label="Environmental Check", 
                emoji="🌡️", 
                style=discord.ButtonStyle.secondary,
                service_type="environmental_check"
            ))
        elif self.sub_type == 'mining_control':
            self.add_item(SubLocationButton(
                label="Monitor Operations", 
                emoji="📊", 
                style=discord.ButtonStyle.primary,
                service_type="monitor_operations"
            ))
            self.add_item(SubLocationButton(
                label="Equipment Status", 
                emoji="⚙️", 
                style=discord.ButtonStyle.secondary,
                service_type="equipment_status"
            ))
            self.add_item(SubLocationButton(
                label="Production Reports", 
                emoji="📈", 
                style=discord.ButtonStyle.secondary,
                service_type="production_reports"
            ))
        elif self.sub_type == 'refinery_module':
            self.add_item(SubLocationButton(
                label="Check Processing", 
                emoji="🏭", 
                style=discord.ButtonStyle.primary,
                service_type="check_processing"
            ))
            self.add_item(SubLocationButton(
                label="Quality Control", 
                emoji="✅", 
                style=discord.ButtonStyle.success,
                service_type="quality_control"
            ))
            self.add_item(SubLocationButton(
                label="Output Status", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="output_status"
            ))
        elif self.sub_type == 'sensor_array':
            self.add_item(SubLocationButton(
                label="Scan Readings", 
                emoji="📡", 
                style=discord.ButtonStyle.primary,
                service_type="scan_readings"
            ))
            self.add_item(SubLocationButton(
                label="Calibrate Sensors", 
                emoji="🎛️", 
                style=discord.ButtonStyle.secondary,
                service_type="calibrate_sensors"
            ))
            self.add_item(SubLocationButton(
                label="Alert Status", 
                emoji="🚨", 
                style=discord.ButtonStyle.danger,
                service_type="alert_status"
            ))
        elif self.sub_type == 'beacon_control':
            self.add_item(SubLocationButton(
                label="Navigation Status", 
                emoji="🚨", 
                style=discord.ButtonStyle.danger,
                service_type="navigation_status"
            ))
            self.add_item(SubLocationButton(
                label="Signal Strength", 
                emoji="📶", 
                style=discord.ButtonStyle.secondary,
                service_type="signal_strength"
            ))
            self.add_item(SubLocationButton(
                label="Maintenance Log", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="maintenance_log"
            ))
        elif self.sub_type == 'weather_station':
            self.add_item(SubLocationButton(
                label="Weather Data", 
                emoji="🌡️", 
                style=discord.ButtonStyle.primary,
                service_type="weather_data"
            ))
            self.add_item(SubLocationButton(
                label="Storm Tracking", 
                emoji="⛈️", 
                style=discord.ButtonStyle.secondary,
                service_type="storm_tracking"
            ))
            self.add_item(SubLocationButton(
                label="Atmospheric Report", 
                emoji="📊", 
                style=discord.ButtonStyle.secondary,
                service_type="atmospheric_report"
            ))
        elif self.sub_type == 'supply_depot':
            self.add_item(SubLocationButton(
                label="Inventory Check", 
                emoji="📦", 
                style=discord.ButtonStyle.primary,
                service_type="inventory_check"
            ))
            self.add_item(SubLocationButton(
                label="Request Supplies", 
                emoji="📝", 
                style=discord.ButtonStyle.secondary,
                service_type="request_supplies"
            ))
            self.add_item(SubLocationButton(
                label="Emergency Cache", 
                emoji="🆘", 
                style=discord.ButtonStyle.danger,
                service_type="emergency_cache"
            ))
        elif self.sub_type == 'drone_bay':
            self.add_item(SubLocationButton(
                label="Launch Drone", 
                emoji="🚁", 
                style=discord.ButtonStyle.primary,
                service_type="launch_drone"
            ))
            self.add_item(SubLocationButton(
                label="Maintenance Check", 
                emoji="🔧", 
                style=discord.ButtonStyle.secondary,
                service_type="maintenance_check"
            ))
            self.add_item(SubLocationButton(
                label="Mission Planning", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="mission_planning"
            ))
        elif self.sub_type == 'isolation_ward':
            self.add_item(SubLocationButton(
                label="Containment Status", 
                emoji="☣️", 
                style=discord.ButtonStyle.danger,
                service_type="containment_status"
            ))
            self.add_item(SubLocationButton(
                label="Decontamination", 
                emoji="🧼", 
                style=discord.ButtonStyle.success,
                service_type="decontamination"
            ))
            self.add_item(SubLocationButton(
                label="Emergency Protocol", 
                emoji="🚨", 
                style=discord.ButtonStyle.danger,
                service_type="emergency_protocol"
            ))
        elif self.sub_type == 'manufacturing_bay':
            self.add_item(SubLocationButton(
                label="Production Status", 
                emoji="🏭", 
                style=discord.ButtonStyle.primary,
                service_type="production_status"
            ))
            self.add_item(SubLocationButton(
                label="Quality Control", 
                emoji="✅", 
                style=discord.ButtonStyle.success,
                service_type="quality_control"
            ))
            self.add_item(SubLocationButton(
                label="Order Processing", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="order_processing"
            ))
        elif self.sub_type == 'fusion_reactor':
            self.add_item(SubLocationButton(
                label="Reactor Status", 
                emoji="⚛️", 
                style=discord.ButtonStyle.primary,
                service_type="reactor_status"
            ))
            self.add_item(SubLocationButton(
                label="Safety Check", 
                emoji="🛡️", 
                style=discord.ButtonStyle.success,
                service_type="safety_check"
            ))
            self.add_item(SubLocationButton(
                label="Power Output", 
                emoji="⚡", 
                style=discord.ButtonStyle.secondary,
                service_type="power_output"
            ))
        elif self.sub_type == 'cargo_bay':
            self.add_item(SubLocationButton(
                label="Inventory Check", 
                emoji="📦", 
                style=discord.ButtonStyle.primary,
                service_type="inventory_check"
            ))
            self.add_item(SubLocationButton(
                label="Loading Schedule", 
                emoji="🚚", 
                style=discord.ButtonStyle.secondary,
                service_type="loading_schedule"
            ))
            self.add_item(SubLocationButton(
                label="Storage Request", 
                emoji="📝", 
                style=discord.ButtonStyle.secondary,
                service_type="storage_request"
            ))
        elif self.sub_type == 'recycling_center':
            self.add_item(SubLocationButton(
                label="Waste Processing", 
                emoji="♻️", 
                style=discord.ButtonStyle.success,
                service_type="waste_processing"
            ))
            self.add_item(SubLocationButton(
                label="Material Status", 
                emoji="📊", 
                style=discord.ButtonStyle.secondary,
                service_type="material_status"
            ))
            self.add_item(SubLocationButton(
                label="Drop Off Items", 
                emoji="🗂️", 
                style=discord.ButtonStyle.primary,
                service_type="drop_off_items"
            ))
        elif self.sub_type == 'chapel':
            self.add_item(SubLocationButton(
                label="Quiet Reflection", 
                emoji="🕊️", 
                style=discord.ButtonStyle.secondary,
                service_type="quiet_reflection"
            ))
            self.add_item(SubLocationButton(
                label="Community Service", 
                emoji="🤝", 
                style=discord.ButtonStyle.success,
                service_type="community_service"
            ))
            self.add_item(SubLocationButton(
                label="Spiritual Guidance", 
                emoji="📿", 
                style=discord.ButtonStyle.primary,
                service_type="spiritual_guidance"
            ))
        elif self.sub_type == 'art_gallery':
            self.add_item(SubLocationButton(
                label="View Exhibitions", 
                emoji="🎨", 
                style=discord.ButtonStyle.primary,
                service_type="view_exhibitions"
            ))
            self.add_item(SubLocationButton(
                label="Artist Information", 
                emoji="👨‍🎨", 
                style=discord.ButtonStyle.secondary,
                service_type="artist_information"
            ))
            self.add_item(SubLocationButton(
                label="Cultural Events", 
                emoji="🎭", 
                style=discord.ButtonStyle.success,
                service_type="cultural_events"
            ))
        elif self.sub_type == 'theater':
            self.add_item(SubLocationButton(
                label="Check Shows", 
                emoji="🎭", 
                style=discord.ButtonStyle.primary,
                service_type="check_shows"
            ))
            self.add_item(SubLocationButton(
                label="Book Tickets", 
                emoji="🎫", 
                style=discord.ButtonStyle.success,
                service_type="book_tickets"
            ))
            self.add_item(SubLocationButton(
                label="Performance Schedule", 
                emoji="📅", 
                style=discord.ButtonStyle.secondary,
                service_type="performance_schedule"
            ))
        elif self.sub_type == 'plaza':
            self.add_item(SubLocationButton(
                label="Browse Market", 
                emoji="🏛️", 
                style=discord.ButtonStyle.primary,
                service_type="browse_market"
            ))
            self.add_item(SubLocationButton(
                label="Meet People", 
                emoji="👥", 
                style=discord.ButtonStyle.secondary,
                service_type="meet_people"
            ))
            self.add_item(SubLocationButton(
                label="Attend Events", 
                emoji="🎉", 
                style=discord.ButtonStyle.success,
                service_type="attend_events"
            ))
        elif self.sub_type == 'customs_office':
            self.add_item(SubLocationButton(
                label="Declare Goods", 
                emoji="📋", 
                style=discord.ButtonStyle.primary,
                service_type="declare_goods"
            ))
            self.add_item(SubLocationButton(
                label="Tax Information", 
                emoji="💰", 
                style=discord.ButtonStyle.secondary,
                service_type="tax_information"
            ))
            self.add_item(SubLocationButton(
                label="Trade Permits", 
                emoji="📜", 
                style=discord.ButtonStyle.success,
                service_type="trade_permits"
            ))
        elif self.sub_type == 'immigration_office':
            self.add_item(SubLocationButton(
                label="Residency Info", 
                emoji="🎫", 
                style=discord.ButtonStyle.primary,
                service_type="residency_info"
            ))
            self.add_item(SubLocationButton(
                label="Citizenship Process", 
                emoji="📄", 
                style=discord.ButtonStyle.secondary,
                service_type="citizenship_process"
            ))
            self.add_item(SubLocationButton(
                label="Documentation", 
                emoji="📋", 
                style=discord.ButtonStyle.success,
                service_type="documentation"
            ))
            
        elif self.sub_type == 'cargo_inspection':
            self.add_item(SubLocationButton(
                label="Inspect Cargo", 
                emoji="⚖️", 
                style=discord.ButtonStyle.primary,
                service_type="inspect_cargo"
            ))
            self.add_item(SubLocationButton(
                label="File Manifest", 
                emoji="📋", 
                style=discord.ButtonStyle.secondary,
                service_type="file_manifest"
            ))
            self.add_item(SubLocationButton(
                label="Pay Transit Fee", 
                emoji="💳", 
                style=discord.ButtonStyle.success,
                service_type="pay_transit_fee"
            ))
            
        elif self.sub_type == 'vessel_wash':
            self.add_item(SubLocationButton(
                label="Hull Cleaning - 75C", 
                emoji="🧽", 
                style=discord.ButtonStyle.primary,
                service_type="hull_cleaning"
            ))
            self.add_item(SubLocationButton(
                label="Radiation Scrub - 50C", 
                emoji="☢️", 
                style=discord.ButtonStyle.secondary,
                service_type="radiation_scrub"
            ))
            self.add_item(SubLocationButton(
                label="Basic Decon - 30C", 
                emoji="🛡️", 
                style=discord.ButtonStyle.success,
                service_type="basic_decon"
            ))
            
        elif self.sub_type == 'pilot_quarters':
            self.add_item(SubLocationButton(
                label="Rest in Pod", 
                emoji="🛌", 
                style=discord.ButtonStyle.primary,
                service_type="rest_in_pod"
            ))
            self.add_item(SubLocationButton(
                label="Shower Facilities", 
                emoji="🚿", 
                style=discord.ButtonStyle.secondary,
                service_type="shower_facilities"
            ))
            self.add_item(SubLocationButton(
                label="Pilot Lounge", 
                emoji="☕", 
                style=discord.ButtonStyle.success,
                service_type="pilot_lounge"
            ))
            
        elif self.sub_type == 'freight_depot':
            self.add_item(SubLocationButton(
                label="Scan Cargo", 
                emoji="📦", 
                style=discord.ButtonStyle.primary,
                service_type="store_cargo"
            ))
            self.add_item(SubLocationButton(
                label="Retrieve Cargo", 
                emoji="📤", 
                style=discord.ButtonStyle.secondary,
                service_type="retrieve_cargo"
            ))
            self.add_item(SubLocationButton(
                label="Cargo Insurance", 
                emoji="🛡️", 
                style=discord.ButtonStyle.success,
                service_type="cargo_insurance"
            ))
            
        elif self.sub_type == 'component_shop':
            self.add_item(SubLocationButton(
                label="Buy Components", 
                emoji="🔩", 
                style=discord.ButtonStyle.primary,
                service_type="buy_components"
            ))
            self.add_item(SubLocationButton(
                label="Emergency Repair Kit", 
                emoji="🧰", 
                style=discord.ButtonStyle.secondary,
                service_type="emergency_repair_kit"
            ))
            self.add_item(SubLocationButton(
                label="Spare Parts", 
                emoji="⚙️", 
                style=discord.ButtonStyle.success,
                service_type="spare_parts"
            ))
            
        elif self.sub_type == 'travel_cafe':
            self.add_item(SubLocationButton(
                label="Order Coffee", 
                emoji="☕", 
                style=discord.ButtonStyle.primary,
                service_type="order_coffee"
            ))
            self.add_item(SubLocationButton(
                label="Quick Meal", 
                emoji="🍕", 
                style=discord.ButtonStyle.secondary,
                service_type="quick_meal"
            ))
            self.add_item(SubLocationButton(
                label="Energy Drinks", 
                emoji="⚡", 
                style=discord.ButtonStyle.success,
                service_type="energy_drinks"
            ))
            
        elif self.sub_type == 'family_area':
            self.add_item(SubLocationButton(
                label="Kids Play Area", 
                emoji="👶", 
                style=discord.ButtonStyle.primary,
                service_type="kids_play_area"
            ))
            self.add_item(SubLocationButton(
                label="Baby Care Station", 
                emoji="🍼", 
                style=discord.ButtonStyle.secondary,
                service_type="baby_care_station"
            ))
            self.add_item(SubLocationButton(
                label="Family Rest", 
                emoji="🛋️", 
                style=discord.ButtonStyle.success,
                service_type="family_rest"
            ))
            
        elif self.sub_type == 'passenger_pods':
            self.add_item(SubLocationButton(
                label="Rent Sleep Pod", 
                emoji="🛏️", 
                style=discord.ButtonStyle.primary,
                service_type="rent_sleep_pod"
            ))
            self.add_item(SubLocationButton(
                label="Premium Pod", 
                emoji="✨", 
                style=discord.ButtonStyle.secondary,
                service_type="premium_pod"
            ))
            self.add_item(SubLocationButton(
                label="Pod Services", 
                emoji="🔧", 
                style=discord.ButtonStyle.success,
                service_type="pod_services"
            ))
            
        elif self.sub_type == 'entertainment_lounge':
            self.add_item(SubLocationButton(
                label="Holo-Games", 
                emoji="🎮", 
                style=discord.ButtonStyle.primary,
                service_type="holo_games"
            ))
            self.add_item(SubLocationButton(
                label="Virtual Reality", 
                emoji="🥽", 
                style=discord.ButtonStyle.secondary,
                service_type="virtual_reality"
            ))
            self.add_item(SubLocationButton(
                label="Music & Media", 
                emoji="🎵", 
                style=discord.ButtonStyle.success,
                service_type="music_media"
            ))
            
        elif self.sub_type == 'travel_services':
            self.add_item(SubLocationButton(
                label="Book Passage", 
                emoji="🎫", 
                style=discord.ButtonStyle.primary,
                service_type="book_passage"
            ))
            self.add_item(SubLocationButton(
                label="Route Planning", 
                emoji="🗺️", 
                style=discord.ButtonStyle.secondary,
                service_type="route_planning"
            ))
            self.add_item(SubLocationButton(
                label="Travel Insurance", 
                emoji="🛡️", 
                style=discord.ButtonStyle.success,
                service_type="travel_insurance"
            ))
            
        elif self.sub_type == 'casino':
            self.add_item(SubLocationButton(
                label="🎰 Slot Machine", 
                emoji="🎰", 
                style=discord.ButtonStyle.primary,
                service_type="slot_machine"
            ))
            self.add_item(SubLocationButton(
                label="🃏 Blackjack", 
                emoji="🃏", 
                style=discord.ButtonStyle.primary,
                service_type="blackjack"
            ))
            self.add_item(SubLocationButton(
                label="🎲 Dice Roll", 
                emoji="🎲", 
                style=discord.ButtonStyle.primary,
                service_type="dice_roll"
            ))
            
        # Derelict area services
        elif self.sub_type in ['abandoned_quarters', 'emergency_shelter', 'salvage_yard', 'power_core', 'scavenger_den']:
            self.add_item(SubLocationButton(
                label="Search for Supplies", 
                emoji="🔍", 
                style=discord.ButtonStyle.secondary,
                service_type="search_supplies"
            ))
            if self.sub_type == 'salvage_yard':
                self.add_item(SubLocationButton(
                    label="Scavenge Parts", 
                    emoji="⚙️", 
                    style=discord.ButtonStyle.primary,
                    service_type="scavenge_parts"
                ))
            if self.sub_type == 'emergency_shelter':
                self.add_item(SubLocationButton(
                    label="Use Emergency Med", 
                    emoji="🩹", 
                    style=discord.ButtonStyle.success,
                    service_type="emergency_medical"
                ))

    async def handle_service(self, interaction: discord.Interaction, service_type: str):
        """Handle service interactions"""
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT name, hp, max_hp, money, current_location, appearance FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("You need a character to use services!", ephemeral=False)
            return
        
        char_name, hp, max_hp, money, current_location, appearance = char_info
        
        # Check if user is at this location
        if current_location != self.location_id:
            await interaction.response.send_message("You need to be at this location to use its services!", ephemeral=False)
            return
        
        # Handle administration services that use modals
        if service_type == "change_name":
            modal = ChangeNameModal(
                title="Change Character Name",
                field_label="New Name",
                placeholder="Enter the new name for your character.",
                current_value=char_name,
                cost=50,
                bot=self.bot
            )
            await interaction.response.send_modal(modal)
            
        elif service_type == "change_description":
            modal = ChangeDescriptionModal(
                title="Change Character Description",
                field_label="New Appearance Description",
                placeholder="Describe your character's appearance.",
                current_value=appearance,
                cost=50,
                bot=self.bot
            )
            await interaction.response.send_modal(modal)

        elif service_type == "change_bio":
            bio = self.db.execute_query(
                "SELECT biography FROM character_identity WHERE user_id = ?",
                (interaction.user.id,), fetch='one'
            )
            modal = ChangeBioModal(
                title="Change Character Biography",
                field_label="New Biography",
                placeholder="Tell your character's story...",
                current_value=bio[0] if bio else "",
                cost=25,
                bot=self.bot
            )
            await interaction.response.send_modal(modal)

        elif service_type == "change_dob":
            dob = self.db.execute_query(
                "SELECT birth_month, birth_day FROM character_identity WHERE user_id = ?",
                (interaction.user.id,), fetch='one'
            )
            current_dob = f"{dob[0]:02d}/{dob[1]:02d}" if dob else ""
            modal = ChangeDOBModal(
                title="Change Date of Birth",
                field_label="New Birth Date (MM/DD)",
                placeholder="e.g., 03/15 for March 15th",
                current_value=current_dob,
                cost=500,
                bot=self.bot
            )
            await interaction.response.send_modal(modal)
            
        elif service_type == "take_id_photo":
            current_image = self.db.execute_query(
                "SELECT image_url FROM characters WHERE user_id = ?",
                (interaction.user.id,), fetch='one'
            )
            current_url = current_image[0] if current_image else ""
            modal = ChangeImageModal(
                title="Take ID Photo",
                field_label="Image URL",
                placeholder="Enter the URL of your character's photo",
                current_value=current_url,
                cost=50,
                bot=self.bot
            )
            await interaction.response.send_modal(modal)
            
        # Handle other service types with direct responses
        elif service_type == "medical_treatment":
            await self._handle_medical_treatment(interaction, char_name, hp, max_hp, money)
        elif service_type == "buy_medical":
            await self._handle_buy_medical(interaction, char_name, money)
        elif service_type == "health_checkup":
            await self._handle_health_checkup(interaction, char_name, hp, max_hp)
        elif service_type == "repair_ship":
            await self._handle_repair_ship(interaction, char_name, money)
        elif service_type == "stellar_charts":
            await self._handle_stellar_charts(interaction, char_name)
        elif service_type == "ship_diagnostics":
            await self._handle_ship_diagnostics(interaction, char_name)
        elif service_type == "order_drink":
            await self._handle_order_drink(interaction, char_name, money)
        elif service_type == "listen_gossip":
            await self._handle_listen_gossip(interaction, char_name)
        elif service_type == "play_cards":
            await self._handle_play_cards(interaction, char_name, money)
        elif service_type == "relax":
            await self._handle_relax(interaction, char_name)
        elif service_type == "watch_news":
            await self._handle_watch_news(interaction, char_name)
        elif service_type == "refreshments":
            await self._handle_refreshments(interaction, char_name, money)
        elif service_type == "browse_shops":
            await self._handle_browse_shops(interaction, char_name)
        elif service_type == "apply_permits":
            await self._handle_apply_permits(interaction, char_name, money)
        elif service_type == "info_desk":
            await self._handle_info_desk(interaction, char_name)
        elif service_type == "file_complaint":
            await self._handle_file_complaint(interaction, char_name)
        elif service_type == "check_traffic":
            await self._handle_check_traffic(interaction, char_name)
        elif service_type == "corridor_status":
            await self._handle_corridor_status(interaction, char_name)
        elif service_type == "rest_recuperate":
            await self._handle_rest_recuperate(interaction, char_name)
        elif service_type == "travel_info":
            await self._handle_traveler_info(interaction, char_name)
        elif service_type == "security_scan":
            await self._handle_security_scan(interaction, char_name)
        elif service_type == "report_incident":
            await self._handle_report_incident(interaction, char_name)
        elif service_type == "transit_papers":
            await self._handle_transit_papers(interaction, char_name, money)
        elif service_type == "priority_refuel":
            await self._handle_priority_refuel(interaction, char_name, money)
        elif service_type == "fuel_quality":
            await self._handle_fuel_quality(interaction, char_name)
        elif service_type == "pre_transit_check":
            await self._handle_pre_transit_check(interaction, char_name)
        elif service_type == "emergency_repairs":
            await self._handle_emergency_repairs(interaction, char_name, money)
        elif service_type == "search_supplies":
            await self._handle_search_supplies(interaction, char_name)
        elif service_type == "scavenge_parts":
            await self._handle_scavenge_parts(interaction, char_name)
        elif service_type == "emergency_medical":
            await self._handle_emergency_medical(interaction, char_name, money)
        elif service_type == "equipment_mods":
            await self._handle_equipment_mods(interaction, char_name, money)
        elif service_type == "deep_space_scan":
            await self._handle_deep_space_scan(interaction, char_name)
        elif service_type == "navigation_data":
            await self._handle_navigation_data(interaction, char_name)
        elif service_type == "slot_machine":
            await self._handle_slot_machine(interaction, char_name, money)
        elif service_type == "blackjack":
            await self._handle_blackjack(interaction, char_name, money)
        elif service_type == "dice_roll":
            await self._handle_dice_roll(interaction, char_name, money)
        elif service_type == "check_prices":
            await self._handle_check_prices(interaction, char_name)
        elif service_type == "specialty_vendors":
            await self._handle_specialty_vendors(interaction, char_name, money)
        elif service_type == "rest_quarters":
            await self._handle_rest_quarters(interaction, char_name, hp, max_hp)
        elif service_type == "use_facilities":
            await self._handle_use_facilities(interaction, char_name)
        elif service_type == "check_amenities":
            await self._handle_check_amenities(interaction, char_name)
        elif service_type == "browse_research":
            await self._handle_browse_research(interaction, char_name)
        elif service_type == "use_equipment":
            await self._handle_use_equipment(interaction, char_name)
        elif service_type == "review_data":
            await self._handle_review_data(interaction, char_name)
        elif service_type == "collaborate":
            await self._handle_collaborate(interaction, char_name)
        elif service_type == "tour_gardens":
            await self._handle_tour_gardens(interaction, char_name)
        elif service_type == "market_info":
            await self._handle_market_info(interaction, char_name)
        elif service_type == "learn_techniques":
            await self._handle_learn_techniques(interaction, char_name)
        elif service_type == "play_games":
            await self._handle_play_games(interaction, char_name)
        elif service_type == "exercise":
            await self._handle_exercise(interaction, char_name, hp, max_hp)
        elif service_type == "join_activity":
            await self._handle_join_activity(interaction, char_name)
        elif service_type == "relax_unwind":
            await self._handle_relax_unwind(interaction, char_name)
        elif service_type == "send_message":
            await self._handle_send_message(interaction, char_name, money)
        elif service_type == "check_signals":
            await self._handle_check_signals(interaction, char_name)
        elif service_type == "monitor_channels":
            await self._handle_monitor_channels(interaction, char_name)
        elif service_type == "order_meal":
            await self._handle_order_meal(interaction, char_name, money, hp, max_hp)
        elif service_type == "check_menu":
            await self._handle_check_menu(interaction, char_name)
        elif service_type == "socialize":
            await self._handle_socialize(interaction, char_name)
        elif service_type == "wait_comfortably":
            await self._handle_wait_comfortably(interaction, char_name, hp, max_hp)
        elif service_type == "check_schedules":
            await self._handle_check_schedules(interaction, char_name)
        elif service_type == "travel_info":
            await self._handle_traveler_info(interaction, char_name)
        elif service_type == "security_consult":
            await self._handle_security_consult(interaction, char_name)
        elif service_type == "browse_archives":
            await self._handle_browse_archives(interaction, char_name)
        elif service_type == "research_records":
            await self._handle_research_records(interaction, char_name)
        elif service_type == "study_figures":
            await self._handle_study_figures(interaction, char_name)
        # Gate service types
        elif service_type == "manifest_review":
            await self._handle_manifest_review(interaction, char_name)
        elif service_type == "customs_declaration":
            await self._handle_customs_declaration(interaction, char_name)
        elif service_type == "cargo_scan":
            await self._handle_cargo_scan(interaction, char_name)
        elif service_type == "schedule_cleaning":
            await self._handle_schedule_cleaning(interaction, char_name)
        elif service_type == "decontamination_check":
            await self._handle_decontamination_check(interaction, char_name)
        elif service_type == "hull_inspection":
            await self._handle_hull_inspection(interaction, char_name)
        elif service_type == "reserve_bunk":
            await self._handle_reserve_bunk(interaction, char_name)
        elif service_type == "check_in_out":
            await self._handle_check_in_out(interaction, char_name)
        elif service_type == "amenities_info":
            await self._handle_amenities_info(interaction, char_name)
        elif service_type == "storage_inquiry":
            await self._handle_storage_inquiry(interaction, char_name)
        elif service_type == "schedule_pickup":
            await self._handle_schedule_pickup(interaction, char_name)
        elif service_type == "track_shipment":
            await self._handle_track_shipment(interaction, char_name)
        elif service_type == "browse_parts":
            await self._handle_browse_parts(interaction, char_name)
        elif service_type == "emergency_kit":
            await self._handle_emergency_kit(interaction, char_name)
        elif service_type == "technical_support":
            await self._handle_technical_support(interaction, char_name)
        elif service_type == "order_food":
            await self._handle_order_food(interaction, char_name)
        elif service_type == "local_specialties":
            await self._handle_local_specialties(interaction, char_name)
        elif service_type == "take_break":
            await self._handle_take_break(interaction, char_name)
        elif service_type == "child_care_info":
            await self._handle_child_care_info(interaction, char_name)
        elif service_type == "family_services":
            await self._handle_family_services(interaction, char_name)
        elif service_type == "rest_together":
            await self._handle_rest_together(interaction, char_name)
        elif service_type == "book_pod":
            await self._handle_book_pod(interaction, char_name)
        elif service_type == "check_availability":
            await self._handle_check_availability(interaction, char_name)
        elif service_type == "pod_services":
            await self._handle_pod_services(interaction, char_name)
        elif service_type == "play_holo_games":
            await self._handle_play_holo_games(interaction, char_name)
        elif service_type == "vr_experience":
            await self._handle_vr_experience(interaction, char_name)
        elif service_type == "social_activities":
            await self._handle_social_activities(interaction, char_name)
        elif service_type == "route_planning":
            await self._handle_route_planning(interaction, char_name)
        elif service_type == "book_passage":
            await self._handle_book_passage(interaction, char_name)
        elif service_type == "travel_insurance":
            await self._handle_travel_insurance(interaction, char_name)
        # Outpost service types
        elif service_type == "review_samples":
            await self._handle_review_samples(interaction, char_name)
        elif service_type == "data_analysis":
            await self._handle_data_analysis(interaction, char_name)
        elif service_type == "equipment_check":
            await self._handle_equipment_check(interaction, char_name)
        elif service_type == "sample_catalog":
            await self._handle_sample_catalog(interaction, char_name)
        elif service_type == "access_records":
            await self._handle_access_records(interaction, char_name)
        elif service_type == "environmental_check":
            await self._handle_environmental_check(interaction, char_name)
        elif service_type == "monitor_operations":
            await self._handle_monitor_operations(interaction, char_name)
        elif service_type == "equipment_status":
            await self._handle_equipment_status(interaction, char_name)
        elif service_type == "production_reports":
            await self._handle_production_reports(interaction, char_name)
        elif service_type == "check_processing":
            await self._handle_check_processing(interaction, char_name)
        elif service_type == "quality_control":
            await self._handle_quality_control(interaction, char_name)
        elif service_type == "output_status":
            await self._handle_output_status(interaction, char_name)
        elif service_type == "scan_readings":
            await self._handle_scan_readings(interaction, char_name)
        elif service_type == "calibrate_sensors":
            await self._handle_calibrate_sensors(interaction, char_name)
        elif service_type == "alert_status":
            await self._handle_alert_status(interaction, char_name)
        elif service_type == "navigation_status":
            await self._handle_navigation_status(interaction, char_name)
        elif service_type == "signal_strength":
            await self._handle_signal_strength(interaction, char_name)
        elif service_type == "maintenance_log":
            await self._handle_maintenance_log(interaction, char_name)
        elif service_type == "weather_data":
            await self._handle_weather_data(interaction, char_name)
        elif service_type == "storm_tracking":
            await self._handle_storm_tracking(interaction, char_name)
        elif service_type == "atmospheric_report":
            await self._handle_atmospheric_report(interaction, char_name)
        elif service_type == "inventory_check":
            await self._handle_inventory_check(interaction, char_name)
        elif service_type == "request_supplies":
            await self._handle_request_supplies(interaction, char_name)
        elif service_type == "emergency_cache":
            await self._handle_emergency_cache(interaction, char_name)
        elif service_type == "launch_drone":
            await self._handle_launch_drone(interaction, char_name)
        elif service_type == "maintenance_check":
            await self._handle_maintenance_check(interaction, char_name)
        elif service_type == "mission_planning":
            await self._handle_mission_planning(interaction, char_name)
        elif service_type == "containment_status":
            await self._handle_containment_status(interaction, char_name)
        elif service_type == "decontamination":
            await self._handle_decontamination(interaction, char_name)
        elif service_type == "emergency_protocol":
            await self._handle_emergency_protocol(interaction, char_name)
        # Station/Colony service types
        elif service_type == "production_status":
            await self._handle_production_status(interaction, char_name)
        elif service_type == "order_processing":
            await self._handle_order_processing(interaction, char_name)
        elif service_type == "reactor_status":
            await self._handle_reactor_status(interaction, char_name)
        elif service_type == "safety_check":
            await self._handle_safety_check(interaction, char_name)
        elif service_type == "power_output":
            await self._handle_power_output(interaction, char_name)
        elif service_type == "loading_schedule":
            await self._handle_loading_schedule(interaction, char_name)
        elif service_type == "storage_request":
            await self._handle_storage_request(interaction, char_name)
        elif service_type == "waste_processing":
            await self._handle_waste_processing(interaction, char_name)
        elif service_type == "material_status":
            await self._handle_material_status(interaction, char_name)
        elif service_type == "drop_off_items":
            await self._handle_drop_off_items(interaction, char_name)
        elif service_type == "quiet_reflection":
            await self._handle_quiet_reflection(interaction, char_name)
        elif service_type == "community_service":
            await self._handle_community_service(interaction, char_name)
        elif service_type == "spiritual_guidance":
            await self._handle_spiritual_guidance(interaction, char_name)
        elif service_type == "view_exhibitions":
            await self._handle_view_exhibitions(interaction, char_name)
        elif service_type == "artist_information":
            await self._handle_artist_information(interaction, char_name)
        elif service_type == "cultural_events":
            await self._handle_cultural_events(interaction, char_name)
        elif service_type == "check_shows":
            await self._handle_check_shows(interaction, char_name)
        elif service_type == "book_tickets":
            await self._handle_book_tickets(interaction, char_name)
        elif service_type == "performance_schedule":
            await self._handle_performance_schedule(interaction, char_name)
        elif service_type == "browse_market":
            await self._handle_browse_market(interaction, char_name)
        elif service_type == "meet_people":
            await self._handle_meet_people(interaction, char_name)
        elif service_type == "attend_events":
            await self._handle_attend_events(interaction, char_name)
        elif service_type == "declare_goods":
            await self._handle_declare_goods(interaction, char_name)
        elif service_type == "tax_information":
            await self._handle_tax_information(interaction, char_name)
        elif service_type == "trade_permits":
            await self._handle_trade_permits(interaction, char_name)
        elif service_type == "residency_info":
            await self._handle_residency_info(interaction, char_name)
        elif service_type == "citizenship_process":
            await self._handle_citizenship_process(interaction, char_name)
        elif service_type == "documentation":
            await self._handle_documentation(interaction, char_name)
        
        # Cargo Inspection Bay services
        elif service_type == "inspect_cargo":
            await self._handle_inspect_cargo(interaction, char_name)
        elif service_type == "file_manifest":
            await self._handle_file_manifest(interaction, char_name)
        elif service_type == "pay_transit_fee":
            await self._handle_pay_transit_fee(interaction, char_name)
        
        # Hull Cleaning Bay services
        elif service_type == "hull_cleaning":
            await self._handle_hull_cleaning(interaction, char_name)
        elif service_type == "radiation_scrub":
            await self._handle_radiation_scrub(interaction, char_name)
        elif service_type == "basic_decon":
            await self._handle_basic_decon(interaction, char_name)
        
        # Pilot Rest Quarters services
        elif service_type == "rest_in_pod":
            await self._handle_rest_in_pod(interaction, char_name)
        elif service_type == "shower_facilities":
            await self._handle_shower_facilities(interaction, char_name)
        elif service_type == "pilot_lounge":
            await self._handle_pilot_lounge(interaction, char_name)
        
        # Freight Storage Depot services
        elif service_type == "store_cargo":
            await self._handle_store_cargo(interaction, char_name)
        elif service_type == "retrieve_cargo":
            await self._handle_retrieve_cargo(interaction, char_name)
        elif service_type == "cargo_insurance":
            await self._handle_cargo_insurance(interaction, char_name)
        
        # Ship Components Shop services
        elif service_type == "buy_components":
            await self._handle_buy_components(interaction, char_name)
        elif service_type == "emergency_repair_kit":
            await self._handle_emergency_repair_kit(interaction, char_name)
        elif service_type == "spare_parts":
            await self._handle_spare_parts(interaction, char_name)
        
        # Transit Café services
        elif service_type == "order_coffee":
            await self._handle_order_coffee(interaction, char_name)
        elif service_type == "quick_meal":
            await self._handle_quick_meal(interaction, char_name)
        elif service_type == "energy_drinks":
            await self._handle_energy_drinks(interaction, char_name)
        
        # Family Rest Area services
        elif service_type == "kids_play_area":
            await self._handle_kids_play_area(interaction, char_name)
        elif service_type == "baby_care_station":
            await self._handle_baby_care_station(interaction, char_name)
        elif service_type == "family_rest":
            await self._handle_family_rest(interaction, char_name)
        
        # Sleep Pods services
        elif service_type == "rent_sleep_pod":
            await self._handle_rent_sleep_pod(interaction, char_name)
        elif service_type == "premium_pod":
            await self._handle_premium_pod(interaction, char_name)
        elif service_type == "pod_services":
            await self._handle_pod_services(interaction, char_name)
        
        # Entertainment Hub services
        elif service_type == "holo_games":
            await self._handle_holo_games(interaction, char_name)
        elif service_type == "virtual_reality":
            await self._handle_virtual_reality(interaction, char_name)
        elif service_type == "music_media":
            await self._handle_music_media(interaction, char_name)
        
        else:
            # Generic flavor response for unimplemented services
            await self._handle_generic_service(interaction, service_type, char_name)

    # Service handler methods - keeping the most functional versions
    async def _handle_medical_treatment(self, interaction: discord.Interaction, char_name: str, hp: int, max_hp: int, money: int):
        """Handle medical treatment service"""
        if hp >= max_hp:
            embed = discord.Embed(
                title="⚕️ Medical Bay",
                description=f"**{char_name}**, your vitals are optimal. No treatment required.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        healing_needed = max_hp - hp
        cost_per_hp = 15
        total_cost = healing_needed * cost_per_hp
        
        if money < total_cost:
            embed = discord.Embed(
                title="⚕️ Medical Bay",
                description=f"**Treatment Cost:** {total_cost} credits\n**Your Credits:** {money}\n\nInsufficient funds for full treatment.",
                color=0xff0000
            )
            embed.add_field(
                name="💊 Partial Treatment Available",
                value=f"We can heal {money // cost_per_hp} HP for {(money // cost_per_hp) * cost_per_hp} credits.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply healing
        self.db.execute_query(
            "UPDATE characters SET hp = ?, money = ? WHERE user_id = ?",
            (max_hp, money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="⚕️ Medical Treatment Complete",
            description=f"**{char_name}**, you have been fully healed.",
            color=0x00ff00
        )
        embed.add_field(name="💚 Health Restored", value=f"{hp} → {max_hp} HP", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    async def _handle_transit_papers(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle transit documentation services"""
        import random
        
        cost = 5
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford transit documentation services.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        document_types = [
            "Corridor Transit Permit",
            "Emergency Travel Authorization",
            "Cargo Manifest Certification",
            "Pilot License Renewal",
            "Medical Certificate Update"
        ]
        
        doc_type = random.choice(document_types)
        
        embed = discord.Embed(
            title="📄 Transit Documentation",
            description=f"**{char_name}** obtains official transit documentation.",
            color=0x4169e1
        )
        embed.add_field(name="📋 Document Type", value=doc_type, inline=False)
        embed.add_field(name="🆔 Validity", value="Valid for standard corridor transit operations", inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    async def _handle_security_scan(self, interaction: discord.Interaction, char_name: str):
        """Handle security scanning at checkpoint"""
        import random
        
        scan_results = [
            "All clear - no prohibited items detected",
            "Standard scan complete - you're cleared for transit",
            "Routine inspection passed - proceed to gate",
            "Security clearance confirmed - safe travels",
            "Biometric verification successful - transit approved"
        ]
        
        scan_details = [
            "The scanner hums as it analyzes your belongings",
            "Biometric sensors confirm your identity",
            "X-ray scanners examine your equipment thoroughly",
            "Chemical detectors find no contraband",
            "The security AI processes your travel authorization"
        ]
        
        embed = discord.Embed(
            title="🔍 Security Scan",
            description=f"**{char_name}** undergoes mandatory security screening.",
            color=0x4682b4
        )
        embed.add_field(name="📋 Scan Result", value=random.choice(scan_results), inline=False)
        embed.add_field(name="🔬 Process", value=random.choice(scan_details), inline=False)
        embed.add_field(name="✅ Status", value="You are cleared to proceed through the checkpoint.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    
    async def _handle_rest_recuperate(self, interaction: discord.Interaction, char_name: str):
        """Handle rest and recuperation at truck stop (free, no HP restoration)"""
        import random
        
        rest_quality = [
            "The public rest area's benches are surprisingly comfortable for a brief nap.",
            "You find a quiet corner and take a moment to collect your thoughts.",
            "The gentle hum of station systems provides a relaxing atmosphere.",
            "A comfortable chair by the viewport offers a peaceful place to rest."
        ]
        
        rest_activities = [
            "You watch the flow of travelers through the corridor while relaxing.",
            "The ambient lighting creates a calming environment for contemplation.",
            "You observe the occasional ship passing by through the large windows.",
            "The comfortable seating area provides a welcome break from travel."
        ]
        
        embed = discord.Embed(
            title="😴 Rest & Recuperation",
            description=f"**{char_name}** takes time to rest in the common lounge area.",
            color=0x9370db
        )
        embed.add_field(name="🛋️ Rest Experience", value=random.choice(rest_quality), inline=False)
        embed.add_field(name="✨ Activity", value=random.choice(rest_activities), inline=False)
        embed.add_field(name="💰 Cost", value="Free service", inline=True)
        embed.add_field(name="⏱️ Duration", value="Relaxing break", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    async def _handle_fuel_quality(self, interaction: discord.Interaction, char_name: str):
        """Handle fuel quality inspection"""
        import random
        
        quality_ratings = [
            ("Premium Grade", "99.8% purity - exceptional quality"),
            ("Standard Grade", "97.2% purity - meets all specifications"),
            ("Commercial Grade", "95.1% purity - acceptable for most vessels"),
            ("Economy Grade", "92.8% purity - basic but functional")
        ]
        
        grade, description = random.choice(quality_ratings)
        
        fuel_properties = [
            "Low impurity content ensures clean combustion",
            "Additive package includes corrosion inhibitors",
            "Stable molecular structure for long-term storage",
            "Enhanced energy density for extended range",
            "Filtered through advanced purification systems"
        ]
        
        embed = discord.Embed(
            title="🧪 Fuel Quality Analysis",
            description=f"**{char_name}** reviews detailed fuel quality reports.",
            color=0x20b2aa
        )
        embed.add_field(name="⭐ Quality Grade", value=grade, inline=True)
        embed.add_field(name="📊 Analysis", value=description, inline=True)
        embed.add_field(name="🔬 Properties", value=random.choice(fuel_properties), inline=False)
        embed.add_field(name="✅ Certification", value="All fuel meets galactic safety standards.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_emergency_medical(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle emergency medical services"""
        import random
        
        char_info = self.db.execute_query(
            "SELECT hp, max_hp FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character data not found.", ephemeral=False)
            return
        
        hp, max_hp = char_info
        
        if hp >= max_hp * 0.8:  # If above 80% health
            embed = discord.Embed(
                title="🩹 Emergency Medical",
                description=f"**{char_name}**, your condition doesn't require emergency intervention.",
                color=0x90ee90
            )
            embed.add_field(name="💚 Current Health", value=f"{hp}/{max_hp} HP", inline=True)
            embed.add_field(name="📋 Assessment", value="Stable condition", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Emergency medical is expensive but provides significant healing
        base_cost = 100
        emergency_surcharge = 50
        total_cost = base_cost + emergency_surcharge
        
        if money < total_cost:
            # Offer basic emergency treatment
            basic_cost = 60
            if money >= basic_cost:
                healing = 20
                self.db.execute_query(
                    "UPDATE characters SET hp = hp + ?, money = money - ? WHERE user_id = ?",
                    (healing, basic_cost, interaction.user.id)
                )
                embed = discord.Embed(
                    title="🩹 Basic Emergency Care",
                    description=f"**{char_name}** receives basic emergency medical treatment.",
                    color=0xffd700
                )
                embed.add_field(name="💚 Treatment", value=f"+{healing} HP restored", inline=True)
                embed.add_field(name="💰 Cost", value=f"{basic_cost} credits", inline=True)
            else:
                embed = discord.Embed(
                    title="❌ Insufficient Credits",
                    description=f"**{char_name}** cannot afford emergency medical services.",
                    color=0xff4500
                )
                embed.add_field(name="💰 Required", value=f"{basic_cost} credits (basic care)", inline=True)
                embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Full emergency treatment
        healing = max_hp - hp  # Full heal
        self.db.execute_query(
            "UPDATE characters SET hp = ?, money = money - ? WHERE user_id = ?",
            (max_hp, total_cost, interaction.user.id)
        )
        
        treatments = [
            "Advanced trauma stabilization protocols",
            "Rapid cellular regeneration therapy",
            "Emergency surgical intervention",
            "Critical care life support systems",
            "Intensive medical monitoring"
        ]
        
        embed = discord.Embed(
            title="🚨 Emergency Medical Treatment",
            description=f"**{char_name}** receives immediate emergency medical care.",
            color=0xff6347
        )
        embed.add_field(name="🏥 Treatment", value=random.choice(treatments), inline=False)
        embed.add_field(name="💚 Health Restored", value=f"+{healing} HP (Full Recovery)", inline=True)
        embed.add_field(name="💰 Total Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - total_cost} credits", inline=True)
        embed.add_field(name="⚡ Status", value="Emergency treatment complete - patient stabilized.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_equipment_mods(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle equipment modifications"""
        import random
        
        modifications = [
            ("Ship Sensor Upgrade", 150, "Enhanced long-range detection capabilities"),
            ("Hull Reinforcement", 200, "Additional armor plating for improved protection"),
            ("Engine Efficiency Mod", 175, "Improved fuel consumption and performance"),
            ("Communication Booster", 100, "Extended communication range and clarity"),
            ("Navigation Enhancement", 125, "Advanced routing and corridor analysis systems"),
            ("Life Support Upgrade", 140, "Improved environmental systems and backup power")
        ]
        
        mod_name, cost, description = random.choice(modifications)
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford the {mod_name} modification.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            embed.add_field(name="📝 Description", value=description, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Check if user has a ship
        ship_exists = self.db.execute_query(
            "SELECT COUNT(*) FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_exists or ship_exists[0] == 0:
            embed = discord.Embed(
                title="❌ No Ship Found",
                description="Equipment modifications require a registered vessel.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply modification (add to inventory as an upgrade)
        from utils.item_config import ItemConfig
        metadata = ItemConfig.create_item_metadata(mod_name)
        self.db.execute_query(
            '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (interaction.user.id, mod_name, "ship_modification", 1, description, cost, metadata)
        )
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="⚙️ Equipment Modification",
            description=f"**{char_name}** has their equipment professionally modified.",
            color=0x4169e1
        )
        embed.add_field(name="🔧 Modification", value=mod_name, inline=False)
        embed.add_field(name="📝 Enhancement", value=description, inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        embed.add_field(name="✅ Status", value="Modification installed and operational.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)  
        
    async def _handle_stellar_charts(self, interaction: discord.Interaction, char_name: str):
        """Handle stellar chart viewing (free activity)"""
        import random
        
        chart_types = [
            ("Local System Map", "Detailed navigation data for nearby sectors"),
            ("Trade Route Atlas", "Commercial shipping lanes and waypoints"),
            ("Hazard Charts", "Known dangers: asteroid fields, solar storms"),
            ("Deep Space Survey", "Uncharted regions and exploration opportunities"),
            ("Historical Charts", "Ancient trade routes and forgotten settlements")
        ]
        
        chart_name, description = random.choice(chart_types)
        
        discoveries = [
            "You notice an unmarked asteroid field that could contain valuable minerals",
            "Ancient beacon signals are marked on routes through this sector", 
            "Trade opportunities between distant systems become apparent",
            "A previously unknown jump gate appears on the deep range scans",
            "Navigation warnings highlight recent pirate activity zones"
        ]
        
        embed = discord.Embed(
            title="🗺️ Stellar Navigation Charts",
            description=f"**{char_name}** studies the comprehensive star charts.",
            color=0x1e90ff
        )
        embed.add_field(name="📊 Chart Type", value=chart_name, inline=True)
        embed.add_field(name="🔍 Status", value="Access Granted", inline=True)
        embed.add_field(name="📋 Information", value=description, inline=False)
        embed.add_field(name="✨ Discovery", value=random.choice(discoveries), inline=False)
        embed.add_field(name="💰 Cost", value="Complimentary service", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_deep_space_scan(self, interaction: discord.Interaction, char_name: str):
        """Handle deep space scanning (free activity)"""
        import random
        
        scan_results = [
            ("Anomalous Signals", "Long-range sensors detect unusual energy readings"),
            ("Stellar Activity", "Solar flare warnings issued for nearby systems"),
            ("Ship Traffic", "Multiple vessels detected on common trade routes"),
            ("Cosmic Phenomena", "Interesting nebula formations spotted in outer systems"),
            ("Debris Fields", "Scattered wreckage from old conflicts identified")
        ]
        
        result_type, description = random.choice(scan_results)
        
        technical_details = [
            "Quantum sensors operating at maximum sensitivity",
            "Multi-spectrum analysis reveals detailed compositions",
            "Advanced algorithms filter out background radiation",
            "Cross-referencing with galactic databases for verification",
            "Real-time monitoring provides up-to-date information"
        ]
        
        embed = discord.Embed(
            title="📡 Deep Space Monitoring",
            description=f"**{char_name}** accesses the station's deep space sensors.",
            color=0x4169e1
        )
        embed.add_field(name="🔭 Scan Type", value="Long-Range Survey", inline=True)
        embed.add_field(name="📊 Status", value="Scan Complete", inline=True)
        embed.add_field(name="🎯 Detection", value=result_type, inline=False)
        embed.add_field(name="📋 Details", value=description, inline=False)
        embed.add_field(name="⚙️ Technology", value=random.choice(technical_details), inline=False)
        embed.add_field(name="💰 Cost", value="Public access terminal", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_navigation_data(self, interaction: discord.Interaction, char_name: str):
        """Handle navigation data access (free activity)"""
        import random
        
        data_types = [
            ("Jump Gate Network", "Current status and routing information for all gates"),
            ("Fuel Station Directory", "Locations and prices of refueling stations"),
            ("Weather Patterns", "Solar wind and space weather forecasts"),
            ("Traffic Control", "Optimal routes to avoid congestion"),
            ("Emergency Services", "Rescue and repair service locations")
        ]
        
        data_name, info = random.choice(data_types)
        
        insights = [
            "Several faster routes are available during off-peak hours",
            "Fuel prices vary significantly between different sectors",
            "Emergency beacon frequencies are clearly marked",
            "Alternative routes can save time during heavy traffic periods",
            "Station facilities and services are comprehensively catalogued"
        ]
        
        embed = discord.Embed(
            title="🧭 Navigation Database",
            description=f"**{char_name}** accesses the central navigation database.",
            color=0x32cd32
        )
        embed.add_field(name="📂 Data Category", value=data_name, inline=True)
        embed.add_field(name="📡 Coverage", value="Sector-wide", inline=True)
        embed.add_field(name="ℹ️ Information", value=info, inline=False)
        embed.add_field(name="💡 Insight", value=random.choice(insights), inline=False)
        embed.add_field(name="🕒 Last Updated", value="Real-time data feed", inline=False)
        embed.add_field(name="💰 Cost", value="Free public service", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    async def _handle_check_prices(self, interaction: discord.Interaction, char_name: str):
        """Handle checking market prices"""
        import random
        
        # Generate current market prices for common goods
        market_items = [
            ("Fuel (per unit)", random.randint(2, 5)),
            ("Medical Supplies", random.randint(20, 60)),
            ("Ship Parts", random.randint(50, 150)),
            ("Food Rations", random.randint(8, 25)),
            ("Raw Materials", random.randint(15, 40)),
            ("Electronics", random.randint(75, 200)),
            ("Refined Metals", random.randint(30, 80)),
            ("Luxury Goods", random.randint(100, 300))
        ]
        
        # Market conditions
        market_conditions = [
            ("🟢 Stable", "Prices are holding steady"),
            ("📈 Rising", "Demand is driving prices up"),
            ("📉 Falling", "Oversupply causing price drops"),
            ("⚡ Volatile", "Prices fluctuating rapidly"),
            ("🔒 Controlled", "Government price controls in effect")
        ]
        
        condition, condition_desc = random.choice(market_conditions)
        
        # Format price list
        price_list = []
        for item, price in random.sample(market_items, 6):
            price_list.append(f"**{item}**: {price} credits")
        
        embed = discord.Embed(
            title="📈 Market Price Check",
            description=f"**{char_name}** reviews current market conditions and pricing.",
            color=0x32cd32
        )
        embed.add_field(name="💰 Current Prices", value="\n".join(price_list), inline=False)
        embed.add_field(name="📊 Market Condition", value=f"{condition}", inline=True)
        embed.add_field(name="📋 Analysis", value=condition_desc, inline=True)
        embed.add_field(name="💡 Trading Tip", value="Prices vary by location and local supply/demand.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)    
        
    async def _handle_specialty_vendors(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle specialty vendor interactions"""
        import random
        
        specialty_items = [
            ("Rare Crystal", 200, "exotic", "Crystalline formation with unique properties"),
            ("Vintage Tech", 150, "equipment", "Pre-colonial technology in working condition"),
            ("Strange Artifact", 300, "exotic", "Mysterious object of unknown origin"),
            ("Collector's Map", 100, "information", "Hand-drawn star charts from early explorers"),
            ("Exotic Spice", 75, "consumable", "Rare seasoning from distant worlds"),
            ("Archived Data", 180, "equipment", "Data storage device with historical records")
        ]
        
        item_name, cost, item_type, description = random.choice(specialty_items)
        
        if money < cost:
            embed = discord.Embed(
                title="🏪 Specialty Vendor",
                description=f"**{char_name}** browses unique and rare items.",
                color=0x9370db
            )
            embed.add_field(name="💎 Featured Item", value=f"{item_name}", inline=False)
            embed.add_field(name="📝 Description", value=description, inline=False)
            embed.add_field(name="💰 Price", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Your Credits", value=f"{money} credits", inline=True)
            embed.add_field(name="❌ Status", value="Insufficient credits for purchase", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Add item to inventory
        from utils.item_config import ItemConfig
        metadata = ItemConfig.create_item_metadata(item_name)
        self.db.execute_query(
            '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (interaction.user.id, item_name, item_type, 1, description, cost, metadata)
        )
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        vendor_comments = [
            "A fine choice! This piece has quite a history.",
            "You have an excellent eye for quality items.",
            "This item comes from a private collection.",
            "A rare find - you won't see another like it.",
            "This piece has traveled far to reach our shop."
        ]
        
        embed = discord.Embed(
            title="🏪 Specialty Purchase",
            description=f"**{char_name}** acquires a unique item from the specialty vendor.",
            color=0x9370db
        )
        embed.add_field(name="💎 Purchased", value=item_name, inline=False)
        embed.add_field(name="📝 Description", value=description, inline=False)
        embed.add_field(name="💬 Vendor Note", value=random.choice(vendor_comments), inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)    
    async def _handle_scavenge_parts(self, interaction: discord.Interaction, char_name: str):
        """Handle scavenging for parts in salvage areas"""
        import random
        
        if random.random() < 0.4:  # 40% chance of finding something
            salvaged_items = [
                ("Scrap Electronics", "equipment", random.randint(1, 2), "Salvaged electronic components", 20),
                ("Metal Plating", "material", random.randint(1, 3), "Reinforced metal plating strips", 15),
                ("Power Coupling", "equipment", 1, "Damaged but repairable power coupling", 35),
                ("Circuit Board", "equipment", 1, "Partially functional circuit board", 25),
                ("Fuel Line", "equipment", 1, "Intact flexible fuel line", 18),
                ("Sensor Array", "equipment", 1, "Damaged sensor array components", 45)
            ]
            
            item_name, item_type, quantity, description, value = random.choice(salvaged_items)
            
            # Add to inventory
            from utils.item_config import ItemConfig
            metadata = ItemConfig.create_item_metadata(item_name)
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_type, quantity, description, value, metadata)
            )
            
            embed = discord.Embed(
                title="⚙️ Parts Scavenged",
                description=f"**{char_name}** searches through the salvage yard and finds useful components.",
                color=0x8fbc8f
            )
            embed.add_field(name="🔧 Found", value=f"{quantity}x {item_name}", inline=False)
            embed.add_field(name="📝 Description", value=description, inline=False)
            embed.add_field(name="💎 Estimated Value", value=f"{value * quantity} credits", inline=False)
            
            # Small chance of finding something rare
            if random.random() < 0.1:  # 10% chance
                embed.add_field(name="✨ Bonus", value="This appears to be a particularly well-preserved piece!", inline=False)
        else:
            embed = discord.Embed(
                title="⚙️ Scavenging Attempt",
                description=f"**{char_name}** searches the salvage yard thoroughly.",
                color=0x696969
            )
            embed.add_field(name="🔍 Result", value="Nothing useful found this time. The area has been well-picked by previous scavengers.", inline=False)
            embed.add_field(name="💭 Note", value="Scavenging success varies - keep trying different areas.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_emergency_repairs(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle emergency ship repairs"""
        import random
        
        ship_info = self.db.execute_query(
            "SELECT hull_integrity, max_hull FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="❌ No Ship Found",
                description="Emergency repairs require a registered vessel.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        hull_integrity, max_hull = ship_info
        
        if hull_integrity >= max_hull:
            embed = discord.Embed(
                title="🔧 Emergency Repairs",
                description=f"**{char_name}**, your ship doesn't require emergency repairs.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Emergency repairs are expensive but fast
        repairs_needed = max_hull - hull_integrity
        cost_per_point = 50  # Double normal repair cost
        total_cost = repairs_needed * cost_per_point
        
        if money < total_cost:
            # Offer partial emergency repairs
            max_affordable_repairs = money // cost_per_point
            embed = discord.Embed(
                title="🚨 Emergency Repair Service",
                description=f"**Full Emergency Repair Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff6600
            )
            if max_affordable_repairs > 0:
                embed.add_field(
                    name="⚡ Partial Emergency Repairs",
                    value=f"We can repair {max_affordable_repairs} hull points for {max_affordable_repairs * cost_per_point} credits.",
                    inline=False
                )
            embed.add_field(name="⚠️ Note", value="Emergency repairs cost double the standard rate.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply emergency repairs
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = ? WHERE owner_id = ?",
            (max_hull, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚨 Emergency Repairs Complete",
            description=f"**{char_name}**, your ship has been rapidly repaired using priority protocols.",
            color=0x00ff00
        )
        embed.add_field(name="🛠️ Hull Restored", value=f"{hull_integrity} → {max_hull}", inline=True)
        embed.add_field(name="⚡ Service Type", value="Emergency Priority", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - total_cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_pre_transit_check(self, interaction: discord.Interaction, char_name: str):
        """Handle pre-transit system check"""
        import random
        
        ship_info = self.db.execute_query(
            "SELECT hull_integrity, max_hull, current_fuel, fuel_capacity FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="❌ No Ship Found",
                description="Pre-transit check requires a registered vessel.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        hull_integrity, max_hull, current_fuel, fuel_capacity = ship_info
        hull_percent = (hull_integrity / max_hull) * 100
        fuel_percent = (current_fuel / fuel_capacity) * 100
        
        # Determine overall readiness
        if hull_percent >= 80 and fuel_percent >= 50:
            status = "✅ CLEARED FOR TRANSIT"
            color = 0x00ff00
            recommendation = "All systems nominal. Safe travels!"
        elif hull_percent >= 60 and fuel_percent >= 25:
            status = "⚠️ CAUTION ADVISED"
            color = 0xffff00
            recommendation = "Systems functional but consider repairs/refueling."
        else:
            status = "❌ NOT RECOMMENDED"
            color = 0xff0000
            recommendation = "Critical issues detected. Repairs required before transit."
        
        system_checks = [
            f"Hull Integrity: {hull_percent:.1f}%",
            f"Fuel Level: {fuel_percent:.1f}%",
            "Navigation Systems: Operational",
            "Life Support: Nominal",
            "Communication Array: Active"
        ]
        
        embed = discord.Embed(
            title="🔧 Pre-Transit Check",
            description=f"**{char_name}**'s vessel undergoes comprehensive system evaluation.",
            color=color
        )
        embed.add_field(name="📋 System Status", value="\n".join(system_checks), inline=False)
        embed.add_field(name="🎯 Overall Status", value=status, inline=False)
        embed.add_field(name="💡 Recommendation", value=recommendation, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False) 
    
    async def _handle_browse_archives(self, interaction, char_name: str):
        """Handle browsing historical archives with enhanced functionality"""
        from utils.history_generator import HistoryGenerator
        
        # Get current location
        location_data = self.db.execute_query(
            """SELECT l.location_id, l.name, l.location_type, l.wealth_level 
               FROM characters c 
               JOIN locations l ON c.current_location = l.location_id 
               WHERE c.user_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_data:
            await interaction.response.send_message("Unable to determine your current location.", ephemeral=False)
            return
        
        location_id, location_name, location_type, wealth_level = location_data
        
        # First, check if there's any history at all
        total_history = self.db.execute_query(
            "SELECT COUNT(*) FROM galactic_history",
            fetch='one'
        )[0]
        
        if total_history == 0:
            embed = discord.Embed(
                title="📚 Archive Browse",
                description=f"**{char_name}** searches through the archives but finds them completely empty. The galaxy's history has yet to be written.",
                color=0x8b4513
            )
            embed.set_footer(text="💡 Tip: An administrator needs to generate galaxy history first.")
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Try to get a historical event - prioritize local events but fall back to general
        history_gen = HistoryGenerator(self.bot)
        
        # First try: Get event specific to this location
        event = self.db.execute_query(
            '''SELECT event_title, event_description, historical_figure, event_date, event_type
               FROM galactic_history 
               WHERE location_id = ?
               ORDER BY RANDOM() LIMIT 1''',
            (location_id,),
            fetch='one'
        )
        
        # Second try: Get any event (local or general) if no location-specific event found
        if not event:
            event = self.db.execute_query(
                '''SELECT gh.event_title, gh.event_description, gh.historical_figure, 
                          gh.event_date, gh.event_type, l.name as event_location
                   FROM galactic_history gh
                   LEFT JOIN locations l ON gh.location_id = l.location_id
                   ORDER BY RANDOM() LIMIT 1''',
                fetch='one'
            )
            
            if event and len(event) > 5:  # Has location name
                event_location = event[5]
            else:
                event_location = None
        else:
            event_location = location_name
        
        if not event:
            embed = discord.Embed(
                title="📚 Archive Browse",
                description=f"**{char_name}** searches through the archives but finds only corrupted data files.",
                color=0x8b4513
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Parse event data
        event_title = event[0]
        event_description = event[1]
        historical_figure = event[2]
        event_date = event[3]
        event_type = event[4]
        
        # Create immersive historical record embed
        embed = discord.Embed(
            title="📚 Historical Archive Discovery",
            color=0x4169e1
        )
        
        # Add archive interaction description
        archive_descriptions = [
            f"**{char_name}** carefully activates an ancient data terminal, its holographic display flickering to life...",
            f"**{char_name}** discovers a well-preserved memory crystal and inserts it into the archive reader...",
            f"**{char_name}** browses through digital manuscripts, stopping at an intriguing entry...",
            f"**{char_name}** accesses the neural archive interface, historical data flooding their consciousness...",
            f"**{char_name}** finds a secured vault containing classified historical records..."
        ]
        
        embed.description = random.choice(archive_descriptions)
        
        # Add the historical record with better formatting
        embed.add_field(
            name=f"📜 {event_title}",
            value=f"*Archive Classification: {event_type.title()}*",
            inline=False
        )
        
        # Format the description with proper line breaks
        formatted_description = event_description
        if len(formatted_description) > 200:
            # Add line breaks for readability
            words = formatted_description.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) > 80:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word) + 1
            
            if current_line:
                lines.append(' '.join(current_line))
            
            formatted_description = '\n'.join(lines)
        
        embed.add_field(
            name="📖 Historical Account",
            value=f"```{formatted_description}```",
            inline=False
        )
        
        # Add additional details in a clean format
        details = []
        
        if historical_figure:
            details.append(f"**Notable Figure:** {historical_figure}")
        
        if event_location:
            details.append(f"**Location:** {event_location}")
        
        details.append(f"**Date:** {event_date}")
        
        if details:
            embed.add_field(
                name="📋 Archive Metadata",
                value='\n'.join(details),
                inline=False
            )
        
        # Add some flavor text based on the archive's wealth level
        if wealth_level >= 6:
            footer_text = "This premium archive contains millions of meticulously preserved historical records."
        elif wealth_level >= 4:
            footer_text = "This well-maintained archive houses extensive historical documentation."
        else:
            footer_text = "This modest archive contains what historical records could be preserved."
        
        embed.set_footer(text=footer_text)
        
        # Add a timestamp
        embed.timestamp = interaction.created_at
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
        # Optional: Add a small chance to discover something special
        if random.random() < 0.05:  # 5% chance
            special_discovery = discord.Embed(
                title="🌟 Rare Discovery!",
                description=f"While browsing the archives, **{char_name}** notices a hidden compartment containing additional materials related to this historical event!",
                color=0xffd700
            )
            
            # Could add rewards here - credits, items, reputation, etc.
            reward = random.randint(50, 200)
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            special_discovery.add_field(
                name="💰 Archive Preservation Reward",
                value=f"The archive's automated systems award {reward} credits for your careful handling of historical materials.",
                inline=False
            )
            
            await interaction.followup.send(embed=special_discovery)

    # Additional method for "Study Historical Figures" feature
    async def _handle_study_figures(self, interaction, char_name: str):
        """Handle studying historical figures in the archives"""
        # Get all unique historical figures
        figures = self.db.execute_query(
            '''SELECT DISTINCT historical_figure, COUNT(*) as event_count
               FROM galactic_history 
               WHERE historical_figure IS NOT NULL
               GROUP BY historical_figure
               ORDER BY event_count DESC
               LIMIT 10''',
            fetch='all'
        )
        
        if not figures:
            embed = discord.Embed(
                title="👤 Historical Figures Database",
                description=f"**{char_name}** searches the biographical archives but finds no records of notable figures.",
                color=0x8b4513
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Pick a random figure from the top 10
        figure_name, event_count = random.choice(figures)
        
        # Get all events related to this figure
        figure_events = self.db.execute_query(
            '''SELECT event_title, event_description, event_date, event_type, l.name as location_name
               FROM galactic_history gh
               LEFT JOIN locations l ON gh.location_id = l.location_id
               WHERE historical_figure = ?
               ORDER BY event_date ASC
               LIMIT 3''',
            (figure_name,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"👤 Historical Figure: {figure_name}",
            description=f"**{char_name}** accesses the biographical database and reviews the life and achievements of a notable historical figure.",
            color=0x9370db
        )
        
        # Add a biography summary
        biography_intros = [
            f"{figure_name} was a pivotal figure in galactic history, known for their significant contributions across multiple sectors.",
            f"The legacy of {figure_name} continues to influence galactic civilization to this day.",
            f"Historical records show that {figure_name} played a crucial role in shaping the modern galaxy.",
            f"{figure_name}'s actions during their lifetime had far-reaching consequences that echo through history."
        ]
        
        embed.add_field(
            name="📜 Biography",
            value=random.choice(biography_intros),
            inline=False
        )
        
        # Add their notable events
        if figure_events:
            timeline_text = []
            for title, desc, date, event_type, location in figure_events:
                location_text = f" at {location}" if location else ""
                timeline_text.append(f"**{date}** - {title}{location_text}")
            
            embed.add_field(
                name="🗓️ Historical Timeline",
                value='\n'.join(timeline_text),
                inline=False
            )
        
        embed.add_field(
            name="📊 Historical Impact",
            value=f"Featured in {event_count} recorded historical events",
            inline=True
        )
        
        embed.set_footer(text="The archive's biographical database contains records of thousands of influential figures.")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Additional helper method to get multiple history entries (for future "Research Records" feature)
    async def _handle_research_records(self, interaction, char_name: str):
        """Handle researching multiple historical records"""
        # Get current location
        location_data = self.db.execute_query(
            """SELECT l.location_id, l.name 
               FROM characters c 
               JOIN locations l ON c.current_location = l.location_id 
               WHERE c.user_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_data:
            await interaction.response.send_message("Unable to determine your current location.", ephemeral=False)
            return
        
        location_id, location_name = location_data
        
        # Get multiple historical events (3-5)
        events = self.db.execute_query(
            '''SELECT event_title, event_date, event_type, 
                      CASE WHEN location_id = ? THEN 'Local' ELSE 'Galactic' END as scope
               FROM galactic_history 
               WHERE location_id = ? OR location_id IS NULL
               ORDER BY RANDOM() LIMIT 5''',
            (location_id, location_id),
            fetch='all'
        )
        
        if not events:
            embed = discord.Embed(
                title="📖 Research Records",
                description=f"**{char_name}** attempts to access the research terminal, but finds no accessible records.",
                color=0x8b4513
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        embed = discord.Embed(
            title="📖 Historical Research Terminal",
            description=f"**{char_name}** accesses the archive's research interface and discovers several historical records:",
            color=0x4682b4
        )
        
        for i, (title, date, event_type, scope) in enumerate(events, 1):
            embed.add_field(
                name=f"{i}. {title}",
                value=f"*{event_type.title()} • {date} • {scope} History*",
                inline=False
            )
        
        embed.set_footer(text="Each record contains detailed information about significant galactic events.")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    async def _handle_buy_medical(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle buying medical supplies"""
        medical_items = [
            ("Basic Med Kit", 50, "Restores 25 HP when used"),
            ("Emergency Stims", 75, "Instantly restores 15 HP in emergencies"),
            ("Radiation Pills", 30, "Provides protection against radiation"),
            ("Pain Killers", 25, "Reduces pain and improves recovery"),
            ("Advanced Trauma Kit", 150, "Professional medical supplies for serious injuries")
        ]
        
        item_name, cost, description = random.choice(medical_items)
        
        if money < cost:
            embed = discord.Embed(
                title="💊 Medical Supplies",
                description=f"**{char_name}**, you don't have enough credits for {item_name}.",
                color=0xff0000
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
        else:
            # Add item to inventory
            from utils.item_config import ItemConfig
            metadata = ItemConfig.create_item_metadata(item_name)
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, "medical", 1, description, cost, metadata)
            )
            
            # Deduct money
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (cost, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="💊 Medical Purchase",
                description=f"**{char_name}** purchases {item_name}.",
                color=0x00ff00
            )
            embed.add_field(name="📦 Item", value=item_name, inline=True)
            embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
            embed.add_field(name="📝 Description", value=description, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_health_checkup(self, interaction: discord.Interaction, char_name: str, hp: int, max_hp: int):
        """Handle health checkup"""
        health_percentage = (hp / max_hp) * 100
        
        if health_percentage >= 90:
            status = "Excellent"
            color = 0x00ff00
        elif health_percentage >= 70:
            status = "Good"
            color = 0x90ee90
        elif health_percentage >= 50:
            status = "Fair"
            color = 0xffff00
        elif health_percentage >= 30:
            status = "Poor"
            color = 0xff8c00
        else:
            status = "Critical"
            color = 0xff0000
        
        embed = discord.Embed(
            title="🩺 Health Checkup",
            description=f"**{char_name}**'s medical examination results:",
            color=color
        )
        embed.add_field(name="💚 Health Points", value=f"{hp}/{max_hp} HP", inline=True)
        embed.add_field(name="📊 Overall Status", value=status, inline=True)
        embed.add_field(name="📈 Health Percentage", value=f"{health_percentage:.1f}%", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_repair_ship(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle ship repair service"""
        ship_info = self.db.execute_query(
            "SELECT hull_integrity, max_hull FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🔧 Ship Repair Bay",
                description="No ship found to repair.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        hull_integrity, max_hull = ship_info
        
        if hull_integrity >= max_hull:
            embed = discord.Embed(
                title="🔧 Ship Repair Bay",
                description=f"**{char_name}**, your ship's hull is in perfect condition.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        repairs_needed = max_hull - hull_integrity
        cost_per_point = 25
        total_cost = repairs_needed * cost_per_point
        
        if money < total_cost:
            max_affordable_repairs = money // cost_per_point
            embed = discord.Embed(
                title="🔧 Ship Repair Bay",
                description=f"**Full Repair Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff6600
            )
            if max_affordable_repairs > 0:
                embed.add_field(
                    name="🔧 Partial Repairs Available",
                    value=f"We can repair {max_affordable_repairs} hull points for {max_affordable_repairs * cost_per_point} credits.",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply repairs
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = ? WHERE owner_id = ?",
            (max_hull, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🔧 Ship Repairs Complete",
            description=f"**{char_name}**, your ship has been fully repaired.",
            color=0x00ff00
        )
        embed.add_field(name="🛠️ Hull Integrity", value=f"{hull_integrity} → {max_hull}", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_refuel_ship(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle ship refueling service"""
        ship_info = self.db.execute_query(
            "SELECT fuel_capacity, current_fuel FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="⛽ Refueling Station",
                description="No ship found to refuel.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        fuel_capacity, current_fuel = ship_info
        
        if current_fuel >= fuel_capacity:
            embed = discord.Embed(
                title="⛽ Refueling Station",
                description=f"**{char_name}**, your ship's fuel tanks are already full.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        fuel_needed = fuel_capacity - current_fuel
        cost_per_fuel = 3
        total_cost = fuel_needed * cost_per_fuel
        
        if money < total_cost:
            max_affordable_fuel = money // cost_per_fuel
            embed = discord.Embed(
                title="⛽ Refueling Station",
                description=f"**Full Refuel Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff6600
            )
            if max_affordable_fuel > 0:
                embed.add_field(
                    name="⛽ Partial Refuel Available",
                    value=f"We can provide {max_affordable_fuel} fuel units for {max_affordable_fuel * cost_per_fuel} credits.",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply refueling
        self.db.execute_query(
            "UPDATE ships SET current_fuel = ? WHERE owner_id = ?",
            (fuel_capacity, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="⛽ Refueling Complete",
            description=f"**{char_name}**, your ship has been refueled.",
            color=0x00ff00
        )
        embed.add_field(name="⛽ Fuel Level", value=f"{current_fuel} → {fuel_capacity}", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_ship_diagnostics(self, interaction: discord.Interaction, char_name: str):
        """Handle ship diagnostics"""
        ship_info = self.db.execute_query(
            "SELECT name, ship_type, fuel_capacity, current_fuel, hull_integrity, max_hull FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="📊 Ship Diagnostics",
                description="No ship found for diagnostic scan.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        ship_name, ship_type, fuel_cap, current_fuel, hull, max_hull = ship_info
        
        fuel_percentage = (current_fuel / fuel_cap) * 100 if fuel_cap > 0 else 0
        hull_percentage = (hull / max_hull) * 100 if max_hull > 0 else 0
        
        embed = discord.Embed(
            title="📊 Ship Diagnostics",
            description=f"**{char_name}**'s ship diagnostic report:",
            color=0x4169e1
        )
        embed.add_field(name="🚀 Ship Name", value=ship_name, inline=True)
        embed.add_field(name="🛸 Ship Type", value=ship_type, inline=True)
        embed.add_field(name="⛽ Fuel Status", value=f"{current_fuel}/{fuel_cap} ({fuel_percentage:.1f}%)", inline=True)
        embed.add_field(name="🛡️ Hull Integrity", value=f"{hull}/{max_hull} ({hull_percentage:.1f}%)", inline=True)
        
        overall_status = "Operational" if fuel_percentage > 20 and hull_percentage > 50 else "Needs Attention"
        embed.add_field(name="📋 Overall Status", value=overall_status, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_order_drink(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle ordering drinks at the bar"""
        drinks = [
            ("Whiskey", 25, "A smooth whiskey aged in zero gravity."),
            ("Vodka", 20, "Crystal clear vodka from the colonies."),
            ("Beer", 15, "Local brew with a peculiar aftertaste."),
            ("Synthale", 10, "Synthetic alcohol, safe and reliable."),
            ("Absinthe", 18, "Dark Green and fruity, very intoxicating.")
        ]
        
        drink_name, cost, description = random.choice(drinks)
        
        if money < cost:
            embed = discord.Embed(
                title="🍺 The Bar",
                description=f"**{char_name}**, you don't have enough credits for a drink.\n**{drink_name}** costs {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - cost, interaction.user.id)
        )
        
        flavor_responses = [
            "The bartender nods approvingly at your choice.",
            "You overhear fragments of conversation from other patrons.",
            "The drink helps wash away the stress of space travel.",
            "You feel a bit more social after the drink.",
            "The alcohol warms you against the cold of space."
        ]
        
        embed = discord.Embed(
            title="🍺 Drink Ordered",
            description=f"**{char_name}** orders **{drink_name}**\n*{description}*",
            color=0xffa500
        )
        embed.add_field(name="💭 Effect", value=random.choice(flavor_responses), inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_listen_gossip(self, interaction: discord.Interaction, char_name: str):
        """Handle listening to gossip at the bar"""
        gossip_topics = [
            "Word is that corridor instabilities have been increasing lately...",
            "A trader mentioned seeing strange lights inside a corridor...",
            "Some colonial administrator was talking about new mining quotas...",
            "Heard that gate fees might be going up next cycle...",
            "There's rumors of pirates operating in the ungated corridors...",
            "Someone lost a cargo ship to static fog last week...",
            "The local security chief looked stressed when he came in earlier...",
            "A pilot was bragging about finding a new trade route...",
            "Corporate types have been asking questions about local operations...",
            "Emergency medical supplies are running low at some outposts..."
        ]
        
        gossip = random.choice(gossip_topics)
        
        embed = discord.Embed(
            title="👂 Bar Gossip",
            description=f"**{char_name}** listens carefully to the conversations around the bar...",
            color=0x9932cc
        )
        embed.add_field(name="🗣️ Overheard", value=f"*\"{gossip}\"*", inline=False)
        embed.add_field(name="💭 Knowledge", value="You file this information away for later.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_play_cards(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle playing cards at the bar"""
        if money < 20:
            embed = discord.Embed(
                title="🎲 Card Game",
                description=f"**{char_name}**, you need at least 20 credits to join a card game.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Simple gambling mechanic
        bet = 20
        outcome = random.random()
        
        if outcome < 0.4:  # 40% chance to win
            winnings = bet * 2
            self.db.execute_query(
                "UPDATE characters SET money = ? WHERE user_id = ?",
                (money + winnings - bet, interaction.user.id)
            )
            result = f"You win {winnings} credits!"
            color = 0x00ff00
        else:  # 60% chance to lose
            self.db.execute_query(
                "UPDATE characters SET money = ? WHERE user_id = ?",
                (money - bet, interaction.user.id)
            )
            result = f"You lose {bet} credits."
            color = 0xff0000
        
        embed = discord.Embed(
            title="🎲 Card Game Result",
            description=f"**{char_name}** plays a hand of cards...",
            color=color
        )
        embed.add_field(name="🃏 Outcome", value=result, inline=False)
        embed.add_field(name="💰 Credits", value=f"{money - bet if outcome >= 0.4 else money + winnings - bet}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    async def _handle_security_consult(self, interaction: discord.Interaction, char_name: str):
        """Handle a security consultation."""
        import random

        consultation_topics = [
            "personal defense protocols",
            "ship security hardening",
            "local threat assessments",
            "safe travel practices in this sector",
            "recognizing common scams and traps",
            "tips on staying alive in outer space"
        ]
        advice_given = [
            "The officer advises you to always be aware of your surroundings and to avoid unlit or deserted areas.",
            "A review of your ship's security logs is recommended to check for unauthorized access attempts.",
            "You're given an overview of current known threats, including pirate activity in nearby ungated corridors.",
            "The consultant stresses the importance of keeping your ship's transponder active and avoiding deviations from approved routes.",
            "You are warned about a common grift involving fake distress calls and advised on proper verification procedures.",
            "You are told that death is inevitable and unescapable, no matter how much security and defenses you have."
        ]

        topic = random.choice(consultation_topics)
        advice = random.choice(advice_given)

        embed = discord.Embed(
            title="🛡️ Security Consultation",
            description=f"**{char_name}** sits down with a security consultant to discuss **{topic}**.",
            color=0x4682b4
        )
        embed.add_field(
            name="Key Takeaway",
            value=advice,
            inline=False
        )
        embed.add_field(
            name="Status",
            value="You leave the consultation better informed and more prepared for potential dangers.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_report_incident(self, interaction: discord.Interaction, char_name: str):
        """Handle reporting a security incident."""
        import random
        
        incident_types = [
            "suspicious activity",
            "theft or vandalism",
            "safety hazard",
            "harassment or threats",
            "equipment malfunction",
            "unknown individuals"
        ]
        
        incident_id = f"INC-{random.randint(10000, 99999)}"
        incident_type = random.choice(incident_types)
        
        responses = [
            "Security has been notified and will investigate promptly.",
            "An officer will review your report and follow up if needed.",
            "Your report has been logged with high priority status.",
            "Security teams are taking immediate action based on your report."
        ]
        response = random.choice(responses)
        
        embed = discord.Embed(
            title="🚨 Security Incident Report",
            description=f"**{char_name}** files an incident report regarding **{incident_type}**.",
            color=0xff4500
        )
        embed.add_field(
            name="Incident ID",
            value=incident_id,
            inline=True
        )
        embed.add_field(
            name="Status",
            value=response,
            inline=False
        )
        embed.add_field(
            name="Next Steps",
            value="Keep your incident ID for any follow-up inquiries.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_file_complaint(self, interaction: discord.Interaction, char_name: str):
        """Handle filing a complaint with the security office."""
        import random
        
        case_number = f"CASE-{random.randint(1000, 9999)}-{random.choice(['A', 'B', 'C'])}"
        responses = [
            "Your complaint has been filed and will be reviewed in due course.",
            "Thank you for your report. The security office takes these matters seriously.",
            "The complaint has been logged. Please refer to your case number for follow-ups.",
            "Your report is now on record. An officer may contact you for more details."
        ]
        response = random.choice(responses)

        embed = discord.Embed(
            title="📝 Complaint Filed",
            description=f"**{char_name}** files an official complaint with the security office.",
            color=0x708090
        )
        embed.add_field(name="🧾 Case Number", value=case_number, inline=False)
        embed.add_field(name="📋 Status", value=response, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_info_desk(self, interaction: discord.Interaction, char_name: str):
        """Handle information desk services (free)"""
        import random
        
        info_categories = [
            ("Station Directory", "Complete list of facilities, services, and personnel"),
            ("Transportation Guide", "Schedules, routes, and connection information"),
            ("Emergency Procedures", "Safety protocols and evacuation procedures"),
            ("Local Regulations", "Station rules, customs, and legal requirements"),
            ("Visitor Services", "Tourist information and recreational activities")
        ]
        
        category, description = random.choice(info_categories)
        
        helpful_details = [
            "Staff member provides detailed maps and printed guides",
            "Digital displays show real-time updates and announcements",
            "Multi-language support ensures clear communication",
            "Emergency contact numbers and locations clearly marked",
            "Helpful staff eager to assist with any questions"
        ]
        
        desk_staff = ["Clerk Martinez", "Info Specialist Chen", "Assistant Director Vale", "Service Coordinator Ross"]
        staff_member = random.choice(desk_staff)
        
        embed = discord.Embed(
            title="ℹ️ Information Services",
            description=f"**{char_name}** approaches the information desk for assistance.",
            color=0x4169e1
        )
        embed.add_field(name="📋 Information Type", value=category, inline=True)
        embed.add_field(name="👨‍💼 Staff Member", value=staff_member, inline=True)
        embed.add_field(name="📄 Details", value=description, inline=False)
        embed.add_field(name="✨ Service Quality", value=random.choice(helpful_details), inline=False)
        embed.add_field(name="🕒 Availability", value="24/7 public service", inline=True)
        embed.add_field(name="💰 Cost", value="Free information service", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    async def _handle_relax(self, interaction: discord.Interaction, char_name: str):
        """Handle relaxing in the lounge"""
        relaxation_responses = [
            "You sink into a comfortable chair and feel your stress melting away.",
            "The soft ambient lighting helps you unwind from your journey.",
            "You watch other travelers come and go while enjoying the peace.",
            "The gentle hum of life support systems is oddly soothing.",
            "You close your eyes and take a few deep, calming breaths.",
            "The lounge's atmosphere helps clear your mind of worries."
        ]
        
        embed = discord.Embed(
            title="🛋️ Relaxation",
            description=f"**{char_name}** takes some time to relax in the comfortable lounge.",
            color=0x4169e1
        )
        embed.add_field(name="😌 Effect", value=random.choice(relaxation_responses), inline=False)
        embed.add_field(name="💭 Mental State", value="Feeling refreshed and ready for the next challenge.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_watch_news(self, interaction: discord.Interaction, char_name: str):
        """Handle watching news in the lounge"""
        news_stories = [
            "**Sector News**: Colonial production quotas below expectations for third consecutive quarter.",
            "**Traffic Advisory**: Gate systems scheduled for major maintenance over the coming days.",
            "**Market Report**: Fuel prices stable across most systems, slight increase in outer colonies.",
            "**Safety Notice**: Pilots advised to exercise caution in ungated corridors due to increased instability.",
            "**Corporate Update**: New mining contracts awarded to several independent operators.",
            "**Weather Alert**: Solar storm activity may affect communication systems in some sectors.",
            "**Trade News**: Shipping delays reported due to recent corridor shifts in the Gallux, Vortush, and Malanar sectors.",
            "**Health Advisory**: Radiation exposure protocols updated for deep space operations."
        ]
        
        news = random.choice(news_stories)
        
        embed = discord.Embed(
            title="📺 News Update",
            description=f"**{char_name}** catches up on current events...",
            color=0x1e90ff
        )
        embed.add_field(name="📰 Headlines", value=news, inline=False)
        embed.add_field(name="📡 Status", value="Staying informed about galactic developments.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_refreshments(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle buying refreshments"""
        drinks = [
            ("Cola", 4, "A crisp refreshing Cola, locally made."),
            ("'Fruit' Soda", 3, "A can labelled 'Fruit' Soda."),
            ("Water", 5, "A plain bottle of filtered water."),
            ("Space Milk", 10, "Space milk from, uh..."),
            ("Buzzless Light Beer", 6, "Non-Alcoholic Beer substitute."),
            ("Sizzla' Juice", 4, "A sweet and spicy beverage, enjoyed on some colonies.")
        ]
        
        drink_name, cost, description = random.choice(drinks)
        
        if money < cost:
            embed = discord.Embed(
                title="🥤 Buy a Refreshment",
                description=f"**{char_name}**, you don't have enough credits to buy a refreshment.\n**{drink_name}** costs {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - cost, interaction.user.id)
        )
        
        flavor_responses = [
            "The machine rumbles as the drink rolls out.",
            "The drink machine stalls before serving your refreshment.",
            "Your refreshing beverage eases your worries, for a moment.",
            "You feel pleasantly hydrated.",
            "You enjoy the taste of your bottled refreshment."
        ]
        
        embed = discord.Embed(
            title="🥤 Refreshment Ordered",
            description=f"**{char_name}** orders **{drink_name}**\n*{description}*",
            color=0xffa500
        )
        embed.add_field(name="🥤 Result", value=random.choice(flavor_responses), inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    async def _handle_browse_shops(self, interaction: discord.Interaction, char_name: str):
        """Handle browsing shops"""
        embed = discord.Embed(
            title="🛒 Shop Browser",
            description=f"**{char_name}** browses the available shops.",
            color=0x708090
        )
        embed.add_field(name="📋 Status", value="Use `/tqe` to see available items for purchase.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_apply_permits(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle applying for permits"""
        embed = discord.Embed(
            title="📝 Permit Applications",
            description=f"Apply for some permits.",
            color=0x708090
        )
        embed.add_field(name="📋 Status", value="The government agency will have your permit application reviewed within: 90 years.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Gate services
    async def _handle_check_traffic(self, interaction: discord.Interaction, char_name: str):
        """Handle traffic monitoring at gate control"""
        traffic_levels = ["Light", "Moderate", "Heavy", "Critical"]
        current_traffic = random.choice(traffic_levels)
        
        delays = {
            "Light": "No delays expected",
            "Moderate": "Minor delays possible", 
            "Heavy": "Significant delays likely",
            "Critical": "Major delays - consider alternate routes"
        }
        
        embed = discord.Embed(
            title="📊 Gate Traffic Control",
            description=f"**{char_name}** checks current corridor traffic conditions.",
            color=0x4169e1
        )
        embed.add_field(name="🚦 Current Traffic", value=current_traffic, inline=True)
        embed.add_field(name="⏱️ Expected Delays", value=delays[current_traffic], inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_corridor_status(self, interaction: discord.Interaction, char_name: str):
        """Handle corridor status check"""
        gate_corridors = self.db.execute_query(
            """SELECT c.name, c.danger_level, c.is_active 
               FROM corridors c WHERE c.origin_location = ? OR c.destination_location = ?""",
            (self.location_id, self.location_id),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🌌 Corridor Status Report",
            description=f"**{char_name}** reviews corridor conditions.",
            color=0x800080
        )
        
        if gate_corridors:
            status_list = []
            for name, danger, is_active in gate_corridors[:5]:
                status = "🟢 ACTIVE" if is_active else "🔴 INACTIVE"
                danger_text = "⚠️" * danger
                status_list.append(f"**{name}** - {status} {danger_text}")
            
            embed.add_field(name="📡 Active Corridors", value="\n".join(status_list), inline=False)
        else:
            embed.add_field(name="📡 Status", value="No corridor data available", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Premium gate services
    async def _handle_priority_refuel(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle priority refueling service at gate fuel depot"""
        ship_info = self.db.execute_query(
            "SELECT fuel_capacity, current_fuel FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="⛽ Priority Refuel",
                description="No ship found to refuel.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        fuel_capacity, current_fuel = ship_info
        
        if current_fuel >= fuel_capacity:
            embed = discord.Embed(
                title="⛽ Priority Refuel",
                description=f"**{char_name}**, your ship's fuel tanks are already full.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        fuel_needed = fuel_capacity - current_fuel
        cost_per_fuel = 5  # More expensive than regular refuel
        total_cost = fuel_needed * cost_per_fuel
        
        if money < total_cost:
            max_affordable_fuel = money // cost_per_fuel
            embed = discord.Embed(
                title="⛽ Priority Refuel Service",
                description=f"**Premium Refuel Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff6600
            )
            if max_affordable_fuel > 0:
                embed.add_field(
                    name="⛽ Partial Service Available",
                    value=f"We can provide {max_affordable_fuel} premium fuel units for {max_affordable_fuel * cost_per_fuel} credits.",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply premium refueling (also gives small efficiency bonus)
        self.db.execute_query(
            "UPDATE ships SET current_fuel = ?, fuel_efficiency = fuel_efficiency + 1 WHERE owner_id = ?",
            (fuel_capacity, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="⛽ Priority Refuel Complete",
            description=f"**{char_name}**, your ship has been refueled with premium fuel.",
            color=0x00ff00
        )
        embed.add_field(name="⛽ Fuel Level", value=f"{current_fuel} → {fuel_capacity}", inline=True)
        embed.add_field(name="✨ Bonus", value="+1 Fuel Efficiency", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Derelict services
    async def _handle_search_supplies(self, interaction: discord.Interaction, char_name: str):
        """Handle searching for supplies in derelict areas"""
        if random.random() < 0.3:  # 30% chance
            found_items = [
                ("Emergency Rations", "consumable", 1, "Expired but still edible emergency food", 5),
                ("Scrap Metal", "material", random.randint(1, 3), "Useful salvaged metal", 8),
                ("Broken Tool", "equipment", 1, "Damaged but potentially repairable tool", 15),
                ("Power Cell", "equipment", 1, "Partially charged emergency power cell", 25)
            ]
            
            item_name, item_type, quantity, description, value = random.choice(found_items)
            
            # Add to inventory
            from utils.item_config import ItemConfig
            metadata = ItemConfig.create_item_metadata(item_name)
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_type, quantity, description, value, metadata)
            )
            
            embed = discord.Embed(
                title="🔍 Supply Search",
                description=f"**{char_name}** searches through the abandoned area...",
                color=0x90EE90
            )
            embed.add_field(name="✨ Found", value=f"{quantity}x {item_name}", inline=False)
            embed.add_field(name="📝 Description", value=description, inline=False)
        else:
            embed = discord.Embed(
                title="🔍 Supply Search",
                description=f"**{char_name}** searches but finds nothing useful.",
                color=0x808080
            )
            embed.add_field(name="💭 Result", value="The area has been thoroughly picked clean by previous scavengers.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Generic service handler for unimplemented services
    async def _handle_generic_service(self, interaction: discord.Interaction, service_type: str, char_name: str):
        """Handle generic/flavor services"""
        generic_responses = {
            "equipment_mods": "You browse available modifications, but nothing catches your eye right now.",
            "ship_storage": "Storage services are available, but you don't need them at the moment.",
            "cargo_services": "Cargo handling services are ready when you need them.",
            "check_prices": "You review current market prices and make mental notes.",
            "specialty_vendors": "You browse specialty items but don't find anything you need right now.",
            "request_escort": "Security services are available if you need an escort.",
            "file_complaint": "Administrative services are ready to process any complaints.",
            "rest_recuperate": "You take some time to rest and recover.",
            "traveler_info": "You gather useful information for travelers.",
            "security_scan": "Security procedures are in place for your safety.",
            "transit_papers": "Documentation services are available when needed.",
            "fuel_quality": "Fuel quality meets all safety standards.",
            "pre_transit_check": "All systems check out for safe travel.",
            "emergency_repairs": "Emergency services are standing by if needed."
        }
        
        response = generic_responses.get(service_type, "You interact with the service but find nothing of immediate interest.")
        
        embed = discord.Embed(
            title="🏢 Service Interaction",
            description=f"**{char_name}** uses the available services.",
            color=0x708090
        )
        embed.add_field(name="📋 Result", value=response, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

# Continuing from where NEWsub_locations.py left off...
# Add the remaining missing handler methods:

    # Additional missing handler methods referenced in handle_service:

    async def _handle_rest_quarters(self, interaction, char_name: str, hp: int, max_hp: int):
        """Handle resting in quarters"""
        if hp >= max_hp:
            embed = discord.Embed(
                title="🛏️ Well Rested",
                description=f"**{char_name}** is already at full health and energy.",
                color=0x90ee90
            )
        else:
            # Restore some HP
            hp_restored = min(max_hp - hp, 25)
            new_hp = hp + hp_restored
            
            self.db.execute_query(
                "UPDATE characters SET hp = ? WHERE user_id = ?",
                (new_hp, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="🛏️ Restful Sleep",
                description=f"**{char_name}** gets some much-needed rest in comfortable quarters.",
                color=0x90ee90
            )
            embed.add_field(name="💚 Health Restored", value=f"+{hp_restored} HP", inline=True)
            embed.add_field(name="🏥 Current Health", value=f"{new_hp}/{max_hp} HP", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_use_facilities(self, interaction, char_name: str):
        """Handle using dormitory facilities"""
        import random
        
        facilities = [
            "You enjoy a refreshing shower in the clean facilities.",
            "The climate control keeps the quarters at perfect temperature.",
            "You use the personal storage locker to organize your belongings.",
            "The emergency communication system is tested and functional.",
            "You appreciate the privacy and comfort of personal quarters."
        ]
        
        embed = discord.Embed(
            title="🚿 Facilities Access",
            description=f"**{char_name}** makes use of the dormitory facilities.",
            color=0x87ceeb
        )
        embed.add_field(name="🏠 Comfort", value=random.choice(facilities), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_amenities(self, interaction, char_name: str):
        """Handle checking dormitory amenities"""
        amenities = [
            "🛏️ Comfortable sleeping quarters with adjustable beds",
            "🚿 Private hygiene facilities with hot water",
            "📚 Personal storage and work spaces",
            "🌡️ Climate control and air filtration",
            "📞 Emergency communication systems",
            "🔒 Secure personal lockers"
        ]
        
        embed = discord.Embed(
            title="🏠 Dormitory Amenities",
            description=f"**{char_name}** reviews available amenities.",
            color=0xdda0dd
        )
        embed.add_field(name="🏨 Available Features", value="\n".join(amenities), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_browse_research(self, interaction, char_name: str):
        """Handle browsing research projects"""
        import random
        
        research_topics = [
            "Advanced corridor navigation algorithms",
            "Static fog behavioral patterns",
            "Improved life support efficiency systems",
            "Communication relay enhancement studies",
            "Resource extraction optimization",
            "Ship hull integrity under corridor stress",
            "Long-range sensor array improvements",
            "Bio-containment protocols and safety"
        ]
        
        topic = random.choice(research_topics)
        
        embed = discord.Embed(
            title="🔬 Research Browse",
            description=f"**{char_name}** reviews current research projects.",
            color=0x4682b4
        )
        embed.add_field(name="📊 Current Study", value=f"*{topic}*", inline=False)
        embed.add_field(name="🧪 Status", value="Ongoing research with preliminary results available", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_use_equipment(self, interaction, char_name: str):
        """Handle using research equipment"""
        import random
        
        equipment = [
            "Advanced microscopy systems reveal microscopic details",
            "Particle analyzers process complex material samples",
            "Data processing arrays crunch numbers at incredible speeds",
            "Simulation chambers test theoretical scenarios safely",
            "Precision measurement tools provide exact specifications"
        ]
        
        embed = discord.Embed(
            title="⚗️ Equipment Access",
            description=f"**{char_name}** gains access to sophisticated research equipment.",
            color=0x20b2aa
        )
        embed.add_field(name="🔧 Equipment Used", value=random.choice(equipment), inline=False)
        embed.add_field(name="📈 Result", value="Valuable data collected for further analysis", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_review_data(self, interaction, char_name: str):
        """Handle reviewing research data"""
        import random
        
        data_insights = [
            "Recent corridor mapping shows unusual instability patterns",
            "Life support efficiency can be improved by 12% with new protocols",
            "Ship sensor arrays perform better with recalibrated algorithms",
            "Material stress tests reveal optimal hull configurations",
            "Communication range extends 15% further with relay adjustments"
        ]
        
        embed = discord.Embed(
            title="📊 Data Review",
            description=f"**{char_name}** examines recent research findings.",
            color=0x9370db
        )
        embed.add_field(name="💡 Key Finding", value=random.choice(data_insights), inline=False)
        embed.add_field(name="🎓 Knowledge", value="You gain insight into current technological developments.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_collaborate(self, interaction, char_name: str):
        """Handle collaborating with researchers"""
        import random
        
        collaborations = [
            "You assist with data analysis and spot an interesting pattern",
            "Your practical experience provides valuable real-world context",
            "You help troubleshoot a technical problem with your expertise",
            "Your observations contribute to a breakthrough discovery",
            "You participate in a productive brainstorming session"
        ]
        
        embed = discord.Embed(
            title="🤝 Research Collaboration",
            description=f"**{char_name}** collaborates with the research team.",
            color=0xffa500
        )
        embed.add_field(name="👥 Contribution", value=random.choice(collaborations), inline=False)
        embed.add_field(name="🎯 Impact", value="Your collaboration advances the research project.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_tour_gardens(self, interaction, char_name: str):
        """Handle touring the hydroponics gardens"""
        import random
        
        garden_sights = [
            "Rows of vibrant green vegetables grow in perfect conditions",
            "Automated systems carefully monitor nutrition and water levels",
            "The air is fresh and filled with the scent of growing plants",
            "Exotic fruits from various worlds flourish in controlled environments",
            "Advanced LED arrays provide optimal light spectrums for growth"
        ]
        
        embed = discord.Embed(
            title="🌱 Garden Tour",
            description=f"**{char_name}** takes a guided tour of the hydroponics facility.",
            color=0x32cd32
        )
        embed.add_field(name="🌿 Observation", value=random.choice(garden_sights), inline=False)
        embed.add_field(name="📚 Learning", value="You gain appreciation for sustainable food production.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_market_info(self, interaction, char_name: str):
        """Handle market information access (free activity)"""
        import random
        
        market_reports = [
            ("Trade Route Analysis", "Current shipping lanes showing highest profitability"),
            ("Supply Demand Report", "Critical shortages and surplus goods across sectors"),  
            ("Market Volatility Alert", "Price fluctuations and market stability predictions"),
            ("Commodity Tracking", "Real-time pricing for essential goods and materials"),
            ("Economic Forecast", "Projected market trends for the upcoming quarter")
        ]
        
        report_type, description = random.choice(market_reports)
        
        insights = [
            "Electronics are seeing a price surge due to increased demand in outer systems",
            "Fuel prices are stabilizing after recent supply chain disruptions",
            "Rare materials from mining operations are commanding premium prices", 
            "Food imports are in high demand at frontier colonies",
            "Luxury goods markets are experiencing seasonal fluctuations"
        ]
        
        trader_tips = [
            "Best profit margins are on routes avoiding high-traffic corridors",
            "Independent traders can capitalize on gaps in major shipping schedules",
            "Bulk purchases often qualify for significant volume discounts",
            "Market timing is crucial - prices can shift within hours",
            "Local specialties often have the highest profit potential"
        ]
        
        embed = discord.Embed(
            title="📊 Market Information Center",
            description=f"**{char_name}** accesses comprehensive market data.",
            color=0x4169e1
        )
        embed.add_field(name="📈 Report Type", value=report_type, inline=True)
        embed.add_field(name="📱 Access Level", value="Public Terminal", inline=True)
        embed.add_field(name="📋 Overview", value=description, inline=False)
        embed.add_field(name="💡 Market Insight", value=random.choice(insights), inline=False)
        embed.add_field(name="💼 Trading Tip", value=random.choice(trader_tips), inline=False)
        embed.add_field(name="💰 Cost", value="Free information service", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_learn_techniques(self, interaction, char_name: str):
        """Handle learning hydroponics techniques"""
        import random
        
        techniques = [
            "optimal nutrient solution mixing ratios",
            "proper pH balance maintenance methods",
            "efficient water circulation system design",
            "pest management in closed environments",
            "maximizing yield through lighting optimization",
            "crop rotation strategies for continuous production"
        ]
        
        embed = discord.Embed(
            title="📚 Learning Experience",
            description=f"**{char_name}** learns about hydroponics techniques.",
            color=0x6b8e23
        )
        embed.add_field(name="🎓 Technique Learned", value=f"How to manage {random.choice(techniques)}", inline=False)
        embed.add_field(name="🧠 Knowledge", value="This knowledge could be useful for future endeavors.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_play_games(self, interaction, char_name: str):
        """Handle playing games in recreation"""
        import random
        
        games = [
            "VR simulations of exotic worlds",
            "classic card games with other travelers",
            "holographic puzzle challenges", 
            "competitive strategy games",
            "immersive adventure simulations",
            "skill-based arcade challenges"
        ]
        
        game = random.choice(games)
        outcomes = ["won", "lost", "tied", "had fun with"]
        outcome = random.choice(outcomes)
        
        embed = discord.Embed(
            title="🎮 Gaming Session",
            description=f"**{char_name}** plays {game} and {outcome}!",
            color=0xff1493
        )
        embed.add_field(name="🎯 Result", value="An entertaining break from the rigors of space travel.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_exercise(self, interaction, char_name: str, hp: int, max_hp: int):
        """Handle exercising in recreation"""
        import random
        
        if hp >= max_hp:
            fitness_boost = 0
            message = "You maintain your excellent physical condition."
        else:
            fitness_boost = min(max_hp - hp, 15)
            self.db.execute_query(
                "UPDATE characters SET hp = hp + ? WHERE user_id = ?",
                (fitness_boost, interaction.user.id)
            )
            message = f"The workout improves your physical condition! (+{fitness_boost} HP)"
        
        workouts = [
            "cardiovascular training on the treadmill",
            "strength exercises with resistance equipment",
            "flexibility training and stretching",
            "zero-gravity fitness routines",
            "balance and coordination exercises"
        ]
        
        embed = discord.Embed(
            title="🏋️ Exercise Session",
            description=f"**{char_name}** engages in {random.choice(workouts)}.",
            color=0x32cd32
        )
        embed.add_field(name="💪 Fitness", value=message, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_join_activity(self, interaction, char_name: str):
        """Handle joining recreational activities"""
        import random
        
        activities = [
            "a friendly table tennis tournament",
            "group meditation and relaxation session",
            "collaborative art and crafts workshop",
            "book club discussion about recent reads",
            "movie night with classic space adventure films",
            "music jam session with other talented travelers"
        ]
        
        embed = discord.Embed(
            title="🏓 Group Activity",
            description=f"**{char_name}** joins {random.choice(activities)}.",
            color=0xffd700
        )
        embed.add_field(name="👥 Social", value="You meet interesting people and make new connections.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_relax_unwind(self, interaction, char_name: str):
        """Handle relaxing and unwinding"""
        import random
        
        relaxation_activities = [
            "You find a quiet corner to read and decompress",
            "Soft music and ambient lighting help you unwind",
            "You practice breathing exercises to reduce stress",
            "The comfortable seating provides much-needed rest",
            "You enjoy peaceful moments watching space through viewports"
        ]
        
        embed = discord.Embed(
            title="😌 Relaxation",
            description=f"**{char_name}** takes time to relax and unwind.",
            color=0x9370db
        )
        embed.add_field(name="🧘 Effect", value=random.choice(relaxation_activities), inline=False)
        embed.add_field(name="💭 Mental State", value="You feel refreshed and mentally recharged.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_send_message(self, interaction, char_name: str, money: int):
        """Handle sending messages"""
        import random
        
        cost = random.randint(10, 25)
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford to send a message right now.",
                color=0xff4500
            )
        else:
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (cost, interaction.user.id)
            )
            
            destinations = [
                "family back home",
                "business contacts",
                "fellow travelers",
                "station administrators",
                "trading partners"
            ]
            
            embed = discord.Embed(
                title="📡 Message Sent",
                description=f"**{char_name}** sends a message to {random.choice(destinations)}.",
                color=0x4169e1
            )
            embed.add_field(name="📨 Status", value="Message transmitted successfully", inline=False)
            embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_signals(self, interaction, char_name: str):
        """Handle checking communication signals"""
        import random
        
        signals = [
            "📡 Emergency beacon from a distant outpost",
            "📻 Trading frequency broadcasting current prices",
            "🎵 Music transmission from a nearby colony",
            "📰 News updates from major system events",
            "🚨 Safety warnings about corridor conditions",
            "💼 Job postings and contract opportunities"
        ]
        
        embed = discord.Embed(
            title="📻 Signal Check",
            description=f"**{char_name}** monitors communication channels.",
            color=0x1e90ff
        )
        embed.add_field(name="📡 Detected Signal", value=random.choice(signals), inline=False)
        embed.add_field(name="🔍 Information", value="You stay informed about current events and opportunities.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_monitor_channels(self, interaction, char_name: str):
        """Handle monitoring communication channels"""
        import random
        
        channel_activity = [
            "Routine traffic control communications",
            "Emergency services coordination chatter",
            "Corporate data transmission bursts",
            "Personal communications between travelers",
            "Automated system status reports",
            "Navigation updates and corridor conditions"
        ]
        
        embed = discord.Embed(
            title="🎧 Channel Monitoring",
            description=f"**{char_name}** monitors various communication channels.",
            color=0x6495ed
        )
        embed.add_field(name="📻 Activity", value=random.choice(channel_activity), inline=False)
        embed.add_field(name="ℹ️ Insight", value="You gain awareness of local communication patterns.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_order_meal(self, interaction, char_name: str, money: int, hp: int, max_hp: int):
        """Handle ordering a meal"""
        import random
        
        meals = [
            ("Hearty Protein Bowl", 25, 15),
            ("Fresh Salad Medley", 15, 10),
            ("Comfort Food Special", 30, 20),
            ("Quick Energy Bar", 10, 5),
            ("Gourmet Space Cuisine", 45, 25),
            ("Traditional Home Cooking", 35, 18)
        ]
        
        meal_name, cost, hp_restore = random.choice(meals)
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford the {meal_name} right now.",
                color=0xff4500
            )
        else:
            # Calculate actual HP restored
            actual_restore = min(hp_restore, max_hp - hp)
            
            self.db.execute_query(
                "UPDATE characters SET money = money - ?, hp = hp + ? WHERE user_id = ?",
                (cost, actual_restore, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="🍽️ Meal Ordered",
                description=f"**{char_name}** enjoys a delicious {meal_name}.",
                color=0xffa500
            )
            embed.add_field(name="💚 Nourishment", value=f"+{actual_restore} HP restored", inline=True)
            embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_menu(self, interaction, char_name: str):
        """Handle checking the cafeteria menu"""
        menu_items = [
            "🥩 Protein Dishes: Grilled meats and plant-based alternatives",
            "🥗 Fresh Salads: Hydroponically grown vegetables",
            "🍲 Comfort Foods: Hearty soups and traditional favorites",
            "🍰 Desserts: Sweet treats and energy bars",
            "☕ Beverages: Coffee, tea, and nutritional drinks",
            "🌮 Specialty Items: Regional cuisine from various worlds"
        ]
        
        embed = discord.Embed(
            title="📋 Cafeteria Menu",
            description=f"**{char_name}** reviews today's menu offerings.",
            color=0xdaa520
        )
        embed.add_field(name="🍽️ Available Items", value="\n".join(menu_items), inline=False)
        embed.add_field(name="💰 Price Range", value="10-45 credits per item", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_socialize(self, interaction, char_name: str):
        """Enhanced socializing with varied outcomes"""
        import random
        
        # Different social encounters based on location context
        social_encounters = [
            {
                "type": "conversation",
                "description": "You join a lively conversation about recent events",
                "outcome": "You learn some interesting local gossip and feel more connected to the community."
            },
            {
                "type": "networking",
                "description": "You meet a fellow traveler with similar interests",
                "outcome": "You exchange contact information and might cross paths again in the future."
            },
            {
                "type": "storytelling",
                "description": "Others gather as you share tales of your recent adventures",
                "outcome": "Your stories entertain the crowd and enhance your local reputation."
            },
            {
                "type": "advice",
                "description": "A experienced local offers you some helpful advice",
                "outcome": "You gain valuable insights about navigation, trade, or survival."
            },
            {
                "type": "information",
                "description": "You overhear useful information about job opportunities",
                "outcome": "You learn about potential work or business opportunities in the area."
            }
        ]
        
        encounter = random.choice(social_encounters)
        
        embed = discord.Embed(
            title="👥 Social Interaction",
            description=f"**{char_name}** {encounter['description']}.",
            color=0x20b2aa
        )
        
        embed.add_field(name="💬 Outcome", value=encounter['outcome'], inline=False)
        
        # Small chance of gaining reputation or credits from social interactions
        if random.random() < 0.15:  # 15% chance
            bonus_type = random.choice(["credits", "reputation"])
            if bonus_type == "credits":
                bonus_amount = random.randint(5, 25)
                self.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (bonus_amount, interaction.user.id)
                )
                embed.add_field(name="💰 Bonus", value=f"Someone appreciated your company! +{bonus_amount} credits", inline=False)
            else:
                embed.add_field(name="⭐ Bonus", value="Your positive interaction improved your local standing!", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_wait_comfortably(self, interaction, char_name: str, hp: int, max_hp: int):
        """Handle waiting comfortably in transit lounge"""  
        message = "You find peace in the quiet moments, letting the gentle hum of the station wash over you."
        
        embed = discord.Embed(
            title="🛋️ Comfortable Wait",
            description=f"**{char_name}** settles into the comfortable transit lounge.",
            color=0x9370db
        )
        embed.add_field(name="😌 Comfort", value=message, inline=False)
        embed.add_field(name="⏱️ Time", value="You pass the time in pleasant relaxation.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_schedules(self, interaction, char_name: str):
        """Handle checking transit schedules"""
        import random
        
        schedule_info = [
            "📅 Next corridor opening: 15 minutes",
            "🚀 Express service to major hub: 2 hours",
            "🛸 Local shuttle departures: Every 30 minutes",
            "⏰ Gate maintenance window: 3-4 hours daily",
            "🎯 Priority transit available for emergency travel",
            "📊 Current corridor stability: 87% optimal"
        ]
        
        embed = discord.Embed(
            title="⏱️ Transit Schedules",
            description=f"**{char_name}** reviews current transit information.",
            color=0x4682b4
        )
        embed.add_field(name="📋 Schedule Info", value="\n".join(random.sample(schedule_info, 4)), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_travel_info(self, interaction, char_name: str):
        """Handle getting travel information"""
        import random
        
        travel_tips = [
            "🗺️ Corridor maps show optimal routes to major destinations",
            "⚠️ Current hazard warnings for specific corridor segments",
            "💰 Transit fees and fuel costs for various destinations",
            "🛡️ Safety protocols for corridor travel procedures",
            "📡 Communication relay points along major routes",
            "🔧 Emergency repair stations and their service capabilities"
        ]
        
        embed = discord.Embed(
            title="🗺️ Travel Information",
            description=f"**{char_name}** gathers helpful travel information.",
            color=0x32cd32
        )
        embed.add_field(name="ℹ️ Travel Tips", value="\n".join(random.sample(travel_tips, 3)), inline=False)
        embed.add_field(name="🎯 Planning", value="This information will help you plan your journey more effectively.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Additional placeholder methods for any remaining services:
    async def _handle_generic_service(self, interaction, service_type: str, char_name: str):
        """Handle generic/flavor services that don't have specific implementations yet"""
        import random
        
        generic_responses = {
            "equipment_mods": "You browse available modifications, but nothing catches your eye right now.",
            "ship_storage": "Storage services are available, but you don't need them at the moment.",
            "cargo_services": "Cargo handling services are ready when you need them.",
            "check_prices": "You review current market prices and make mental notes.",
            "specialty_vendors": "You browse specialty items but don't find anything you need right now.",
            "request_escort": "Security services are available if you need an escort.",
            "file_complaint": "Administrative services are ready to process any complaints.",
            "rest_recuperate": "You take some time to rest and recover.",
            "security_scan": "Security procedures are in place for your safety.",
            "transit_papers": "Documentation services are available when needed.",
            "fuel_quality": "Fuel quality meets all safety standards.",
            "pre_transit_check": "All systems check out for safe travel.",
            "emergency_repairs": "Emergency services are standing by if needed.",
            "search_supplies": "You search but find nothing useful at the moment.",
            "scavenge_parts": "Scavenging yields no results this time.",
            "emergency_medical": "Emergency medical services are available if needed."
        }
        
        response = generic_responses.get(service_type, "You interact with the service but find nothing of immediate interest.")
        
        embed = discord.Embed(
            title="🏢 Service Interaction",
            description=f"**{char_name}** uses the available services.",
            color=0x708090
        )
        embed.add_field(name="📋 Result", value=response, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        """Handle view errors gracefully"""
        print(f"❌ SubLocationServiceView error: {error}")
        import traceback
        traceback.print_exc()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=False
                )
            else:
                await interaction.followup.send(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=False
                )
        except:
            pass

    # Gate service handlers
    async def _handle_manifest_review(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo inspection - manifest review"""
        embed = discord.Embed(
            title="📋 Manifest Review",
            description=f"**{char_name}** reviews cargo manifests with gate security. All documentation appears to be in order.",
            color=0x4169E1
        )
        embed.add_field(name="🔍 Status", value="Documentation verified", inline=True)
        embed.add_field(name="📊 Result", value="All cargo properly declared", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_customs_declaration(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo inspection - customs declaration"""
        embed = discord.Embed(
            title="📋 Customs Declaration",
            description=f"**{char_name}** submits customs documentation. All items properly declared and fees paid.",
            color=0x4169E1
        )
        embed.add_field(name="📋 Forms", value="Completed successfully", inline=True)
        embed.add_field(name="💰 Fees", value="All duties settled", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_cargo_scan(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo inspection - cargo scan"""
        embed = discord.Embed(
            title="🔍 Cargo Scan",
            description=f"**{char_name}** submits to cargo scanning procedures. All items cleared for transit.",
            color=0x4169E1
        )
        embed.add_field(name="📡 Scan Result", value="No contraband detected", inline=True)
        embed.add_field(name="✅ Status", value="Cleared for passage", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_schedule_cleaning(self, interaction: discord.Interaction, char_name: str):
        """Handle vessel wash - schedule cleaning"""
        embed = discord.Embed(
            title="🚿 Schedule Cleaning",
            description=f"**{char_name}** schedules vessel cleaning services. Your ship will be spotless for the next leg of your journey.",
            color=0x4169E1
        )
        embed.add_field(name="⏰ Time Slot", value="Next available bay", inline=True)
        embed.add_field(name="🧽 Service", value="Full exterior wash", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_decontamination_check(self, interaction: discord.Interaction, char_name: str):
        """Handle vessel wash - decontamination check"""
        embed = discord.Embed(
            title="🧪 Decontamination Check",
            description=f"**{char_name}** undergoes decontamination screening. No harmful substances detected.",
            color=0x4169E1
        )
        embed.add_field(name="🔬 Scan Result", value="All clear", inline=True)
        embed.add_field(name="✅ Status", value="Decontamination complete", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_hull_inspection(self, interaction: discord.Interaction, char_name: str):
        """Handle vessel wash - hull inspection"""
        embed = discord.Embed(
            title="🔍 Hull Inspection",
            description=f"**{char_name}** requests hull integrity inspection. Your vessel passes all safety checks.",
            color=0x4169E1
        )
        embed.add_field(name="🔧 Integrity", value="Structural sound", inline=True)
        embed.add_field(name="📋 Report", value="No repairs needed", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_reserve_bunk(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot quarters - reserve bunk"""
        embed = discord.Embed(
            title="🛏️ Reserve Bunk",
            description=f"**{char_name}** reserves a sleeping quarters. A comfortable bunk awaits your rest.",
            color=0x4169E1
        )
        embed.add_field(name="🏠 Accommodation", value="Standard pilot quarters", inline=True)
        embed.add_field(name="⏰ Duration", value="8-hour standard rest", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_in_out(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot quarters - check in/out"""
        embed = discord.Embed(
            title="📝 Check In/Out",
            description=f"**{char_name}** completes quarters check-in procedures. Welcome to your temporary accommodations.",
            color=0x4169E1
        )
        embed.add_field(name="📋 Status", value="Successfully checked in", inline=True)
        embed.add_field(name="🔑 Access", value="Quarters unlocked", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_amenities_info(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot quarters - amenities info"""
        embed = discord.Embed(
            title="ℹ️ Amenities Information",
            description=f"**{char_name}** reviews available amenities. Standard quarters include shower, comm terminal, and refreshment station.",
            color=0x4169E1
        )
        embed.add_field(name="🚿 Facilities", value="Private refresher", inline=True)
        embed.add_field(name="📡 Comms", value="Standard terminal", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_storage_inquiry(self, interaction: discord.Interaction, char_name: str):
        """Handle freight depot - storage inquiry"""
        embed = discord.Embed(
            title="📦 Storage Inquiry",
            description=f"**{char_name}** inquires about storage options. Various freight storage solutions are available.",
            color=0x4169E1
        )
        embed.add_field(name="📊 Capacity", value="Multiple bay sizes", inline=True)
        embed.add_field(name="💰 Rates", value="Competitive pricing", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_schedule_pickup(self, interaction: discord.Interaction, char_name: str):
        """Handle freight depot - schedule pickup"""
        embed = discord.Embed(
            title="🚚 Schedule Pickup",
            description=f"**{char_name}** schedules freight pickup. Your cargo will be ready for collection.",
            color=0x4169E1
        )
        embed.add_field(name="⏰ Time", value="Next available slot", inline=True)
        embed.add_field(name="📋 Status", value="Pickup scheduled", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_track_shipment(self, interaction: discord.Interaction, char_name: str):
        """Handle freight depot - track shipment"""
        embed = discord.Embed(
            title="📍 Track Shipment",
            description=f"**{char_name}** checks shipment tracking. All cargo accounted for and on schedule.",
            color=0x4169E1
        )
        embed.add_field(name="📦 Status", value="In transit", inline=True)
        embed.add_field(name="📍 Location", value="On schedule", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_browse_parts(self, interaction: discord.Interaction, char_name: str):
        """Handle component shop - browse parts"""
        embed = discord.Embed(
            title="🔧 Browse Parts",
            description=f"**{char_name}** browses available components. Standard ship parts and upgrades in stock.",
            color=0x4169E1
        )
        embed.add_field(name="⚙️ Inventory", value="Well stocked", inline=True)
        embed.add_field(name="🔍 Quality", value="Certified components", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_emergency_kit(self, interaction: discord.Interaction, char_name: str):
        """Handle component shop - emergency kit"""
        embed = discord.Embed(
            title="🆘 Emergency Kit",
            description=f"**{char_name}** examines emergency repair kits. Essential supplies for critical repairs.",
            color=0x4169E1
        )
        embed.add_field(name="🔧 Contents", value="Basic repair tools", inline=True)
        embed.add_field(name="✅ Status", value="Ready for use", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_technical_support(self, interaction: discord.Interaction, char_name: str):
        """Handle component shop - technical support"""
        embed = discord.Embed(
            title="💬 Technical Support",
            description=f"**{char_name}** consults with technical specialists. Expert advice on ship maintenance and repairs.",
            color=0x4169E1
        )
        embed.add_field(name="👨‍🔧 Expert", value="Certified technician", inline=True)
        embed.add_field(name="📋 Advice", value="Maintenance tips provided", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_order_food(self, interaction: discord.Interaction, char_name: str):
        """Handle travel cafe - order food"""
        embed = discord.Embed(
            title="🍽️ Order Food",
            description=f"**{char_name}** orders from the travel cafe menu. Fresh meals to fuel your journey.",
            color=0x4169E1
        )
        embed.add_field(name="🍕 Menu", value="Traveler favorites", inline=True)
        embed.add_field(name="⏰ Service", value="Quick preparation", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_local_specialties(self, interaction: discord.Interaction, char_name: str):
        """Handle travel cafe - local specialties"""
        embed = discord.Embed(
            title="🌟 Local Specialties",
            description=f"**{char_name}** samples regional cuisine. Unique flavors from across the galaxy.",
            color=0x4169E1
        )
        embed.add_field(name="🍜 Specialty", value="Regional delicacies", inline=True)
        embed.add_field(name="👨‍🍳 Chef", value="Local recipes", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_take_break(self, interaction: discord.Interaction, char_name: str):
        """Handle travel cafe - take break"""
        embed = discord.Embed(
            title="☕ Take Break",
            description=f"**{char_name}** takes a relaxing break. A moment to recharge before continuing your journey.",
            color=0x4169E1
        )
        embed.add_field(name="😌 Relaxation", value="Well-deserved rest", inline=True)
        embed.add_field(name="☕ Refreshment", value="Energy restored", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_child_care_info(self, interaction: discord.Interaction, char_name: str):
        """Handle family area - child care info"""
        embed = discord.Embed(
            title="👶 Child Care Information",
            description=f"**{char_name}** learns about family services. Safe and supervised activities for young travelers.",
            color=0x4169E1
        )
        embed.add_field(name="👨‍👩‍👧‍👦 Services", value="Family-friendly facilities", inline=True)
        embed.add_field(name="🎮 Activities", value="Safe entertainment", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_family_services(self, interaction: discord.Interaction, char_name: str):
        """Handle family area - family services"""
        embed = discord.Embed(
            title="👨‍👩‍👧‍👦 Family Services",
            description=f"**{char_name}** explores family amenities. Comfortable spaces designed for traveling families.",
            color=0x4169E1
        )
        embed.add_field(name="🏠 Facilities", value="Family-oriented spaces", inline=True)
        embed.add_field(name="🤝 Support", value="Family assistance available", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_rest_together(self, interaction: discord.Interaction, char_name: str):
        """Handle family area - rest together"""
        embed = discord.Embed(
            title="🛋️ Rest Together",
            description=f"**{char_name}** enjoys quality family time. A peaceful moment together during your travels.",
            color=0x4169E1
        )
        embed.add_field(name="👨‍👩‍👧‍👦 Together", value="Family bonding time", inline=True)
        embed.add_field(name="😌 Peaceful", value="Relaxing atmosphere", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_book_pod(self, interaction: discord.Interaction, char_name: str):
        """Handle passenger pods - book pod"""
        embed = discord.Embed(
            title="🚀 Book Pod",
            description=f"**{char_name}** reserves a passenger pod. Comfortable private transit for your journey.",
            color=0x4169E1
        )
        embed.add_field(name="🎫 Booking", value="Pod reserved", inline=True)
        embed.add_field(name="🛏️ Comfort", value="Premium seating", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_availability(self, interaction: discord.Interaction, char_name: str):
        """Handle passenger pods - check availability"""
        embed = discord.Embed(
            title="📅 Check Availability",
            description=f"**{char_name}** checks pod availability. Multiple options for your travel schedule.",
            color=0x4169E1
        )
        embed.add_field(name="📊 Status", value="Pods available", inline=True)
        embed.add_field(name="⏰ Schedule", value="Flexible timing", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_pod_services(self, interaction: discord.Interaction, char_name: str):
        """Handle passenger pods - pod services"""
        embed = discord.Embed(
            title="🛎️ Pod Services",
            description=f"**{char_name}** reviews pod amenities. Premium services for comfortable travel.",
            color=0x4169E1
        )
        embed.add_field(name="🍽️ Catering", value="In-pod dining", inline=True)
        embed.add_field(name="📺 Entertainment", value="Personal screens", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_play_holo_games(self, interaction: discord.Interaction, char_name: str):
        """Handle entertainment lounge - play holo games"""
        embed = discord.Embed(
            title="🎮 Holo Games",
            description=f"**{char_name}** enjoys holographic entertainment. Immersive gaming experiences await.",
            color=0x4169E1
        )
        embed.add_field(name="🎯 Games", value="Multiple options", inline=True)
        embed.add_field(name="🌟 Experience", value="Fully immersive", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_holo_games(self, interaction: discord.Interaction, char_name: str):
        """Handle entertainment hub - holo games"""
        embed = discord.Embed(
            title="🎮 Holographic Games",
            description=f"**{char_name}** accesses the holographic game system. Advanced entertainment technology provides immersive experiences.",
            color=0x4169E1
        )
        embed.add_field(name="🎯 Available Games", value="Strategy, adventure, simulation", inline=True)
        embed.add_field(name="🌟 Features", value="Full sensory immersion", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_vr_experience(self, interaction: discord.Interaction, char_name: str):
        """Handle entertainment lounge - VR experience"""
        embed = discord.Embed(
            title="🥽 VR Experience",
            description=f"**{char_name}** enters virtual reality worlds. Escape to fantastic digital realms.",
            color=0x4169E1
        )
        embed.add_field(name="🌍 Worlds", value="Endless possibilities", inline=True)
        embed.add_field(name="✨ Reality", value="Breathtaking visuals", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_virtual_reality(self, interaction: discord.Interaction, char_name: str):
        """Handle entertainment hub - virtual reality"""
        embed = discord.Embed(
            title="🥽 Virtual Reality",
            description=f"**{char_name}** enters an advanced virtual reality chamber. Next-generation immersion technology awaits.",
            color=0x4169E1
        )
        embed.add_field(name="🌍 Virtual Worlds", value="Limitless exploration", inline=True)
        embed.add_field(name="🎮 Experiences", value="Interactive adventures", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_music_media(self, interaction: discord.Interaction, char_name: str):
        """Handle entertainment hub - music and media"""
        embed = discord.Embed(
            title="🎵 Music & Media",
            description=f"**{char_name}** accesses the multimedia entertainment system. High-quality audio and visual content from across the galaxy.",
            color=0x4169E1
        )
        embed.add_field(name="🎶 Music Library", value="Galactic collection", inline=True)
        embed.add_field(name="📺 Media Center", value="Movies, shows, documentaries", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_social_activities(self, interaction: discord.Interaction, char_name: str):
        """Handle entertainment lounge - social activities"""
        embed = discord.Embed(
            title="👥 Social Activities",
            description=f"**{char_name}** joins other travelers. Meet fellow explorers and share stories.",
            color=0x4169E1
        )
        embed.add_field(name="🤝 Community", value="Fellow travelers", inline=True)
        embed.add_field(name="💬 Stories", value="Shared experiences", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_route_planning(self, interaction: discord.Interaction, char_name: str):
        """Handle travel services - route planning"""
        embed = discord.Embed(
            title="🗺️ Route Planning",
            description=f"**{char_name}** plans optimal travel routes. Expert guidance for efficient journeys.",
            color=0x4169E1
        )
        embed.add_field(name="📍 Routes", value="Optimized paths", inline=True)
        embed.add_field(name="⏱️ Efficiency", value="Time-saving routes", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_book_passage(self, interaction: discord.Interaction, char_name: str):
        """Handle travel services - book passage"""
        embed = discord.Embed(
            title="🎫 Book Passage",
            description=f"**{char_name}** books travel arrangements. Secure your journey to distant destinations.",
            color=0x4169E1
        )
        embed.add_field(name="✈️ Transport", value="Passage confirmed", inline=True)
        embed.add_field(name="📋 Details", value="All arrangements set", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_travel_insurance(self, interaction: discord.Interaction, char_name: str):
        """Handle travel services - travel insurance"""
        embed = discord.Embed(
            title="🛡️ Travel Insurance",
            description=f"**{char_name}** reviews insurance options. Protect yourself against the unexpected.",
            color=0x4169E1
        )
        embed.add_field(name="🔒 Coverage", value="Comprehensive protection", inline=True)
        embed.add_field(name="💰 Value", value="Affordable peace of mind", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Outpost service handlers
    async def _handle_review_samples(self, interaction: discord.Interaction, char_name: str):
        """Handle survey lab - review samples"""
        embed = discord.Embed(
            title="🧪 Review Samples",
            description=f"**{char_name}** examines collected specimens. Scientific analysis reveals interesting discoveries.",
            color=0x9932CC
        )
        embed.add_field(name="🔬 Analysis", value="Specimens catalogued", inline=True)
        embed.add_field(name="📋 Results", value="Data recorded", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_data_analysis(self, interaction: discord.Interaction, char_name: str):
        """Handle survey lab - data analysis"""
        embed = discord.Embed(
            title="📊 Data Analysis",
            description=f"**{char_name}** processes survey data. Complex patterns emerge from the scientific measurements.",
            color=0x9932CC
        )
        embed.add_field(name="📈 Processing", value="Data analyzed", inline=True)
        embed.add_field(name="🎯 Patterns", value="Correlations found", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_equipment_check(self, interaction: discord.Interaction, char_name: str):
        """Handle survey lab - equipment check"""
        embed = discord.Embed(
            title="🔧 Equipment Check",
            description=f"**{char_name}** inspects laboratory equipment. All instruments are calibrated and functioning properly.",
            color=0x9932CC
        )
        embed.add_field(name="⚙️ Status", value="All systems nominal", inline=True)
        embed.add_field(name="📏 Calibration", value="Within specifications", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_sample_catalog(self, interaction: discord.Interaction, char_name: str):
        """Handle core storage - sample catalog"""
        embed = discord.Embed(
            title="📂 Sample Catalog",
            description=f"**{char_name}** reviews the specimen inventory. Extensive collection of geological and biological samples.",
            color=0x9932CC
        )
        embed.add_field(name="📚 Catalog", value="Comprehensive database", inline=True)
        embed.add_field(name="🗃️ Storage", value="Organized by type", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_access_records(self, interaction: discord.Interaction, char_name: str):
        """Handle core storage - access records"""
        embed = discord.Embed(
            title="📝 Access Records",
            description=f"**{char_name}** checks storage access logs. All sample retrievals properly documented.",
            color=0x9932CC
        )
        embed.add_field(name="🔐 Security", value="Access controlled", inline=True)
        embed.add_field(name="📋 Logs", value="All activities tracked", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_environmental_check(self, interaction: discord.Interaction, char_name: str):
        """Handle core storage - environmental check"""
        embed = discord.Embed(
            title="🌡️ Environmental Check",
            description=f"**{char_name}** monitors storage conditions. Temperature and humidity within optimal ranges.",
            color=0x9932CC
        )
        embed.add_field(name="🌡️ Temperature", value="Stable conditions", inline=True)
        embed.add_field(name="💧 Humidity", value="Controlled environment", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_monitor_operations(self, interaction: discord.Interaction, char_name: str):
        """Handle mining control - monitor operations"""
        embed = discord.Embed(
            title="⛏️ Monitor Operations",
            description=f"**{char_name}** oversees mining activities. All extraction operations proceeding smoothly.",
            color=0x9932CC
        )
        embed.add_field(name="⚡ Operations", value="Running efficiently", inline=True)
        embed.add_field(name="📊 Output", value="Meeting quotas", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_equipment_status(self, interaction: discord.Interaction, char_name: str):
        """Handle mining control - equipment status"""
        embed = discord.Embed(
            title="🔧 Equipment Status",
            description=f"**{char_name}** checks mining machinery. All systems operational and maintenance up to date.",
            color=0x9932CC
        )
        embed.add_field(name="⚙️ Machinery", value="Fully operational", inline=True)
        embed.add_field(name="🔧 Maintenance", value="Scheduled and current", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_production_reports(self, interaction: discord.Interaction, char_name: str):
        """Handle mining control - production reports"""
        embed = discord.Embed(
            title="📈 Production Reports",
            description=f"**{char_name}** reviews extraction statistics. Output levels consistent with projections.",
            color=0x9932CC
        )
        embed.add_field(name="📊 Output", value="On target", inline=True)
        embed.add_field(name="📈 Trends", value="Steady progress", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_processing(self, interaction: discord.Interaction, char_name: str):
        """Handle refinery module - check processing"""
        embed = discord.Embed(
            title="⚗️ Check Processing",
            description=f"**{char_name}** monitors refinery operations. Raw materials being processed efficiently.",
            color=0x9932CC
        )
        embed.add_field(name="⚗️ Refining", value="Processing smoothly", inline=True)
        embed.add_field(name="📊 Efficiency", value="Optimal throughput", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_quality_control(self, interaction: discord.Interaction, char_name: str):
        """Handle refinery module - quality control"""
        embed = discord.Embed(
            title="✅ Quality Control",
            description=f"**{char_name}** inspects refined products. All output meets quality standards.",
            color=0x9932CC
        )
        embed.add_field(name="🔍 Inspection", value="Standards met", inline=True)
        embed.add_field(name="✅ Quality", value="Certified grade", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_output_status(self, interaction: discord.Interaction, char_name: str):
        """Handle refinery module - output status"""
        embed = discord.Embed(
            title="📦 Output Status",
            description=f"**{char_name}** checks refined material stockpiles. Inventory levels adequate for operations.",
            color=0x9932CC
        )
        embed.add_field(name="📦 Inventory", value="Well stocked", inline=True)
        embed.add_field(name="📊 Status", value="Production on schedule", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_scan_readings(self, interaction: discord.Interaction, char_name: str):
        """Handle sensor array - scan readings"""
        embed = discord.Embed(
            title="📡 Scan Readings",
            description=f"**{char_name}** reviews sensor data. Long-range scans detecting various astronomical phenomena.",
            color=0x9932CC
        )
        embed.add_field(name="📡 Sensors", value="Detecting activity", inline=True)
        embed.add_field(name="📊 Data", value="Anomalies catalogued", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_calibrate_sensors(self, interaction: discord.Interaction, char_name: str):
        """Handle sensor array - calibrate sensors"""
        embed = discord.Embed(
            title="🎯 Calibrate Sensors",
            description=f"**{char_name}** fine-tunes sensor arrays. Detection accuracy improved across all frequencies.",
            color=0x9932CC
        )
        embed.add_field(name="🎯 Precision", value="Calibration complete", inline=True)
        embed.add_field(name="📈 Accuracy", value="Enhanced sensitivity", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_alert_status(self, interaction: discord.Interaction, char_name: str):
        """Handle sensor array - alert status"""
        embed = discord.Embed(
            title="🚨 Alert Status",
            description=f"**{char_name}** checks threat detection systems. All monitoring systems active and responsive.",
            color=0x9932CC
        )
        embed.add_field(name="🚨 Alerts", value="Systems active", inline=True)
        embed.add_field(name="👁️ Monitoring", value="Continuous surveillance", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_navigation_status(self, interaction: discord.Interaction, char_name: str):
        """Handle beacon control - navigation status"""
        embed = discord.Embed(
            title="🧭 Navigation Status",
            description=f"**{char_name}** checks navigation beacon systems. All guidance signals broadcasting clearly.",
            color=0x9932CC
        )
        embed.add_field(name="📡 Beacon", value="Signal strong", inline=True)
        embed.add_field(name="🧭 Navigation", value="Routes updated", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_signal_strength(self, interaction: discord.Interaction, char_name: str):
        """Handle beacon control - signal strength"""
        embed = discord.Embed(
            title="📶 Signal Strength",
            description=f"**{char_name}** monitors transmission power. Navigation signals maintaining optimal range.",
            color=0x9932CC
        )
        embed.add_field(name="📶 Strength", value="Maximum range", inline=True)
        embed.add_field(name="🔋 Power", value="Operating efficiently", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_maintenance_log(self, interaction: discord.Interaction, char_name: str):
        """Handle beacon control - maintenance log"""
        embed = discord.Embed(
            title="📋 Maintenance Log",
            description=f"**{char_name}** reviews system maintenance records. All service schedules up to date.",
            color=0x9932CC
        )
        embed.add_field(name="🔧 Maintenance", value="Current and complete", inline=True)
        embed.add_field(name="📅 Schedule", value="Next service planned", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_weather_data(self, interaction: discord.Interaction, char_name: str):
        """Handle weather station - weather data"""
        embed = discord.Embed(
            title="🌤️ Weather Data",
            description=f"**{char_name}** reviews atmospheric conditions. Current weather patterns stable across the region.",
            color=0x9932CC
        )
        embed.add_field(name="🌡️ Conditions", value="Stable patterns", inline=True)
        embed.add_field(name="📊 Data", value="Comprehensive readings", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_storm_tracking(self, interaction: discord.Interaction, char_name: str):
        """Handle weather station - storm tracking"""
        embed = discord.Embed(
            title="⛈️ Storm Tracking",
            description=f"**{char_name}** monitors severe weather systems. All major storm fronts tracked and predicted.",
            color=0x9932CC
        )
        embed.add_field(name="⛈️ Storms", value="Tracking systems", inline=True)
        embed.add_field(name="📈 Predictions", value="Advance warnings issued", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_atmospheric_report(self, interaction: discord.Interaction, char_name: str):
        """Handle weather station - atmospheric report"""
        embed = discord.Embed(
            title="🌬️ Atmospheric Report",
            description=f"**{char_name}** analyzes atmospheric composition. All readings within normal parameters.",
            color=0x9932CC
        )
        embed.add_field(name="🌬️ Atmosphere", value="Composition normal", inline=True)
        embed.add_field(name="📋 Report", value="Detailed analysis", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_inventory_check(self, interaction: discord.Interaction, char_name: str):
        """Handle supply depot - inventory check"""
        embed = discord.Embed(
            title="📦 Inventory Check",
            description=f"**{char_name}** reviews supply levels. Essential materials well stocked for operations.",
            color=0x9932CC
        )
        embed.add_field(name="📦 Supplies", value="Adequate stock", inline=True)
        embed.add_field(name="📊 Status", value="Inventory updated", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_request_supplies(self, interaction: discord.Interaction, char_name: str):
        """Handle supply depot - request supplies"""
        embed = discord.Embed(
            title="📋 Request Supplies",
            description=f"**{char_name}** submits supply requisition. Essential materials ordered for delivery.",
            color=0x9932CC
        )
        embed.add_field(name="📋 Request", value="Submitted successfully", inline=True)
        embed.add_field(name="🚚 Delivery", value="Scheduled arrival", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_emergency_cache(self, interaction: discord.Interaction, char_name: str):
        """Handle supply depot - emergency cache"""
        embed = discord.Embed(
            title="🆘 Emergency Cache",
            description=f"**{char_name}** inspects emergency supplies. Critical resources secured and accessible.",
            color=0x9932CC
        )
        embed.add_field(name="🆘 Emergency", value="Supplies ready", inline=True)
        embed.add_field(name="🔐 Security", value="Access verified", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_launch_drone(self, interaction: discord.Interaction, char_name: str):
        """Handle drone bay - launch drone"""
        embed = discord.Embed(
            title="🚁 Launch Drone",
            description=f"**{char_name}** deploys reconnaissance drone. Automated survey mission initiated.",
            color=0x9932CC
        )
        embed.add_field(name="🚁 Drone", value="Mission launched", inline=True)
        embed.add_field(name="📡 Telemetry", value="Signal established", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_maintenance_check(self, interaction: discord.Interaction, char_name: str):
        """Handle drone bay - maintenance check"""
        embed = discord.Embed(
            title="🔧 Maintenance Check",
            description=f"**{char_name}** inspects drone fleet. All units serviced and ready for deployment.",
            color=0x9932CC
        )
        embed.add_field(name="🔧 Service", value="Maintenance complete", inline=True)
        embed.add_field(name="✅ Status", value="Fleet ready", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_mission_planning(self, interaction: discord.Interaction, char_name: str):
        """Handle drone bay - mission planning"""
        embed = discord.Embed(
            title="📋 Mission Planning",
            description=f"**{char_name}** designs drone operations. Survey routes optimized for maximum coverage.",
            color=0x9932CC
        )
        embed.add_field(name="📋 Planning", value="Mission designed", inline=True)
        embed.add_field(name="🎯 Objectives", value="Routes optimized", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_containment_status(self, interaction: discord.Interaction, char_name: str):
        """Handle isolation ward - containment status"""
        embed = discord.Embed(
            title="🔒 Containment Status",
            description=f"**{char_name}** checks isolation protocols. All containment systems operating normally.",
            color=0x9932CC
        )
        embed.add_field(name="🔒 Containment", value="Secure protocols", inline=True)
        embed.add_field(name="✅ Status", value="Systems nominal", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_decontamination(self, interaction: discord.Interaction, char_name: str):
        """Handle isolation ward - decontamination"""
        embed = discord.Embed(
            title="🧼 Decontamination",
            description=f"**{char_name}** undergoes sterilization procedures. All contamination risks eliminated.",
            color=0x9932CC
        )
        embed.add_field(name="🧼 Sterilization", value="Procedure complete", inline=True)
        embed.add_field(name="✅ Clear", value="No contamination", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_emergency_protocol(self, interaction: discord.Interaction, char_name: str):
        """Handle isolation ward - emergency protocol"""
        embed = discord.Embed(
            title="🚨 Emergency Protocol",
            description=f"**{char_name}** reviews emergency procedures. All safety protocols current and accessible.",
            color=0x9932CC
        )
        embed.add_field(name="🚨 Protocol", value="Procedures ready", inline=True)
        embed.add_field(name="📋 Safety", value="Measures in place", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Station/Colony service handlers
    async def _handle_production_status(self, interaction: discord.Interaction, char_name: str):
        """Handle manufacturing bay - production status"""
        embed = discord.Embed(
            title="🏭 Production Status",
            description=f"**{char_name}** reviews manufacturing operations. All production lines operating at optimal capacity.",
            color=0x228B22
        )
        embed.add_field(name="🏭 Manufacturing", value="Full capacity", inline=True)
        embed.add_field(name="📊 Output", value="Meeting targets", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_order_processing(self, interaction: discord.Interaction, char_name: str):
        """Handle manufacturing bay - order processing"""
        embed = discord.Embed(
            title="📋 Order Processing",
            description=f"**{char_name}** checks manufacturing orders. Current queue being processed efficiently.",
            color=0x228B22
        )
        embed.add_field(name="📋 Orders", value="Queue processing", inline=True)
        embed.add_field(name="⏰ Schedule", value="On time delivery", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_reactor_status(self, interaction: discord.Interaction, char_name: str):
        """Handle fusion reactor - reactor status"""
        embed = discord.Embed(
            title="⚛️ Reactor Status",
            description=f"**{char_name}** monitors fusion reactor core. All systems operating within normal parameters.",
            color=0x228B22
        )
        embed.add_field(name="⚛️ Fusion", value="Stable reaction", inline=True)
        embed.add_field(name="📊 Output", value="Optimal efficiency", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_safety_check(self, interaction: discord.Interaction, char_name: str):
        """Handle fusion reactor - safety check"""
        embed = discord.Embed(
            title="🛡️ Safety Check",
            description=f"**{char_name}** performs safety inspection. All reactor safety systems functioning properly.",
            color=0x228B22
        )
        embed.add_field(name="🛡️ Safety", value="All systems green", inline=True)
        embed.add_field(name="🔐 Security", value="Containment secure", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_power_output(self, interaction: discord.Interaction, char_name: str):
        """Handle fusion reactor - power output"""
        embed = discord.Embed(
            title="⚡ Power Output",
            description=f"**{char_name}** monitors energy generation. Power grid receiving steady, reliable energy.",
            color=0x228B22
        )
        embed.add_field(name="⚡ Generation", value="Stable output", inline=True)
        embed.add_field(name="🔋 Grid", value="Full capacity", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_loading_schedule(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo bay - loading schedule"""
        embed = discord.Embed(
            title="📦 Loading Schedule",
            description=f"**{char_name}** reviews cargo operations. All shipments scheduled for efficient loading.",
            color=0x228B22
        )
        embed.add_field(name="📦 Cargo", value="Scheduled loading", inline=True)
        embed.add_field(name="⏰ Timeline", value="On schedule", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_storage_request(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo bay - storage request"""
        embed = discord.Embed(
            title="🗃️ Storage Request",
            description=f"**{char_name}** submits storage requisition. Bay space allocated for your cargo needs.",
            color=0x228B22
        )
        embed.add_field(name="🗃️ Space", value="Bay allocated", inline=True)
        embed.add_field(name="📋 Request", value="Approved", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_waste_processing(self, interaction: discord.Interaction, char_name: str):
        """Handle recycling center - waste processing"""
        embed = discord.Embed(
            title="♻️ Waste Processing",
            description=f"**{char_name}** monitors recycling operations. Material recovery systems operating efficiently.",
            color=0x228B22
        )
        embed.add_field(name="♻️ Processing", value="Active recycling", inline=True)
        embed.add_field(name="📊 Recovery", value="High efficiency", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_material_status(self, interaction: discord.Interaction, char_name: str):
        """Handle recycling center - material status"""
        embed = discord.Embed(
            title="📊 Material Status",
            description=f"**{char_name}** checks recyclable inventory. Good variety of materials available for processing.",
            color=0x228B22
        )
        embed.add_field(name="📊 Inventory", value="Well stocked", inline=True)
        embed.add_field(name="♻️ Types", value="Various materials", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_drop_off_items(self, interaction: discord.Interaction, char_name: str):
        """Handle recycling center - drop off items"""
        embed = discord.Embed(
            title="📦 Drop Off Items",
            description=f"**{char_name}** delivers materials for recycling. Items accepted for processing.",
            color=0x228B22
        )
        embed.add_field(name="📦 Delivery", value="Materials accepted", inline=True)
        embed.add_field(name="♻️ Processing", value="Queue added", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_quiet_reflection(self, interaction: discord.Interaction, char_name: str):
        """Handle chapel - quiet reflection"""
        embed = discord.Embed(
            title="🕊️ Quiet Reflection",
            description=f"**{char_name}** finds peace in meditation. A moment of tranquility amid the vast cosmos.",
            color=0x228B22
        )
        embed.add_field(name="🧘 Meditation", value="Inner peace", inline=True)
        embed.add_field(name="🕊️ Serenity", value="Mind cleared", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_community_service(self, interaction: discord.Interaction, char_name: str):
        """Handle chapel - community service"""
        embed = discord.Embed(
            title="🤝 Community Service",
            description=f"**{char_name}** participates in community outreach. Contributing to the welfare of fellow residents.",
            color=0x228B22
        )
        embed.add_field(name="🤝 Service", value="Community aid", inline=True)
        embed.add_field(name="❤️ Contribution", value="Helping others", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_spiritual_guidance(self, interaction: discord.Interaction, char_name: str):
        """Handle chapel - spiritual guidance"""
        embed = discord.Embed(
            title="✨ Spiritual Guidance",
            description=f"**{char_name}** seeks wisdom and comfort. Finding strength in spiritual contemplation.",
            color=0x228B22
        )
        embed.add_field(name="✨ Guidance", value="Wisdom shared", inline=True)
        embed.add_field(name="💫 Comfort", value="Spirit renewed", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_view_exhibitions(self, interaction: discord.Interaction, char_name: str):
        """Handle art gallery - view exhibitions"""
        embed = discord.Embed(
            title="🎨 View Exhibitions",
            description=f"**{char_name}** explores artistic displays. Remarkable works from across the galaxy on display.",
            color=0x228B22
        )
        embed.add_field(name="🎨 Art", value="Diverse collections", inline=True)
        embed.add_field(name="🌌 Culture", value="Galactic heritage", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_artist_information(self, interaction: discord.Interaction, char_name: str):
        """Handle art gallery - artist information"""
        embed = discord.Embed(
            title="👨‍🎨 Artist Information",
            description=f"**{char_name}** learns about featured artists. Fascinating stories behind the creative minds.",
            color=0x228B22
        )
        embed.add_field(name="👨‍🎨 Artists", value="Background stories", inline=True)
        embed.add_field(name="📚 History", value="Creative journeys", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_cultural_events(self, interaction: discord.Interaction, char_name: str):
        """Handle art gallery - cultural events"""
        embed = discord.Embed(
            title="🎭 Cultural Events",
            description=f"**{char_name}** reviews upcoming cultural activities. Rich schedule of artistic programming.",
            color=0x228B22
        )
        embed.add_field(name="🎭 Events", value="Upcoming shows", inline=True)
        embed.add_field(name="📅 Schedule", value="Regular programming", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_check_shows(self, interaction: discord.Interaction, char_name: str):
        """Handle theater - check shows"""
        embed = discord.Embed(
            title="🎭 Check Shows",
            description=f"**{char_name}** browses performance listings. Excellent productions scheduled for entertainment.",
            color=0x228B22
        )
        embed.add_field(name="🎭 Productions", value="Quality shows", inline=True)
        embed.add_field(name="🎫 Availability", value="Tickets available", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_book_tickets(self, interaction: discord.Interaction, char_name: str):
        """Handle theater - book tickets"""
        embed = discord.Embed(
            title="🎫 Book Tickets",
            description=f"**{char_name}** reserves performance seats. Your entertainment is secured for the evening.",
            color=0x228B22
        )
        embed.add_field(name="🎫 Tickets", value="Seats reserved", inline=True)
        embed.add_field(name="🎭 Show", value="Performance confirmed", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_performance_schedule(self, interaction: discord.Interaction, char_name: str):
        """Handle theater - performance schedule"""
        embed = discord.Embed(
            title="📅 Performance Schedule",
            description=f"**{char_name}** reviews show times. Comprehensive listing of all upcoming performances.",
            color=0x228B22
        )
        embed.add_field(name="📅 Schedule", value="All show times", inline=True)
        embed.add_field(name="🎭 Variety", value="Multiple genres", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_browse_market(self, interaction: discord.Interaction, char_name: str):
        """Handle plaza - browse market"""
        embed = discord.Embed(
            title="🛒 Browse Market",
            description=f"**{char_name}** explores the marketplace. Vendors offering goods from across the system.",
            color=0x228B22
        )
        embed.add_field(name="🛒 Market", value="Diverse vendors", inline=True)
        embed.add_field(name="🌟 Goods", value="Unique items", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_meet_people(self, interaction: discord.Interaction, char_name: str):
        """Handle plaza - meet people"""
        embed = discord.Embed(
            title="👥 Meet People",
            description=f"**{char_name}** socializes with other residents. Building connections in the community.",
            color=0x228B22
        )
        embed.add_field(name="👥 Social", value="New connections", inline=True)
        embed.add_field(name="🤝 Community", value="Friendly atmosphere", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_attend_events(self, interaction: discord.Interaction, char_name: str):
        """Handle plaza - attend events"""
        embed = discord.Embed(
            title="🎉 Attend Events",
            description=f"**{char_name}** participates in plaza activities. Community gatherings bring people together.",
            color=0x228B22
        )
        embed.add_field(name="🎉 Events", value="Community activities", inline=True)
        embed.add_field(name="👨‍👩‍👧‍👦 Gathering", value="Social engagement", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_declare_goods(self, interaction: discord.Interaction, char_name: str):
        """Handle customs office - declare goods"""
        embed = discord.Embed(
            title="📋 Declare Goods",
            description=f"**{char_name}** submits customs declaration. All items properly documented for import.",
            color=0x228B22
        )
        embed.add_field(name="📋 Declaration", value="Forms completed", inline=True)
        embed.add_field(name="✅ Status", value="Goods declared", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_tax_information(self, interaction: discord.Interaction, char_name: str):
        """Handle customs office - tax information"""
        embed = discord.Embed(
            title="💰 Tax Information",
            description=f"**{char_name}** reviews import duties. Current tax rates and exemptions clearly explained.",
            color=0x228B22
        )
        embed.add_field(name="💰 Duties", value="Rates current", inline=True)
        embed.add_field(name="📋 Info", value="Guidelines provided", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_trade_permits(self, interaction: discord.Interaction, char_name: str):
        """Handle customs office - trade permits"""
        embed = discord.Embed(
            title="📜 Trade Permits",
            description=f"**{char_name}** applies for trading authorization. Commercial permits processed efficiently.",
            color=0x228B22
        )
        embed.add_field(name="📜 Permits", value="Authorization issued", inline=True)
        embed.add_field(name="💼 Trade", value="Commerce approved", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_residency_info(self, interaction: discord.Interaction, char_name: str):
        """Handle immigration office - residency info"""
        embed = discord.Embed(
            title="🏠 Residency Information",
            description=f"**{char_name}** inquires about permanent residence. Comprehensive immigration services available.",
            color=0x228B22
        )
        embed.add_field(name="🏠 Residency", value="Options explained", inline=True)
        embed.add_field(name="📋 Process", value="Steps outlined", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_citizenship_process(self, interaction: discord.Interaction, char_name: str):
        """Handle immigration office - citizenship process"""
        embed = discord.Embed(
            title="🎖️ Citizenship Process",
            description=f"**{char_name}** learns about naturalization. Path to full citizenship clearly defined.",
            color=0x228B22
        )
        embed.add_field(name="🎖️ Citizenship", value="Process explained", inline=True)
        embed.add_field(name="📚 Requirements", value="Criteria outlined", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_documentation(self, interaction: discord.Interaction, char_name: str):
        """Handle immigration office - documentation"""
        embed = discord.Embed(
            title="📑 Documentation",
            description=f"**{char_name}** submits required paperwork. All immigration documents processed efficiently.",
            color=0x228B22
        )
        embed.add_field(name="📑 Documents", value="Papers filed", inline=True)
        embed.add_field(name="✅ Status", value="Processing begun", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Cargo Inspection Bay handlers
    async def _handle_inspect_cargo(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo inspection service"""
        import random
        
        # Get character data for money check
        char_info = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character data not found.", ephemeral=False)
            return
        
        money = char_info[0]
        cost = 50
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford cargo inspection services.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        inspection_results = [
            "All cargo containers verified - no contraband detected",
            "Manifest records match physical inventory - inspection passed",
            "Biometric seals intact - cargo authenticity confirmed",
            "Standard freight inspection complete - cleared for transit",
            "Documentation verified - all items within legal parameters"
        ]
        
        inspection_details = [
            "Scanner arrays analyze each container's contents",
            "Automated systems cross-reference manifest data",
            "Chemical sensors detect no prohibited substances",
            "Weight and volume measurements confirm accuracy",
            "Digital signatures validate cargo authentication"
        ]
        
        result = random.choice(inspection_results)
        detail = random.choice(inspection_details)
        
        embed = discord.Embed(
            title="📦 Cargo Inspection Complete",
            description=f"**{char_name}** submits cargo for mandatory inspection.",
            color=0x4682b4
        )
        embed.add_field(name="🔍 Inspection Process", value=detail, inline=False)
        embed.add_field(name="✅ Result", value=result, inline=False)
        embed.add_field(name="📋 Status", value="Cleared for interstellar transport", inline=False)
        embed.add_field(name="💰 Inspection Fee", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_file_manifest(self, interaction: discord.Interaction, char_name: str):
        """Handle filing manifest paperwork"""
        import random
        
        # Get character data for money check
        char_info = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character data not found.", ephemeral=False)
            return
        
        money = char_info[0]
        cost = 25
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford manifest filing services.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        manifest_types = [
            "Standard Freight Manifest - Form CF-2847",
            "Hazardous Materials Declaration - Form HM-1205",
            "Live Cargo Transport Permit - Form LC-3991",
            "High-Value Goods Manifest - Form HV-7432",
            "Perishable Goods Declaration - Form PG-5618"
        ]
        
        filing_details = [
            "Digital signatures applied to all documentation",
            "Biometric verification stamps cargo authenticity", 
            "Automated systems update galactic freight database",
            "Cross-referenced with customs and excise records",
            "Blockchain verification ensures document integrity"
        ]
        
        manifest_type = random.choice(manifest_types)
        filing_detail = random.choice(filing_details)
        reference_number = f"MF-{random.randint(100000, 999999)}"
        
        embed = discord.Embed(
            title="📄 Manifest Filing Complete",
            description=f"**{char_name}** files official cargo manifest paperwork.",
            color=0x4169e1
        )
        embed.add_field(name="📋 Document Type", value=manifest_type, inline=False)
        embed.add_field(name="🔢 Reference Number", value=reference_number, inline=True)
        embed.add_field(name="⚙️ Processing", value=filing_detail, inline=False)
        embed.add_field(name="✅ Status", value="Filed and registered in galactic database", inline=False)
        embed.add_field(name="💰 Filing Fee", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_pay_transit_fee(self, interaction: discord.Interaction, char_name: str):
        """Handle transit fee payment"""
        import random
        
        # Get character data for money check
        char_info = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character data not found.", ephemeral=False)
            return
        
        money = char_info[0]
        base_cost = 75
        
        # Random surcharge system
        surcharge_types = [
            ("Standard Rate", 0),
            ("Peak Hours Surcharge", 15),
            ("Heavy Traffic Fee", 25),
            ("Priority Lane Access", 35),
            ("Express Processing", 20)
        ]
        
        surcharge_name, surcharge_amount = random.choice(surcharge_types)
        total_cost = base_cost + surcharge_amount
        
        if money < total_cost:
            # Offer basic transit option
            basic_cost = base_cost
            if money >= basic_cost:
                self.db.execute_query(
                    "UPDATE characters SET money = money - ? WHERE user_id = ?",
                    (basic_cost, interaction.user.id)
                )
                embed = discord.Embed(
                    title="🚀 Basic Transit Fee Paid",
                    description=f"**{char_name}** pays standard transit fee.",
                    color=0xffd700
                )
                embed.add_field(name="🎫 Transit Type", value="Standard Corridor Access", inline=False)
                embed.add_field(name="⏰ Processing Time", value="Standard queue (30-45 minutes)", inline=False)
                embed.add_field(name="💰 Fee Paid", value=f"{basic_cost} credits", inline=True)
                embed.add_field(name="🏦 Remaining", value=f"{money - basic_cost} credits", inline=True)
            else:
                embed = discord.Embed(
                    title="❌ Insufficient Credits",
                    description=f"**{char_name}** cannot afford transit fees.",
                    color=0xff4500
                )
                embed.add_field(name="💰 Required", value=f"{basic_cost} credits (basic transit)", inline=True)
                embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Deduct full cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        processing_benefits = [
            "Priority lane access granted",
            "Expedited customs processing", 
            "VIP lounge access included",
            "Express boarding privileges",
            "Premium service tier activated"
        ]
        
        gate_assignments = [
            "Gate Alpha-7 (Premium Corridor)",
            "Gate Beta-12 (Express Lane)",
            "Gate Gamma-3 (Priority Access)",
            "Gate Delta-9 (VIP Terminal)",
            "Gate Epsilon-5 (Fast Track)"
        ]
        
        benefit = random.choice(processing_benefits)
        gate = random.choice(gate_assignments)
        transit_id = f"TF-{random.randint(1000000, 9999999)}"
        
        embed = discord.Embed(
            title="🎫 Transit Fee Payment Complete",
            description=f"**{char_name}** successfully pays transit corridor fees.",
            color=0x00ff00
        )
        embed.add_field(name="🚪 Gate Assignment", value=gate, inline=False)
        embed.add_field(name="🎯 Service Level", value=surcharge_name, inline=True)
        embed.add_field(name="✨ Benefits", value=benefit, inline=False)
        embed.add_field(name="🆔 Transit ID", value=transit_id, inline=True)
        embed.add_field(name="💰 Total Fee", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - total_cost} credits", inline=True)
        
        if surcharge_amount > 0:
            embed.add_field(name="📊 Fee Breakdown", 
                           value=f"Base: {base_cost} + {surcharge_name}: {surcharge_amount}", 
                           inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Hull Cleaning Bay handlers
    async def _handle_hull_cleaning(self, interaction: discord.Interaction, char_name: str):
        """Handle full hull cleaning service"""
        import random
        
        char_data = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            embed = discord.Embed(title="🧽 Hull Cleaning Bay - 75C", description="Character data not found.", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        money = char_data[0]
        cost = 75
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford the full hull cleaning service.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            embed.add_field(name="ℹ️ Service Details", value="Complete hull cleaning removes all debris, micro-meteorite damage, and spatial contamination.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        self.db.execute_query("UPDATE characters SET money = money - ? WHERE user_id = ?", (cost, interaction.user.id))
        
        cleaning_outcomes = [
            "Micro-meteorite scarring polished to pristine condition",
            "Nebula particulates completely removed from hull plating",
            "Ion storm residue cleared from external sensors",
            "Deep space debris extraction and surface restoration",
            "Quantum field contamination neutralized and cleaned"
        ]
        
        embed = discord.Embed(
            title="🧽 Hull Cleaning Complete",
            description=f"**{char_name}**, your vessel has undergone comprehensive hull restoration.",
            color=0x00ff00
        )
        embed.add_field(name="🔧 Service Performed", value=random.choice(cleaning_outcomes), inline=False)
        embed.add_field(name="✨ Hull Condition", value="Restored to factory specifications", inline=False)
        embed.add_field(name="💰 Service Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - cost}", inline=True)
        embed.add_field(name="📋 Technical Notes", value="Hull integrity optimized • External sensors recalibrated • Protective coating renewed", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_radiation_scrub(self, interaction: discord.Interaction, char_name: str):
        """Handle radiation decontamination service"""
        import random
        
        char_data = self.db.execute_query("SELECT money FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
        
        if not char_data:
            embed = discord.Embed(title="☢️ Radiation Decontamination - 50C", description="Character data not found.", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        money = char_data[0]
        cost = 50
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford radiation decontamination services.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            embed.add_field(name="⚠️ Service Details", value="Specialized radiation scrubbing removes harmful isotopic contamination from hull surfaces.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        self.db.execute_query("UPDATE characters SET money = money - ? WHERE user_id = ?", (cost, interaction.user.id))
        
        radiation_sources = ["Pulsar proximity contamination", "Solar flare particle exposure", "Quantum tunnel radiation residue", "Asteroid belt radioactive dust", "Neutron star field contamination", "Cosmic ray bombardment traces"]
        decon_methods = ["Ion beam neutralization protocol", "Electromagnetic field purging sequence", "Molecular disintegration chambers", "Quantum flux stabilization process", "Particle beam decontamination sweep"]
        
        embed = discord.Embed(
            title="☢️ Radiation Scrub Complete",
            description=f"**{char_name}**, your vessel has been successfully decontaminated.",
            color=0x00ff00
        )
        embed.add_field(name="🔍 Contamination Source", value=random.choice(radiation_sources), inline=False)
        embed.add_field(name="🧪 Decontamination Method", value=random.choice(decon_methods), inline=False)
        embed.add_field(name="✅ Radiation Levels", value="Within safe operational parameters", inline=False)
        embed.add_field(name="💰 Service Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - cost}", inline=True)
        embed.add_field(name="🛡️ Safety Certification", value="Hull cleared for standard corridor transit • Crew exposure risk eliminated", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_basic_decon(self, interaction: discord.Interaction, char_name: str):
        """Handle basic decontamination service"""
        import random
        
        char_data = self.db.execute_query("SELECT money FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
        
        if not char_data:
            embed = discord.Embed(title="🛡️ Basic Decontamination - 30C", description="Character data not found.", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        money = char_data[0]
        cost = 30
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford basic decontamination services.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            embed.add_field(name="ℹ️ Service Details", value="Standard decontamination removes common space debris and surface contaminants.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        self.db.execute_query("UPDATE characters SET money = money - ? WHERE user_id = ?", (cost, interaction.user.id))
        
        basic_contaminants = ["Standard space dust accumulation", "Atmospheric entry burn residue", "Docking bay particulate matter", "Common stellar wind deposits", "Navigation beacon interference particles"]
        cleaning_procedures = ["Automated spray wash cycle", "Sonic vibration cleaning", "Electrostatic dust removal", "Pressure wash and rinse sequence", "Standard decontamination protocol"]
        
        embed = discord.Embed(
            title="🛡️ Basic Decontamination Complete",
            description=f"**{char_name}**, your vessel has received standard cleaning services.",
            color=0x00ff00
        )
        embed.add_field(name="🧹 Contaminants Removed", value=random.choice(basic_contaminants), inline=False)
        embed.add_field(name="🔧 Cleaning Method", value=random.choice(cleaning_procedures), inline=False)
        embed.add_field(name="✨ Hull Status", value="Clean and ready for operations", inline=False)
        embed.add_field(name="💰 Service Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - cost}", inline=True)
        embed.add_field(name="📋 Service Notes", value="Basic cleaning completed • Routine maintenance recommended after extended travel", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_baby_care_station(self, interaction: discord.Interaction, char_name: str):
        """Handle family zone - baby care station"""
        embed = discord.Embed(
            title="👶 Baby Care Station",
            description=f"**{char_name}** accesses dedicated childcare facilities.",
            color=0xff69b4
        )
        embed.add_field(name="🍼 Feeding Area:", value="Clean and private", inline=True)
        embed.add_field(name="🛏️ Changing Station:", value="Fully equipped", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_buy_components(self, interaction: discord.Interaction, char_name: str):
        """Handle spare parts vendor - buy components"""
        embed = discord.Embed(
            title="🔧 Ship Components",
            description=f"**{char_name}** browses available ship components at a stall, but the owner is absent.",
            color=0x708090
        )
        embed.add_field(name="⚙️ Available Parts", value="Various components", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_cargo_insurance(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo storage - cargo insurance"""
        embed = discord.Embed(
            title="📋 Cargo Insurance",
            description=f"**{char_name}** reviews insurance options for stored cargo. Protect your valuable shipments.",
            color=0x4682b4
        )
        embed.add_field(name="🛡️ Coverage Options:", value="Comprehensive protection", inline=True)
        embed.add_field(name="📊 Risk Assessment:", value="Professional evaluation", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_emergency_repair_kit(self, interaction: discord.Interaction, char_name: str):
        """Handle spare parts vendor - emergency repair kit"""
        embed = discord.Embed(
            title="🚨 Emergency Repair Kit",
            description=f"**{char_name}** examines emergency repair supplies, but they seem incompatible with their ship.",
            color=0xff4500
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_energy_drinks(self, interaction: discord.Interaction, char_name: str):
        """Handle quick food vendor - energy drinks"""
        embed = discord.Embed(
            title="⚡ Energy Drinks",
            description=f"**{char_name}** selects from various energy beverages, high-caffeine drinks to keep spacers alert on long journeys.",
            color=0x32cd32
        )
        embed.add_field(name="🥤 Drink Options:", value="Fruity, Sweet, Bitter, Tasteless and more.", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_family_rest(self, interaction: discord.Interaction, char_name: str):
        """Handle family zone - family rest"""
        embed = discord.Embed(
            title="👨‍👩‍👧‍👦 Family Rest Area",
            description=f"**{char_name}** accesses the family relaxation area, a comfortable space designed for families traveling together.",
            color=0xffd700
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_kids_play_area(self, interaction: discord.Interaction, char_name: str):
        """Handle family zone - kids play area"""
        embed = discord.Embed(
            title="🎪 Kids Play Area",
            description=f"**{char_name}** visits the children's play zone.",
            color=0xff6347
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_order_coffee(self, interaction: discord.Interaction, char_name: str):
        """Handle quick food vendor - order coffee"""
        embed = discord.Embed(
            title="☕ Fresh Coffee",
            description=f"**{char_name}** orders freshly brewed coffee.",
            color=0x8b4513
        )
        embed.add_field(name="☕ Coffee Types:", value="Various synthetic blends available", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_pilot_lounge(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot rest quarters - pilot lounge"""
        embed = discord.Embed(
            title="✈️ Pilot Lounge",
            description=f"**{char_name}** enters the exclusive pilot lounge, a relaxation space for certified pilots.",
            color=0x4169e1
        )
        embed.add_field(name="👨‍✈️ Access Level:", value="Licensed pilots only", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_premium_pod(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot rest quarters - premium pod"""
        embed = discord.Embed(
            title="🏨 Premium Sleep Pod",
            description=f"**{char_name}** books a luxury sleep pod. High-end accommodation for discerning travelers.",
            color=0xffd700
        )
        embed.add_field(name="🛏️ Comfort Level:", value="Maximum luxury", inline=True)
        embed.add_field(name="🌟 Features:", value="Premium amenities, inter-solar TV, in mattress massagers", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_quick_meal(self, interaction: discord.Interaction, char_name: str):
        """Handle quick food vendor - quick meal"""
        embed = discord.Embed(
            title="🍽️ Quick Meal",
            description=f"**{char_name}** orders a complimentary meal.",
            color=0xff8c00
        )
        embed.add_field(name="🍱 Meal Options:", value="Varied and nutritional.", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_rent_sleep_pod(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot rest quarters - rent sleep pod"""
        embed = discord.Embed(
            title="🛏️ Sleep Pod Rental",
            description=f"**{char_name}** rents a standard sleep pod..",
            color=0x87ceeb
        )
        embed.add_field(name="🏠 Pod Features", value="Clean and comfortable", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_rest_in_pod(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot rest quarters - rest in pod"""
        embed = discord.Embed(
            title="😴 Rest in Pod",
            description=f"**{char_name}** settles in for a quick rest. A private sleep pod provides peaceful environment for a nap.",
            color=0x191970
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_retrieve_cargo(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo storage - retrieve cargo"""
        embed = discord.Embed(
            title="📦 Retrieve Cargo",
            description=f"**{char_name}** accesses their cargo stored in the gate's hold.",
            color=0x8b4513
        )
        embed.add_field(name="📋 Manifest", value="Passes inventory verification", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_shower_facilities(self, interaction: discord.Interaction, char_name: str):
        """Handle pilot rest quarters - shower facilities"""
        embed = discord.Embed(
            title="🚿 Shower Facilities",
            description=f"**{char_name}** uses the shower facilities to clean themselves.",
            color=0x20b2aa
        )
        embed.add_field(name="🧼 Amenities:", value="Full hygiene facilities", inline=True)
        embed.add_field(name="💧 Water System:", value="Recycled, purified and heated for comfort", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_spare_parts(self, interaction: discord.Interaction, char_name: str):
        """Handle spare parts vendor - spare parts"""
        embed = discord.Embed(
            title="🔩 Spare Parts",
            description=f"**{char_name}** browses through the spare parts bin but finds nothing useful.",
            color=0x696969
        )
        embed.add_field(name="⚙️ Parts Available:", value="Junk", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_store_cargo(self, interaction: discord.Interaction, char_name: str):
        """Handle cargo storage - store cargo"""
        embed = discord.Embed(
            title="📦 Scan Cargo",
            description=f"**{char_name}** has their cargo processed and scanned for verification.",
            color=0x8b4513
        )
        embed.add_field(name="📋 Verification:", value="Passing all checks", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_traveler_info(self, interaction: discord.Interaction, char_name: str):
        """Handle transit center - traveler info"""
        embed = discord.Embed(
            title="ℹ️ Traveler Information",
            description=f"**{char_name}** accesses traveler information services. Current routes, schedules, and travel advisories.",
            color=0x4682b4
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_slot_machine(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle slot machine gambling game"""
        casino_cog = self.bot.get_cog('CasinoCog')
        if not casino_cog:
            await interaction.response.send_message("❌ Casino games are currently unavailable.", ephemeral=True)
            return
        
        view = casino_cog.create_slot_machine_view(interaction.user.id)
        embed = discord.Embed(
            title="🎰 Slot Machine",
            description="**How to Play:**\n"
                       "• Choose your bet amount (10-1000 credits)\n"
                       "• Hit SPIN to play!\n"
                       "• Match 3 symbols to win big!\n\n"
                       "**Payouts:**\n"
                       "🍒🍒🍒 = 2x bet\n"
                       "🍋🍋🍋 = 3x bet\n"
                       "🍊🍊🍊 = 5x bet\n"
                       "💎💎💎 = 10x bet\n"
                       "🎰🎰🎰 = 20x bet\n\n"
                       f"**Your Balance:** {money:,} credits",
            color=0xFFD700
        )
        embed.set_footer(text="⚠️ Gamble responsibly! The house always has an edge.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _handle_blackjack(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle blackjack gambling game"""
        casino_cog = self.bot.get_cog('CasinoCog')
        if not casino_cog:
            await interaction.response.send_message("❌ Casino games are currently unavailable.", ephemeral=True)
            return
        
        view = casino_cog.create_blackjack_view(interaction.user.id)
        embed = discord.Embed(
            title="🃏 Blackjack",
            description="**How to Play:**\n"
                       "• Choose your bet amount (10-1000 credits)\n"
                       "• Get as close to 21 as possible without going over\n"
                       "• Aces = 1 or 11, Face cards = 10\n"
                       "• Hit to draw cards, Stand to stop\n"
                       "• Beat the dealer to win 2x your bet!\n\n"
                       f"**Your Balance:** {money:,} credits",
            color=0x000000
        )
        embed.set_footer(text="⚠️ Gamble responsibly! The house always has an edge.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _handle_dice_roll(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle dice roll gambling game"""
        casino_cog = self.bot.get_cog('CasinoCog')
        if not casino_cog:
            await interaction.response.send_message("❌ Casino games are currently unavailable.", ephemeral=True)
            return
        
        view = casino_cog.create_dice_game_view(interaction.user.id)
        embed = discord.Embed(
            title="🎲 Dice Roll",
            description="**How to Play:**\n"
                       "• Choose your bet amount (10-1000 credits)\n"
                       "• Predict if the roll will be HIGH (8-12) or LOW (2-6)\n"
                       "• Rolling exactly 7 is a push (get your bet back)\n"
                       "• Correct guess wins 2x your bet!\n\n"
                       f"**Your Balance:** {money:,} credits",
            color=0xFF4500
        )
        embed.set_footer(text="⚠️ Gamble responsibly! The house always has an edge.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class SubLocationButton(discord.ui.Button):
    """Individual service button for sub-locations"""
    
    def __init__(self, service_type: str, **kwargs):
        super().__init__(**kwargs)
        self.service_type = service_type
    
    async def callback(self, interaction: discord.Interaction):
        # Get the view and delegate to service handler
        view = self.view
        await view.handle_service(interaction, self.service_type)


class ChangeCharacterInfoModal(discord.ui.Modal):
    """Base modal for changing character info for a price."""
    def __init__(self, title: str, field_label: str, placeholder: str, current_value: str, cost: int, bot):
        super().__init__(title=title)
        self.bot = bot
        self.db = bot.db
        self.cost = cost
        
        self.new_value_input = discord.ui.TextInput(
            label=f"{field_label} (Cost: {cost:,} credits)",
            placeholder=placeholder,
            default=current_value,
            style=discord.TextStyle.paragraph if len(current_value or "") > 100 else discord.TextStyle.short,
            max_length=1000 if len(current_value or "") > 100 else 100
        )
        self.add_item(self.new_value_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # Check character funds
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not money or money[0] < self.cost:
            await interaction.followup.send(
                f"❌ You don't have enough credits. This change costs {self.cost:,} credits.",
                ephemeral=False
            )
            return

        # Process the change
        try:
            await self.update_database(interaction, self.new_value_input.value)
            
            # Deduct cost
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (self.cost, interaction.user.id)
            )
            
            await interaction.followup.send(
                f"✅ Your information has been updated for {self.cost:,} credits.",
                ephemeral=False
            )
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid input: {e}", ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=False)

    async def update_database(self, interaction: discord.Interaction, new_value: str):
        # This method will be overridden by subclasses
        raise NotImplementedError

    # New service handlers for missing sub-location activities
    


class ChangeNameModal(ChangeCharacterInfoModal):
    async def update_database(self, interaction: discord.Interaction, new_value: str):
        self.db.execute_query(
            "UPDATE characters SET name = ? WHERE user_id = ?",
            (new_value, interaction.user.id)
        )
        # Also update their server nickname
        try:
            await interaction.user.edit(nick=new_value[:32])
        except discord.Forbidden:
            print(f"⚠️ No permission to change nickname for {interaction.user.name}")
        except Exception as e:
            print(f"❌ Error changing nickname for {interaction.user.name}: {e}")

class ChangeDescriptionModal(discord.ui.Modal):
    """Modal for changing character appearance with higher character limit."""
    def __init__(self, title: str, field_label: str, placeholder: str, current_value: str, cost: int, bot):
        super().__init__(title=title)
        self.bot = bot
        self.db = bot.db
        self.cost = cost
        
        self.new_value_input = discord.ui.TextInput(
            label=f"{field_label} (Cost: {cost:,} credits)",
            placeholder=placeholder,
            default=current_value,
            style=discord.TextStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.new_value_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # Check character funds
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not money or money[0] < self.cost:
            await interaction.followup.send(
                f"❌ You don't have enough credits. This change costs {self.cost:,} credits.",
                ephemeral=False
            )
            return

        # Update database
        try:
            await self.update_database(interaction, self.new_value_input.value)
            
            # Deduct cost
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (self.cost, interaction.user.id)
            )
            
            await interaction.followup.send(
                f"✅ Your information has been updated for {self.cost:,} credits.",
                ephemeral=False
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error updating information: {str(e)}",
                ephemeral=False
            )

    async def update_database(self, interaction: discord.Interaction, new_value: str):
        self.db.execute_query(
            "UPDATE characters SET appearance = ? WHERE user_id = ?",
            (new_value, interaction.user.id)
        )

class ChangeBioModal(discord.ui.Modal):
    """Modal for changing character biography with higher character limit."""
    def __init__(self, title: str, field_label: str, placeholder: str, current_value: str, cost: int, bot):
        super().__init__(title=title)
        self.bot = bot
        self.db = bot.db
        self.cost = cost
        
        self.new_value_input = discord.ui.TextInput(
            label=f"{field_label} (Cost: {cost:,} credits)",
            placeholder=placeholder,
            default=current_value,
            style=discord.TextStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.new_value_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # Check character funds
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not money or money[0] < self.cost:
            await interaction.followup.send(
                f"❌ You don't have enough credits. This change costs {self.cost:,} credits.",
                ephemeral=False
            )
            return

        # Update database
        try:
            await self.update_database(interaction, self.new_value_input.value)
            
            # Deduct cost
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (self.cost, interaction.user.id)
            )
            
            await interaction.followup.send(
                f"✅ Your information has been updated for {self.cost:,} credits.",
                ephemeral=False
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error updating information: {str(e)}",
                ephemeral=False
            )

    async def update_database(self, interaction: discord.Interaction, new_value: str):
        self.db.execute_query(
            "UPDATE character_identity SET biography = ? WHERE user_id = ?",
            (new_value, interaction.user.id)
        )

class ChangeDOBModal(ChangeCharacterInfoModal):
    async def update_database(self, interaction: discord.Interaction, new_value: str):
        try:
            birth_month, birth_day = map(int, new_value.split('/'))
            if not (1 <= birth_month <= 12 and 1 <= birth_day <= 31):
                raise ValueError("Date must be a valid month/day.")
        except (ValueError, IndexError):
            raise ValueError("Please use MM/DD format (e.g., 03/15).")

        self.db.execute_query(
            "UPDATE character_identity SET birth_month = ?, birth_day = ? WHERE user_id = ?",
            (birth_month, birth_day, interaction.user.id)
        )
class ChangeImageModal(ChangeCharacterInfoModal):
    async def update_database(self, interaction: discord.Interaction, new_value: str):
        # Basic URL validation
        if new_value and not (new_value.startswith('http://') or new_value.startswith('https://')):
            raise ValueError("Image URL must start with http:// or https://")
        
        # Optional: Basic image URL validation (check for common image extensions)
        if new_value:
            valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
            if not any(new_value.lower().endswith(ext) for ext in valid_extensions):
                raise ValueError("URL must link to an image file (.jpg, .jpeg, .png, .gif, .webp)")
        
        self.db.execute_query(
            "UPDATE characters SET image_url = ? WHERE user_id = ?",
            (new_value if new_value else None, interaction.user.id)
        )