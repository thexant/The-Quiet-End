# utils/sub_locations.py
import discord
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
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
                'location_types': ['station', 'colony'],
                'min_wealth': 1
            },
            'research': {
                'name': 'Research Lab',
                'icon': '🔬',
                'description': 'Cutting-edge scientific workspaces.',
                'location_types': ['station', 'colony'],
                'min_wealth': 5
            },
            'hydroponics': {
                'name': 'Hydroponics Bay',
                'icon': '🌱',
                'description': 'Food production and botanical research.',
                'location_types': ['station', 'colony'],
                'min_wealth': 2
            },
            'recreation': {
                'name': 'Recreation Deck',
                'icon': '🎮',
                'description': 'Leisure and fitness facilities.',
                'location_types': ['station', 'colony'],
                'min_wealth': 3
            },
            'communications': {
                'name': 'Comm Center',
                'icon': '📡',
                'description': 'Long-range comms and sensor array.',
                'location_types': ['station', 'outpost'],
                'min_wealth': 1
            },
            'cafeteria': {
                'name': 'Cafeteria',
                'icon': '🍽️',
                'description': 'Food service and social hub.',
                'location_types': ['station', 'colony', 'outpost'],
                'min_wealth': 0
            },
            # Add these entries to the existing sub_location_types dictionary in SubLocationManager.__init__

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
            }
        }
    
    async def get_available_sub_locations(self, parent_location_id: int) -> List[Dict]:
        """
        Return the persistent sub-locations for this parent location
        """
        # Get all sub-locations that were generated for this parent location
        stored_subs = self.db.execute_query(
            '''SELECT sub_type, name, description, thread_id 
               FROM sub_locations 
               WHERE parent_location_id = ? AND is_active = 1''',
            (parent_location_id,),
            fetch='all'
        )
        
        available = []
        for sub_type, name, description, thread_id in stored_subs:
            # Check if thread exists (for the 'exists' flag)
            thread_exists = bool(thread_id)
            
            # Get icon from sub_location_types
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
            # Try to get existing thread
            thread = guild.get_thread(existing[0])
            if thread:
                # If thread exists, just add the user to it
                try:
                    await thread.add_user(user)
                except Exception as e:
                    print(f"Failed to add user to existing sub-location thread: {e}")
                return thread
            else:
                # Thread was deleted, but the record remains. We'll create a new one.
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
        
        # Get parent location info
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
            value="This thread will auto-archive after 1 hour of inactivity. Use it to roleplay and interact with this specific area.",
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
            
            # Send buttons in a separate message to ensure they appear
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
        # This would be called periodically to clean up old threads
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        inactive_threads = self.db.execute_query(
            '''SELECT sl.sub_location_id, sl.thread_id, sl.parent_location_id, sl.sub_type
               FROM sub_locations sl
               WHERE sl.is_active = 1 AND sl.last_active < ?''',
            (cutoff_time,),
            fetch='all'
        )
        
        for sub_id, thread_id, location_id, sub_type in inactive_threads:
            # Check if thread still exists and is empty
            guild = self.bot.get_guild(thread_id)  # This won't work, we need the guild from somewhere else
            # For now, just mark as inactive in database
            self.db.execute_query(
                "UPDATE sub_locations SET is_active = 0 WHERE sub_location_id = ?",
                (sub_id,)
            )
            
            if thread_id in self.active_threads:
                del self.active_threads[thread_id]
    
    async def get_sub_location_occupants(self, sub_location_id: int) -> List[int]:
        """Get list of user IDs currently in a sub-location"""
        # This is a placeholder - in a real implementation, you'd track
        # which users are currently active in each sub-location thread
        return []

    async def generate_persistent_sub_locations(self, parent_location_id: int, location_type: str, wealth_level: int, is_derelict: bool = False) -> int:
        """Generate and store persistent sub-locations for a location during galaxy generation"""
        import random
        
        # Clear any existing sub-locations for this parent (in case of regeneration)
        self.db.execute_query(
            "DELETE FROM sub_locations WHERE parent_location_id = ?",
            (parent_location_id,)
        )
        
        # Handle derelict locations
        if is_derelict:
            # Only derelict-themed sub-locations
            candidates = []
            for key, props in self.sub_location_types.items():
                if props.get('derelict_only', False) and location_type in props['location_types']:
                    candidates.append((key, props))
            
            if not candidates:
                return 0
            
            # Derelict locations have fewer sub-locations (0-2)
            max_count = min(len(candidates), random.randint(0, 2))
            if max_count == 0:
                return 0
            
            selected = random.sample(candidates, max_count)
            
            # Create the derelict sub-locations
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
        # Filter valid candidates based on location type and wealth (exclude derelict-only)
        candidates = []
        for key, props in self.sub_location_types.items():
            # Skip derelict-only sub-locations for normal locations
            if props.get('derelict_only', False):
                continue
            # location_type filter
            if location_type not in props['location_types']:
                continue
            # min wealth filter
            if props.get('min_wealth', 0) > wealth_level:
                continue
            candidates.append((key, props))
        
        if not candidates:
            return 0
        
        # Determine how many sub-locations this location should have
        # Based on location type and wealth
        if location_type == 'space_station':
            base_count = 3 if wealth_level >= 7 else 2 if wealth_level >= 4 else 1
            max_count = min(len(candidates), base_count + random.randint(0, 2))
        elif location_type == 'colony':
            base_count = 2 if wealth_level >= 6 else 1 if wealth_level >= 3 else 1
            max_count = min(len(candidates), base_count + random.randint(0, 1))
        elif location_type == 'outpost':
            max_count = min(len(candidates), 1 if wealth_level >= 4 else random.randint(0, 1))
        else:  # gate
            # Gates are major infrastructure, always have multiple sub-locations
            base_count = 4 if wealth_level >= 6 else 3 if wealth_level >= 3 else 2
            max_count = min(len(candidates), base_count + random.randint(0, 2))
        
        if max_count == 0:
            return 0
        
        # Randomly select which sub-locations to create
        selected = random.sample(candidates, max_count)
        
        # Create the sub-locations in the database
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

