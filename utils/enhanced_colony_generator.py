# Enhanced Location Generators - All location types with named sub-locations
from PIL import Image, ImageDraw, ImageFont
import os
import math
from typing import Dict, List

class EnhancedLocationGenerator:
    def __init__(self):
        # Sci-fi terminal color scheme
        self.colors = {
            # Room type colors - sci-fi terminal theme
            'residential': '#00BFFF',    # Deep sky blue
            'commercial': '#00FF7F',     # Spring green  
            'administrative': '#9370DB', # Medium slate blue
            'medical': '#FF6347',        # Tomato red
            'engineering': '#FFA500',    # Orange
            'security': '#DC143C',       # Crimson
            'recreation': '#20B2AA',     # Light sea green
            'storage': '#708090',        # Slate gray
            'special': '#FFD700',        # Gold
            'hydroponics': '#32CD32',    # Lime green
            'casino': '#FF1493',         # Deep pink
            'plaza': '#87CEEB',          # Sky blue
            
            # Structure colors - dark sci-fi theme
            'wall': '#1C1C1C',           # Very dark gray
            'corridor': '#2F4F4F',       # Dark slate gray
            'door': '#00FFFF',           # Cyan
            'background': '#0A0A0A',     # Almost black
            'text': '#00FF00',           # Terminal green
            'border': '#00FFFF',         # Cyan borders
            'street': '#4B4B4D',         # Dark gray for streets
            'building': '#363636',       # Dark gray for generic buildings
            'highlight': '#FF0000',      # Red for important areas
            
            # Property ownership colors
            'property_available': '#FF4500',   # Orange red - available for purchase
            'property_owned': '#32CD32',       # Lime green - owned
            'property_player_owned': '#00BFFF', # Deep sky blue - player owned
            'property_faction_owned': '#9370DB' # Medium slate blue - faction owned
        }
        
        # Room type mappings for color selection
        self.room_type_colors = {
            'dormitory': 'residential',
            'lounge': 'residential',
            'market': 'commercial',
            'bar': 'commercial',
            'casino': 'casino',
            'admin': 'administrative',
            'security': 'security',
            'medbay': 'medical',
            'engineering': 'engineering',
            'hangar': 'engineering',
            'research': 'special',
            'hydroponics': 'hydroponics',
            'recreation': 'recreation',
            'communications': 'engineering',
            'storage': 'storage',
            'plaza': 'plaza'
        }
    
    def try_load_font(self, size: int = 12):
        """Try to load a system font, fallback to default if not available"""
        try:
            font_names = [
                "arial.ttf", "Arial.ttf", "DejaVuSans.ttf", 
                "liberation-sans.ttf", "NotoSans-Regular.ttf"
            ]
            
            for font_name in font_names:
                try:
                    return ImageFont.truetype(font_name, size)
                except (OSError, IOError):
                    continue
                    
            return ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()
    
    def get_room_color(self, room_type: str) -> str:
        """Get the color for a room type"""
        color_type = self.room_type_colors.get(room_type, 'storage')
        return self.colors[color_type]
    
    def draw_named_facility(self, draw, x, y, width, height, facility_name, facility_type, font):
        """Draw a named facility with proper styling"""
        # Get room color
        room_color = self.get_room_color(facility_type)
        
        # Draw room rectangle with sci-fi styling
        draw.rectangle([x, y, x + width, y + height], 
                      fill=room_color, outline=self.colors['border'], width=2)
        
        # Add inner glow effect
        draw.rectangle([x+2, y+2, x + width-2, y + height-2], 
                      fill=None, outline=self.colors['door'], width=1)
        
        # Calculate text position (centered)
        text_bbox = draw.textbbox((0, 0), facility_name, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = x + (width - text_width) // 2
        text_y = y + (height - text_height) // 2
        
        # Draw dark background for text readability
        padding = 3
        draw.rectangle([text_x - padding, text_y - padding, 
                       text_x + text_width + padding, text_y + text_height + padding],
                      fill=self.colors['background'], outline=self.colors['border'], width=1)
        
        # Draw text in terminal green
        draw.text((text_x, text_y), facility_name, fill=self.colors['text'], font=font)
    
    def generate_enhanced_colony(self, location_data: Dict, sub_locations: List[Dict], ownership_info: Dict) -> str:
        """Generate enhanced colony map showing actual named sub-locations"""
        # High resolution for readability
        width, height = 1600, 1200
        image = Image.new('RGB', (width, height), self.colors['background'])
        draw = ImageDraw.Draw(image)
        
        # Enhanced fonts
        font = self.try_load_font(14)
        title_font = self.try_load_font(28)
        small_font = self.try_load_font(12)
        facility_font = self.try_load_font(11)
        
        # Enhanced sci-fi header
        header_height = 120
        draw.rectangle([0, 0, width, header_height], fill=self.colors['wall'])
        
        # Add grid lines for sci-fi effect
        for i in range(0, width, 40):
            draw.line([i, 0, i, header_height], fill=self.colors['border'], width=1)
        
        # Title with ownership info
        title = f"◢ {location_data['name']} ◣"
        if ownership_info.get('custom_name'):
            title = f"◢ {ownership_info['custom_name']} ({location_data['name']}) ◣"
        
        # Status info
        subtitle = f"COLONY SECTOR • POP: {location_data['population']:,} • WEALTH LVL: {location_data['wealth_level']}"
        if location_data['faction'] != 'Independent':
            subtitle += f" • FACTION: {location_data['faction']}"
        
        # Ownership status
        ownership_line = ""
        if ownership_info.get('is_owned'):
            if ownership_info.get('owner_name'):
                ownership_line = f"▶ PRIVATE OWNERSHIP: {ownership_info['owner_name']}"
            elif ownership_info.get('faction_name'):
                ownership_line = f"▶ FACTION CONTROL: {ownership_info['faction_name']}"
        elif ownership_info.get('is_purchasable'):
            ownership_line = f"▶ AVAILABLE FOR ACQUISITION • PRICE: {ownership_info['estimated_price']:,} CR"
        else:
            ownership_line = "▶ PUBLIC COLONIAL TERRITORY"
        
        # Draw header text
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 15), title, fill=self.colors['text'], font=title_font)
        
        sub_bbox = draw.textbbox((0, 0), subtitle, font=font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_width) // 2, 55), subtitle, fill=self.colors['text'], font=font)
        
        own_bbox = draw.textbbox((0, 0), ownership_line, font=small_font)
        own_width = own_bbox[2] - own_bbox[0]
        draw.text(((width - own_width) // 2, 85), ownership_line, fill=self.colors['border'], font=small_font)
        
        start_y = header_height + 20
        
        # Create a grid system for placing actual named facilities
        # First, let's categorize the actual sub-locations
        named_facilities = {}
        for facility in sub_locations:
            facility_type = facility['type']
            if facility_type not in named_facilities:
                named_facilities[facility_type] = []
            named_facilities[facility_type].append(facility)
        
        # Central Plaza Area - show plazas and important locations
        central_y = start_y + 100
        central_x = width // 2 - 200
        central_w, central_h = 400, 150
        
        # Check for plaza-type facilities
        plaza_facilities = named_facilities.get('plaza', [])
        recreation_facilities = named_facilities.get('recreation', [])
        special_facilities = named_facilities.get('research', []) + named_facilities.get('hydroponics', [])
        
        if plaza_facilities or recreation_facilities:
            draw.rectangle([central_x, central_y, central_x + central_w, central_y + central_h],
                          fill=self.colors['plaza'], outline=self.colors['border'], width=3)
            
            # Draw named plazas/recreation areas
            if plaza_facilities:
                for i, facility in enumerate(plaza_facilities[:2]):
                    fac_x = central_x + 20 + i * 180
                    fac_y = central_y + 20
                    self.draw_named_facility(draw, fac_x, fac_y, 160, 50, 
                                           facility['name'][:15], facility['type'], facility_font)
            
            if recreation_facilities:
                for i, facility in enumerate(recreation_facilities[:2]):
                    fac_x = central_x + 20 + i * 180
                    fac_y = central_y + 80
                    self.draw_named_facility(draw, fac_x, fac_y, 160, 50, 
                                           facility['name'][:15], facility['type'], facility_font)
        
        # Commercial District - show actual markets, bars, casinos
        comm_y = start_y + 20
        comm_facilities = (named_facilities.get('market', []) + 
                          named_facilities.get('bar', []) + 
                          named_facilities.get('casino', []))
        
        if comm_facilities:
            # Draw commercial district header
            draw.rectangle([50, comm_y, width - 50, comm_y + 40],
                          fill=self.colors['commercial'], outline=self.colors['border'], width=2)
            draw.text((60, comm_y + 10), "▶ COMMERCIAL DISTRICT", fill=self.colors['background'], font=font)
            
            # Place actual commercial facilities
            for i, facility in enumerate(comm_facilities[:6]):
                col = i % 3
                row = i // 3
                fac_x = 70 + col * 180
                fac_y = comm_y + 50 + row * 80
                fac_w, fac_h = 160, 60
                
                self.draw_named_facility(draw, fac_x, fac_y, fac_w, fac_h, 
                                       facility['name'][:12], facility['type'], facility_font)
        
        # Administrative Sector
        admin_y = start_y + 300
        admin_facilities = (named_facilities.get('admin', []) + 
                           named_facilities.get('security', []))
        
        if admin_facilities:
            draw.rectangle([50, admin_y, width - 50, admin_y + 40],
                          fill=self.colors['administrative'], outline=self.colors['border'], width=2)
            draw.text((60, admin_y + 10), "▶ ADMINISTRATIVE SECTOR", fill=self.colors['background'], font=font)
            
            for i, facility in enumerate(admin_facilities[:4]):
                col = i % 2
                row = i // 2
                fac_x = 70 + col * 200
                fac_y = admin_y + 50 + row * 80
                fac_w, fac_h = 180, 60
                
                self.draw_named_facility(draw, fac_x, fac_y, fac_w, fac_h, 
                                       facility['name'][:12], facility['type'], facility_font)
        
        # Medical and Engineering Sectors
        tech_y = start_y + 500
        medical_facilities = named_facilities.get('medbay', [])
        engineering_facilities = (named_facilities.get('engineering', []) + 
                                 named_facilities.get('hangar', []) +
                                 named_facilities.get('communications', []))
        
        # Medical section
        if medical_facilities:
            draw.rectangle([50, tech_y, 400, tech_y + 40],
                          fill=self.colors['medical'], outline=self.colors['border'], width=2)
            draw.text((60, tech_y + 10), "▶ MEDICAL SECTOR", fill=self.colors['background'], font=font)
            
            for i, facility in enumerate(medical_facilities[:2]):
                fac_x = 70 + i * 160
                fac_y = tech_y + 50
                self.draw_named_facility(draw, fac_x, fac_y, 140, 60, 
                                       facility['name'][:10], facility['type'], facility_font)
        
        # Engineering section
        if engineering_facilities:
            draw.rectangle([width - 450, tech_y, 400, tech_y + 40],
                          fill=self.colors['engineering'], outline=self.colors['border'], width=2)
            draw.text((width - 440, tech_y + 10), "▶ ENGINEERING SECTOR", fill=self.colors['background'], font=font)
            
            for i, facility in enumerate(engineering_facilities[:2]):
                fac_x = width - 430 + i * 160
                fac_y = tech_y + 50
                self.draw_named_facility(draw, fac_x, fac_y, 140, 60, 
                                       facility['name'][:10], facility['type'], facility_font)
        
        # Special Facilities Section
        if special_facilities:
            spec_y = start_y + 650
            draw.rectangle([200, spec_y, width - 200, spec_y + 40],
                          fill=self.colors['special'], outline=self.colors['border'], width=2)
            draw.text((210, spec_y + 10), "▶ SPECIAL FACILITIES", fill=self.colors['background'], font=font)
            
            for i, facility in enumerate(special_facilities[:4]):
                col = i % 2
                row = i // 2
                fac_x = 220 + col * 200
                fac_y = spec_y + 50 + row * 80
                fac_w, fac_h = 180, 60
                
                self.draw_named_facility(draw, fac_x, fac_y, fac_w, fac_h, 
                                       facility['name'][:12], facility['type'], facility_font)
        
        # Add comprehensive facility directory
        dir_y = height - 200
        draw.rectangle([20, dir_y, width - 20, height - 20],
                      fill=self.colors['wall'], outline=self.colors['border'], width=2)
        draw.text((30, dir_y + 10), "▶ FACILITY DIRECTORY:", fill=self.colors['text'], font=font)
        
        # List all named facilities
        y_offset = 35
        col_width = 300
        for i, facility in enumerate(sub_locations):
            col = i % 5
            row = i // 5
            if row < 4:  # Limit to 4 rows
                text_x = 30 + col * col_width
                text_y = dir_y + y_offset + row * 25
                
                facility_text = f"• {facility['name'][:20]}"
                draw.text((text_x, text_y), facility_text, fill=self.colors['text'], font=small_font)
        
        # Return the image object for the caller to save
        return image
    
    def generate_enhanced_space_station(self, location_data: Dict, sub_locations: List[Dict], ownership_info: Dict) -> Image.Image:
        """Generate enhanced space station map showing actual named sub-locations"""
        # Higher resolution for better readability
        width, height = 1200, 1000
        image = Image.new('RGB', (width, height), self.colors['background'])
        draw = ImageDraw.Draw(image)
        
        # Enhanced fonts
        font = self.try_load_font(13)
        title_font = self.try_load_font(26)
        small_font = self.try_load_font(11)
        facility_font = self.try_load_font(10)
        
        # Enhanced sci-fi header
        header_height = 100
        draw.rectangle([0, 0, width, header_height], fill=self.colors['wall'])
        
        # Add grid lines for sci-fi effect
        for i in range(0, width, 30):
            draw.line([i, 0, i, header_height], fill=self.colors['border'], width=1)
        
        # Title with ownership info
        title = f"◈ {location_data['name']} ◈"
        if ownership_info.get('custom_name'):
            title = f"◈ {ownership_info['custom_name']} ({location_data['name']}) ◈"
        
        # Status info
        subtitle = f"SPACE STATION • CREW: {location_data['population']:,} • TECH LVL: {location_data['wealth_level']}"
        if location_data['faction'] != 'Independent':
            subtitle += f" • FACTION: {location_data['faction']}"
        
        # Ownership status
        ownership_line = ""
        if ownership_info.get('is_owned'):
            if ownership_info.get('owner_name'):
                ownership_line = f"▶ STATION COMMANDER: {ownership_info['owner_name']}"
            elif ownership_info.get('faction_name'):
                ownership_line = f"▶ FACTION OPERATED: {ownership_info['faction_name']}"
        elif ownership_info.get('is_purchasable'):
            ownership_line = f"▶ STATION FOR SALE • PRICE: {ownership_info['estimated_price']:,} CR"
        else:
            ownership_line = "▶ NEUTRAL STATION"
        
        # Draw header text
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 15), title, fill=self.colors['text'], font=title_font)
        
        sub_bbox = draw.textbbox((0, 0), subtitle, font=font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_width) // 2, 50), subtitle, fill=self.colors['text'], font=font)
        
        own_bbox = draw.textbbox((0, 0), ownership_line, font=small_font)
        own_width = own_bbox[2] - own_bbox[0]
        draw.text(((width - own_width) // 2, 75), ownership_line, fill=self.colors['border'], font=small_font)
        
        # Categorize actual sub-locations
        named_facilities = {}
        for facility in sub_locations:
            facility_type = facility['type']
            if facility_type not in named_facilities:
                named_facilities[facility_type] = []
            named_facilities[facility_type].append(facility)
        
        center_x, center_y = width // 2, (height + header_height) // 2
        
        # Central Command Hub
        hub_radius = 80
        draw.ellipse([center_x - hub_radius, center_y - hub_radius, 
                     center_x + hub_radius, center_y + hub_radius],
                    fill=self.colors['administrative'], outline=self.colors['border'], width=4)
        
        # Add inner details to hub
        draw.ellipse([center_x - 50, center_y - 50, center_x + 50, center_y + 50],
                    fill=None, outline=self.colors['door'], width=2)
        
        draw.text((center_x - 35, center_y - 30), "COMMAND", fill=self.colors['text'], font=font)
        draw.text((center_x - 20, center_y - 10), "HUB", fill=self.colors['text'], font=title_font)
        draw.text((center_x - 30, center_y + 15), "CENTER", fill=self.colors['text'], font=font)
        
        # Docking Ring - show actual hangar/docking facilities
        dock_radius = 180
        docking_facilities = named_facilities.get('hangar', []) + named_facilities.get('engineering', [])
        dock_count = max(6, len(docking_facilities))
        
        for i in range(dock_count):
            angle = (i * 60) * math.pi / 180  # 60 degrees apart
            dock_x = center_x + int(dock_radius * math.cos(angle)) - 70
            dock_y = center_y + int(dock_radius * math.sin(angle)) - 25
            
            # Determine if this is a named facility
            if i < len(docking_facilities):
                facility = docking_facilities[i]
                dock_name = facility['name'][:10]
                dock_color = self.get_room_color(facility['type'])
            else:
                dock_name = f"DOCK {i+1}"
                dock_color = self.colors['engineering']
            
            # Docking bay
            draw.rectangle([dock_x, dock_y, dock_x + 140, dock_y + 50],
                          fill=dock_color, outline=self.colors['border'], width=2)
            draw.text((dock_x + 10, dock_y + 15), dock_name, fill=self.colors['background'], font=facility_font)
            
            # Connection to hub
            hub_edge_x = center_x + int(hub_radius * math.cos(angle))
            hub_edge_y = center_y + int(hub_radius * math.sin(angle))
            draw.line([hub_edge_x, hub_edge_y, dock_x + 70, dock_y + 25], 
                     fill=self.colors['corridor'], width=6)
        
        # Residential Modules - show actual living quarters
        residential_facilities = named_facilities.get('dormitory', []) + named_facilities.get('lounge', [])
        res_positions = [
            (150, 200, "RESIDENTIAL A"),
            (950, 200, "RESIDENTIAL B"), 
            (150, 650, "RESIDENTIAL C"),
            (950, 650, "RESIDENTIAL D")
        ]
        
        for i, (rx, ry, default_label) in enumerate(res_positions):
            # Use actual facility if available
            if i < len(residential_facilities):
                facility = residential_facilities[i]
                module_name = facility['name'][:12]
                module_color = self.get_room_color(facility['type'])
            else:
                module_name = default_label
                module_color = self.colors['residential']
            
            # Large residential module
            module_w, module_h = 160, 120
            draw.rectangle([rx - module_w//2, ry - module_h//2, rx + module_w//2, ry + module_h//2],
                          fill=module_color, outline=self.colors['border'], width=3)
            
            # Module header
            draw.text((rx - 50, ry - 50), module_name, fill=self.colors['background'], font=font)
            
            # Individual quarters visual
            for qx in range(3):
                for qy in range(2):
                    quarter_x = rx - 60 + qx * 40
                    quarter_y = ry - 20 + qy * 30
                    
                    draw.rectangle([quarter_x, quarter_y, quarter_x + 30, quarter_y + 25],
                                  fill=self.colors['building'], outline=self.colors['border'])
            
            # Connect to hub
            draw.line([rx, ry, center_x, center_y], fill=self.colors['corridor'], width=8)
        
        # Service Modules - show actual medical, commercial, admin facilities
        service_positions = [
            (center_x - 200, center_y - 150, "SERVICE A"),
            (center_x + 200, center_y - 150, "SERVICE B"),
            (center_x - 200, center_y + 150, "SERVICE C"), 
            (center_x + 200, center_y + 150, "SERVICE D")
        ]
        
        service_facilities = (named_facilities.get('medbay', []) + 
                             named_facilities.get('bar', []) + 
                             named_facilities.get('market', []) +
                             named_facilities.get('admin', []))
        
        for i, (sx, sy, default_label) in enumerate(service_positions):
            if i < len(service_facilities):
                facility = service_facilities[i]
                service_name = facility['name'][:10]
                service_color = self.get_room_color(facility['type'])
            else:
                # Default services
                defaults = [
                    {'name': 'Medical Bay', 'type': 'medbay'},
                    {'name': 'Market Hub', 'type': 'market'},
                    {'name': 'Admin Office', 'type': 'admin'},
                    {'name': 'Security', 'type': 'security'}
                ]
                if i < len(defaults):
                    service_name = defaults[i]['name']
                    service_color = self.get_room_color(defaults[i]['type'])
                else:
                    service_name = default_label
                    service_color = self.colors['storage']
            
            # Service module
            service_w, service_h = 120, 80
            draw.rectangle([sx - service_w//2, sy - service_h//2, sx + service_w//2, sy + service_h//2],
                          fill=service_color, outline=self.colors['border'], width=2)
            draw.text((sx - len(service_name)*4, sy - 8), service_name, fill=self.colors['background'], font=facility_font)
            
            # Connect to hub
            draw.line([sx, sy, center_x, center_y], fill=self.colors['corridor'], width=6)
        
        # Special Facilities Section
        special_facilities = (named_facilities.get('research', []) + 
                             named_facilities.get('hydroponics', []) +
                             named_facilities.get('recreation', []) +
                             named_facilities.get('casino', []))
        
        if special_facilities:
            spec_y = height - 150
            draw.rectangle([100, spec_y, width - 100, spec_y + 30],
                          fill=self.colors['special'], outline=self.colors['border'], width=2)
            draw.text((110, spec_y + 5), "▶ SPECIAL FACILITIES", fill=self.colors['background'], font=font)
            
            for i, facility in enumerate(special_facilities[:6]):
                fac_x = 120 + i * 160
                fac_y = spec_y + 40
                fac_w, fac_h = 140, 50
                
                self.draw_named_facility(draw, fac_x, fac_y, fac_w, fac_h, 
                                       facility['name'][:11], facility['type'], facility_font)
        
        # Station Directory
        dir_y = height - 120
        draw.rectangle([20, dir_y, width - 20, height - 20],
                      fill=self.colors['wall'], outline=self.colors['border'], width=2)
        draw.text((30, dir_y + 10), "▶ STATION DIRECTORY:", fill=self.colors['text'], font=font)
        
        # List all named facilities
        y_offset = 35
        col_width = 200
        for i, facility in enumerate(sub_locations):
            col = i % 5
            row = i // 5
            if row < 3:  # Limit to 3 rows
                text_x = 30 + col * col_width
                text_y = dir_y + y_offset + row * 20
                
                facility_text = f"• {facility['name'][:18]}"
                draw.text((text_x, text_y), facility_text, fill=self.colors['text'], font=small_font)
        
        return image
    
    def generate_enhanced_outpost(self, location_data: Dict, sub_locations: List[Dict], ownership_info: Dict) -> Image.Image:
        """Generate enhanced outpost map showing actual named sub-locations"""
        # Higher resolution for better readability
        width, height = 800, 600
        image = Image.new('RGB', (width, height), self.colors['background'])
        draw = ImageDraw.Draw(image)
        
        # Enhanced fonts
        font = self.try_load_font(12)
        title_font = self.try_load_font(22)
        small_font = self.try_load_font(10)
        facility_font = self.try_load_font(9)
        
        # Enhanced sci-fi header
        header_height = 80
        draw.rectangle([0, 0, width, header_height], fill=self.colors['wall'])
        
        # Add grid lines for sci-fi effect
        for i in range(0, width, 25):
            draw.line([i, 0, i, header_height], fill=self.colors['border'], width=1)
        
        # Title with ownership info
        title = f"◢ {location_data['name']} ◣"
        if ownership_info.get('custom_name'):
            title = f"◢ {ownership_info['custom_name']} ◣"
        
        # Status info
        subtitle = f"OUTPOST • CREW: {location_data['population']:,} • SUPPLY LVL: {location_data['wealth_level']}"
        if location_data['faction'] != 'Independent':
            subtitle += f" • {location_data['faction']}"
        
        # Ownership status
        ownership_line = ""
        if ownership_info.get('is_owned'):
            if ownership_info.get('owner_name'):
                ownership_line = f"▶ OUTPOST COMMANDER: {ownership_info['owner_name']}"
            elif ownership_info.get('faction_name'):
                ownership_line = f"▶ FACTION OUTPOST: {ownership_info['faction_name']}"
        elif ownership_info.get('is_purchasable'):
            ownership_line = f"▶ OUTPOST FOR SALE • PRICE: {ownership_info['estimated_price']:,} CR"
        else:
            ownership_line = "▶ INDEPENDENT OUTPOST"
        
        # Draw header text
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 10), title, fill=self.colors['text'], font=title_font)
        
        sub_bbox = draw.textbbox((0, 0), subtitle, font=font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_width) // 2, 40), subtitle, fill=self.colors['text'], font=font)
        
        own_bbox = draw.textbbox((0, 0), ownership_line, font=small_font)
        own_width = own_bbox[2] - own_bbox[0]
        draw.text(((width - own_width) // 2, 60), ownership_line, fill=self.colors['border'], font=small_font)
        
        # Categorize actual sub-locations
        named_facilities = {}
        for facility in sub_locations:
            facility_type = facility['type']
            if facility_type not in named_facilities:
                named_facilities[facility_type] = []
            named_facilities[facility_type].append(facility)
        
        start_y = header_height + 20
        
        # Entry Airlock
        airlock_x, airlock_y = width//2 - 100, start_y
        draw.rectangle([airlock_x, airlock_y, airlock_x + 200, airlock_y + 40],
                      fill=self.colors['security'], outline=self.colors['border'], width=3)
        draw.text((airlock_x + 70, airlock_y + 15), "MAIN AIRLOCK", fill=self.colors['background'], font=font)
        
        # Main Corridor
        corridor_x = width // 2
        corridor_start = airlock_y + 40
        corridor_end = height - 80
        draw.rectangle([corridor_x - 20, corridor_start, corridor_x + 20, corridor_end],
                      fill=self.colors['corridor'], outline=self.colors['border'], width=2)
        
        # Room positions (3x2 grid for main facilities)
        room_positions = [
            (150, start_y + 80, "LEFT A"),
            (550, start_y + 80, "RIGHT A"),
            (150, start_y + 180, "LEFT B"),
            (550, start_y + 180, "RIGHT B"),
            (150, start_y + 280, "LEFT C"),
            (550, start_y + 280, "RIGHT C")
        ]
        
        # Get all facilities for placement
        all_facilities = []
        for category in ['admin', 'security', 'medbay', 'engineering', 'storage', 'communications', 'dormitory']:
            all_facilities.extend(named_facilities.get(category, []))
        
        # Place actual named facilities
        for i, (room_x, room_y, default_name) in enumerate(room_positions):
            if i < len(all_facilities):
                facility = all_facilities[i]
                room_name = facility['name'][:12]
                room_color = self.get_room_color(facility['type'])
                room_type = facility['type'].upper()
            else:
                # Default rooms based on position
                defaults = [
                    {'name': 'Control Room', 'type': 'admin'},
                    {'name': 'Storage Bay', 'type': 'storage'},
                    {'name': 'Quarters', 'type': 'dormitory'},
                    {'name': 'Workshop', 'type': 'engineering'},
                    {'name': 'Medical', 'type': 'medbay'},
                    {'name': 'Security', 'type': 'security'}
                ]
                if i < len(defaults):
                    room_name = defaults[i]['name']
                    room_color = self.get_room_color(defaults[i]['type'])
                    room_type = defaults[i]['type'].upper()
                else:
                    room_name = default_name
                    room_color = self.colors['storage']
                    room_type = "GENERAL"
            
            # Draw room
            room_w, room_h = 120, 80
            draw.rectangle([room_x - room_w//2, room_y - room_h//2, room_x + room_w//2, room_y + room_h//2],
                          fill=room_color, outline=self.colors['border'], width=2)
            
            # Room label
            draw.text((room_x - len(room_name)*3, room_y - 20), room_name, fill=self.colors['background'], font=facility_font)
            draw.text((room_x - len(room_type)*2, room_y + 5), room_type, fill=self.colors['background'], font=small_font)
            
            # Connect to corridor
            if room_x < corridor_x:  # Left side
                draw.line([room_x + room_w//2, room_y, corridor_x - 20, room_y], 
                         fill=self.colors['corridor'], width=8)
            else:  # Right side
                draw.line([corridor_x + 20, room_y, room_x - room_w//2, room_y], 
                         fill=self.colors['corridor'], width=8)
        
        # Special Facilities (if any remain)
        remaining_facilities = all_facilities[6:] + named_facilities.get('research', []) + named_facilities.get('hydroponics', [])
        if remaining_facilities:
            spec_y = height - 150
            draw.rectangle([50, spec_y, width - 50, spec_y + 30],
                          fill=self.colors['special'], outline=self.colors['border'], width=2)
            draw.text((60, spec_y + 5), "▶ ADDITIONAL FACILITIES", fill=self.colors['background'], font=font)
            
            for i, facility in enumerate(remaining_facilities[:4]):
                fac_x = 70 + i * 150
                fac_y = spec_y + 40
                fac_w, fac_h = 130, 40
                
                self.draw_named_facility(draw, fac_x, fac_y, fac_w, fac_h, 
                                       facility['name'][:10], facility['type'], facility_font)
        
        # Outpost Directory
        dir_y = height - 100
        draw.rectangle([20, dir_y, width - 20, height - 20],
                      fill=self.colors['wall'], outline=self.colors['border'], width=2)
        draw.text((30, dir_y + 10), "▶ OUTPOST DIRECTORY:", fill=self.colors['text'], font=font)
        
        # List all named facilities
        y_offset = 30
        col_width = 180
        for i, facility in enumerate(sub_locations):
            col = i % 4
            row = i // 4
            if row < 2:  # Limit to 2 rows
                text_x = 30 + col * col_width
                text_y = dir_y + y_offset + row * 20
                
                facility_text = f"• {facility['name'][:16]}"
                draw.text((text_x, text_y), facility_text, fill=self.colors['text'], font=small_font)
        
        return image
    
    def generate_enhanced_gate(self, location_data: Dict, sub_locations: List[Dict], ownership_info: Dict) -> Image.Image:
        """Generate enhanced gate map showing actual named sub-locations"""
        # Higher resolution for better readability
        width, height = 600, 800
        image = Image.new('RGB', (width, height), self.colors['background'])
        draw = ImageDraw.Draw(image)
        
        # Enhanced fonts
        font = self.try_load_font(11)
        title_font = self.try_load_font(20)
        small_font = self.try_load_font(9)
        facility_font = self.try_load_font(8)
        
        # Enhanced sci-fi header
        header_height = 80
        draw.rectangle([0, 0, width, header_height], fill=self.colors['wall'])
        
        # Add grid lines for sci-fi effect
        for i in range(0, width, 20):
            draw.line([i, 0, i, header_height], fill=self.colors['border'], width=1)
        
        # Title with ownership info
        title = f"◆ {location_data['name']} ◆"
        if ownership_info.get('custom_name'):
            title = f"◆ {ownership_info['custom_name']} ◆"
        
        # Status info
        subtitle = f"TRANSIT GATE • TRAFFIC: {location_data['population']:,}/day • CLASS: {location_data['wealth_level']}"
        if location_data['faction'] != 'Independent':
            subtitle += f" • {location_data['faction']}"
        
        # Ownership status
        ownership_line = ""
        if ownership_info.get('is_owned'):
            if ownership_info.get('owner_name'):
                ownership_line = f"▶ GATE AUTHORITY: {ownership_info['owner_name']}"
            elif ownership_info.get('faction_name'):
                ownership_line = f"▶ OPERATED BY: {ownership_info['faction_name']}"
        elif ownership_info.get('is_purchasable'):
            ownership_line = f"▶ GATE FRANCHISE AVAILABLE • PRICE: {ownership_info['estimated_price']:,} CR"
        else:
            ownership_line = "▶ PUBLIC TRANSIT GATE"
        
        # Draw header text
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 10), title, fill=self.colors['text'], font=title_font)
        
        sub_bbox = draw.textbbox((0, 0), subtitle, font=font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_width) // 2, 35), subtitle, fill=self.colors['text'], font=font)
        
        own_bbox = draw.textbbox((0, 0), ownership_line, font=small_font)
        own_width = own_bbox[2] - own_bbox[0]
        draw.text(((width - own_width) // 2, 55), ownership_line, fill=self.colors['border'], font=small_font)
        
        # Categorize actual sub-locations
        named_facilities = {}
        for facility in sub_locations:
            facility_type = facility['type']
            if facility_type not in named_facilities:
                named_facilities[facility_type] = []
            named_facilities[facility_type].append(facility)
        
        start_y = header_height + 20
        
        # Entry Checkpoint
        entry_y = start_y
        draw.rectangle([50, entry_y, width - 50, entry_y + 50],
                      fill=self.colors['security'], outline=self.colors['border'], width=3)
        draw.text((width//2 - 60, entry_y + 20), "ENTRY CHECKPOINT", fill=self.colors['background'], font=font)
        
        # Main Transit Corridor (vertical)
        corridor_x = width // 2
        corridor_start = entry_y + 50
        corridor_end = height - 100
        draw.rectangle([corridor_x - 25, corridor_start, corridor_x + 25, corridor_end],
                      fill=self.colors['corridor'], outline=self.colors['border'], width=3)
        
        # Security/Customs Area
        security_facilities = named_facilities.get('security', []) + named_facilities.get('admin', [])
        customs_y = start_y + 70
        
        if security_facilities:
            sec_facility = security_facilities[0]
            sec_name = sec_facility['name'][:15]
            sec_color = self.get_room_color(sec_facility['type'])
        else:
            sec_name = "Security Office"
            sec_color = self.colors['security']
        
        draw.rectangle([100, customs_y, width - 100, customs_y + 40],
                      fill=sec_color, outline=self.colors['border'], width=2)
        draw.text((width//2 - len(sec_name)*3, customs_y + 15), sec_name, fill=self.colors['background'], font=facility_font)
        
        # Service Areas (left and right of corridor)
        service_y_start = customs_y + 60
        service_facilities = (named_facilities.get('market', []) + 
                             named_facilities.get('bar', []) + 
                             named_facilities.get('engineering', []) +
                             named_facilities.get('medbay', []) +
                             named_facilities.get('communications', []))
        
        # Left side services
        left_services = service_facilities[::2]  # Every other facility
        right_services = service_facilities[1::2]  # Remaining facilities
        
        # Default services if none exist
        if not left_services:
            left_services = [
                {'name': 'Information Kiosk', 'type': 'admin'},
                {'name': 'Fuel Station', 'type': 'engineering'}
            ]
        if not right_services:
            right_services = [
                {'name': 'Snack Bar', 'type': 'market'},
                {'name': 'First Aid', 'type': 'medbay'}
            ]
        
        # Draw left side services
        for i, facility in enumerate(left_services[:4]):
            svc_y = service_y_start + i * 80
            svc_color = self.get_room_color(facility['type'])
            
            draw.rectangle([20, svc_y, corridor_x - 35, svc_y + 60],
                          fill=svc_color, outline=self.colors['border'], width=2)
            draw.text((30, svc_y + 20), facility['name'][:12], fill=self.colors['background'], font=facility_font)
            draw.text((30, svc_y + 35), facility['type'].upper(), fill=self.colors['background'], font=small_font)
            
            # Connect to corridor
            draw.line([corridor_x - 35, svc_y + 30, corridor_x - 25, svc_y + 30], 
                     fill=self.colors['corridor'], width=6)
        
        # Draw right side services
        for i, facility in enumerate(right_services[:4]):
            svc_y = service_y_start + 40 + i * 80  # Offset for staggered layout
            svc_color = self.get_room_color(facility['type'])
            
            draw.rectangle([corridor_x + 35, svc_y, width - 20, svc_y + 60],
                          fill=svc_color, outline=self.colors['border'], width=2)
            draw.text((corridor_x + 45, svc_y + 20), facility['name'][:12], fill=self.colors['background'], font=facility_font)
            draw.text((corridor_x + 45, svc_y + 35), facility['type'].upper(), fill=self.colors['background'], font=small_font)
            
            # Connect to corridor
            draw.line([corridor_x + 25, svc_y + 30, corridor_x + 35, svc_y + 30], 
                     fill=self.colors['corridor'], width=6)
        
        # Waiting/Lounge Area
        lounge_y = service_y_start + 340
        lounge_facilities = named_facilities.get('lounge', []) + named_facilities.get('recreation', [])
        
        if lounge_facilities:
            lounge_facility = lounge_facilities[0]
            lounge_name = lounge_facility['name'][:18]
            lounge_color = self.get_room_color(lounge_facility['type'])
        else:
            lounge_name = "Passenger Lounge"
            lounge_color = self.colors['recreation']
        
        draw.rectangle([70, lounge_y, width - 70, lounge_y + 80],
                      fill=lounge_color, outline=self.colors['border'], width=2)
        draw.text((width//2 - len(lounge_name)*3, lounge_y + 20), lounge_name, fill=self.colors['background'], font=font)
        draw.text((width//2 - 30, lounge_y + 50), "WAITING AREA", fill=self.colors['background'], font=small_font)
        
        # Departure Gate
        gate_y = lounge_y + 100
        draw.rectangle([50, gate_y, width - 50, gate_y + 60],
                      fill=self.colors['engineering'], outline=self.colors['border'], width=4)
        draw.text((width//2 - 50, gate_y + 15), "DEPARTURE GATE", fill=self.colors['background'], font=font)
        draw.text((width//2 - 30, gate_y + 35), "TO SPACE", fill=self.colors['background'], font=font)
        
        # Gate Directory
        dir_y = height - 120
        draw.rectangle([20, dir_y, width - 20, height - 20],
                      fill=self.colors['wall'], outline=self.colors['border'], width=2)
        draw.text((30, dir_y + 10), "▶ GATE DIRECTORY:", fill=self.colors['text'], font=font)
        
        # List all named facilities
        y_offset = 30
        col_width = 160
        for i, facility in enumerate(sub_locations):
            col = i % 3
            row = i // 3
            if row < 4:  # Limit to 4 rows
                text_x = 30 + col * col_width
                text_y = dir_y + y_offset + row * 18
                
                facility_text = f"• {facility['name'][:14]}"
                draw.text((text_x, text_y), facility_text, fill=self.colors['text'], font=small_font)
        
        return image


# Test usage
if __name__ == "__main__":
    generator = EnhancedLocationGenerator()
    
    # Sample data for testing
    test_location = {
        'location_id': 1,
        'name': 'New Terra',
        'population': 5445,
        'wealth_level': 7,
        'faction': 'Colonial Alliance'
    }
    
    test_sub_locations = [
        {'name': 'Hydroponics Bay', 'type': 'hydroponics'},
        {'name': 'Historical Archive', 'type': 'research'},
        {'name': 'Casino Royale', 'type': 'casino'},
        {'name': 'Central Plaza', 'type': 'plaza'},
        {'name': 'Security Headquarters', 'type': 'security'},
        {'name': 'Medical Center', 'type': 'medbay'}
    ]
    
    test_ownership = {
        'is_owned': False,
        'is_purchasable': True,
        'estimated_price': 75000
    }
    
    filepath = generator.generate_enhanced_colony(test_location, test_sub_locations, test_ownership)
    print(f"Generated enhanced colony map: {filepath}")