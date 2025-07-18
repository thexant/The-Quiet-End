# utils/sub_locations.py
import discord
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from discord import app_commands
from discord.ext import commands
import random

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
            'hangar': {
                'name': 'Hangar Bay',
                'description': 'Large docking area where ships are serviced and stored.',
                'icon': '🚁',
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
        elif sub_data['name'] == 'Hangar Bay':
            features.extend([
                "🚁 Ship docking and storage",
                "⛽ Fuel and supply services",
                "🔧 Ship modifications",
                "📦 Cargo handling"
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
            value="This thread will auto-archive after 1 hour of inactivity. Use it to roleplay and interact with this specific area.\n Use `/area leave` to leave this area.",
            inline=False
        )
        
        # Determine sub_type for view creation
        sub_type = None
        for key, props in self.sub_location_types.items():
            if props['name'] == sub_data['name']:
                sub_type = key
                break
        
        try:
            # Send initial message
            await thread.send(embed=embed)
            
            # Send buttons in a separate message
            if sub_type:
                view = SubLocationServiceView(sub_type, location_id, self.bot)
                button_embed = discord.Embed(
                    title="🔧 Available Services",
                    description="Click the buttons below to use the services available in this area:",
                    color=0x00ff88
                )
                await thread.send(embed=button_embed, view=view)
                print(f"🏢 Sub-location welcome sent with {len(view.children)} buttons for {sub_data['name']}")
            else:
                print(f"⚠️ No sub_type found for {sub_data['name']}")
                
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
    def get_persistent_sub_locations_data(self, parent_location_id: int, location_type: str, wealth_level: int, is_derelict: bool = False) -> List[Tuple]:
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
            
        elif self.sub_type == 'hangar':
            self.add_item(SubLocationButton(
                label="Refuel Ship", 
                emoji="⛽", 
                style=discord.ButtonStyle.success,
                service_type="refuel_ship"
            ))
            self.add_item(SubLocationButton(
                label="Ship Storage", 
                emoji="🚁", 
                style=discord.ButtonStyle.secondary,
                service_type="ship_storage"
            ))
            self.add_item(SubLocationButton(
                label="Cargo Services", 
                emoji="📦", 
                style=discord.ButtonStyle.primary,
                service_type="cargo_services"
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
                label="Request Escort", 
                emoji="👮", 
                style=discord.ButtonStyle.primary,
                service_type="request_escort"
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
                service_type="traveler_info"
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
                label="Fresh Produce", 
                emoji="🥬", 
                style=discord.ButtonStyle.primary,
                service_type="fresh_produce"
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
                label="Send Message", 
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
        elif sub_type == 'historical_archive':
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
        elif service_type == "refuel_ship":
            await self._handle_refuel_ship(interaction, char_name, money)
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
        elif service_type == "request_escort":
            await self._handle_request_escort(interaction, char_name, money)
        elif service_type == "file_complaint":
            await self._handle_file_complaint(interaction, char_name)
        elif service_type == "check_traffic":
            await self._handle_check_traffic(interaction, char_name)
        elif service_type == "corridor_status":
            await self._handle_corridor_status(interaction, char_name)
        elif service_type == "rest_recuperate":
            await self._handle_rest_recuperate(interaction, char_name, money)
        elif service_type == "traveler_info":
            await self._handle_traveler_info(interaction, char_name)
        elif service_type == "security_scan":
            await self._handle_security_scan(interaction, char_name)
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
        elif service_type == "ship_storage":
            await self._handle_ship_storage(interaction, char_name, money)
        elif service_type == "cargo_services":
            await self._handle_cargo_services(interaction, char_name, money)
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
        elif service_type == "fresh_produce":
            await self._handle_fresh_produce(interaction, char_name, money)
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
            await self._handle_travel_info(interaction, char_name)
        elif service_type == "security_consult":
            await self._handle_security_consult(interaction, char_name)
        elif service_type == "browse_archives":
            await self._handle_browse_archives(interaction, char_name)
        elif service_type == "research_records":
            await self._handle_research_records(interaction, char_name)
        elif service_type == "study_figures":
            await self._handle_study_figures(interaction, char_name)
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

    
    async def _handle_rest_recuperate(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle rest and recuperation at truck stop"""
        cost = 30
        
        if money < cost:
            embed = discord.Embed(
                title="😴 Traveler Services",
                description=f"**{char_name}**, a rest pod costs {cost} credits.",
                color=0xff6600
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Check current HP to determine rest quality
        char_data = self.db.execute_query(
            "SELECT hp, max_hp FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if char_data:
            hp, max_hp = char_data
            hp_restored = min(max_hp - hp, random.randint(20, 35))
            
            # Apply healing and charge
            self.db.execute_query(
                "UPDATE characters SET hp = hp + ?, money = money - ? WHERE user_id = ?",
                (hp_restored, cost, interaction.user.id)
            )
            
            rest_quality = [
                "The sleep pod's white noise generator blocks out all corridor traffic sounds.",
                "Temperature-controlled environment and memory foam help you achieve deep sleep.",
                "You wake feeling refreshed after the pod's circadian rhythm light therapy.",
                "The isolation from ship vibrations provides the best rest you've had in weeks."
            ]
            
            embed = discord.Embed(
                title="😴 Rest Pod Session",
                description=f"**{char_name}** rents a premium rest pod for recuperation.",
                color=0x9370db
            )
            embed.add_field(name="🛏️ Rest Quality", value=random.choice(rest_quality), inline=False)
            embed.add_field(name="💚 Health Restored", value=f"+{hp_restored} HP", inline=True)
            embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
            embed.add_field(name="⏱️ Duration", value="4 hour session", inline=True)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not process rest session.",
                color=0xff0000
            )
        
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
        self.db.execute_query(
            '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (interaction.user.id, mod_name, "ship_modification", 1, description, cost)
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
        
    async def _handle_ship_storage(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle ship storage services"""
        import random
        
        storage_options = [
            ("Short-term Storage", 25, "Secure storage for up to 30 days"),
            ("Extended Storage", 60, "Long-term storage with maintenance included"),
            ("Premium Storage", 100, "Climate-controlled with full security monitoring"),
            ("Maintenance Storage", 150, "Storage with routine maintenance and inspections")
        ]
        
        storage_type, cost, description = random.choice(storage_options)
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford {storage_type} services.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Check if user has a ship
        ship_info = self.db.execute_query(
            "SELECT name FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="❌ No Ship Found",
                description="Storage services require a registered vessel.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        ship_name = ship_info[0]
        
        # Deduct cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        bay_numbers = [f"Bay {random.randint(1, 50)}-{random.choice(['A', 'B', 'C'])}" for _ in range(1)]
        
        embed = discord.Embed(
            title="🚁 Ship Storage Service",
            description=f"**{char_name}** arranges storage for the {ship_name}.",
            color=0x708090
        )
        embed.add_field(name="📦 Storage Type", value=storage_type, inline=True)
        embed.add_field(name="🏢 Location", value=random.choice(bay_numbers), inline=True)
        embed.add_field(name="📋 Details", value=description, inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        embed.add_field(name="🔒 Security", value="Your vessel is now safely stored and monitored.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    async def _handle_cargo_services(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle cargo handling services"""
        import random
        
        cargo_services = [
            ("Cargo Loading", 40, "Professional loading of goods and materials"),
            ("Cargo Unloading", 35, "Safe unloading and inventory verification"),
            ("Cargo Inspection", 20, "Detailed inspection and documentation"),
            ("Cargo Securing", 30, "Proper restraint and safety protocols"),
            ("Hazmat Handling", 80, "Specialized dangerous goods handling"),
            ("Bulk Transfer", 60, "Large volume cargo transfer operations")
        ]
        
        service_name, cost, description = random.choice(cargo_services)
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}** cannot afford {service_name} services.",
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
        
        service_details = [
            "Certified cargo handlers ensure safe transport",
            "All procedures follow galactic safety standards",
            "Documentation provided for insurance purposes",
            "Expert crew handles delicate and valuable items",
            "Advanced equipment ensures efficient operations"
        ]
        
        embed = discord.Embed(
            title="📦 Cargo Services",
            description=f"**{char_name}** arranges professional cargo handling.",
            color=0x4682b4
        )
        embed.add_field(name="🚛 Service", value=service_name, inline=True)
        embed.add_field(name="👷 Crew", value="Professional handlers", inline=True)
        embed.add_field(name="📋 Description", value=description, inline=False)
        embed.add_field(name="🔧 Details", value=random.choice(service_details), inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
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
        self.db.execute_query(
            '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (interaction.user.id, item_name, item_type, 1, description, cost)
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
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_type, quantity, description, value)
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
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, "medical", 1, description, cost)
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

    async def _handle_request_escort(self, interaction: discord.Interaction, char_name: str, money: int):
        """Handle requesting a security escort for a fee."""
        import random
        
        cost = 20

        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Credits",
                description=f"**{char_name}**, you cannot afford a security escort.",
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

        officer_names = ["Officer Jax", "Sergeant Valerius", "Corporal Thorne", "Enforcer Kade"]
        officer = random.choice(officer_names)

        embed = discord.Embed(
            title="🛡️ Security Escort Requested",
            description=f"**{char_name}** requests and pays for a security escort.",
            color=0x00bfff
        )
        embed.add_field(name="👮 Assigned Officer", value=f"{officer} is on their way to meet you.", inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
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
        embed.add_field(name="📋 Status", value="Use `/shop list` to see available items for purchase.", inline=False)
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
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_type, quantity, description, value)
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

    async def _handle_fresh_produce(self, interaction, char_name: str, money: int):
        """Handle buying fresh produce"""
        import random
        
        cost = random.randint(15, 35)
        
        if money < cost:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"**{char_name}** cannot afford fresh produce right now.",
                color=0xff4500
            )
            embed.add_field(name="💰 Required", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Available", value=f"{money} credits", inline=True)
        else:
            produce_items = [
                "fresh leafy greens",
                "ripe hydroponic tomatoes", 
                "crisp vegetables",
                "exotic fruits",
                "aromatic herbs"
            ]
            
            item = random.choice(produce_items)
            
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (cost, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="🥬 Fresh Produce",
                description=f"**{char_name}** purchases some {item}.",
                color=0x9acd32
            )
            embed.add_field(name="🌱 Quality", value="Freshly harvested and nutrient-rich", inline=False)
            embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
            embed.add_field(name="🏦 Remaining", value=f"{money - cost} credits", inline=True)
        
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
        if hp >= max_hp:
            rest_bonus = 0
            message = "You relax in comfort while maintaining peak condition."
        else:
            rest_bonus = min(max_hp - hp, 10)
            self.db.execute_query(
                "UPDATE characters SET hp = hp + ? WHERE user_id = ?",
                (rest_bonus, interaction.user.id)
            )
            message = f"The comfortable seating helps you recover! (+{rest_bonus} HP)"
        
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
            "traveler_info": "You gather useful information for travelers.",
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

class ChangeDescriptionModal(ChangeCharacterInfoModal):
    async def update_database(self, interaction: discord.Interaction, new_value: str):
        self.db.execute_query(
            "UPDATE characters SET appearance = ? WHERE user_id = ?",
            (new_value, interaction.user.id)
        )

class ChangeBioModal(ChangeCharacterInfoModal):
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