class SubLocationServiceView(discord.ui.View):
    """Interactive view for sub-location services"""
    
    def __init__(self, sub_type: str, location_id: int, bot):
        super().__init__(timeout=1800)  # 30 minute timeout instead of 5
        self.sub_type = sub_type
        self.location_id = location_id
        self.bot = bot
        self.db = bot.db
        
        # Add buttons based on sub-location type
        self._add_service_buttons()
        print(f"🔧 Created SubLocationServiceView for {sub_type} with {len(self.children)} buttons")
        
    def _add_service_buttons(self):
        """Add service buttons based on sub-location type"""
        
        # Clear existing buttons to prevent duplicates
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
            await interaction.response.send_message("You need a character to use services!", ephemeral=True)
            return
        
        char_name, hp, max_hp, money, current_location, appearance = char_info
        
        # Check if user is at this location
        if current_location != self.location_id:
            await interaction.response.send_message("You need to be at this location to use its services!", ephemeral=True)
            return
        
        # Handle different service types
        if service_type == "medical_treatment":
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
            await self._handle_request_escort(interaction, char_name)
        elif service_type == "file_complaint":
            await self._handle_file_complaint(interaction, char_name)
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

        elif service_type == "change_name":
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
        else:
            # Generic flavor response for unimplemented services
            await self._handle_generic_service(interaction, service_type, char_name)
        

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        """Handle view errors gracefully"""
        print(f"❌ SubLocationServiceView error: {error}")
        import traceback
        traceback.print_exc()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
        except:
            pass
    async def _handle_priority_refuel(self, interaction, char_name: str, money: int):
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
        
        # Priority refuel costs more but gives better fuel
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

    async def _handle_pre_transit_check(self, interaction, char_name: str):
        """Handle pre-transit system check at gate mechanics"""
        ship_info = self.db.execute_query(
            "SELECT name, ship_type, fuel_capacity, current_fuel, hull_integrity, max_hull, fuel_efficiency FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🔧 Pre-Transit Check",
                description="No ship found for inspection.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        ship_name, ship_type, fuel_cap, current_fuel, hull, max_hull, fuel_eff = ship_info
        
        # Calculate readiness scores
        fuel_readiness = (current_fuel / fuel_cap) * 100 if fuel_cap > 0 else 0
        hull_readiness = (hull / max_hull) * 100 if max_hull > 0 else 0
        
        # Determine overall readiness
        overall_readiness = (fuel_readiness + hull_readiness) / 2
        
        if overall_readiness >= 80:
            status = "✅ CLEARED FOR TRANSIT"
            color = 0x00ff00
            recommendation = "All systems nominal. Safe travels!"
        elif overall_readiness >= 60:
            status = "⚠️ CAUTION ADVISED"
            color = 0xffa500
            recommendation = "Consider repairs or refueling before long-distance travel."
        else:
            status = "🚨 NOT RECOMMENDED"
            color = 0xff0000
            recommendation = "Immediate maintenance required before corridor transit."
        
        embed = discord.Embed(
            title="🔧 Pre-Transit System Check",
            description=f"**{char_name}**'s ship **{ship_name}** inspection results:",
            color=color
        )
        
        embed.add_field(name="🚀 Ship Type", value=ship_type, inline=True)
        embed.add_field(name="📊 Overall Status", value=status, inline=True)
        embed.add_field(name="⭐ Readiness Score", value=f"{overall_readiness:.1f}%", inline=True)
        
        embed.add_field(
            name="🔍 System Details",
            value=f"⛽ Fuel: {current_fuel}/{fuel_cap} ({fuel_readiness:.1f}%)\n🛡️ Hull: {hull}/{max_hull} ({hull_readiness:.1f}%)\n⚙️ Efficiency: {fuel_eff}",
            inline=False
        )
        
        embed.add_field(name="💡 Recommendation", value=recommendation, inline=False)
        
        if overall_readiness < 80:
            services = []
            if fuel_readiness < 80:
                services.append("• Refuel at Fuel Depot")
            if hull_readiness < 80:
                services.append("• Hull repairs needed")
            
            if services:
                embed.add_field(name="🛠️ Suggested Services", value="\n".join(services), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_emergency_repairs(self, interaction, char_name: str, money: int):
        """Handle emergency repair service at gate mechanics"""
        ship_info = self.db.execute_query(
            "SELECT hull_integrity, max_hull FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🚨 Emergency Repairs",
                description="No ship found for emergency repairs.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        hull_integrity, max_hull = ship_info
        
        if hull_integrity >= max_hull * 0.8:  # 80% or better
            embed = discord.Embed(
                title="🚨 Emergency Repairs",
                description=f"**{char_name}**, your ship doesn't require emergency repairs.",
                color=0x00ff00
            )
            embed.add_field(name="🛡️ Hull Status", value=f"{hull_integrity}/{max_hull} ({(hull_integrity/max_hull)*100:.1f}%)", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Emergency repairs are expensive but fast
        critical_repairs = min(max_hull - hull_integrity, max_hull // 2)  # Repair up to 50% or to full
        cost_per_point = 40  # More expensive than regular repairs
        total_cost = critical_repairs * cost_per_point
        
        if money < total_cost:
            embed = discord.Embed(
                title="🚨 Emergency Repair Service",
                description=f"**Emergency Repair Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff0000
            )
            embed.add_field(
                name="⚠️ Critical Notice",
                value="Emergency repairs required for safe corridor transit. Consider requesting assistance or emergency funding.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Apply emergency repairs
        new_hull = hull_integrity + critical_repairs
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = ? WHERE owner_id = ?",
            (new_hull, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚨 Emergency Repairs Complete",
            description=f"**{char_name}**, critical hull repairs have been completed.",
            color=0x00ff00
        )
        embed.add_field(name="🛠️ Hull Integrity", value=f"{hull_integrity} → {new_hull}", inline=True)
        embed.add_field(name="⚡ Service Type", value="Emergency Priority", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        embed.add_field(
            name="🛡️ Status", 
            value="Ship cleared for corridor transit" if new_hull >= max_hull * 0.6 else "Additional repairs recommended", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_search_supplies(self, interaction, char_name: str):
        """Handle searching for supplies in derelict areas"""
        import random
        
        # Low chance of finding something useful
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

    async def _handle_scavenge_parts(self, interaction, char_name: str):
        """Handle scavenging for ship parts in salvage yard"""
        import random
        
        # Scavenging has costs (time/risk) but potential rewards
        scavenge_cost = random.randint(10, 30)  # Time cost in "minutes"
        
        # Check if player wants to spend the time
        success_chance = 0.4  # 40% chance of finding something useful
        
        if random.random() < success_chance:
            # Found something useful
            salvaged_items = [
                ("Salvaged Hull Plating", "ship_part", 1, "Damaged but repairable hull material", 45),
                ("Scrap Electronics", "component", random.randint(2, 5), "Useful electronic components", 15),
                ("Fuel Line Segment", "ship_part", 1, "Replacement fuel system component", 35),
                ("Navigation Computer Core", "component", 1, "Partially functional nav computer", 80),
                ("Power Coupling", "component", random.randint(1, 3), "Standard power system parts", 25),
                ("Thruster Nozzle", "ship_part", 1, "Worn but functional thruster component", 60),
                ("Sensor Array Module", "component", 1, "Damaged sensor equipment", 55),
                ("Emergency Beacon", "equipment", 1, "Distress signal transmitter", 40)
            ]
            
            item_name, item_type, quantity, description, value = random.choice(salvaged_items)
            
            # Add to inventory
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_type, quantity, description, value)
            )
            
            embed = discord.Embed(
                title="⚙️ Salvage Operation",
                description=f"**{char_name}** spends {scavenge_cost} minutes carefully scavenging through the salvage yard.",
                color=0x8B4513
            )
            embed.add_field(name="🔍 Discovery", value=f"{quantity}x {item_name}", inline=False)
            embed.add_field(name="📝 Condition", value=description, inline=False)
            embed.add_field(name="💰 Estimated Value", value=f"{value * quantity} credits", inline=True)
            embed.add_field(name="🛠️ Usage", value="Can be sold or used for ship modifications", inline=True)
            
            # Small chance of finding something extra valuable
            if random.random() < 0.1:  # 10% chance
                embed.add_field(
                    name="✨ Bonus Find", 
                    value="You also discover some useful technical documentation!", 
                    inline=False
                )
        else:
            # Found nothing useful
            nothing_found = [
                "The area has been thoroughly picked clean by previous scavengers.",
                "Most of the remaining parts are too damaged to be useful.",
                "You find only worthless scrap metal and burned-out components.",
                "Other scavengers have already taken anything of value.",
                "The salvage appears to be from very old, incompatible ship designs."
            ]
            
            embed = discord.Embed(
                title="⚙️ Salvage Operation",
                description=f"**{char_name}** spends {scavenge_cost} minutes searching the salvage yard.",
                color=0x696969
            )
            embed.add_field(name="🔍 Result", value="Nothing useful found", inline=False)
            embed.add_field(name="💭 Outcome", value=random.choice(nothing_found), inline=False)
            embed.add_field(name="⏰ Time Spent", value=f"{scavenge_cost} minutes", inline=True)
            
            # Small chance of at least finding basic scrap
            if random.random() < 0.3:  # 30% chance of consolation prize
                self.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (interaction.user.id, "Scrap Metal", "material", random.randint(1, 2), "Basic salvaged metal", 3)
                )
                embed.add_field(name="🔩 Consolation", value="Found small amount of scrap metal", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _handle_emergency_medical(self, interaction, char_name: str, money: int):
        """Handle emergency medical treatment in derelict emergency shelter"""
        cost = 50  # More expensive due to limited supplies
        
        char_info = self.db.execute_query(
            "SELECT hp, max_hp FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            return
        
        hp, max_hp = char_info
        
        if hp >= max_hp:
            embed = discord.Embed(
                title="🩹 Emergency Medical",
                description=f"**{char_name}**, you don't need medical attention.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        if money < cost:
            embed = discord.Embed(
                title="🩹 Emergency Medical",
                description=f"**{char_name}**, emergency medical treatment costs {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # Limited healing (not full recovery like normal medical)
        healing = min(max_hp - hp, random.randint(10, 25))
        
        self.db.execute_query(
            "UPDATE characters SET hp = hp + ?, money = money - ? WHERE user_id = ?",
            (healing, cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🩹 Emergency Treatment",
            description=f"**{char_name}** uses the emergency medical supplies.",
            color=0xff6600
        )
        embed.add_field(name="💚 Healing", value=f"+{healing} HP", inline=True)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="⚠️ Note", value="Limited supplies - not full treatment", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    async def _handle_medical_treatment(self, interaction, char_name: str, hp: int, max_hp: int, money: int):
        """Handle medical treatment service"""
        if hp >= max_hp:
            embed = discord.Embed(
                title="⚕️ Medical Bay",
                description=f"**{char_name}**, your vitals are optimal. No treatment required.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate healing and cost
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_priority_refuel(self, interaction, char_name: str, money: int):
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        fuel_capacity, current_fuel = ship_info
        
        if current_fuel >= fuel_capacity:
            embed = discord.Embed(
                title="⛽ Priority Refuel",
                description=f"**{char_name}**, your ship's fuel tanks are already full.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Priority refuel costs more but gives better fuel
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_pre_transit_check(self, interaction, char_name: str):
        """Handle pre-transit system check at gate mechanics"""
        ship_info = self.db.execute_query(
            "SELECT name, ship_type, fuel_capacity, current_fuel, hull_integrity, max_hull, fuel_efficiency FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🔧 Pre-Transit Check",
                description="No ship found for inspection.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        ship_name, ship_type, fuel_cap, current_fuel, hull, max_hull, fuel_eff = ship_info
        
        # Calculate readiness scores
        fuel_readiness = (current_fuel / fuel_cap) * 100 if fuel_cap > 0 else 0
        hull_readiness = (hull / max_hull) * 100 if max_hull > 0 else 0
        
        # Determine overall readiness
        overall_readiness = (fuel_readiness + hull_readiness) / 2
        
        if overall_readiness >= 80:
            status = "✅ CLEARED FOR TRANSIT"
            color = 0x00ff00
            recommendation = "All systems nominal. Safe travels!"
        elif overall_readiness >= 60:
            status = "⚠️ CAUTION ADVISED"
            color = 0xffa500
            recommendation = "Consider repairs or refueling before long-distance travel."
        else:
            status = "🚨 NOT RECOMMENDED"
            color = 0xff0000
            recommendation = "Immediate maintenance required before corridor transit."
        
        embed = discord.Embed(
            title="🔧 Pre-Transit System Check",
            description=f"**{char_name}**'s ship **{ship_name}** inspection results:",
            color=color
        )
        
        embed.add_field(name="🚀 Ship Type", value=ship_type, inline=True)
        embed.add_field(name="📊 Overall Status", value=status, inline=True)
        embed.add_field(name="⭐ Readiness Score", value=f"{overall_readiness:.1f}%", inline=True)
        
        embed.add_field(
            name="🔍 System Details",
            value=f"⛽ Fuel: {current_fuel}/{fuel_cap} ({fuel_readiness:.1f}%)\n🛡️ Hull: {hull}/{max_hull} ({hull_readiness:.1f}%)\n⚙️ Efficiency: {fuel_eff}",
            inline=False
        )
        
        embed.add_field(name="💡 Recommendation", value=recommendation, inline=False)
        
        if overall_readiness < 80:
            services = []
            if fuel_readiness < 80:
                services.append("• Refuel at Fuel Depot")
            if hull_readiness < 80:
                services.append("• Hull repairs needed")
            
            if services:
                embed.add_field(name="🛠️ Suggested Services", value="\n".join(services), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_emergency_repairs(self, interaction, char_name: str, money: int):
        """Handle emergency repair service at gate mechanics"""
        ship_info = self.db.execute_query(
            "SELECT hull_integrity, max_hull FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🚨 Emergency Repairs",
                description="No ship found for emergency repairs.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        hull_integrity, max_hull = ship_info
        
        if hull_integrity >= max_hull * 0.8:  # 80% or better
            embed = discord.Embed(
                title="🚨 Emergency Repairs",
                description=f"**{char_name}**, your ship doesn't require emergency repairs.",
                color=0x00ff00
            )
            embed.add_field(name="🛡️ Hull Status", value=f"{hull_integrity}/{max_hull} ({(hull_integrity/max_hull)*100:.1f}%)", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Emergency repairs are expensive but fast
        critical_repairs = min(max_hull - hull_integrity, max_hull // 2)  # Repair up to 50% or to full
        cost_per_point = 40  # More expensive than regular repairs
        total_cost = critical_repairs * cost_per_point
        
        if money < total_cost:
            embed = discord.Embed(
                title="🚨 Emergency Repair Service",
                description=f"**Emergency Repair Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff0000
            )
            embed.add_field(
                name="⚠️ Critical Notice",
                value="Emergency repairs required for safe corridor transit. Consider requesting assistance or emergency funding.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Apply emergency repairs
        new_hull = hull_integrity + critical_repairs
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = ? WHERE owner_id = ?",
            (new_hull, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚨 Emergency Repairs Complete",
            description=f"**{char_name}**, critical hull repairs have been completed.",
            color=0x00ff00
        )
        embed.add_field(name="🛠️ Hull Integrity", value=f"{hull_integrity} → {new_hull}", inline=True)
        embed.add_field(name="⚡ Service Type", value="Emergency Priority", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        embed.add_field(
            name="🛡️ Status", 
            value="Ship cleared for corridor transit" if new_hull >= max_hull * 0.6 else "Additional repairs recommended", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        """Handle view errors gracefully"""
        print(f"❌ SubLocationServiceView error: {error}")
        import traceback
        traceback.print_exc()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
        except:
            pass  # Couldn't send error message
    async def handle_service(self, interaction: discord.Interaction, service_type: str):
        """Handle service interactions"""
        
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT name, hp, max_hp, money, current_location, appearance FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("You need a character to use services!", ephemeral=True)
            return
        
        char_name, hp, max_hp, money, current_location, appearance = char_info
        
        # Check if user is at this location
        if current_location != self.location_id:
            await interaction.response.send_message("You need to be at this location to use its services!", ephemeral=True)
            return
        
        # Handle different service types
        if service_type == "medical_treatment":
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
            await self._handle_request_escort(interaction, char_name)
        elif service_type == "file_complaint":
            await self._handle_file_complaint(interaction, char_name)
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

        # Administration services - these use modals
        elif service_type == "change_name":
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
    
    async def _handle_medical_treatment(self, interaction, char_name: str, hp: int, max_hp: int, money: int):
        """Handle medical treatment service"""
        if hp >= max_hp:
            embed = discord.Embed(
                title="⚕️ Medical Bay",
                description=f"**{char_name}**, your vitals are optimal. No treatment required.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate healing and cost
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_priority_refuel(self, interaction, char_name: str, money: int):
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        fuel_capacity, current_fuel = ship_info
        
        if current_fuel >= fuel_capacity:
            embed = discord.Embed(
                title="⛽ Priority Refuel",
                description=f"**{char_name}**, your ship's fuel tanks are already full.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Priority refuel costs more but gives better fuel
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_pre_transit_check(self, interaction, char_name: str):
        """Handle pre-transit system check at gate mechanics"""
        ship_info = self.db.execute_query(
            "SELECT name, ship_type, fuel_capacity, current_fuel, hull_integrity, max_hull, fuel_efficiency FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🔧 Pre-Transit Check",
                description="No ship found for inspection.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        ship_name, ship_type, fuel_cap, current_fuel, hull, max_hull, fuel_eff = ship_info
        
        # Calculate readiness scores
        fuel_readiness = (current_fuel / fuel_cap) * 100 if fuel_cap > 0 else 0
        hull_readiness = (hull / max_hull) * 100 if max_hull > 0 else 0
        
        # Determine overall readiness
        overall_readiness = (fuel_readiness + hull_readiness) / 2
        
        if overall_readiness >= 80:
            status = "✅ CLEARED FOR TRANSIT"
            color = 0x00ff00
            recommendation = "All systems nominal. Safe travels!"
        elif overall_readiness >= 60:
            status = "⚠️ CAUTION ADVISED"
            color = 0xffa500
            recommendation = "Consider repairs or refueling before long-distance travel."
        else:
            status = "🚨 NOT RECOMMENDED"
            color = 0xff0000
            recommendation = "Immediate maintenance required before corridor transit."
        
        embed = discord.Embed(
            title="🔧 Pre-Transit System Check",
            description=f"**{char_name}**'s ship **{ship_name}** inspection results:",
            color=color
        )
        
        embed.add_field(name="🚀 Ship Type", value=ship_type, inline=True)
        embed.add_field(name="📊 Overall Status", value=status, inline=True)
        embed.add_field(name="⭐ Readiness Score", value=f"{overall_readiness:.1f}%", inline=True)
        
        embed.add_field(
            name="🔍 System Details",
            value=f"⛽ Fuel: {current_fuel}/{fuel_cap} ({fuel_readiness:.1f}%)\n🛡️ Hull: {hull}/{max_hull} ({hull_readiness:.1f}%)\n⚙️ Efficiency: {fuel_eff}",
            inline=False
        )
        
        embed.add_field(name="💡 Recommendation", value=recommendation, inline=False)
        
        if overall_readiness < 80:
            services = []
            if fuel_readiness < 80:
                services.append("• Refuel at Fuel Depot")
            if hull_readiness < 80:
                services.append("• Hull repairs needed")
            
            if services:
                embed.add_field(name="🛠️ Suggested Services", value="\n".join(services), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_emergency_repairs(self, interaction, char_name: str, money: int):
        """Handle emergency repair service at gate mechanics"""
        ship_info = self.db.execute_query(
            "SELECT hull_integrity, max_hull FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🚨 Emergency Repairs",
                description="No ship found for emergency repairs.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        hull_integrity, max_hull = ship_info
        
        if hull_integrity >= max_hull * 0.8:  # 80% or better
            embed = discord.Embed(
                title="🚨 Emergency Repairs",
                description=f"**{char_name}**, your ship doesn't require emergency repairs.",
                color=0x00ff00
            )
            embed.add_field(name="🛡️ Hull Status", value=f"{hull_integrity}/{max_hull} ({(hull_integrity/max_hull)*100:.1f}%)", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Emergency repairs are expensive but fast
        critical_repairs = min(max_hull - hull_integrity, max_hull // 2)  # Repair up to 50% or to full
        cost_per_point = 40  # More expensive than regular repairs
        total_cost = critical_repairs * cost_per_point
        
        if money < total_cost:
            embed = discord.Embed(
                title="🚨 Emergency Repair Service",
                description=f"**Emergency Repair Cost:** {total_cost} credits\n**Your Credits:** {money}",
                color=0xff0000
            )
            embed.add_field(
                name="⚠️ Critical Notice",
                value="Emergency repairs required for safe corridor transit. Consider requesting assistance or emergency funding.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Apply emergency repairs
        new_hull = hull_integrity + critical_repairs
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = ? WHERE owner_id = ?",
            (new_hull, interaction.user.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚨 Emergency Repairs Complete",
            description=f"**{char_name}**, critical hull repairs have been completed.",
            color=0x00ff00
        )
        embed.add_field(name="🛠️ Hull Integrity", value=f"{hull_integrity} → {new_hull}", inline=True)
        embed.add_field(name="⚡ Service Type", value="Emergency Priority", inline=True)
        embed.add_field(name="💰 Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - total_cost}", inline=True)
        embed.add_field(
            name="🛡️ Status", 
            value="Ship cleared for corridor transit" if new_hull >= max_hull * 0.6 else "Additional repairs recommended", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_refuel_ship(self, interaction, char_name: str, money: int):
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        fuel_capacity, current_fuel = ship_info
        
        if current_fuel >= fuel_capacity:
            embed = discord.Embed(
                title="⛽ Refueling Station",
                description=f"**{char_name}**, your ship's fuel tanks are already full.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate refuel cost
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    # Add these methods to the SubLocationServiceView class:

    async def _handle_check_traffic(self, interaction, char_name: str):
        """Handle traffic monitoring at gate control"""
        import random
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_corridor_status(self, interaction, char_name: str):
        """Handle corridor status check"""
        # Get actual corridor data from this gate
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_rest_recuperate(self, interaction, char_name: str, money: int):
        """Handle rest and recuperation at truck stop"""
        cost = 25
        
        if money < cost:
            embed = discord.Embed(
                title="😴 Traveler Services",
                description=f"**{char_name}**, rest services cost {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Small HP recovery
        hp_recovery = random.randint(5, 15)
        self.db.execute_query(
            "UPDATE characters SET hp = MIN(max_hp, hp + ?), money = money - ? WHERE user_id = ?",
            (hp_recovery, cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="😴 Rest & Recuperation",
            description=f"**{char_name}** takes time to rest and recover.",
            color=0x00ff88
        )
        embed.add_field(name="💚 Recovery", value=f"+{hp_recovery} HP", inline=True)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_search_supplies(self, interaction, char_name: str):
        """Handle searching for supplies in derelict areas"""
        import random
        
        # Low chance of finding something useful
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_emergency_medical(self, interaction, char_name: str, money: int):
        """Handle emergency medical treatment in derelict emergency shelter"""
        cost = 50  # More expensive due to limited supplies
        
        char_info = self.db.execute_query(
            "SELECT hp, max_hp FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            return
        
        hp, max_hp = char_info
        
        if hp >= max_hp:
            embed = discord.Embed(
                title="🩹 Emergency Medical",
                description=f"**{char_name}**, you don't need medical attention.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if money < cost:
            embed = discord.Embed(
                title="🩹 Emergency Medical",
                description=f"**{char_name}**, emergency medical treatment costs {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Limited healing (not full recovery like normal medical)
        healing = min(max_hp - hp, random.randint(10, 25))
        
        self.db.execute_query(
            "UPDATE characters SET hp = hp + ?, money = money - ? WHERE user_id = ?",
            (healing, cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🩹 Emergency Treatment",
            description=f"**{char_name}** uses the emergency medical supplies.",
            color=0xff6600
        )
        embed.add_field(name="💚 Healing", value=f"+{healing} HP", inline=True)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="⚠️ Note", value="Limited supplies - not full treatment", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Add placeholder handlers for the other gate services
    async def _handle_traveler_info(self, interaction, char_name: str):
        """Handle traveler information service at truck stop"""
        import random
        
        # Get some useful travel information
        tips = [
            "💡 **Travel Tip**: Ungated corridors are dangerous but faster - carry extra medical supplies.",
            "🛡️ **Safety Notice**: Always check your ship's hull integrity before long-distance travel.",
            "⛽ **Fuel Advice**: Gate fuel stations offer premium quality but at higher prices.",
            "📡 **Communication**: Not all locations have radio repeaters - plan your communications accordingly.",
            "🗺️ **Navigation**: Wealthy colonies often have better services but charge premium rates.",
            "⚠️ **Warning**: Corridor instabilities can change travel times - always carry extra fuel.",
            "💰 **Economic Tip**: Outpost jobs pay less but are usually safer for new travelers.",
            "🔧 **Maintenance**: Regular ship maintenance prevents costly emergency repairs.",
            "👥 **Social**: Group travel through dangerous corridors provides safety in numbers.",
            "📦 **Trade**: Monitor market prices across different systems for profit opportunities."
        ]
        
        # Random route suggestion
        nearby_locations = self.db.execute_query(
            """SELECT l.name, l.location_type, l.wealth_level 
               FROM corridors c 
               JOIN locations l ON c.destination_location = l.location_id 
               WHERE c.origin_location = ? AND c.is_active = 1 
               ORDER BY RANDOM() LIMIT 3""",
            (self.location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🗺️ Traveler Information",
            description=f"**{char_name}** consults the traveler information terminal.",
            color=0x4169e1
        )
        
        embed.add_field(name="💡 Today's Travel Tip", value=random.choice(tips), inline=False)
        
        if nearby_locations:
            route_info = []
            for name, loc_type, wealth in nearby_locations:
                wealth_stars = "⭐" * min(wealth // 2, 5)
                type_emoji = {"colony": "🏘️", "space_station": "🛰️", "outpost": "🏭", "gate": "🚪"}.get(loc_type, "📍")
                route_info.append(f"{type_emoji} **{name}** {wealth_stars}")
            
            embed.add_field(name="🛣️ Nearby Destinations", value="\n".join(route_info), inline=False)
        
        embed.add_field(
            name="ℹ️ Services Available", 
            value="• Route planning assistance\n• Current traffic conditions\n• Weather and hazard reports\n• Local facility information", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_security_scan(self, interaction, char_name: str):
        """Handle security scanning at checkpoint"""
        import random
        
        # Get character's inventory to "scan"
        inventory = self.db.execute_query(
            "SELECT item_name, item_type, quantity FROM inventory WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='all'
        )
        
        # Check for any "contraband" items (for flavor)
        contraband_types = ['illegal', 'restricted', 'black_market']
        flagged_items = []
        
        for item_name, item_type, quantity in inventory:
            if any(keyword in item_name.lower() for keyword in ['weapon', 'explosive', 'illegal', 'contraband']):
                flagged_items.append(f"{quantity}x {item_name}")
        
        scan_results = ["Clean", "Clean", "Clean", "Minor Anomaly", "Flagged for Review"]
        scan_result = random.choice(scan_results) if not flagged_items else "Flagged for Review"
        
        embed = discord.Embed(
            title="🔍 Security Checkpoint",
            description=f"**{char_name}** undergoes mandatory security screening.",
            color=0x00ff00 if scan_result == "Clean" else 0xffa500
        )
        
        embed.add_field(name="📊 Scan Result", value=scan_result, inline=True)
        
        if scan_result == "Clean":
            embed.add_field(name="✅ Status", value="Cleared for corridor transit", inline=True)
            embed.add_field(name="🛂 Clearance", value="All standard protocols satisfied", inline=False)
        elif scan_result == "Minor Anomaly":
            embed.add_field(name="⚠️ Status", value="Minor irregularity detected", inline=True)
            embed.add_field(name="📋 Action", value="Additional documentation may be required", inline=False)
        else:
            embed.add_field(name="🚨 Status", value="Items require additional screening", inline=True)
            if flagged_items:
                embed.add_field(name="📦 Flagged Items", value="\n".join(flagged_items[:3]), inline=False)
            embed.add_field(name="⏳ Processing", value="Security review in progress...", inline=False)
        
        embed.add_field(name="🕐 Processing Time", value=f"{random.randint(30, 180)} seconds", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_transit_papers(self, interaction, char_name: str, money: int):
        """Handle transit documentation services"""
        import random
        
        services = [
            ("Standard Transit Permit", 50, "Basic corridor travel authorization"),
            ("Express Processing", 100, "Priority document processing service"),
            ("Multi-System Visa", 200, "Extended travel authorization package"),
            ("Emergency Transit Pass", 150, "Temporary authorization for urgent travel"),
            ("Cargo Manifest Update", 75, "Update shipping documentation")
        ]
        
        # Random service offering
        service_name, cost, description = random.choice(services)
        
        embed = discord.Embed(
            title="📄 Transit Documentation",
            description=f"**{char_name}** reviews available documentation services.",
            color=0x4169e1
        )
        
        embed.add_field(name="📋 Featured Service", value=service_name, inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="📝 Description", value=description, inline=True)
        
        if money >= cost:
            embed.add_field(name="✅ Status", value="Service available", inline=True)
            embed.add_field(
                name="📄 Standard Documents", 
                value="• Corridor Transit Permit\n• Identity Verification\n• Ship Registration Status\n• Medical Clearance", 
                inline=False
            )
        else:
            embed.add_field(name="❌ Status", value="Insufficient funds", inline=True)
            embed.add_field(name="💡 Note", value="Basic transit rights are always honored regardless of documentation status.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_fuel_quality(self, interaction, char_name: str):
        """Handle fuel quality checking service"""
        import random
        
        # Check current ship fuel
        ship_info = self.db.execute_query(
            "SELECT current_fuel, fuel_capacity, name FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="🧪 Fuel Quality Analysis",
                description="No ship found for fuel analysis.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        current_fuel, fuel_capacity, ship_name = ship_info
        
        # Generate quality analysis
        quality_ratings = ["Premium", "Standard", "Acceptable", "Poor", "Contaminated"]
        purity_levels = ["99.8%", "98.2%", "95.7%", "89.3%", "73.1%"]
        
        quality_index = random.randint(0, len(quality_ratings) - 1)
        quality = quality_ratings[quality_index]
        purity = purity_levels[quality_index]
        
        # Quality affects performance
        performance_impact = {
            "Premium": "+5% efficiency",
            "Standard": "Normal performance", 
            "Acceptable": "-2% efficiency",
            "Poor": "-8% efficiency",
            "Contaminated": "-15% efficiency, system risk"
        }
        
        color_map = {
            "Premium": 0x00ff00,
            "Standard": 0x90EE90,
            "Acceptable": 0xffff00,
            "Poor": 0xffa500,
            "Contaminated": 0xff0000
        }
        
        embed = discord.Embed(
            title="🧪 Fuel Quality Analysis",
            description=f"**{char_name}** analyzes **{ship_name}**'s fuel quality.",
            color=color_map[quality]
        )
        
        embed.add_field(name="⛽ Current Fuel", value=f"{current_fuel}/{fuel_capacity} units", inline=True)
        embed.add_field(name="🏆 Quality Rating", value=quality, inline=True)
        embed.add_field(name="🧪 Purity Level", value=purity, inline=True)
        embed.add_field(name="📊 Performance Impact", value=performance_impact[quality], inline=False)
        
        if quality in ["Poor", "Contaminated"]:
            embed.add_field(
                name="⚠️ Recommendation", 
                value="Consider fuel system cleaning or replacement at next opportunity.", 
                inline=False
            )
        elif quality == "Premium":
            embed.add_field(
                name="✨ Certification", 
                value="Fuel meets all galactic standards for optimal performance.", 
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_scavenge_parts(self, interaction, char_name: str):
        """Handle scavenging for ship parts in salvage yard"""
        import random
        
        # Scavenging has costs (time/risk) but potential rewards
        scavenge_cost = random.randint(10, 30)  # Time cost in "minutes"
        
        # Check if player wants to spend the time
        success_chance = 0.4  # 40% chance of finding something useful
        
        if random.random() < success_chance:
            # Found something useful
            salvaged_items = [
                ("Salvaged Hull Plating", "ship_part", 1, "Damaged but repairable hull material", 45),
                ("Scrap Electronics", "component", random.randint(2, 5), "Useful electronic components", 15),
                ("Fuel Line Segment", "ship_part", 1, "Replacement fuel system component", 35),
                ("Navigation Computer Core", "component", 1, "Partially functional nav computer", 80),
                ("Power Coupling", "component", random.randint(1, 3), "Standard power system parts", 25),
                ("Thruster Nozzle", "ship_part", 1, "Worn but functional thruster component", 60),
                ("Sensor Array Module", "component", 1, "Damaged sensor equipment", 55),
                ("Emergency Beacon", "equipment", 1, "Distress signal transmitter", 40)
            ]
            
            item_name, item_type, quantity, description, value = random.choice(salvaged_items)
            
            # Add to inventory
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_type, quantity, description, value)
            )
            
            embed = discord.Embed(
                title="⚙️ Salvage Operation",
                description=f"**{char_name}** spends {scavenge_cost} minutes carefully scavenging through the salvage yard.",
                color=0x8B4513
            )
            embed.add_field(name="🔍 Discovery", value=f"{quantity}x {item_name}", inline=False)
            embed.add_field(name="📝 Condition", value=description, inline=False)
            embed.add_field(name="💰 Estimated Value", value=f"{value * quantity} credits", inline=True)
            embed.add_field(name="🛠️ Usage", value="Can be sold or used for ship modifications", inline=True)
            
            # Small chance of finding something extra valuable
            if random.random() < 0.1:  # 10% chance
                embed.add_field(
                    name="✨ Bonus Find", 
                    value="You also discover some useful technical documentation!", 
                    inline=False
                )
        else:
            # Found nothing useful
            nothing_found = [
                "The area has been thoroughly picked clean by previous scavengers.",
                "Most of the remaining parts are too damaged to be useful.",
                "You find only worthless scrap metal and burned-out components.",
                "Other scavengers have already taken anything of value.",
                "The salvage appears to be from very old, incompatible ship designs."
            ]
            
            embed = discord.Embed(
                title="⚙️ Salvage Operation",
                description=f"**{char_name}** spends {scavenge_cost} minutes searching the salvage yard.",
                color=0x696969
            )
            embed.add_field(name="🔍 Result", value="Nothing useful found", inline=False)
            embed.add_field(name="💭 Outcome", value=random.choice(nothing_found), inline=False)
            embed.add_field(name="⏰ Time Spent", value=f"{scavenge_cost} minutes", inline=True)
            
            # Small chance of at least finding basic scrap
            if random.random() < 0.3:  # 30% chance of consolation prize
                self.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (interaction.user.id, "Scrap Metal", "material", random.randint(1, 2), "Basic salvaged metal", 3)
                )
                embed.add_field(name="🔩 Consolation", value="Found small amount of scrap metal", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_repair_ship(self, interaction, char_name: str, money: int):
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        hull_integrity, max_hull = ship_info
        
        if hull_integrity >= max_hull:
            embed = discord.Embed(
                title="🔧 Ship Repair Bay",
                description=f"**{char_name}**, your ship's hull is in perfect condition.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate repair cost
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_order_drink(self, interaction, char_name: str, money: int):
        """Handle ordering drinks at the bar"""
        import random
        
        drinks = [
            ("Whiskey", 25, "A smooth whiskey aged in zero gravity."),
            ("Vodka", 20, "Crystal clear vodka from the colonies."),
            ("Beer", 15, "Local brew with a peculiar aftertaste."),
            ("Synthale", 10, "Synthetic alcohol, safe and reliable."),
            ("Absinthe", 18, "Dark Green and fruity, very inotixicating.")
        ]
        
        drink_name, cost, description = random.choice(drinks)
        
        if money < cost:
            embed = discord.Embed(
                title="🍺 The Bar",
                description=f"**{char_name}**, you don't have enough credits for a drink.\n**{drink_name}** costs {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_listen_gossip(self, interaction, char_name: str):
        """Handle listening to gossip at the bar"""
        import random
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_relax(self, interaction, char_name: str):
        """Handle relaxing in the lounge"""
        import random
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_watch_news(self, interaction, char_name: str):
        """Handle watching news in the lounge"""
        import random
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_buy_medical(self, interaction, char_name: str, money: int):
        """Handle buying medical supplies"""
        embed = discord.Embed(
            title="💊 Medical Supplies",
            description=f"**{char_name}**, medical supply purchasing is currently being prepared.",
            color=0x708090
        )
        embed.add_field(name="📋 Status", value="This service will be available in a future update.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_health_checkup(self, interaction, char_name: str, hp: int, max_hp: int):
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_ship_diagnostics(self, interaction, char_name: str):
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_play_cards(self, interaction, char_name: str, money: int):
        """Handle playing cards at the bar"""
        import random
        
        if money < 20:
            embed = discord.Embed(
                title="🎲 Card Game",
                description=f"**{char_name}**, you need at least 20 credits to join a card game.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_refreshments(self, interaction, char_name: str, money: int):
        """Handle getting refreshments"""
        cost = 8
        
        if money < cost:
            embed = discord.Embed(
                title="☕ Refreshments",
                description=f"**{char_name}**, refreshments cost {cost} credits.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        self.db.execute_query(
            "UPDATE characters SET money = ? WHERE user_id = ?",
            (money - cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="☕ Refreshments",
            description=f"**{char_name}** enjoys some light refreshments.",
            color=0x8b4513
        )
        embed.add_field(name="💭 Effect", value="You feel refreshed and ready to continue.", inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{money - cost}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_browse_shops(self, interaction, char_name: str):
        """Handle browsing shops"""
        embed = discord.Embed(
            title="🛒 Shop Browser",
            description=f"**{char_name}** browses the available shops.",
            color=0x708090
        )
        embed.add_field(name="📋 Status", value="Use `/shop list` to see available items for purchase.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_apply_permits(self, interaction, char_name: str, money: int):
        """Handle applying for permits"""
        embed = discord.Embed(
            title="📝 Permit Applications",
            description=f"Apply for some permits.",
            color=0x708090
        )
        embed.add_field(name="📋 Status", value="The governement agency will have your permit application reviewed within: 90 years.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_equipment_mods(self, interaction, char_name: str, money: int):
        """Enhanced equipment modification services"""
        import random
        
        # Check if player has any ship components or equipment to modify
        equipment = self.db.execute_query(
            '''SELECT item_name, item_type, quantity FROM inventory 
               WHERE owner_id = ? AND item_type IN ('equipment', 'ship_component', 'component')
               LIMIT 5''',
            (interaction.user.id,),
            fetch='all'
        )
        
        modifications = [
            ("Performance Boost", 200, "Increase item efficiency by 10%"),
            ("Durability Enhancement", 150, "Extend item lifespan significantly"),
            ("Size Optimization", 100, "Reduce item storage requirements"),
            ("Compatibility Upgrade", 250, "Make item work with more systems")
        ]
        
        mod_name, mod_cost, mod_desc = random.choice(modifications)
        
        embed = discord.Embed(
            title="⚙️ Equipment Modifications",
            description=f"**{char_name}** explores equipment modification services.",
            color=0xff6347
        )
        
        if equipment:
            equip_list = []
            for item_name, item_type, quantity in equipment:
                equip_list.append(f"• {item_name} ({quantity}x) - {item_type}")
            
            embed.add_field(
                name="🔧 Your Modifiable Equipment",
                value="\n".join(equip_list),
                inline=False
            )
        else:
            embed.add_field(
                name="📦 No Equipment",
                value="You don't have any equipment available for modification.",
                inline=False
            )
        
        embed.add_field(name="⚡ Featured Modification", value=mod_name, inline=False)
        embed.add_field(name="💰 Cost", value=f"{mod_cost} credits", inline=True)
        embed.add_field(name="📋 Effect", value=mod_desc, inline=True)
        
        embed.add_field(
            name="🛠️ Modification Process",
            value="Modifications are permanent improvements that enhance your equipment's capabilities.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_ship_storage(self, interaction, char_name: str, money: int):
        """Enhanced ship storage services"""
        import random
        
        storage_services = [
            ("Short-term Parking", 20, "Safe parking for up to 24 hours"),
            ("Extended Storage", 100, "Secure storage for up to 7 days"),
            ("Maintenance Storage", 150, "Storage with basic maintenance included"),
            ("Premium Hangar", 300, "Climate-controlled storage with security")
        ]
        
        service_name, cost, description = random.choice(storage_services)
        
        embed = discord.Embed(
            title="🚁 Ship Storage Services",
            description=f"**{char_name}** inquires about ship storage options.",
            color=0x4682b4
        )
        
        embed.add_field(name="🏢 Featured Service", value=service_name, inline=False)
        embed.add_field(name="💰 Cost", value=f"{cost} credits", inline=True)
        embed.add_field(name="📝 Details", value=description, inline=True)
        
        embed.add_field(
            name="🛡️ Storage Benefits",
            value="• Protection from environmental hazards\n• Security monitoring\n• Insurance coverage\n• Easy retrieval access",
            inline=False
        )
        
        if money >= cost:
            embed.add_field(name="✅ Status", value="Service available", inline=True)
        else:
            embed.add_field(name="❌ Status", value="Insufficient funds", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_generic_service(self, interaction, service_type: str, char_name: str):
        """Handle generic/flavor services"""
        import random
        
        generic_responses = {
            "equipment_mods": "You browse available modifications, but nothing catches your eye right now.",
            "ship_storage": "Storage services are available, but you don't need them at the moment.",
            "cargo_services": "Cargo handling services are ready when you need them.",
            "check_prices": "You review current market prices and make mental notes.",
            "specialty_vendors": "You browse specialty items but don't find anything you need right now.",
            "records_request": "Administrative records are available for review if needed.",
            "report_incident": "Security services are available if you need to report anything.",
            "security_consult": "Security personnel are available for consultation."
        }
        
        response = generic_responses.get(service_type, "You interact with the service but find nothing of immediate interest.")
        
        embed = discord.Embed(
            title="🏢 Service Interaction",
            description=f"**{char_name}** uses the available services.",
            color=0x708090
        )
        embed.add_field(name="📋 Result", value=response, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    # Additional Security Services
    async def _handle_request_escort(self, interaction, char_name: str):
        """Handle requesting security escort"""
        embed = discord.Embed(
            title="👮 Security Escort",
            description=f"**{char_name}** requests a security escort for safe passage.",
            color=0x4169e1
        )
        embed.add_field(name="📋 Service", value="Security personnel will accompany you during travel if needed.", inline=False)
        embed.add_field(name="💰 Cost", value="50 credits per corridor jump", inline=True)
        embed.add_field(name="⏱️ Availability", value="Based on current security status", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_file_complaint(self, interaction, char_name: str):
        """Handle filing a complaint"""
        embed = discord.Embed(
            title="📝 File Complaint",
            description=f"**{char_name}** files an official complaint with security.",
            color=0xff6347
        )
        embed.add_field(name="📋 Process", value="Your complaint has been logged and will be reviewed by security officials.", inline=False)
        embed.add_field(name="🔍 Investigation", value="Serious complaints may result in formal investigations.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Dormitory Services
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_use_facilities(self, interaction, char_name: str):
        """Handle using dormitory facilities"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Research Lab Services
    async def _handle_browse_research(self, interaction, char_name: str):
        """Handle browsing research projects"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_use_equipment(self, interaction, char_name: str):
        """Handle using research equipment"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_review_data(self, interaction, char_name: str):
        """Handle reviewing research data"""
        data_insights = [
            "Recent corridor mapping shows unusual stability patterns",
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_collaborate(self, interaction, char_name: str):
        """Handle collaborating with researchers"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Hydroponics Services
    async def _handle_tour_gardens(self, interaction, char_name: str):
        """Handle touring the hydroponics gardens"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_fresh_produce(self, interaction, char_name: str, money: int):
        """Handle buying fresh produce"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_learn_techniques(self, interaction, char_name: str):
        """Handle learning hydroponics techniques"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Recreation Services
    async def _handle_play_games(self, interaction, char_name: str):
        """Handle playing games in recreation"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_exercise(self, interaction, char_name: str, hp: int, max_hp: int):
        """Handle exercising in recreation"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_join_activity(self, interaction, char_name: str):
        """Handle joining recreational activities"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_relax_unwind(self, interaction, char_name: str):
        """Handle relaxing and unwinding"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Communications Services
    async def _handle_send_message(self, interaction, char_name: str, money: int):
        """Handle sending messages"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_check_signals(self, interaction, char_name: str):
        """Handle checking communication signals"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_monitor_channels(self, interaction, char_name: str):
        """Handle monitoring communication channels"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Cafeteria Services
    async def _handle_order_meal(self, interaction, char_name: str, money: int, hp: int, max_hp: int):
        """Handle ordering a meal"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _handle_cargo_services(self, interaction, char_name: str, money: int):
        """Enhanced cargo services"""
        import random
        
        # Check ship cargo status
        ship_info = self.db.execute_query(
            "SELECT cargo_capacity, cargo_used, name FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            embed = discord.Embed(
                title="📦 Cargo Services",
                description="No ship found for cargo operations.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        cargo_capacity, cargo_used, ship_name = ship_info
        cargo_free = cargo_capacity - cargo_used
        
        services = []
        
        if cargo_used > 0:
            services.append("🔄 **Cargo Reorganization** - Optimize storage layout (50 credits)")
        
        if cargo_free > 0:
            services.append("📦 **Temporary Storage** - Store items while docked (10 credits/day)")
        
        services.extend([
            "🏷️ **Cargo Manifest Update** - Update shipping documentation (25 credits)",
            "🔍 **Cargo Inspection** - Security scan and certification (75 credits)",
            "⚖️ **Weight Distribution** - Balance cargo for optimal flight (40 credits)"
        ])
        
        embed = discord.Embed(
            title="📦 Cargo Services",
            description=f"**{char_name}** reviews cargo handling services for the **{ship_name}**.",
            color=0x8b4513
        )
        
        embed.add_field(
            name="🚀 Current Cargo Status",
            value=f"Used: {cargo_used}/{cargo_capacity} units\nFree Space: {cargo_free} units",
            inline=True
        )
        
        embed.add_field(
            name="🛠️ Available Services",
            value="\n".join(services),
            inline=False
        )
        
        embed.add_field(
            name="💰 Your Credits",
            value=f"{money:,} credits",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
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
    # Transit Lounge Services
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_check_schedules(self, interaction, char_name: str):
        """Handle checking transit schedules"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_travel_info(self, interaction, char_name: str):
        """Handle getting travel information"""
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    async def _handle_browse_shops(self, interaction, char_name: str):
        """Handle browsing shops - show actual shop inventory"""
        await interaction.response.defer(ephemeral=True)
        
        # Get shop items for this location
        items = self.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description
               FROM shop_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1)
               ORDER BY item_type, price''',
            (self.location_id,),
            fetch='all'
        )
        
        # Get location info for shop generation if needed
        location_info = self.db.execute_query(
            "SELECT name, wealth_level, location_type FROM locations WHERE location_id = ?",
            (self.location_id,),
            fetch='one'
        )
        
        if not items and location_info:
            # Generate shop items if none exist
            economy_cog = self.bot.get_cog('EconomyCog')
            if economy_cog:
                await economy_cog._generate_shop_items(self.location_id, location_info[1], location_info[2])
                items = self.db.execute_query(
                    '''SELECT item_name, item_type, price, stock, description
                       FROM shop_items 
                       WHERE location_id = ? AND (stock > 0 OR stock = -1)
                       ORDER BY item_type, price''',
                    (self.location_id,),
                    fetch='all'
                )
        
        embed = discord.Embed(
            title="🛒 Market District Shops",
            description=f"**{char_name}** browses the available shops and vendors.",
            color=0xffd700
        )
        
        if items:
            # Group items by type
            item_types = {}
            for item_name, item_type, price, stock, description in items:
                if item_type not in item_types:
                    item_types[item_type] = []
                
                stock_text = f"({stock} in stock)" if stock != -1 else "(Unlimited)"
                item_types[item_type].append(f"**{item_name}** - {price:,} credits {stock_text}")
            
            for item_type, type_items in item_types.items():
                embed.add_field(
                    name=item_type.replace('_', ' ').title(),
                    value="\n".join(type_items[:5]),  # Limit to 5 items per type
                    inline=True
                )
        else:
            embed.add_field(name="No Items Available", value="The shops are currently out of stock.", inline=False)
        
        embed.add_field(
            name="💡 How to Buy",
            value="Use `/shop buy <item_name> [quantity]` to purchase items",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _handle_specialty_vendors(self, interaction, char_name: str, money: int):
        """Handle specialty vendor interactions with rare items"""
        import random
        
        # Specialty items that are rare/unique
        specialty_items = [
            ("Advanced Navigation Array", "ship_component", 2500, "Reduces travel time by 15%", 1),
            ("Medical Nano-Kit", "medical", 800, "Instantly restores 50 HP when used", 2),
            ("Encrypted Data Core", "information", 1200, "Contains valuable trade route data", 1),
            ("Rare Alloy Sample", "material", 1500, "Premium ship hull reinforcement material", 3),
            ("Personal Shield Generator", "equipment", 3000, "Provides protection during dangerous encounters", 1),
            ("Quantum Fuel Stabilizer", "ship_component", 1800, "Improves fuel efficiency by 20%", 2),
            ("Black Market Contacts", "information", 2200, "Access to exclusive underground markets", 1),
            ("Emergency Beacon", "equipment", 600, "Calls for rescue in critical situations", 4),
        ]
        
        # Randomly select 2-4 items available today
        available_items = random.sample(specialty_items, random.randint(2, 4))
        
        embed = discord.Embed(
            title="🏪 Specialty Vendors",
            description=f"**{char_name}** visits the exclusive specialty vendors.",
            color=0x9400d3
        )
        
        embed.add_field(
            name="✨ Today's Rare Offerings",
            value="These items are only available from specialty vendors and may not appear again.",
            inline=False
        )
        
        items_text = []
        for item_name, item_type, price, description, stock in available_items:
            affordability = "✅" if money >= price else "❌"
            items_text.append(f"{affordability} **{item_name}** - {price:,} credits ({stock} available)")
            items_text.append(f"   *{description}*")
        
        embed.add_field(
            name="🛍️ Available Items",
            value="\n".join(items_text),
            inline=False
        )
        
        embed.add_field(
            name="💰 Your Credits",
            value=f"{money:,} credits",
            inline=True
        )
        
        embed.add_field(
            name="💡 Purchase",
            value="Contact the vendor directly to negotiate purchases of these rare items.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_check_prices(self, interaction, char_name: str):
        """Handle checking current market prices"""
        import random
        
        # Get some sample items and their prices from the shop
        sample_items = self.db.execute_query(
            '''SELECT item_name, price FROM shop_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1)
               ORDER BY RANDOM() LIMIT 6''',
            (self.location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="📈 Market Price Check",
            description=f"**{char_name}** reviews current market prices.",
            color=0x4169e1
        )
        
        if sample_items:
            price_list = []
            for item_name, price in sample_items:
                # Add some price variation flavor
                trend = random.choice(["📈 +5%", "📉 -3%", "📊 stable", "📊 stable", "📊 stable"])
                price_list.append(f"**{item_name}**: {price:,} credits {trend}")
            
            embed.add_field(
                name="💰 Current Prices",
                value="\n".join(price_list),
                inline=False
            )
        else:
            embed.add_field(
                name="📊 Market Status",
                value="No price data available at this time.",
                inline=False
            )
        
        # Add some market intelligence
        market_conditions = [
            "Fuel prices expected to rise due to corridor instabilities",
            "Medical supplies in high demand at outer colonies",
            "Ship parts showing price volatility across different systems",
            "Food prices stable due to good hydroponics yields",
            "Luxury goods commanding premium prices at wealthy stations"
        ]
        
        embed.add_field(
            name="📰 Market Intelligence",
            value=random.choice(market_conditions),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
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
        await interaction.response.defer(ephemeral=True)
        
        # Check character funds
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not money or money[0] < self.cost:
            await interaction.followup.send(
                f"❌ You don't have enough credits. This change costs {self.cost:,} credits.",
                ephemeral=True
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
                ephemeral=True
            )
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid input: {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

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