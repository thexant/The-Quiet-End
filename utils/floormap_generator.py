# utils/floormap_generator.py
import random
import os
from typing import Dict, List, Tuple, Optional
from utils.sub_locations import SubLocationManager

class FloormapGenerator:
    """
    Generates unique, deterministic floormaps for locations based on their properties.
    Uses location_id as seed to ensure same location always generates identical map.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.sub_manager = SubLocationManager(bot)
        self.floormaps_dir = "floormaps"
        
        # Ensure floormaps directory exists
        os.makedirs(self.floormaps_dir, exist_ok=True)
        
        # Room symbols for ASCII maps
        self.room_symbols = {
            'bar': '🍺',
            'medbay': '⚕️',
            'engineering': '🔧',
            'security': '🛡️',
            'hangar': '🚁',
            'lounge': '🛋️',
            'market': '🛒',
            'admin': '📋',
            'casino': '🎰',
            'dormitory': '🛏️',
            'research': '🔬',
            'hydroponics': '🌱',
            'recreation': '🎮',
            'communications': '📡',
            'storage': '📦',
            'corridor': '─',
            'vertical_corridor': '│',
            'junction': '┼',
            'corner_tl': '┌',
            'corner_tr': '┐',
            'corner_bl': '└',
            'corner_br': '┘',
            'wall_h': '─',
            'wall_v': '│',
            'door': ' ',
            'wall': '█',
            'open': ' ',
            'plaza': '🌳',
            'park': '🌲',
            'residential': '🏠'
        }
    
    def get_floormap_path(self, location_id: int) -> str:
        """Get file path for location's floormap"""
        return os.path.join(self.floormaps_dir, f"{location_id}.txt")
    
    def load_cached_floormap(self, location_id: int) -> Optional[str]:
        """Load existing floormap from cache if it exists"""
        filepath = self.get_floormap_path(location_id)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Error loading cached floormap for location {location_id}: {e}")
        return None
    
    def save_floormap(self, location_id: int, floormap: str):
        """Save generated floormap to cache"""
        filepath = self.get_floormap_path(location_id)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(floormap)
        except Exception as e:
            print(f"Error saving floormap for location {location_id}: {e}")
    
    def get_location_data(self, location_id: int) -> Optional[Dict]:
        """Get location data needed for floormap generation"""
        location_data = self.db.execute_query(
            """SELECT location_id, name, location_type, wealth_level, population, 
                      is_derelict, faction, description
               FROM locations WHERE location_id = %s""",
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            return None
            
        return {
            'location_id': location_data[0],
            'name': location_data[1],
            'location_type': location_data[2],
            'wealth_level': location_data[3],
            'population': location_data[4],
            'is_derelict': bool(location_data[5]),
            'faction': location_data[6],
            'description': location_data[7]
        }
    
    def get_actual_sub_locations(self, location_id: int) -> List[Dict]:
        """Get actual sub-locations that exist at this location from the database"""
        sub_locations = self.db.execute_query(
            """SELECT sub_location_id, name, sub_type, description, is_active 
               FROM sub_locations 
               WHERE parent_location_id = %s AND is_active = true""",
            (location_id,),
            fetch='all'
        )
        
        if not sub_locations:
            return []
        
        sub_location_list = []
        for sub_loc in sub_locations:
            sub_location_data = {
                'id': sub_loc[0],
                'name': sub_loc[1],
                'type': sub_loc[2],
                'description': sub_loc[3],
                'is_active': bool(sub_loc[4])
            }
            
            # Get icon and size info from sub_manager
            type_info = self.sub_manager.sub_location_types.get(sub_loc[2], {})
            sub_location_data['icon'] = type_info.get('icon', '🏢')
            sub_location_data['size'] = self._get_room_size(sub_loc[2])
            
            sub_location_list.append(sub_location_data)
        
        return sub_location_list
    
    def get_available_rooms(self, location_data: Dict) -> List[str]:
        """Get list of available sub-location types for this location (for fallback)"""
        available_rooms = []
        location_type = location_data['location_type']
        wealth_level = location_data['wealth_level']
        
        for room_type, room_info in self.sub_manager.sub_location_types.items():
            # Check if this room type is available for this location type
            if location_type in room_info.get('location_types', []):
                # Check wealth requirement if specified
                min_wealth = room_info.get('min_wealth', 0)
                if wealth_level >= min_wealth:
                    available_rooms.append(room_type)
        
        return available_rooms
    
    def _get_room_size(self, room_type: str) -> str:
        """Determine the size category of a room type"""
        large_rooms = ['hangar', 'market', 'casino', 'research', 'hydroponics', 'recreation']
        medium_rooms = ['bar', 'medbay', 'engineering', 'security', 'lounge', 'admin']
        small_rooms = ['dormitory', 'communications', 'storage']
        
        if room_type in large_rooms:
            return 'large'
        elif room_type in medium_rooms:
            return 'medium'
        elif room_type in small_rooms:
            return 'small'
        else:
            return 'medium'  # Default
    
    def generate_floormap(self, location_id: int) -> Optional[str]:
        """
        Generate a unique floormap for the given location.
        Returns the floormap string, or None if location not found.
        """
        # Check cache first
        cached_map = self.load_cached_floormap(location_id)
        if cached_map:
            return cached_map
        
        # Get location data
        location_data = self.get_location_data(location_id)
        if not location_data:
            return None
        
        # Set random seed based on location_id for deterministic generation
        random.seed(location_id)
        
        # Get actual sub-locations for this location
        actual_sub_locations = self.get_actual_sub_locations(location_id)
        
        # Generate floormap based on location type
        location_type = location_data['location_type']
        
        if location_type == 'colony':
            floormap = self._generate_colony_map(location_data, actual_sub_locations)
        elif location_type == 'space_station':
            floormap = self._generate_station_map(location_data, actual_sub_locations)
        elif location_type == 'outpost':
            floormap = self._generate_outpost_map(location_data, actual_sub_locations)
        elif location_type == 'gate':
            floormap = self._generate_gate_map(location_data, actual_sub_locations)
        else:
            # Default to outpost for unknown types
            floormap = self._generate_outpost_map(location_data, actual_sub_locations)
        
        # Apply derelict modifications if needed
        if location_data['is_derelict']:
            floormap = self._apply_derelict_damage(floormap, location_data)
        
        # Save to cache
        self.save_floormap(location_id, floormap)
        
        return floormap
    
    def _generate_colony_map(self, location_data: Dict, sub_locations: List[Dict]) -> str:
        """Generate floormap for a colony (largest, city-like layout)"""
        wealth = location_data['wealth_level']
        population = location_data['population']
        
        # Create header
        header = f"═══ {location_data['name']} ═══\n"
        header += f"Colony • Population: {population:,} • Wealth Level: {wealth}\n"
        if location_data['faction'] != 'Independent':
            header += f"Faction: {location_data['faction']}\n"
        header += "\n"
        
        # Organize sub-locations by placement zones
        residential = [sl for sl in sub_locations if sl['type'] in ['dormitory', 'lounge']]
        commercial = [sl for sl in sub_locations if sl['type'] in ['market', 'bar', 'casino']]
        admin = [sl for sl in sub_locations if sl['type'] in ['admin', 'security']]
        special = [sl for sl in sub_locations if sl['type'] in ['research', 'medbay', 'hydroponics', 'recreation']]
        industrial = [sl for sl in sub_locations if sl['type'] in ['engineering', 'hangar', 'storage', 'communications']]
        
        layout = []
        
        # Colony district layout with actual spatial relationships
        layout.append("┌─────────────────────────────────────────────────────────────┐")
        layout.append("│                      COLONY ENTRANCE                       │")
        layout.append("└───────────────────────┬─────────────────────────────────────┘")
        layout.append("                        │ MAIN AVENUE                          ")
        layout.append("┌───────────────────────┼─────────────────────────────────────┐")
        
        # Left side - Residential area
        res_area_1 = residential[0] if len(residential) > 0 else {'icon': '🏠', 'name': 'Housing'}
        res_area_2 = residential[1] if len(residential) > 1 else {'icon': '🛋️', 'name': 'Commons'}
        
        layout.append(f"│ 🌳  RESIDENTIAL DISTRICT  │                                 │")
        layout.append(f"│ ┌─────────────────────┐   │         CENTRAL PLAZA         │")
        layout.append(f"│ │ {res_area_1['icon']} {res_area_1['name'][:12]:<12}      │   │                                 │")
        layout.append(f"│ │                     │   │           🌳 🗿 🌳             │")
        layout.append(f"│ │ {res_area_2['icon']} {res_area_2['name'][:12]:<12}      │   │                                 │")
        layout.append(f"│ └─────────────────────┘   │                                 │")
        layout.append("├───────────────────────────┼─────────────────────────────────┤")
        
        # Bottom left - Administrative
        admin_room = admin[0] if admin else {'icon': '📋', 'name': 'Administration'}
        sec_room = admin[1] if len(admin) > 1 else {'icon': '🛡️', 'name': 'Security'}
        
        layout.append(f"│  GOVERNMENT COMPLEX       │                                 │")
        layout.append(f"│ ┌─────────┐ ┌─────────┐   │        COMMERCIAL SECTOR        │")
        layout.append(f"│ │ {admin_room['icon']} {admin_room['name'][:6]:<6} │ │ {sec_room['icon']} {sec_room['name'][:6]:<6} │   │                                 │")
        layout.append(f"│ │         │ │         │   │                                 │")
        layout.append(f"│ └─────────┘ └─────────┘   │                                 │")
        
        # Right side - Commercial area
        comm_1 = commercial[0] if len(commercial) > 0 else {'icon': '🛒', 'name': 'Market'}
        comm_2 = commercial[1] if len(commercial) > 1 else {'icon': '🍺', 'name': 'Cantina'}
        comm_3 = commercial[2] if len(commercial) > 2 else {'icon': '🎰', 'name': 'Recreation'}
        
        layout.append(f"└───────────────────────────┤ ┌─────┐ ┌─────┐ ┌─────┐ │")
        layout.append(f"                            │ │ {comm_1['icon']} {comm_1['name'][:3]:<3} │ │ {comm_2['icon']} {comm_2['name'][:3]:<3} │ │ {comm_3['icon']} {comm_3['name'][:3]:<3} │ │")
        layout.append(f"                            │ │     │ │     │ │     │ │")
        layout.append(f"                            │ └─────┘ └─────┘ └─────┘ │")
        layout.append("                            └─────────────────────────┘")
        layout.append("                                        │                ")
        
        # Special facilities section
        if special:
            layout.append("┌───────────────────────────────────────┼─────────────────────┐")
            layout.append("│           SPECIAL FACILITIES          │   INDUSTRIAL ZONE   │")
            spec_1 = special[0] if len(special) > 0 else None
            spec_2 = special[1] if len(special) > 1 else None
            
            if spec_1 and spec_2:
                layout.append(f"│ ┌─────────────────┐ ┌─────────────────┐│                     │")
                layout.append(f"│ │ {spec_1['icon']} {spec_1['name'][:12]:<12}    │ │ {spec_2['icon']} {spec_2['name'][:12]:<12}    ││                     │")
                layout.append(f"│ │                 │ │                 ││                     │")
                layout.append(f"│ └─────────────────┘ └─────────────────┘│                     │")
            elif spec_1:
                layout.append(f"│ ┌─────────────────────────────────────┐│                     │")
                layout.append(f"│ │ {spec_1['icon']} {spec_1['name']:<28}   ││                     │")
                layout.append(f"│ │                                     ││                     │")
                layout.append(f"│ └─────────────────────────────────────┘│                     │")
            
            # Industrial area
            ind_1 = industrial[0] if len(industrial) > 0 else {'icon': '🔧', 'name': 'Workshop'}
            ind_2 = industrial[1] if len(industrial) > 1 else {'icon': '📦', 'name': 'Storage'}
            
            layout.append(f"└───────────────────────────────────────┤ ┌─────────────────┐ │")
            layout.append(f"                                        │ │ {ind_1['icon']} {ind_1['name'][:12]:<12}    │ │")
            layout.append(f"                                        │ │                 │ │")
            layout.append(f"                                        │ └─────────────────┘ │")
            layout.append(f"                                        │ ┌─────────────────┐ │")
            layout.append(f"                                        │ │ {ind_2['icon']} {ind_2['name'][:12]:<12}    │ │")
            layout.append(f"                                        │ └─────────────────┘ │")
            layout.append("                                        └─────────────────────┘")
        
        # Add facility directory
        if sub_locations:
            layout.append("")
            layout.append("FACILITY DIRECTORY:")
            for sub_loc in sub_locations:
                layout.append(f"• {sub_loc['icon']} {sub_loc['name']}")
        
        full_map = header + "\n".join(layout)
        return full_map
    
    def _generate_station_map(self, location_data: Dict, sub_locations: List[Dict]) -> str:
        """Generate floormap for a space station (medium, hub-and-spoke layout)"""
        wealth = location_data['wealth_level']
        population = location_data['population']
        
        # Create header
        header = f"═══ {location_data['name']} ═══\n"
        header += f"Space Station • Population: {population:,} • Wealth Level: {wealth}\n"
        if location_data['faction'] != 'Independent':
            header += f"Faction: {location_data['faction']}\n"
        header += "\n"
        
        # Organize sub-locations by placement zones
        residential = [sl for sl in sub_locations if sl['type'] in ['dormitory', 'lounge']]
        service = [sl for sl in sub_locations if sl['type'] in ['medbay', 'bar', 'market', 'admin', 'recreation']]
        technical = [sl for sl in sub_locations if sl['type'] in ['engineering', 'hangar', 'storage', 'communications']]
        special = [sl for sl in sub_locations if sl['type'] in ['research', 'security', 'casino', 'hydroponics']]
        
        # Hub-and-spoke station design with actual spatial layout
        layout = []
        
        # Docking ring
        layout.append("                ┌────┐  ┌────┐                ")
        layout.append("                │🚁 01│  │🚁 02│                ")
        layout.append("                └──┬─┘  └─┬──┘                ")
        layout.append("                   │      │                   ")
        layout.append("┌─────────────────┐└──┬───┘┌─────────────────┐")
        
        # Residential pods
        res_a = residential[0] if len(residential) > 0 else {'icon': '🛏️', 'name': 'Quarters A'}
        res_b = residential[1] if len(residential) > 1 else {'icon': '🛏️', 'name': 'Quarters B'}
        
        layout.append(f"│   RESIDENTIAL A   │  │  │   RESIDENTIAL B   │")
        layout.append(f"│ ┌───────────────┐ │  │  │ ┌───────────────┐ │")
        layout.append(f"│ │ {res_a['icon']} {res_a['name'][:10]:<10}    │ │  │  │ │ {res_b['icon']} {res_b['name'][:10]:<10}    │ │")
        layout.append(f"│ │               │ │  │  │ │               │ │")
        layout.append(f"│ │  🛏️  🛏️  🛏️   │ │  │  │ │  🛏️  🛏️  🛏️   │ │")
        layout.append(f"│ └───────────────┘ │  │  │ └───────────────┘ │")
        layout.append("└─────────────────┬─┘  │  └─┬─────────────────┘")
        layout.append("                  │    │    │                  ")
        
        # Central hub
        hub_service_1 = service[0] if len(service) > 0 else {'icon': '🛋️', 'name': 'Lounge'}
        hub_service_2 = service[1] if len(service) > 1 else {'icon': '📋', 'name': 'Admin'}
        
        layout.append("                  └────┼────┘                  ")
        layout.append("               ┌───────┼───────┐               ")
        layout.append("               │   CENTRAL HUB  │               ")
        layout.append(f"               │                │               ")
        layout.append(f"               │  {hub_service_1['icon']} {hub_service_1['name'][:6]:<6}     │               ")
        layout.append(f"               │  {hub_service_2['icon']} {hub_service_2['name'][:6]:<6}     │               ")
        layout.append("               │                │               ")
        layout.append("               └─┬─────────────┬─┘               ")
        layout.append("                 │             │                 ")
        
        # Service levels
        service_rooms = service[2:] if len(service) > 2 else []
        svc_1 = service_rooms[0] if len(service_rooms) > 0 else {'icon': '⚕️', 'name': 'Medical'}
        svc_2 = service_rooms[1] if len(service_rooms) > 1 else {'icon': '🛒', 'name': 'Shop'}
        
        layout.append("┌────────────────┘             └────────────────┐")
        layout.append(f"│   SERVICE BAY A                SERVICE BAY B   │")
        layout.append(f"│ ┌─────────────┐               ┌─────────────┐ │")
        layout.append(f"│ │ {svc_1['icon']} {svc_1['name'][:8]:<8}    │               │ {svc_2['icon']} {svc_2['name'][:8]:<8}    │ │")
        layout.append(f"│ │             │               │             │ │")
        layout.append(f"│ └─────────────┘               └─────────────┘ │")
        layout.append("└─┬─────────────┐               ┌─────────────┬─┘")
        layout.append("  │             │               │             │  ")
        
        # Technical/Engineering level
        tech_a = technical[0] if len(technical) > 0 else {'icon': '🔧', 'name': 'Engineering'}
        tech_b = technical[1] if len(technical) > 1 else {'icon': '📦', 'name': 'Storage'}
        
        layout.append("┌─┴─────────────┐               ┌─────────────┴─┐")
        layout.append(f"│ TECHNICAL A    │               │ TECHNICAL B    │")
        layout.append(f"│ ┌───────────┐  │               │ ┌───────────┐  │")
        layout.append(f"│ │ {tech_a['icon']} {tech_a['name'][:6]:<6}   │  │               │ │ {tech_b['icon']} {tech_b['name'][:6]:<6}   │  │")
        layout.append(f"│ │           │  │               │ │           │  │")
        layout.append(f"│ └───────────┘  │               │ └───────────┘  │")
        layout.append("└────────────────┘               └────────────────┘")
        
        # Special facilities (if any)
        if special:
            layout.append("")
            layout.append("        ┌─────────────────────────────┐        ")
            layout.append("        │      SPECIAL SECTION        │        ")
            for i, facility in enumerate(special[:2]):  # Max 2 special facilities
                layout.append(f"        │ {facility['icon']} {facility['name']:<20}      │        ")
            layout.append("        └─────────────────────────────┘        ")
        
        # Add facility directory
        if sub_locations:
            layout.append("")
            layout.append("STATION DIRECTORY:")
            for sub_loc in sub_locations:
                layout.append(f"• {sub_loc['icon']} {sub_loc['name']} - {sub_loc['type'].title()}")
        
        full_map = header + "\n".join(layout)
        return full_map
    
    def _generate_outpost_map(self, location_data: Dict, sub_locations: List[Dict]) -> str:
        """Generate floormap for an outpost (small, compact functional layout)"""
        wealth = location_data['wealth_level']
        population = location_data['population']
        
        # Create header
        header = f"═══ {location_data['name']} ═══\n"
        header += f"Outpost • Population: {population:,} • Wealth Level: {wealth}\n"
        if location_data['faction'] != 'Independent':
            header += f"Faction: {location_data['faction']}\n"
        header += "\n"
        
        # Organize sub-locations for compact placement
        primary = sub_locations[:3] if sub_locations else []
        secondary = sub_locations[3:5] if len(sub_locations) > 3 else []
        
        # Compact functional layout with actual rooms
        layout = []
        
        # Entry airlock
        layout.append("      ┌───────────────────────┐      ")
        layout.append("      │        AIRLOCK        │      ")
        layout.append("      └─────────┬─────────────┘      ")
        layout.append("                │                    ")
        layout.append("                │ MAIN CORRIDOR      ")
        layout.append("                │                    ")
        layout.append("┌───────────────┼───────────────────┐")
        layout.append("│               │                   │")
        
        # Top row - primary facilities
        if len(primary) >= 3:
            room_a = primary[0]
            room_b = primary[1] 
            room_c = primary[2]
        elif len(primary) == 2:
            room_a = primary[0]
            room_b = primary[1]
            room_c = {'icon': '🛏️', 'name': 'Quarters'}
        elif len(primary) == 1:
            room_a = primary[0]
            room_b = {'icon': '🖥️', 'name': 'Control'}
            room_c = {'icon': '🛏️', 'name': 'Quarters'}
        else:
            # Default layout if no sub-locations
            room_a = {'icon': '📦', 'name': 'Storage'}
            room_b = {'icon': '🖥️', 'name': 'Control'}
            room_c = {'icon': '🛏️', 'name': 'Quarters'}
        
        layout.append(f"│ ┌───────────┐ │ ┌───────────────┐ │")
        layout.append(f"│ │ {room_a['icon']} {room_a['name'][:8]:<8}  │ │ │ {room_b['icon']} {room_b['name'][:10]:<10}   │ │")
        layout.append(f"│ │           │ │ │               │ │")
        layout.append(f"│ └───────────┘ │ └───────────────┘ │")
        layout.append(f"├───────────────┤                   │")
        layout.append(f"│ ┌───────────┐ │                   │")
        layout.append(f"│ │ {room_c['icon']} {room_c['name'][:8]:<8}  │ │                   │")
        layout.append(f"│ │           │ │                   │")
        layout.append(f"│ └───────────┘ │                   │")
        layout.append("├───────────────┼───────────────────┤")
        layout.append("│               │                   │")
        
        # Bottom row - secondary facilities or shared areas
        if len(secondary) >= 2:
            room_d = secondary[0]
            room_e = secondary[1]
        elif len(secondary) == 1:
            room_d = secondary[0]
            room_e = {'icon': '🔧', 'name': 'Maintenance'}
        else:
            # Default bottom layout based on wealth
            if wealth >= 3:
                room_d = {'icon': '⚕️', 'name': 'Medical'}
                room_e = {'icon': '📦', 'name': 'Supply'}
            else:
                room_d = {'icon': '📦', 'name': 'Storage'}
                room_e = {'icon': '🔧', 'name': 'Maintenance'}
        
        layout.append(f"│ ┌───────────┐ │ ┌───────────────┐ │")
        layout.append(f"│ │ {room_d['icon']} {room_d['name'][:8]:<8}  │ │ │ {room_e['icon']} {room_e['name'][:10]:<10}   │ │")
        layout.append(f"│ │           │ │ │               │ │")
        layout.append(f"│ └───────────┘ │ └───────────────┘ │")
        layout.append("│               │                   │")
        layout.append("└───────────────┴───────────────────┘")
        
        # Add facility listing if there are sub-locations
        if sub_locations:
            layout.append("")
            layout.append("OUTPOST FACILITIES:")
            for sub_loc in sub_locations:
                layout.append(f"• {sub_loc['icon']} {sub_loc['name']} - {sub_loc['type'].title()}")
        
        full_map = header + "\n".join(layout)
        return full_map
    
    def _generate_gate_map(self, location_data: Dict, sub_locations: List[Dict]) -> str:
        """Generate floormap for a gate (smallest, compact terminal layout)"""
        wealth = location_data['wealth_level']
        population = location_data['population']
        
        # Create header
        header = f"═══ {location_data['name']} ═══\n"
        header += f"Gate • Population: {population:,} • Wealth Level: {wealth}\n"
        if location_data['faction'] != 'Independent':
            header += f"Faction: {location_data['faction']}\n"
        header += "\n"
        
        # Organize sub-locations by type
        security_room = None
        service_rooms = []
        comfort_rooms = []
        
        for sl in sub_locations:
            if sl['type'] in ['security', 'admin']:
                security_room = sl
            elif sl['type'] in ['market', 'engineering', 'medbay', 'storage', 'communications']:
                service_rooms.append(sl)
            elif sl['type'] in ['lounge', 'bar', 'recreation']:
                comfort_rooms.append(sl)
        
        # Compact terminal layout with actual rooms and corridors
        layout = []
        
        # Entry airlock and security
        layout.append("┌─────────────────────────────────────┐")
        layout.append("│              AIRLOCK                │")
        layout.append("└─────────────┬───────────────────────┘")
        layout.append("              │                        ")
        
        # Security checkpoint
        if security_room:
            sec_name = security_room['name'][:8]
            sec_icon = security_room['icon']
            layout.append(f"┌─────────────┼───────────────────────┐")
            layout.append(f"│ {sec_icon} {sec_name:<8}   │   MAIN CORRIDOR    │")
            layout.append(f"└─────────────┼───────────────────────┘")
        else:
            layout.append("┌─────────────┼───────────────────────┐")
            layout.append("│ 🛡️ Security   │   MAIN CORRIDOR    │")
            layout.append("└─────────────┼───────────────────────┘")
        
        layout.append("              │                        ")
        
        # Main terminal area with rooms
        layout.append("┌─────────────┼───────────────────────┐")
        
        # Left side - service rooms
        if len(service_rooms) >= 1:
            svc1 = service_rooms[0]
            layout.append(f"│ {svc1['icon']} {svc1['name'][:8]:<8}   │                       │")
        else:
            layout.append("│ 🛒 Shop      │                       │")
        
        layout.append("├─────────────┤     WAITING AREA      │")
        
        if len(service_rooms) >= 2:
            svc2 = service_rooms[1]
            layout.append(f"│ {svc2['icon']} {svc2['name'][:8]:<8}   │        🛋️             │")
        else:
            layout.append("│ 📡 Comms     │        🛋️             │")
        
        layout.append("├─────────────┤                       │")
        
        # Comfort/lounge area
        if comfort_rooms:
            comfort = comfort_rooms[0]
            layout.append(f"│ {comfort['icon']} {comfort['name'][:8]:<8}   │     🗺️   📅         │")
        else:
            layout.append("│ 🍺 Refreshmt │     🗺️   📅         │")
        
        layout.append("└─────────────┼───────────────────────┘")
        layout.append("              │                        ")
        
        # Departure gate
        layout.append("┌─────────────┼───────────────────────┐")
        layout.append("│   DEPARTURE GATE    │  🚀 TO SPACE  │")
        layout.append("└─────────────────────┼───────────────┘")
        layout.append("                      │                ")
        layout.append("                   ┌──┼──┐             ")
        layout.append("                   │🚀 GATE │           ")
        layout.append("                   └───────┘             ")
        
        # Add facility listing
        if sub_locations:
            layout.append("")
            layout.append("TERMINAL DIRECTORY:")
            for sub_loc in sub_locations:
                layout.append(f"• {sub_loc['icon']} {sub_loc['name']}")
        
        full_map = header + "\n".join(layout)
        return full_map
    
    def _apply_derelict_damage(self, floormap: str, location_data: Dict) -> str:
        """Apply derelict damage modifications to the floormap"""
        lines = floormap.split('\n')
        
        # Add derelict status to header
        for i, line in enumerate(lines):
            if 'Wealth Level:' in line:
                lines[i] += " • 💀 DERELICT"
                break
        
        # Add damage indicators
        damaged_map = []
        for line in lines:
            # Replace some rooms with damage (randomly)
            damaged_line = line
            
            # Randomly replace lounge symbols with damage
            if '🛋️' in damaged_line and random.randint(0, 2) == 0:
                damaged_line = damaged_line.replace('🛋️', '💥', 1)  # Some lounges damaged
            
            # Randomly replace shop symbols with closed signs
            if '🛒' in damaged_line and random.randint(0, 3) == 0:
                damaged_line = damaged_line.replace('🛒', '🚫', 1)  # Some shops closed
            
            # Randomly replace bar symbols with warnings
            if '🍺' in damaged_line and random.randint(0, 4) == 0:
                damaged_line = damaged_line.replace('🍺', '⚠️', 1)  # Some bars abandoned
            
            # Add random debris
            if '║' in damaged_line and random.randint(0, 5) == 0:
                damaged_line = damaged_line.replace(' ', '⚠️', 1)  # Add debris
            
            damaged_map.append(damaged_line)
        
        # Add warning footer
        damaged_map.append("")
        damaged_map.append("💀 WARNING: DERELICT FACILITY 💀")
        damaged_map.append("⚠️ Structural damage present")
        damaged_map.append("🚫 Some areas may be inaccessible")
        
        return '\n'.join(damaged_map)