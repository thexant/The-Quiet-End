# utils/holographic_floorplan_generator.py
"""
Holographic Blueprint-Style Floorplan Generator
Creates sci-fi facility blueprints in cyan holographic style for all location types.
Uses NetworkX for layout generation and Pillow for rendering.
"""

import os
import random
import math
from typing import Dict, List, Tuple, Optional, Set
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import networkx as nx
import numpy as np
from utils.sub_locations import SubLocationManager

# Import existing name dictionaries
from utils.npc_data import FIRST_NAMES


class HolographicFloorplanGenerator:
    """
    Advanced procedural floorplan generator creating holographic blueprint-style maps
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.sub_manager = SubLocationManager(bot)
        self.floormaps_dir = "floormaps"
        
        # Ensure floormaps directory exists
        os.makedirs(self.floormaps_dir, exist_ok=True)
        
        # Name dictionaries for variety (from galaxy_generator.py)
        self.location_prefixes = [
            "A-1", "AO", "Acheron", "Aegis", "Alpha", "Amber", "Anchor", "Annex",
            "Apex", "Apollo", "Arc", "Archive", "Ares", "Aries", "Armstrong", "Ash",
            "Ashfall", "Atlas", "Azure", "B-2", "Barren", "Base", "Bastion", "Bay",
            "Bent", "Beta", "Black", "Blackwood", "Bleak", "Block", "Blue", "Bluewater",
            "Breaker", "Broad", "Broadway", "Bronze", "Bulwark", "C-3", "CN", "CT",
            "Cadmus", "Camp", "Cancer", "Canyon", "Central", "Cerberus", "Charon", "Chi",
            "Chronos", "Citadel", "Clear", "Clearwater", "Cobalt", "Cold", "Coldiron", "Conduit",
            "Copernicus", "Copper", "Crater", "Crest", "Crimson", "Crimsonpeak", "Crux", "Curie",
            "D-4", "DS", "DV", "Daedalus", "Dark", "Darwich", "Darwin's", "Deep",
            "Deepwater", "Delta", "Depot", "Distant", "Distantshore", "Drift", "Dry", "Dryland",
            "Dull", "Dust", "Dustveil", "E-5", "EX", "Eastern", "Echo", "Edge",
            "Edison", "Eighteen", "Eighth", "Eighty", "Elephant's", "Eleven", "Elysium", "Emerald",
            "Endeavor", "Epsilon", "Erebus", "Eta", "F-6", "Faint", "Fallout", "Field",
            "Fifth", "Fifty", "First", "Five", "Flat", "Fort", "Forty", "Forty-Six",
            "Four", "Fourteen", "Fourth", "Fringe", "Frontier", "G-7", "GR", "Gaea",
            "Galilei", "Gamma", "Garrison", "Gate", "Gemini", "Glacier", "Gloom", "Glory",
            "Gloryforge", "Golden", "Goldenrod", "Gray", "Greater", "Grid", "H-8", "Hades",
            "Hard", "Haven", "Hawking", "Heavy", "Hephaestus", "High", "Highpoint", "Hold",
            "Hollow", "Hollowstone", "Honor", "Honorbound", "Hub", "Humanity's", "Hundred", "Hydra",
            "I-9", "Indigo", "Iota", "Iron", "Ironclad", "Ironwood", "Isolated", "J-10",
            "Justice", "K-11", "KX", "Kappa", "Kepler", "L-6", "LN", "Lambda",
            "Lavender", "Legacy", "Leo", "Liberty", "Liberty Bell", "Libra", "Lifeless", "Line",
            "Lonely", "Long", "Longview", "Low", "Lowdown", "Lower", "Lyra", "M-13",
            "MA", "MR", "Mariner", "Maroon", "Mesa", "Mighty", "Module", "Mound",
            "Mournful", "Mu", "Murk", "Muted", "N-14", "Narrow", "Neo", "New",
            "Newton", "Nexus", "Nine", "Nineteen", "Ninety", "Ninety-Two", "Node", "Northern",
            "Nova", "Nu", "Nyx", "OB", "Oasis", "Obscure", "Obsidian", "Ochre",
            "Old", "Olympus", "Omega", "Omicron", "One", "Orion", "Outpost", "Overgrown",
            "P-16", "PS", "Pale", "Paleview", "Paragon", "Persephone", "Petrified", "Phi",
            "Pi", "Pierced", "Pisces", "Plateau", "Platform", "Platinum", "Plum", "Point",
            "Port", "Post", "Prometheus", "Providence", "Psi", "Pulse", "Q-17", "Quiet",
            "Quietude", "R-12", "RQ", "RX", "Radiant", "Radiantfield", "Range", "Ravaged",
            "Red", "Redstone", "Reef", "Relay", "Remote", "Resolve", "Rhea", "Rho",
            "Ridge", "Ring", "Rough", "Ruined", "Rust", "S-19", "ST", "SV",
            "Sanctuary", "Sands", "Scarlet", "Scorpio", "Scrap", "Secluded", "Second", "Sector",
            "Sentinel", "Settlement", "Seven", "Seventeen", "Seventy", "Seventy-Nine", "Shade", "Shadow",
            "Shadowbrook", "Shadowed", "Shaft", "Shallows", "Sharp", "Shattered", "Shelter", "Short",
            "Shortwave", "Sigma", "Silent", "Silentbrook", "Silver", "Silverleaf", "Site", "Sixteen",
            "Sixth", "Sixty", "Slag", "Soft", "Sol", "Solemn", "Somber", "Soot",
            "Southern", "Span", "Spire", "Stark", "Station", "Steel", "Steelheart", "Still",
            "Stonefall", "Stonewalled", "Strip", "Styx", "T-20", "TR", "TX", "Talon",
            "Tau", "Teal", "Tenth", "Terra", "Theta", "Thin", "Third", "Thirteen",
            "Thirty", "Thirty-Two", "Thorn", "Thousand", "Three", "Tired", "Titan", "Tomb",
            "Torrent", "Tower", "Triumph", "Tsiolkovsky", "Tundra", "Twelve", "Twenty", "Twenty-One",
            "Twin", "Twinfalls", "Two", "UT", "Unity", "Unitygate", "Upsilon", "V-8",
            "Vanguard", "Veil", "Venan's", "Verdant", "Veridian", "Vesper", "Vetaso's", "Violet",
            "Virgo", "Vision", "Void", "Vortex", "W-23", "Waste", "Western", "White",
            "Whitewash", "Wild", "Worn", "Wreck", "X-9", "Xi", "Y-25", "Z-21",
            "Z-26", "ZC", "Zero", "Zeta", "Zinc"
        ]
        
        self.location_names = [
            "Abyss", "Access", "Acropolis", "Aether", "Alcove", "Alliance", "Alpha", "Altitude",
            "Anchor", "Apex", "Apollo", "Aqueduct", "Arc", "Arch", "Archive", "Arcology",
            "Area", "Ariel", "Armature", "Array", "Arrokoth", "Artemis", "Artery", "Ascent",
            "Ashen", "Asteroid", "Atlas", "Aurora", "Awareness", "Axle", "Balance", "Barren",
            "Base", "Basilica", "Basin", "Bastille", "Bastion", "Battleship", "Bay", "Beacon",
            "Beam", "Being", "Bellow", "Belt", "Bend", "Bennu", "Beta", "Blight",
            "Blink", "Block", "Bluff", "Bomber", "Border", "Borealis", "Brace", "Breadth",
            "Bridge", "Brimstone", "Bristle", "Brood", "Buffer", "Building", "Bulwark", "Burn",
            "Cairn", "Callisto", "Canyon", "Cargo", "Carrier", "Cascade", "Casing",
            "Cassini", "Cauldron", "Causeway", "Cavity", "Cellar", "Centauri", "Centra", "Central",
            "Ceres", "Chandra", "Chang'e", "Channel", "Chaos", "Charon", "Chasm", "Chicxulub",
            "Circle", "Citadel", "City", "Clamp", "Clay", "Cloak", "Coalition", "Coil",
            "Coldiron", "Coliseum", "Column", "Comet", "Commonwealth", "Compass", "Concept",
            "Conclave", "Concord", "Concordat", "Conduit", "Consortium", "Construct", "Containment",
            "Core", "Corona", "Corvette", "Cosmos", "Cove", "Covenant", "Craft", "Crag",
            "Crane", "Cranny", "Crater", "Creation", "Creep", "Crest", "Cross", "Crown",
            "Crucible", "Cruiser", "Crypt", "Curiosity", "Current", "Curve", "Cut", "Dagger",
            "Damper", "Dark", "Dawn", "Decay", "Deep", "Deimos", "Delta", "Deluge",
            "Depot", "Depression", "Depth", "Descent", "Destroyer", "Dip", "Disk", "District",
            "Ditch", "Divide", "Dock", "Domain", "Dome", "Dominion", "Door", "Dreadnought",
            "Drift", "Drop", "Drum", "Dry", "Duct", "Dune", "Dust", "Dwelling",
            "Dynasty", "Eagle", "Earth", "Echo", "Edge", "Elevator", "Empire", "Enclave",
            "Engine", "Enterprise", "Entry", "Epsilon", "Escape", "Europa", "Event", "Exchange",
            "Exile", "Expanse", "Eye", "Face", "Fall", "Field", "Fire", "Fleet",
            "Flow", "Forge", "Fort", "Foundation", "Frame", "Frontier", "Gate", "Genesis",
            "Ghost", "Giant", "Glory", "Grid", "Ground", "Grove", "Guard", "Gulf",
            "Hall", "Harbor", "Haven", "Heart", "Heights", "Hell", "Hive", "Hold",
            "Hollow", "Home", "Hope", "Horn", "House", "Hub", "Hull", "Hunt",
            "Ice", "Isle", "Junction", "Keep", "Key", "Land", "Last", "Launch",
            "Light", "Line", "Lock", "Loop", "Maze", "Mine", "Mirror", "Moon",
            "Mount", "Nest", "Net", "Node", "North", "Orb", "Orbit", "Order",
            "Origin", "Outpost", "Pass", "Path", "Peak", "Pier", "Pit", "Place",
            "Platform", "Point", "Pool", "Port", "Post", "Pulse", "Reach", "Realm",
            "Ridge", "Ring", "Rise", "Rock", "Root", "Route", "Sanctuary", "Sands",
            "Scope", "Sea", "Sector", "Seed", "Shadow", "Shaft", "Shield", "Ship",
            "Shore", "Site", "Sky", "Slope", "South", "Space", "Span", "Sphere",
            "Spine", "Spire", "Star", "Station", "Stone", "Storm", "Stream", "Strip",
            "Sun", "System", "Temple", "Terminal", "Throne", "Tower", "Trade", "Trail",
            "Transit", "Trench", "Tunnel", "Union", "Valley", "Vault", "View", "Void",
            "Wall", "Ward", "Watch", "Wave", "Way", "Well", "West", "Wind",
            "Wing", "World", "Yard", "Zone"
        ]
        
        # Room type suffixes for variety
        self.facility_suffixes = [
            "Block", "Complex", "Center", "Hub", "Station", "Terminal", "Bay", "Wing",
            "Quarters", "Section", "Facility", "Zone", "Area", "District", "Plaza", "Court",
            "Annex", "Module", "Chamber", "Hall", "Deck", "Level", "Tower", "Spire"
        ]
        
        # Holographic blueprint color scheme
        self.colors = {
            # Primary blueprint colors - cyan holographic style
            'background': '#000033',        # Dark blue background
            'background_deep': '#000022',   # Even darker for depth
            'primary_cyan': '#00FFFF',      # Bright cyan for main lines
            'cyan_glow': '#00CCCC',         # Softer cyan for glow
            'cyan_dark': '#008888',         # Dark cyan for secondary elements
            
            # Grid and technical elements
            'grid_major': '#004444',        # Major grid lines
            'grid_minor': '#002222',        # Minor grid lines
            'grid_dots': '#006666',         # Grid intersection dots
            
            # Room and structure colors
            'wall_primary': '#00FFFF',      # Main walls - bright cyan
            'wall_secondary': '#00AAAA',    # Secondary walls
            'corridor': '#001133',          # Corridor fill
            'corridor_outline': '#0088AA',  # Corridor borders
            
            # Text and labels
            'text_primary': '#00FFFF',      # Primary text - cyan
            'text_secondary': '#0099CC',    # Secondary text
            'text_highlight': '#FFFFFF',    # White for emphasis
            'text_annotation': '#0077AA',   # Technical annotations
            
            # Room type colors (holographic variations)
            'residential': '#0088FF',       # Blue residential
            'commercial': '#00FF88',        # Green commercial  
            'administrative': '#FF0088',    # Magenta admin
            'industrial': '#FFAA00',        # Orange industrial
            'medical': '#FF4444',           # Red medical
            'security': '#FF0000',          # Bright red security
            'research': '#AA00FF',          # Purple research
            'special': '#FFFF00',           # Yellow special
            
            # Effects and highlights
            'glow_bright': '#FFFFFF',       # Bright white glow
            'glow_soft': '#66CCFF',         # Soft blue glow
            'energy_line': '#00AAFF',       # Energy conduits
            'access_point': '#00FF00',      # Green access points
        }
        
        # Room type to color mapping
        self.room_colors = {
            'dormitory': 'residential',
            'lounge': 'residential', 
            'quarters': 'residential',
            'residential': 'residential',
            'market': 'commercial',
            'bar': 'commercial',
            'casino': 'commercial',
            'shop': 'commercial',
            'commercial': 'commercial',
            'admin': 'administrative',
            'security': 'security',
            'medbay': 'medical',
            'medical': 'medical',
            'engineering': 'industrial',
            'hangar': 'industrial', 
            'storage': 'industrial',
            'cargo': 'industrial',
            'maintenance': 'industrial',
            'power': 'special',
            'research': 'research',
            'lab': 'research',
            'hydroponics': 'special',
            'recreation': 'special',
            'communications': 'industrial',
            'bridge': 'administrative',
            'command': 'administrative',
            'control': 'administrative',
            'airlock': 'security',
            'docking': 'industrial',
            'decontamination': 'medical',
            'gate_core': 'special',
            'gate_chamber': 'special',
            'observation': 'research',
            'education': 'residential',
            'plaza': 'special',
            'hub': 'special',
            'corridor': 'industrial',
            'travel_services': 'commercial',
            'terminal': 'administrative',
            'hydroponics_bay': 'special',
            'historical_archive': 'research',
            'central_plaza': 'special',
        }
        
        # Multiple layout configurations per location type for variety
        self.layout_configs = {
            'colony': [
                {
                    'style': 'district_grid',
                    'name': 'Organized Districts',
                    'main_corridors': 3,
                    'room_density': 0.7,
                    'grid_size': (4, 3),
                    'special_rooms': ['central_plaza', 'docking_station']
                },
                {
                    'style': 'sprawling_sectors',
                    'name': 'Sprawling Complex',
                    'main_corridors': 5,
                    'room_density': 0.6,
                    'sector_count': 4,
                    'special_rooms': ['command_center', 'industrial_hub']
                },
                {
                    'style': 'industrial_complex',
                    'name': 'Industrial Layout',
                    'main_corridors': 2,
                    'room_density': 0.8,
                    'factory_zones': 3,
                    'special_rooms': ['factory_core', 'shipping_bay']
                },
                {
                    'style': 'orbital_ring',
                    'name': 'Ring Structure',
                    'main_corridors': 1,
                    'room_density': 0.75,
                    'ring_segments': 6,
                    'special_rooms': ['ring_hub', 'observation_deck']
                }
            ],
            'space_station': [
                {
                    'style': 'radial_hub',
                    'name': 'Central Hub Design',
                    'main_corridors': 4,
                    'room_density': 0.8,
                    'hub_radius': 80,
                    'special_rooms': ['central_hub', 'docking_ring']
                },
                {
                    'style': 'modular_sections',
                    'name': 'Modular Sections',
                    'main_corridors': 3,
                    'room_density': 0.7,
                    'module_count': 5,
                    'special_rooms': ['main_junction', 'core_module']
                },
                {
                    'style': 'vertical_tower',
                    'name': 'Tower Configuration',
                    'main_corridors': 2,
                    'room_density': 0.9,
                    'tower_levels': 8,
                    'special_rooms': ['command_deck', 'reactor_level']
                },
                {
                    'style': 'rotating_habitat',
                    'name': 'Rotating Sections',
                    'main_corridors': 6,
                    'room_density': 0.65,
                    'rotation_rings': 3,
                    'special_rooms': ['gravity_well', 'rotation_hub']
                }
            ],
            'outpost': [
                {
                    'style': 'compact_cluster',
                    'name': 'Compact Layout',
                    'main_corridors': 2,
                    'room_density': 0.85,
                    'cluster_count': 3,
                    'special_rooms': ['command_post', 'landing_pad']
                },
                {
                    'style': 'linear_modules',
                    'name': 'Linear Configuration',
                    'main_corridors': 1,
                    'room_density': 0.9,
                    'module_length': 12,
                    'special_rooms': ['main_corridor', 'emergency_pod']
                },
                {
                    'style': 'fortified_compound',
                    'name': 'Defensive Layout',
                    'main_corridors': 2,
                    'room_density': 0.75,
                    'defense_points': 4,
                    'special_rooms': ['armory', 'security_hub']
                }
            ],
            'gate': [
                {
                    'style': 'gate_complex',
                    'name': 'Gate Infrastructure',
                    'main_corridors': 3,
                    'room_density': 0.6,
                    'gate_chambers': 2,
                    'special_rooms': ['gate_core', 'control_chamber']
                },
                {
                    'style': 'research_facility',
                    'name': 'Research Complex',
                    'main_corridors': 4,
                    'room_density': 0.7,
                    'lab_wings': 3,
                    'special_rooms': ['main_lab', 'observation_deck']
                },
                {
                    'style': 'monitoring_station',
                    'name': 'Monitoring Array',
                    'main_corridors': 2,
                    'room_density': 0.8,
                    'sensor_arrays': 6,
                    'special_rooms': ['sensor_core', 'data_center']
                }
            ]
        }
        
    def apply_faction_color_scheme(self, location_data: Dict):
        """Apply faction-specific color schemes to modify the holographic appearance"""
        faction = location_data.get('faction') or 'Independent'
        is_derelict = location_data.get('is_derelict', False)
        
        # Store original colors in case we need them
        if not hasattr(self, 'original_colors'):
            self.original_colors = self.colors.copy()
        
        # Reset to original colors first
        self.colors = self.original_colors.copy()
        
        if is_derelict:
            # Derelict locations: corrupted green/brown decay theme
            self.colors.update({
                'background': '#001100',        # Dark green background
                'background_deep': '#000800',   # Even darker green
                'primary_cyan': '#00AA44',      # Corrupted green instead of cyan
                'cyan_glow': '#00FF44',         # Bright decay green
                'cyan_dark': '#004422',         # Dark decay green
                
                'grid_major': '#002211',        # Darker grid
                'grid_minor': '#001100',        # Very dark grid
                'grid_dots': '#003322',         # Decay grid dots
                
                'wall_primary': '#00AA44',      # Corrupted green walls
                'wall_secondary': '#006633',    # Darker green walls
                'corridor': '#000a00',          # Dark green corridors
                'corridor_outline': '#004422',  # Decay green borders
                
                'text_primary': '#00FF44',      # Corrupted green text
                'text_secondary': '#00CC33',    # Secondary decay text
                'text_highlight': '#AAFF88',    # Pale decay highlight
                'text_annotation': '#006633',   # Dark annotation text
                
                'glow_bright': '#44FF88',       # Corrupted bright glow
                'glow_soft': '#22AA44',         # Soft decay glow
            })
            
        elif faction == 'loyalist':
            # Federal/Loyalist: clean blue-white military precision theme
            self.colors.update({
                'background': '#000044',        # Darker blue background
                'background_deep': '#000033',   # Deep military blue
                'primary_cyan': '#4488FF',      # Bright federal blue
                'cyan_glow': '#6699FF',         # Soft blue glow
                'cyan_dark': '#2266BB',         # Dark federal blue
                
                'grid_major': '#223366',        # Military grid
                'grid_minor': '#112244',        # Subtle grid
                'grid_dots': '#4477AA',         # Bright grid dots
                
                'wall_primary': '#4488FF',      # Federal blue walls
                'wall_secondary': '#6699FF',    # Lighter blue walls
                'corridor': '#001144',          # Deep blue corridors
                'corridor_outline': '#3377CC',  # Federal blue borders
                
                'text_primary': '#FFFFFF',      # Clean white text
                'text_secondary': '#AACCFF',    # Light blue text
                'text_highlight': '#FFFFFF',    # Pure white highlight
                'text_annotation': '#4488FF',   # Federal blue annotations
                
                'glow_bright': '#FFFFFF',       # Pure white glow
                'glow_soft': '#88AAFF',         # Soft federal glow
            })
            
        elif faction == 'outlaw':
            # Outlaw: aggressive red-orange chaotic theme  
            self.colors.update({
                'background': '#330000',        # Dark red background
                'background_deep': '#220000',   # Deep blood red
                'primary_cyan': '#FF4400',      # Aggressive orange-red
                'cyan_glow': '#FF6633',         # Bright outlaw glow
                'cyan_dark': '#AA2200',         # Dark outlaw red
                
                'grid_major': '#442200',        # Rust grid
                'grid_minor': '#221100',        # Dark rust grid
                'grid_dots': '#664422',         # Outlaw grid dots
                
                'wall_primary': '#FF4400',      # Outlaw orange walls
                'wall_secondary': '#CC3300',    # Dark red walls
                'corridor': '#110000',          # Blood red corridors
                'corridor_outline': '#BB2200',  # Outlaw red borders
                
                'text_primary': '#FF6600',      # Bright outlaw text
                'text_secondary': '#DD4400',    # Secondary outlaw text
                'text_highlight': '#FFAA44',    # Orange highlight
                'text_annotation': '#AA3300',   # Dark outlaw annotations
                
                'glow_bright': '#FFAA44',       # Bright orange glow
                'glow_soft': '#CC4422',         # Soft outlaw glow
            })
        
        # Independent locations keep the original cyan holographic scheme
    
    def generate_varied_room_name(self, base_type: str, location_data: Dict, room_index: int = 0) -> str:
        """Generate varied room names using existing name dictionaries"""
        random.seed(location_data['location_id'] + room_index)  # Deterministic but varied
        
        faction = location_data.get('faction', 'Independent')
        wealth = location_data['wealth_level']
        population = location_data['population']
        is_derelict = location_data.get('is_derelict', False)
        
        # Base naming patterns by room type
        room_type_names = {
            'residential': ['Residential', 'Housing', 'Living', 'Habitat', 'Apartment', 'Dormitory'],
            'commercial': ['Commercial', 'Market', 'Trade', 'Business', 'Shopping', 'Merchant'],
            'administrative': ['Administrative', 'Command', 'Control', 'Operations', 'Management', 'Oversight'],
            'industrial': ['Industrial', 'Manufacturing', 'Production', 'Factory', 'Workshop', 'Assembly'],
            'medical': ['Medical', 'Health', 'Clinical', 'Treatment', 'Emergency', 'Surgical'],
            'security': ['Security', 'Defense', 'Guard', 'Patrol', 'Enforcement', 'Protection'],
            'power': ['Power', 'Energy', 'Reactor', 'Generator', 'Fusion', 'Electrical'],
            'storage': ['Storage', 'Warehouse', 'Supply', 'Cargo', 'Archive', 'Repository'],
            'maintenance': ['Maintenance', 'Repair', 'Engineering', 'Technical', 'Systems', 'Service'],
            'communications': ['Communications', 'Signal', 'Transmission', 'Network', 'Data', 'Relay'],
            'docking': ['Docking', 'Landing', 'Port', 'Bay', 'Berth', 'Harbor'],
            'recreational': ['Recreation', 'Entertainment', 'Leisure', 'Social', 'Community', 'Lounge']
        }
        
        # Get base name for the room type
        base_names = room_type_names.get(base_type, ['Facility', 'Area', 'Section'])
        base_name = random.choice(base_names)
        
        # Generate varied naming based on location characteristics
        if is_derelict:
            # Derelict locations: damaged/corrupted names
            prefixes = ['Damaged', 'Abandoned', 'Corrupted', 'Failed', 'Lost', 'Dead', 'Broken']
            prefix = random.choice(prefixes)
            suffix = random.choice(self.facility_suffixes[:8])  # Simpler suffixes for derelict
            return f"{prefix} {base_name} {suffix}"
            
        elif faction == 'loyalist':
            # Federal/Loyalist: military precision naming
            if wealth >= 7:  # High-tech federal facilities
                tech_prefixes = ['Advanced', 'Strategic', 'Classified', 'Priority', 'Secure']
                prefix = random.choice(tech_prefixes)
                designator = random.choice(self.location_prefixes[:20])  # Use tech-sounding prefixes
                suffix = random.choice(['Complex', 'Facility', 'Center', 'Station', 'Hub'])
                return f"{prefix} {base_name} {designator}-{suffix}"
            else:  # Standard military naming
                designator = random.choice(self.location_prefixes[:30])
                suffix = random.choice(['Block', 'Section', 'Wing', 'Deck', 'Zone'])
                return f"{designator} {base_name} {suffix}"
                
        elif faction == 'outlaw':
            # Outlaw: improvised/jury-rigged naming
            if population < 50:  # Small outlaw hideouts
                personal_names = random.sample(FIRST_NAMES, min(10, len(FIRST_NAMES)))
                owner_name = random.choice(personal_names)
                descriptors = ['Makeshift', 'Jury-rigged', 'Cobbled', 'Patched', 'Stolen', 'Salvaged']
                descriptor = random.choice(descriptors)
                return f"{owner_name}'s {descriptor} {base_name}"
            else:  # Larger outlaw bases
                rough_prefixes = ['Black', 'Red', 'Rust', 'Scrap', 'Burnt', 'Twisted', 'Broken']
                prefix = random.choice(rough_prefixes)
                location_name = random.choice(self.location_names[:50])  # Rougher names
                return f"{prefix} {location_name} {base_name}"
                
        else:
            # Independent locations: professional but varied naming
            if wealth >= 8:  # Wealthy locations get fancy names
                fancy_prefixes = ['Golden', 'Platinum', 'Diamond', 'Crystal', 'Prime', 'Elite', 'Luxury']
                prefix = random.choice(fancy_prefixes)
                location_name = random.choice(self.location_names)
                suffix = random.choice(['Complex', 'Center', 'Plaza', 'Tower', 'Spire'])
                return f"{prefix} {location_name} {suffix}"
                
            elif wealth <= 3:  # Poor locations get basic names
                basic_prefixes = ['Block', 'Section', 'Unit', 'Area', 'Zone']
                if random.random() < 0.6:  # 60% chance of simple designation
                    designator = chr(65 + room_index) if room_index < 26 else f"{room_index + 1}"
                    prefix = random.choice(basic_prefixes)
                    return f"{base_name} {prefix} {designator}"
                else:  # 40% chance of named area
                    prefix = random.choice(self.location_prefixes[:20])
                    suffix = random.choice(basic_prefixes)
                    return f"{prefix} {base_name} {suffix}"
                    
            else:  # Mid-wealth: professional naming
                if random.random() < 0.7:  # 70% chance of location-based name
                    prefix = random.choice(self.location_prefixes)
                    suffix = random.choice(self.facility_suffixes)
                    return f"{prefix} {base_name} {suffix}"
                else:  # 30% chance of descriptive name
                    descriptor = random.choice(self.location_names)
                    suffix = random.choice(self.facility_suffixes[:12])  # Professional suffixes
                    return f"{descriptor} {base_name} {suffix}"
    
    def get_floormap_path(self, location_id: int) -> str:
        """Get file path for location's holographic floormap"""
        return os.path.join(self.floormaps_dir, f"holo_{location_id}.png")
    
    def load_cached_floormap(self, location_id: int) -> Optional[str]:
        """Check if cached holographic floormap exists"""
        filepath = self.get_floormap_path(location_id)
        return filepath if os.path.exists(filepath) else None
    
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
    
    def get_sub_locations(self, location_id: int) -> List[Dict]:
        """Get actual sub-locations for this location using SubLocationManager"""
        # Get sub-locations directly from database (SubLocationManager method might be async in other contexts)
        sub_locations = self.db.execute_query(
            """SELECT sub_location_id, name, sub_type, description, is_active 
               FROM sub_locations 
               WHERE parent_location_id = %s AND is_active = true
               ORDER BY sub_type = 'admin' DESC, sub_type""",  # Prioritize admin facilities
            (location_id,),
            fetch='all'
        )
        
        if not sub_locations:
            return []
        
        # Priority mapping for important sub-location types
        priority_types = {
            'admin': 10,        # Highest priority
            'security': 9,
            'medbay': 8,
            'engineering': 7,
            'market': 6,
            'bar': 5,
            'hangar': 5,
            'lounge': 4,
            'dormitory': 3,
            'storage': 2
        }
        
        # Convert to the format expected by the graph generator with priority weighting
        formatted_locations = []
        for sub_loc in sub_locations:
            sub_type = sub_loc[2]
            priority = priority_types.get(sub_type, 1)  # Default priority 1
            
            formatted_locations.append({
                'id': sub_loc[0],  # Use actual sub_location_id
                'name': sub_loc[1],
                'type': sub_type,  # Use sub_type as type
                'description': sub_loc[3],
                'is_active': bool(sub_loc[4]),
                'is_background': False,  # Mark as actual sub-locations (not background)
                'priority': priority  # Add priority for layout decisions
            })
        
        return formatted_locations
    
    def generate_layout_graph(self, location_type: str, sub_locations: List[Dict], 
                            location_data: Dict) -> nx.Graph:
        """Generate NetworkX graph representing the facility layout"""
        # Select from multiple layout configs for variety
        available_configs = self.layout_configs.get(location_type, self.layout_configs['outpost'])
        if isinstance(available_configs, list):
            random.seed(location_data['location_id'])  # Deterministic selection
            config = random.choice(available_configs)
        else:
            config = available_configs
        
        random.seed(location_data['location_id'])  # Deterministic generation
        
        # First, create background rooms appropriate for location type
        background_rooms = self._generate_background_rooms(location_type, location_data, sub_locations)
        
        # Combine sub-locations with background rooms
        all_rooms = sub_locations + background_rooms
        
        graph = nx.Graph()
        
        if config['style'] == 'district_grid':
            return self._generate_district_grid_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'sprawling_sectors':
            return self._generate_sprawling_sectors_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'industrial_complex':
            return self._generate_industrial_complex_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'orbital_ring':
            return self._generate_orbital_ring_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'radial_hub':
            return self._generate_radial_hub_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'modular_sections':
            return self._generate_modular_sections_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'vertical_tower':
            return self._generate_vertical_tower_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'rotating_habitat':
            return self._generate_rotating_habitat_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'dual_ring':
            return self._generate_dual_ring_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'compact_linear':
            return self._generate_compact_linear_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'l_shaped':
            return self._generate_l_shaped_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'fortified_cluster':
            return self._generate_fortified_cluster_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'emergency_bunker':
            return self._generate_emergency_bunker_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'gate_terminal':
            return self._generate_gate_terminal_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'transit_hub':
            return self._generate_transit_hub_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'corridor_junction':
            return self._generate_corridor_junction_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'checkpoint_station':
            return self._generate_checkpoint_station_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'linear_spine':
            return self._generate_linear_spine_layout(graph, all_rooms, config, location_data)
        elif config['style'] == 'multi_deck':
            return self._generate_multi_deck_layout(graph, all_rooms, config, location_data)  
        elif config['style'] == 'modular_ship':
            return self._generate_modular_ship_layout(graph, all_rooms, config, location_data)
        else:
            return self._generate_generic_layout(graph, all_rooms, config, location_data)
    
    def _generate_background_rooms(self, location_type: str, location_data: Dict, existing_sub_locations: List[Dict]) -> List[Dict]:
        """Generate background rooms appropriate for each location type, avoiding conflicts with existing sub-locations"""
        background_rooms = []
        wealth = location_data['wealth_level']
        population = location_data['population']
        
        # Get list of existing sub-location types to avoid duplicates
        existing_types = {sub_loc['type'] for sub_loc in existing_sub_locations}
        existing_names = {sub_loc['name'].lower() for sub_loc in existing_sub_locations}
        
        def should_add_background_room(room_type: str, room_name: str) -> bool:
            """Check if we should add this background room"""
            # Don't add if we already have this exact type
            if room_type in existing_types:
                return False
            # Don't add if we have a similar named room
            if room_name.lower() in existing_names:
                return False
            # Don't add if we have a semantically similar room
            similar_types = {
                'docking': {'hangar', 'landing_pad', 'dock', 'port'},
                'residential': {'quarters', 'dormitory', 'housing'},
                'power': {'reactor', 'generator', 'energy'},
                'medical': {'medbay', 'hospital', 'clinic'},
                'commercial': {'market', 'shop', 'trade', 'bar', 'casino'},  # Added casino
                'storage': {'cargo', 'warehouse', 'supply'},
                'maintenance': {'engineering', 'repair', 'workshop'},
                'communications': {'comm', 'radio', 'signal'},
                'admin': {'office', 'control', 'command', 'bridge'},
                'security': {'guard', 'checkpoint', 'defense'},
                'plaza': {'central_plaza', 'hub', 'plaza'},  # Added plaza types
                'hydroponics': {'hydroponics_bay', 'agriculture', 'farming'},  # Added hydroponics
                'archive': {'historical_archive', 'library', 'records'}  # Added archive types
            }
            
            for existing_type in existing_types:
                for bg_type, similar_set in similar_types.items():
                    if room_type == bg_type and existing_type in similar_set:
                        return False
                    if existing_type == bg_type and room_type in similar_set:
                        return False
            
            return True
        
        if location_type == 'colony':
            # Colonies: enclosed, industrial, functional (50-250 population)
            # Residential blocks based on population
            residential_count = min(8, max(2, population // 25))  # 1 block per 25 people
            for i in range(residential_count):
                room_name = self.generate_varied_room_name('residential', location_data, i)
                if should_add_background_room('residential', room_name):
                    background_rooms.append({
                        'id': f'bg_residential_{i}',
                        'name': room_name,
                        'type': 'residential',
                        'description': 'Housing complex',
                        'is_background': True
                    })
            
            # Essential infrastructure (including docking)  
            infrastructure_types = [
                ('docking', 'Ship landing facility'),
                ('storage', 'Freight handling'),
                ('power', 'Main power generation'),
                ('maintenance', 'Water purification'),
                ('maintenance', 'Waste management'),
                ('storage', 'Supply warehouse'),
                ('maintenance', 'Equipment repair'),
                ('communications', 'Colony communications'),
                ('security', 'Access control'),
                ('administrative', 'Resource allocation'),
            ]
            
            potential_rooms = []
            for i, (room_type, description) in enumerate(infrastructure_types):
                room_name = self.generate_varied_room_name(room_type, location_data, i + residential_count)
                potential_rooms.append({
                    'id': f'bg_{room_type}_{i}',
                    'name': room_name,
                    'type': room_type,
                    'description': description,
                    'is_background': True
                })
            
            for room in potential_rooms:
                if should_add_background_room(room['type'], room['name']):
                    background_rooms.append(room)
            
            # Wealth-based additions
            if wealth >= 6:
                luxury_types = [('recreational', 'Entertainment facility'), ('medical', 'Healthcare facility')]
                wealth_rooms = []
                for i, (room_type, description) in enumerate(luxury_types):
                    room_name = self.generate_varied_room_name(room_type, location_data, i + residential_count + len(infrastructure_types))
                    wealth_rooms.append({
                        'id': f'bg_{room_type}_luxury_{i}',
                        'name': room_name,
                        'type': room_type,
                        'description': description,
                        'is_background': True
                    })
                for room in wealth_rooms:
                    if should_add_background_room(room['type'], room['name']):
                        background_rooms.append(room)
        
        elif location_type == 'space_station':
            # Space stations: orbital hubs, larger than outposts, residential + commercial
            # Essential systems
            essential_systems = [
                {'id': 'bg_life_support', 'name': 'Life Support Systems', 'type': 'maintenance', 'description': 'Environmental control', 'is_background': True},
                {'id': 'bg_reactor_core', 'name': 'Reactor Core', 'type': 'power', 'description': 'Station power source', 'is_background': True},
                {'id': 'bg_power_distribution', 'name': 'Power Distribution', 'type': 'power', 'description': 'Electrical systems', 'is_background': True},
                {'id': 'bg_navigation', 'name': 'Navigation Control', 'type': 'bridge', 'description': 'Station positioning', 'is_background': True},
                {'id': 'bg_engineering', 'name': 'Engineering Deck', 'type': 'engineering', 'description': 'Technical systems', 'is_background': True},
                {'id': 'bg_maintenance', 'name': 'Maintenance Section', 'type': 'maintenance', 'description': 'Repair facilities', 'is_background': True},
                {'id': 'bg_comm_array', 'name': 'Communication Array', 'type': 'communications', 'description': 'Long-range comms', 'is_background': True},
            ]
            
            for room in essential_systems:
                if should_add_background_room(room['type'], room['name']):
                    background_rooms.append(room)
            
            # Docking facilities (multiple ports)
            docking_count = min(6, max(2, population // 100))  # More docking for larger stations
            for i in range(docking_count):
                room_name = self.generate_varied_room_name('docking', location_data, i)
                if should_add_background_room('docking', room_name):
                    background_rooms.append({
                        'id': f'bg_docking_{i}',
                        'name': room_name,
                        'type': 'docking',
                        'description': 'Ship docking port',
                        'is_background': True
                    })
            
            # Residential sections for permanent population
            if population > 50:
                residential_sections = min(4, population // 50)
                for i in range(residential_sections):
                    room_name = self.generate_varied_room_name('residential', location_data, i + docking_count)
                    if should_add_background_room('residential', room_name):
                        background_rooms.append({
                            'id': f'bg_residential_deck_{i}',
                            'name': room_name,
                            'type': 'residential',
                            'description': 'Living quarters',
                            'is_background': True
                        })
            
            # Commercial and trade areas
            commercial_types = [
                ('commercial', 'Shopping and services'),
                ('commercial', 'Merchant center'),
                ('storage', 'Freight handling'),
                ('residential', 'Temporary housing'),
            ]
            
            commercial_areas = []
            residential_section_count = residential_sections if population > 50 else 0
            for i, (room_type, description) in enumerate(commercial_types):
                room_name = self.generate_varied_room_name(room_type, location_data, i + docking_count + residential_section_count)
                commercial_areas.append({
                    'id': f'bg_{room_type}_commercial_{i}',
                    'name': room_name,
                    'type': room_type,
                    'description': description,
                    'is_background': True
                })
            
            for room in commercial_areas:
                if should_add_background_room(room['type'], room['name']):
                    background_rooms.append(room)
        
        elif location_type == 'outpost':
            # Outposts: small, <12 personnel, utilitarian, often unmanned
            outpost_rooms = [
                {'id': 'bg_main_airlock', 'name': 'Main Airlock', 'type': 'airlock', 'description': 'Primary entrance', 'is_background': True},
                {'id': 'bg_emergency_airlock', 'name': 'Emergency Airlock', 'type': 'airlock', 'description': 'Emergency exit', 'is_background': True},
                {'id': 'bg_generator', 'name': 'Generator Room', 'type': 'power', 'description': 'Power generation', 'is_background': True},
                {'id': 'bg_battery_systems', 'name': 'Battery Systems', 'type': 'power', 'description': 'Backup power', 'is_background': True},
                {'id': 'bg_maintenance_bay', 'name': 'Maintenance Bay', 'type': 'maintenance', 'description': 'Equipment repair', 'is_background': True},
                {'id': 'bg_docking_port', 'name': 'Docking Port', 'type': 'docking', 'description': 'Ship docking facility', 'is_background': True},
                {'id': 'bg_supply_storage', 'name': 'Supply Storage', 'type': 'storage', 'description': 'Equipment and supplies', 'is_background': True},
                {'id': 'bg_monitoring', 'name': 'Monitoring Station', 'type': 'communications', 'description': 'Sensor array control', 'is_background': True},
                {'id': 'bg_rest_area', 'name': 'Rest Area', 'type': 'quarters', 'description': 'Crew quarters', 'is_background': True},
                {'id': 'bg_emergency_supplies', 'name': 'Emergency Supplies', 'type': 'storage', 'description': 'Survival equipment', 'is_background': True},
            ]
            
            for room in outpost_rooms:
                if should_add_background_room(room['type'], room['name']):
                    background_rooms.append(room)
            
            # Add observation deck if it's a monitoring outpost
            if population <= 5:  # Very small monitoring stations
                if should_add_background_room('observation', 'Observation Deck'):
                    background_rooms.append({
                        'id': 'bg_observation',
                        'name': 'Observation Deck',
                        'type': 'observation',
                        'description': 'Sensor monitoring',
                        'is_background': True
                    })
        
        elif location_type == 'gate':
            # Gates: small truck stop-like facilities adjacent to corridors
            gate_rooms = [
                {'id': 'bg_control_station', 'name': 'Control Station', 'type': 'control', 'description': 'Gate operation control', 'is_background': True},
                {'id': 'bg_transit_cafe', 'name': 'Transit Cafe', 'type': 'travel_services', 'description': 'Food and services for travelers', 'is_background': True},
                {'id': 'bg_decontamination', 'name': 'Decontamination Bay', 'type': 'decontamination', 'description': 'Radiation cleansing', 'is_background': True},
                {'id': 'bg_transit_office', 'name': 'Transit Office', 'type': 'admin', 'description': 'Processing and customs', 'is_background': True},
                {'id': 'bg_waiting_area', 'name': 'Waiting Area', 'type': 'lounge', 'description': 'Passenger waiting', 'is_background': True},
                {'id': 'bg_power_room', 'name': 'Power Room', 'type': 'power', 'description': 'Facility power', 'is_background': True},
                {'id': 'bg_storage', 'name': 'Storage', 'type': 'storage', 'description': 'Equipment storage', 'is_background': True},
            ]
            
            for room in gate_rooms:
                if should_add_background_room(room['type'], room['name']):
                    background_rooms.append(room)
        
        return background_rooms
    
    def _check_room_collision(self, pos1: Tuple[int, int], size1: Tuple[int, int], 
                            pos2: Tuple[int, int], size2: Tuple[int, int], 
                            buffer: int = 20) -> bool:
        """Check if two rooms would overlap with buffer space"""
        x1, y1 = pos1
        w1, h1 = size1
        x2, y2 = pos2
        w2, h2 = size2
        
        # Calculate room boundaries with buffer
        left1 = x1 - w1//2 - buffer
        right1 = x1 + w1//2 + buffer
        top1 = y1 - h1//2 - buffer
        bottom1 = y1 + h1//2 + buffer
        
        left2 = x2 - w2//2 - buffer
        right2 = x2 + w2//2 + buffer
        top2 = y2 - h2//2 - buffer
        bottom2 = y2 + h2//2 + buffer
        
        # Check for overlap
        return not (right1 < left2 or left1 > right2 or bottom1 < top2 or top1 > bottom2)
    
    def _find_non_overlapping_position(self, graph: nx.Graph, base_x: int, base_y: int, 
                                     room_size: Tuple[int, int], max_attempts: int = 20) -> Tuple[int, int]:
        """Find a position that doesn't overlap with existing rooms"""
        attempts = 0
        search_radius = 50
        
        while attempts < max_attempts:
            # Try positions in expanding spiral around base position
            if attempts == 0:
                test_x, test_y = base_x, base_y
            else:
                # Spiral search pattern
                angle = (attempts * 60) % 360  # 60-degree increments
                radius = search_radius * (1 + attempts // 6)  # Expand radius every 6 attempts
                test_x = base_x + int(radius * math.cos(math.radians(angle)))
                test_y = base_y + int(radius * math.sin(math.radians(angle)))
            
            collision_found = False
            
            # Check against all existing rooms
            for node_name, node_data in graph.nodes(data=True):
                if node_data.get('visible', True) and 'pos' in node_data and 'size' in node_data:
                    existing_pos = node_data['pos']
                    existing_size = node_data['size']
                    
                    if self._check_room_collision((test_x, test_y), room_size, 
                                                existing_pos, existing_size):
                        collision_found = True
                        break
            
            if not collision_found:
                return test_x, test_y
            
            attempts += 1
        
        # If we can't find a good position, use the base with larger offset
        return base_x + search_radius * 2, base_y + search_radius * 2
    
    def _ensure_rooms_fit_in_bounds(self, graph: nx.Graph, image_width: int, image_height: int):
        """Adjust room positions to ensure they fit within image bounds"""
        center_x, center_y = image_width // 2, image_height // 2
        margin = 50  # Safety margin from edges
        
        # Calculate bounds for room centers
        min_x = margin - center_x
        max_x = image_width - margin - center_x
        min_y = margin - center_y
        max_y = image_height - margin - center_y
        
        # Adjust positions for all nodes that might extend beyond bounds
        for node_name, node_data in graph.nodes(data=True):
            if 'pos' not in node_data or 'size' not in node_data:
                continue
                
            pos_x, pos_y = node_data['pos']
            room_width, room_height = node_data['size']
            
            # Calculate room boundaries
            room_left = pos_x - room_width // 2
            room_right = pos_x + room_width // 2
            room_top = pos_y - room_height // 2
            room_bottom = pos_y + room_height // 2
            
            # Check and adjust horizontal position
            if room_left < min_x:
                pos_x = min_x + room_width // 2
            elif room_right > max_x:
                pos_x = max_x - room_width // 2
            
            # Check and adjust vertical position
            if room_top < min_y:
                pos_y = min_y + room_height // 2
            elif room_bottom > max_y:
                pos_y = max_y - room_height // 2
            
            # Update the node position
            graph.nodes[node_name]['pos'] = (pos_x, pos_y)
    
    def _calculate_layout_bounds(self, graph: nx.Graph) -> Dict:
        """Calculate the bounding box of all rooms in the layout"""
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for node_name, node_data in graph.nodes(data=True):
            if 'pos' not in node_data or 'size' not in node_data:
                continue
                
            pos_x, pos_y = node_data['pos']
            room_width, room_height = node_data['size']
            
            # Calculate room boundaries
            room_left = pos_x - room_width // 2
            room_right = pos_x + room_width // 2
            room_top = pos_y - room_height // 2
            room_bottom = pos_y + room_height // 2
            
            # Update bounds
            min_x = min(min_x, room_left)
            max_x = max(max_x, room_right)
            min_y = min(min_y, room_top)
            max_y = max(max_y, room_bottom)
        
        # Handle edge case where no rooms have proper position/size data
        if min_x == float('inf'):
            return {'min_x': -200, 'max_x': 200, 'min_y': -150, 'max_y': 150}
            
        return {'min_x': min_x, 'max_x': max_x, 'min_y': min_y, 'max_y': max_y}
    
    def _center_layout_in_canvas(self, graph: nx.Graph, layout_bounds: Dict, canvas_width: int, canvas_height: int):
        """Center the entire layout within the canvas"""
        # Calculate current layout bounds (in case positions have been modified)
        current_bounds = self._calculate_layout_bounds(graph)
        
        # Calculate layout center from current positions
        layout_center_x = (current_bounds['min_x'] + current_bounds['max_x']) / 2
        layout_center_y = (current_bounds['min_y'] + current_bounds['max_y']) / 2
        
        # Calculate canvas center
        canvas_center_x = canvas_width / 2
        canvas_center_y = canvas_height / 2
        
        # Calculate offset needed to center layout
        offset_x = canvas_center_x - layout_center_x
        offset_y = canvas_center_y - layout_center_y
        
        # Apply offset to all room positions
        for node_name, node_data in graph.nodes(data=True):
            if 'pos' in node_data:
                pos_x, pos_y = node_data['pos']
                graph.nodes[node_name]['pos'] = (pos_x + offset_x, pos_y + offset_y)
    
    def _generate_district_grid_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                     config: Dict, location_data: Dict) -> nx.Graph:
        """Generate grid-based district layout for colonies"""
        grid_w, grid_h = config['grid_size']
        
        # Add central plaza only if there isn't already one from the database
        has_central_plaza = any(room['type'].lower() in ['central_plaza', 'plaza'] and 
                               'central' in room['name'].lower() 
                               for room in all_rooms)
        
        central_plaza_node = 'central_plaza'  # Default name for connections
        
        if not has_central_plaza:
            # Create a background central plaza
            graph.add_node('central_plaza', 
                          pos=(0, 0), 
                          room_type='plaza',
                          name='Central Plaza',
                          size=(120, 120),
                          shape='octagon',
                          is_background=True)
        else:
            # Find the actual Central Plaza from database and place it at center
            for room in all_rooms:
                if (room['type'].lower() in ['central_plaza', 'plaza'] and 
                    'central' in room['name'].lower()):
                    plaza_node_id = f"{room['type']}_{room['id']}"
                    graph.add_node(plaza_node_id,
                                  pos=(0, 0),  # Center position
                                  room_type=room['type'],
                                  name=room['name'],
                                  size=(120, 120),
                                  shape='octagon',
                                  is_background=room.get('is_background', False))
                    central_plaza_node = plaza_node_id  # Use this for connections
                    break
        
        # Filter out central plaza from regular room processing (it's handled separately above)
        other_rooms = [room for room in all_rooms if not (
            room['type'].lower() in ['central_plaza', 'plaza'] and 'central' in room['name'].lower()
        )]
        
        # Sort rooms by priority (highest first) to ensure important facilities get better placement
        other_rooms.sort(key=lambda x: x.get('priority', 1), reverse=True)
        
        # Organize all rooms by type (excluding central plaza which is handled separately)
        residential = [sl for sl in other_rooms if sl['type'] in ['dormitory', 'lounge', 'quarters', 'residential']]
        commercial = [sl for sl in other_rooms if sl['type'] in ['market', 'bar', 'casino', 'shop', 'commercial']]
        admin = [sl for sl in other_rooms if sl['type'] in ['admin', 'security', 'control', 'bridge']]
        industrial = [sl for sl in other_rooms if sl['type'] in ['engineering', 'hangar', 'storage', 'maintenance', 'power', 'cargo']]
        services = [sl for sl in other_rooms if sl['type'] in ['medbay', 'research', 'communications', 'medical', 'decontamination', 'archive', 'historical_archive']]
        special = [sl for sl in other_rooms if sl['type'] in ['airlock', 'docking', 'gate_core', 'observation', 'education', 'plaza', 'hub', 'recreation', 'hydroponics', 'hydroponics_bay']]
        
        # Sort each category by priority to ensure admin facilities get prominent positions
        admin.sort(key=lambda x: x.get('priority', 1), reverse=True)
        services.sort(key=lambda x: x.get('priority', 1), reverse=True)
        commercial.sort(key=lambda x: x.get('priority', 1), reverse=True)
        
        # Place districts around central plaza - admin gets prime position (-300, 200)
        districts = [
            ('residential', residential, (-300, -200)),
            ('commercial', commercial, (300, -200)),
            ('administrative', admin, (-300, 200)),  # Premium location for admin
            ('industrial', industrial, (300, 200)),
            ('services', services, (0, -350)),
            ('special', special, (0, 350))
        ]
        
        for district_name, facilities, (base_x, base_y) in districts:
            if not facilities:
                continue
                
            for i, facility in enumerate(facilities):
                # Position facilities within district with collision detection
                initial_offset_x = (i % 2) * 100 - 50
                initial_offset_y = (i // 2) * 80 - 40
                initial_x = base_x + initial_offset_x
                initial_y = base_y + initial_offset_y
                
                # Find non-overlapping position
                room_size = (80, 60)
                final_x, final_y = self._find_non_overlapping_position(graph, initial_x, initial_y, room_size)
                
                node_name = f"{facility['type']}_{facility['id']}"
                graph.add_node(node_name,
                              pos=(final_x, final_y),
                              room_type=facility['type'],
                              name=facility['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=facility.get('is_background', False))
                
                # Connect to central plaza via district waypoint
                district_waypoint = f"{district_name}_waypoint"
                if district_waypoint not in graph.nodes:
                    # Create district waypoint for cleaner corridor routing
                    waypoint_x = base_x + (50 if base_x > 0 else -50)
                    waypoint_y = base_y + (30 if base_y > 0 else -30)
                    graph.add_node(district_waypoint,
                                  pos=(waypoint_x, waypoint_y),
                                  room_type='waypoint',
                                  name=f'{district_name.title()} Access',
                                  size=(20, 20),
                                  shape='waypoint',
                                  visible=False)
                    
                    # Connect waypoint to central plaza
                    graph.add_edge(central_plaza_node, district_waypoint,
                                  corridor_type='main', width=25)
                
                # Connect room to district waypoint
                graph.add_edge(district_waypoint, node_name,
                              corridor_type='district', width=15)
        
        return graph
    
    def _generate_sprawling_sectors_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                         config: Dict, location_data: Dict) -> nx.Graph:
        """Generate sprawling sectors layout for colonies - more organic, less grid-like"""
        sector_count = config.get('sector_count', 4)
        
        # Create central command area
        graph.add_node('command_center',
                      pos=(0, 0),
                      room_type='administrative',
                      name='Command Center',
                      size=(100, 80),
                      shape='octagon',
                      is_background=True)
        
        # Sort all rooms by priority first
        all_rooms.sort(key=lambda x: x.get('priority', 1), reverse=True)
        
        # Organize rooms by function - admin facilities get priority placement near center
        admin_rooms = [r for r in all_rooms if r['type'] in ['admin', 'security', 'control', 'bridge']]
        residential_rooms = [r for r in all_rooms if r['type'] in ['dormitory', 'quarters', 'residential']]
        industrial_rooms = [r for r in all_rooms if r['type'] in ['engineering', 'maintenance', 'power', 'storage', 'cargo']]
        commercial_rooms = [r for r in all_rooms if r['type'] in ['market', 'bar', 'commercial', 'shop']]
        service_rooms = [r for r in all_rooms if r['type'] in ['medbay', 'communications', 'medical']]
        other_rooms = [r for r in all_rooms if r not in admin_rooms + residential_rooms + industrial_rooms + commercial_rooms + service_rooms]
        
        # Create sectors at different distances and angles from center
        # Admin facilities get closest placement to command center
        sectors = [
            ('administrative', admin_rooms, 150, 0),         # North - closest to center
            ('residential', residential_rooms, 250, 45),     # Northeast
            ('industrial', industrial_rooms, 280, 135),     # Southeast  
            ('commercial', commercial_rooms, 220, 225),     # Southwest
            ('services', service_rooms, 240, 315),          # Northwest
        ]
        
        # Add other rooms to the nearest appropriate sector
        if other_rooms:
            sectors[1] = ('residential', residential_rooms + other_rooms[:len(other_rooms)//2], 250, 45)
            sectors[4] = ('services', service_rooms + other_rooms[len(other_rooms)//2:], 240, 315)
        
        for sector_name, facilities, distance, angle_deg in sectors:
            if not facilities:
                continue
                
            # Create sector hub
            angle_rad = math.radians(angle_deg)
            sector_x = distance * math.cos(angle_rad)
            sector_y = distance * math.sin(angle_rad)
            
            sector_hub = f"{sector_name}_hub"
            graph.add_node(sector_hub,
                          pos=(sector_x, sector_y),
                          room_type='hub',
                          name=f'{sector_name.title()} Hub',
                          size=(60, 60),
                          shape='hexagon',
                          is_background=True)
            
            # Connect sector hub to command center
            graph.add_edge('command_center', sector_hub,
                          corridor_type='main', width=20)
            
            # Arrange facilities in organic clusters around sector hub
            cluster_radius = 80
            facilities_per_cluster = max(2, len(facilities) // 3)
            
            for i, facility in enumerate(facilities):
                # Create mini-clusters around the sector hub
                cluster_angle = (i // facilities_per_cluster) * (2 * math.pi / 3)  # 3 clusters max
                cluster_pos = i % facilities_per_cluster
                
                # Add some randomness for organic feel
                angle_variation = (random.random() - 0.5) * 0.5  # ±0.25 radians
                distance_variation = random.random() * 30 - 15    # ±15 pixels
                
                final_angle = angle_rad + cluster_angle + angle_variation
                final_distance = cluster_radius + distance_variation + (cluster_pos * 25)
                
                room_x = sector_x + final_distance * math.cos(final_angle)
                room_y = sector_y + final_distance * math.sin(final_angle)
                
                # Use collision detection for final positioning
                room_size = (70 + random.randint(-10, 10), 55 + random.randint(-5, 5))  # Varied sizes
                final_x, final_y = self._find_non_overlapping_position(graph, room_x, room_y, room_size)
                
                node_name = f"{facility['type']}_{facility['id']}"
                graph.add_node(node_name,
                              pos=(final_x, final_y),
                              room_type=facility['type'],
                              name=facility['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=facility.get('is_background', False))
                
                # Connect to sector hub with varied corridor widths
                corridor_width = 12 + random.randint(-2, 2)
                graph.add_edge(sector_hub, node_name,
                              corridor_type='sector_internal', width=corridor_width)
        
        return graph
    
    def _generate_radial_hub_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                  config: Dict, location_data: Dict) -> nx.Graph:
        """Generate radial hub layout for space stations"""
        hub_radius = config['hub_radius']
        
        # Central hub
        graph.add_node('central_hub',
                      pos=(0, 0),
                      room_type='hub',
                      name='Central Hub',
                      size=(hub_radius * 2, hub_radius * 2),
                      shape='circle')
        
        # Organize rooms by function for radial placement
        residential_rooms = [r for r in all_rooms if r['type'] in ['dormitory', 'quarters', 'residential']]
        docking_rooms = [r for r in all_rooms if r['type'] in ['docking', 'hangar']]
        commercial_rooms = [r for r in all_rooms if r['type'] in ['market', 'bar', 'commercial', 'trade_hub']]
        technical_rooms = [r for r in all_rooms if r['type'] in ['engineering', 'maintenance', 'power', 'life_support']]
        service_rooms = [r for r in all_rooms if r['type'] in ['medbay', 'admin', 'communications']]
        other_rooms = [r for r in all_rooms if r not in residential_rooms + docking_rooms + commercial_rooms + technical_rooms + service_rooms]
        
        # Create ring sections for different room types
        room_groups = [
            ('docking', docking_rooms, hub_radius + 100),
            ('commercial', commercial_rooms, hub_radius + 180),
            ('residential', residential_rooms, hub_radius + 260),
            ('technical', technical_rooms, hub_radius + 340),
            ('service', service_rooms, hub_radius + 420),
            ('other', other_rooms, hub_radius + 500)
        ]
        
        for group_name, rooms, ring_radius in room_groups:
            if not rooms:
                continue
                
            # Create ring waypoint
            ring_waypoint = f"{group_name}_ring"
            graph.add_node(ring_waypoint,
                          pos=(ring_radius - 50, 0),
                          room_type='waypoint',
                          name=f'{group_name.title()} Ring',
                          size=(15, 15),
                          shape='waypoint',
                          visible=False)
            
            # Connect ring to central hub
            graph.add_edge('central_hub', ring_waypoint,
                          corridor_type='ring_access', width=20)
            
            # Arrange rooms in ring
            angle_step = 2 * math.pi / len(rooms) if len(rooms) > 1 else 0
            
            for i, facility in enumerate(rooms):
                angle = i * angle_step
                base_x = ring_radius * math.cos(angle)
                base_y = ring_radius * math.sin(angle)
                
                # Use collision detection for room placement
                room_size = (90, 70)
                final_x, final_y = self._find_non_overlapping_position(graph, base_x, base_y, room_size)
                
                node_name = f"{facility['type']}_{facility['id']}"
                graph.add_node(node_name,
                              pos=(final_x, final_y),
                              room_type=facility['type'],
                              name=facility['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=facility.get('is_background', False))
                
                # Connect to ring waypoint instead of direct to hub
                graph.add_edge(ring_waypoint, node_name,
                              corridor_type='ring_corridor', width=12)
        
        return graph
    
    def _generate_compact_linear_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                      config: Dict, location_data: Dict) -> nx.Graph:
        """Generate compact linear layout for outposts with proper collision detection"""
        # Main corridor spine
        corridor_length = len(all_rooms) * 100 + 200  # Increased spacing
        
        # Entrance airlock
        graph.add_node('entrance_airlock',
                      pos=(-corridor_length // 2, 0),
                      room_type='airlock',
                      name='Entrance Airlock',
                      size=(60, 80),
                      shape='rectangle')
        
        # Main corridor as invisible connector
        graph.add_node('main_corridor',
                      pos=(0, 0),
                      room_type='corridor',
                      name='Main Corridor',
                      size=(corridor_length, 20),
                      shape='corridor',
                      visible=False)
        
        # Connect entrance to main corridor
        graph.add_edge('entrance_airlock', 'main_corridor',
                      corridor_type='main', width=20)
        
        # Arrange facilities along corridor with collision detection
        for i, facility in enumerate(all_rooms):
            base_x = -corridor_length // 2 + 120 + i * 100  # Increased spacing
            base_y = 100 if i % 2 == 0 else -100  # Alternate sides, increased distance
            
            # Use collision detection to find proper position
            room_size = (70, 60)
            final_x, final_y = self._find_non_overlapping_position(graph, base_x, base_y, room_size)
            
            node_name = f"{facility['type']}_{facility['id']}"
            graph.add_node(node_name,
                          pos=(final_x, final_y),
                          room_type=facility['type'],
                          name=facility['name'],
                          size=room_size,
                          shape='rectangle')
            
            # Connect to main corridor
            graph.add_edge('main_corridor', node_name,
                          corridor_type='branch', width=12)
        
        return graph
    
    def _generate_gate_terminal_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                     config: Dict, location_data: Dict) -> nx.Graph:
        """Generate gate terminal layout with proper docking/airlock flow"""
        # Entrance Airlock - this is the main entry point from space
        graph.add_node('entrance_airlock',
                      pos=(-200, 0),
                      room_type='airlock',
                      name='Entrance Airlock',
                      size=(80, 60),
                      shape='rectangle')
        
        # Docking Pad - directly connected to airlock (ships dock here first)
        graph.add_node('docking_pad',
                      pos=(-300, 0),
                      room_type='docking',
                      name='Docking Pad',
                      size=(100, 80),
                      shape='rectangle')
        
        # Connect docking pad to airlock (logical flow)
        graph.add_edge('docking_pad', 'entrance_airlock',
                      corridor_type='docking_access', width=20)
        
        # Organize rooms by function for better placement
        control_rooms = [r for r in all_rooms if r['type'] in ['control', 'admin', 'security']]
        service_rooms = [r for r in all_rooms if r['type'] in ['travel_services', 'lounge', 'market', 'bar']]
        utility_rooms = [r for r in all_rooms if r['type'] in ['power', 'storage', 'maintenance', 'decontamination']]
        other_rooms = [r for r in all_rooms if r not in control_rooms + service_rooms + utility_rooms]
        
        # Control Station - positioned to oversee docking operations
        if control_rooms:
            control_room = control_rooms[0]
            graph.add_node(f"{control_room['type']}_{control_room['id']}",
                          pos=(-200, 120),
                          room_type=control_room['type'],
                          name=control_room['name'],
                          size=(90, 70),
                          shape='rectangle')
            
            # Connect control to airlock for monitoring
            graph.add_edge('entrance_airlock', f"{control_room['type']}_{control_room['id']}",
                          corridor_type='control_access', width=15)
        
        # Main Terminal Area
        graph.add_node('main_terminal',
                      pos=(0, 0),
                      room_type='terminal',
                      name='Main Terminal',
                      size=(120, 100),
                      shape='octagon')
        
        # Connect airlock to main terminal
        graph.add_edge('entrance_airlock', 'main_terminal',
                      corridor_type='main', width=25)
        
        # Service Area - around the main terminal (expandable positions)
        base_service_positions = [(100, 80), (100, -80), (0, 120), (0, -120)]
        # Generate additional positions in a ring pattern if needed
        service_positions = base_service_positions[:]
        if len(service_rooms) > len(base_service_positions):
            additional_needed = len(service_rooms) - len(base_service_positions)
            for i in range(additional_needed):
                angle = (i + 4) * (360 / (additional_needed + 4))  # Distribute around circle
                radius = 150  # Slightly further out
                x = radius * math.cos(math.radians(angle))
                y = radius * math.sin(math.radians(angle))
                service_positions.append((int(x), int(y)))
        
        for i, service_room in enumerate(service_rooms):  # Process ALL service rooms
            if i < len(service_positions):
                pos_x, pos_y = service_positions[i]
            else:
                # Fallback: place in expanding spiral
                angle = i * 45
                radius = 200 + (i // 8) * 50
                pos_x = radius * math.cos(math.radians(angle))
                pos_y = radius * math.sin(math.radians(angle))
            
            # Use collision detection
            room_size = (80, 60)
            final_x, final_y = self._find_non_overlapping_position(graph, pos_x, pos_y, room_size)
            
            node_name = f"{service_room['type']}_{service_room['id']}"
            graph.add_node(node_name,
                          pos=(final_x, final_y),
                          room_type=service_room['type'],
                          name=service_room['name'],
                          size=room_size,
                          shape='rectangle',
                          is_background=service_room.get('is_background', False))
            
            # Connect to main terminal
            graph.add_edge('main_terminal', node_name,
                          corridor_type='service_access', width=12)
        
        # Utility Area - positioned away from main traffic (expandable)
        base_utility_positions = [(-100, 120), (-100, -120), (200, 0)]
        # Generate additional utility positions if needed
        utility_positions = base_utility_positions[:]
        if len(utility_rooms) > len(base_utility_positions):
            additional_needed = len(utility_rooms) - len(base_utility_positions)
            for i in range(additional_needed):
                # Place utilities in back areas, away from main flow
                angle = 180 + (i * 60)  # Back half of facility
                radius = 180 + (i * 30)
                x = radius * math.cos(math.radians(angle))
                y = radius * math.sin(math.radians(angle))
                utility_positions.append((int(x), int(y)))
        
        for i, utility_room in enumerate(utility_rooms):  # Process ALL utility rooms
            if i < len(utility_positions):
                pos_x, pos_y = utility_positions[i]
            else:
                # Fallback: place behind main terminal
                pos_x = -250 - (i * 60)
                pos_y = (i % 2) * 100 - 50
            
            # Use collision detection
            room_size = (70, 50)
            final_x, final_y = self._find_non_overlapping_position(graph, pos_x, pos_y, room_size)
            
            node_name = f"{utility_room['type']}_{utility_room['id']}"
            graph.add_node(node_name,
                          pos=(final_x, final_y),
                          room_type=utility_room['type'],
                          name=utility_room['name'],
                          size=room_size,
                          shape='rectangle',
                          is_background=utility_room.get('is_background', False))
            
            # Connect to main terminal
            graph.add_edge('main_terminal', node_name,
                          corridor_type='utility_access', width=10)
        
        # Handle remaining rooms (those not yet placed)
        # Get already placed room IDs to avoid duplicates
        placed_room_ids = set()
        for node_name in graph.nodes():
            if '_' in node_name and not node_name.startswith('main_') and not node_name.startswith('entrance_') and not node_name.startswith('docking_'):
                try:
                    room_id = node_name.split('_')[-1]
                    placed_room_ids.add(room_id)
                except:
                    pass
        
        # Find unplaced rooms
        remaining_rooms = [room for room in other_rooms if str(room['id']) not in placed_room_ids]
        if remaining_rooms:
            for i, room in enumerate(remaining_rooms):
                # Place in a secondary ring around the terminal
                angle = (i * 60) % 360  # 60-degree spacing
                radius = 250  # Increased radius to avoid overlaps
                pos_x = radius * math.cos(math.radians(angle))
                pos_y = radius * math.sin(math.radians(angle))
                
                room_size = (60, 50)
                final_x, final_y = self._find_non_overlapping_position(graph, pos_x, pos_y, room_size)
                
                node_name = f"{room['type']}_{room['id']}"
                graph.add_node(node_name,
                              pos=(final_x, final_y),
                              room_type=room['type'],
                              name=room['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=room.get('is_background', False))
                
                # Connect to main terminal
                graph.add_edge('main_terminal', node_name,
                              corridor_type='secondary_access', width=8)
                
        
        return graph
    
    def _generate_modular_sections_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                        config: Dict, location_data: Dict) -> nx.Graph:
        """Generate modular sections layout for stations and facilities"""
        sections = config.get('sections', ['primary', 'secondary', 'tertiary'])
        section_spacing = 200
        section_width = 150
        
        # Create main connecting corridor
        total_width = len(sections) * section_spacing
        graph.add_node('central_corridor',
                      pos=(0, 0),
                      room_type='corridor',
                      name='Central Corridor',
                      size=(total_width, 30),
                      shape='corridor',
                      visible=False)
        
        # Organize rooms by section priority
        critical_rooms = [r for r in all_rooms if r['type'] in ['bridge', 'control', 'security', 'power']]
        standard_rooms = [r for r in all_rooms if r['type'] in ['quarters', 'medbay', 'lounge', 'storage']]
        support_rooms = [r for r in all_rooms if r['type'] in ['cargo', 'maintenance', 'engineering', 'hydroponics']]
        
        room_groups = [critical_rooms, standard_rooms, support_rooms]
        
        for section_idx, (section_name, rooms) in enumerate(zip(sections, room_groups)):
            if not rooms:
                continue
                
            section_x = -total_width // 2 + section_idx * section_spacing + section_spacing // 2
            
            # Create section hub
            hub_name = f"section_{section_idx}_hub"
            graph.add_node(hub_name,
                          pos=(section_x, 0),
                          room_type='hub',
                          name=f'{section_name.title()} Section Hub',
                          size=(40, 40),
                          shape='circle',
                          visible=False)
            
            # Connect hub to central corridor
            graph.add_edge('central_corridor', hub_name,
                          corridor_type='main', width=20)
            
            # Arrange rooms around section hub
            for i, room in enumerate(rooms):
                angle = (i * 360 / len(rooms)) if len(rooms) > 1 else 0
                radius = 80
                room_x = section_x + radius * math.cos(math.radians(angle))
                room_y = radius * math.sin(math.radians(angle))
                
                # Use collision detection to avoid overlaps
                room_size = (60, 50)
                final_x, final_y = self._find_non_overlapping_position(graph, room_x, room_y, room_size)
                
                node_name = f"{room['type']}_{room['id']}"
                graph.add_node(node_name,
                              pos=(final_x, final_y),
                              room_type=room['type'],
                              name=room['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=room.get('is_background', False))
                
                # Connect to section hub
                graph.add_edge(hub_name, node_name,
                              corridor_type='branch', width=12)
        
        return graph
    
    def _generate_vertical_tower_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                      config: Dict, location_data: Dict) -> nx.Graph:
        """Generate vertical tower layout for space stations"""
        tower_levels = config.get('tower_levels', 8)
        level_height = 100
        rooms_per_level = 3
        
        # Create central elevator shaft
        graph.add_node('elevator_shaft',
                      pos=(0, 0),
                      room_type='corridor',
                      name='Central Elevator',
                      size=(30, tower_levels * level_height),
                      shape='corridor',
                      visible=False)
        
        # Sort rooms by priority - admin facilities get upper levels
        all_rooms.sort(key=lambda x: x.get('priority', 1), reverse=True)
        
        # Organize rooms by level priority
        admin_rooms = [r for r in all_rooms if r['type'] in ['admin', 'security', 'control', 'bridge']]
        critical_rooms = [r for r in all_rooms if r['type'] in ['medbay', 'engineering', 'power']]
        service_rooms = [r for r in all_rooms if r['type'] in ['communications', 'research', 'market']]
        residential_rooms = [r for r in all_rooms if r['type'] in ['dormitory', 'lounge', 'recreation']]
        industrial_rooms = [r for r in all_rooms if r['type'] in ['storage', 'cargo', 'hangar', 'maintenance']]
        
        # Assign rooms to levels (top to bottom by importance)
        level_assignments = [
            admin_rooms,           # Top levels - command and administration
            critical_rooms,        # Upper levels - critical systems
            service_rooms,         # Mid levels - services
            residential_rooms,     # Lower levels - living areas
            industrial_rooms       # Bottom levels - storage and maintenance
        ]
        
        level_idx = 0
        for level_rooms in level_assignments:
            if not level_rooms or level_idx >= tower_levels:
                continue
                
            # Place rooms on this level
            rooms_placed = 0
            for room in level_rooms:
                if rooms_placed >= rooms_per_level:
                    level_idx += 1
                    if level_idx >= tower_levels:
                        break
                    rooms_placed = 0
                
                # Calculate level position (higher levels = negative Y)
                level_y = -(level_idx * level_height)
                
                # Arrange rooms in circle around elevator shaft
                angle = (rooms_placed * 360 / rooms_per_level)
                radius = 80
                room_x = radius * math.cos(math.radians(angle))
                room_y = level_y + radius * math.sin(math.radians(angle)) * 0.3  # Flatten the circle
                
                # Create level hub if this is first room on level
                if rooms_placed == 0:
                    hub_name = f"level_{level_idx}_hub"
                    graph.add_node(hub_name,
                                  pos=(0, level_y),
                                  room_type='hub',
                                  name=f'Level {tower_levels - level_idx}',
                                  size=(25, 25),
                                  shape='circle',
                                  visible=False)
                    
                    # Connect hub to elevator
                    graph.add_edge('elevator_shaft', hub_name,
                                  corridor_type='main', width=15)
                
                # Create room node
                room_size = (70, 50) if room['type'] in ['admin', 'bridge', 'control'] else (60, 45)
                node_name = f"{room['type']}_{room['id']}"
                graph.add_node(node_name,
                              pos=(room_x, room_y),
                              room_type=room['type'],
                              name=room['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=room.get('is_background', False))
                
                # Connect to level hub
                hub_name = f"level_{level_idx}_hub"
                graph.add_edge(hub_name, node_name,
                              corridor_type='branch', width=10)
                
                rooms_placed += 1
            
            if rooms_placed > 0:
                level_idx += 1
        
        return graph
    
    def _generate_rotating_habitat_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                        config: Dict, location_data: Dict) -> nx.Graph:
        """Generate rotating habitat layout for space stations"""
        rotation_rings = config.get('rotation_rings', 3)
        ring_radius_base = 120
        
        # Create central rotation hub
        graph.add_node('rotation_hub',
                      pos=(0, 0),
                      room_type='hub',
                      name='Rotation Control Hub',
                      size=(50, 50),
                      shape='circle',
                      is_background=True)
        
        # Sort rooms by priority and type
        all_rooms.sort(key=lambda x: x.get('priority', 1), reverse=True)
        
        # Organize rooms by ring assignment
        core_rooms = [r for r in all_rooms if r['type'] in ['admin', 'control', 'bridge', 'security']]
        mid_ring_rooms = [r for r in all_rooms if r['type'] in ['medbay', 'engineering', 'research', 'communications']]
        outer_ring_rooms = [r for r in all_rooms if r['type'] in ['dormitory', 'lounge', 'recreation', 'market']]
        
        ring_assignments = [core_rooms, mid_ring_rooms, outer_ring_rooms]
        
        for ring_idx in range(min(rotation_rings, len(ring_assignments))):
            ring_rooms = ring_assignments[ring_idx]
            if not ring_rooms:
                continue
                
            ring_radius = ring_radius_base + (ring_idx * 80)
            rooms_count = len(ring_rooms)
            
            # Create gravity well for this ring
            gravity_well_name = f"gravity_well_{ring_idx}"
            graph.add_node(gravity_well_name,
                          pos=(0, -ring_radius),
                          room_type='special',
                          name=f'Gravity Well {ring_idx + 1}',
                          size=(30, 30),
                          shape='circle',
                          visible=False)
            
            # Connect gravity well to rotation hub
            graph.add_edge('rotation_hub', gravity_well_name,
                          corridor_type='main', width=15)
            
            # Place rooms around the ring
            for i, room in enumerate(ring_rooms):
                angle = (i * 360 / rooms_count) if rooms_count > 1 else 0
                room_x = ring_radius * math.cos(math.radians(angle))
                room_y = ring_radius * math.sin(math.radians(angle))
                
                # Adjust room size based on ring position (outer rings = larger rooms)
                base_size = 45 + (ring_idx * 10)
                room_size = (base_size + 15, base_size) if room['type'] in ['dormitory', 'lounge'] else (base_size, base_size)
                
                node_name = f"{room['type']}_{room['id']}"
                graph.add_node(node_name,
                              pos=(room_x, room_y),
                              room_type=room['type'],
                              name=room['name'],
                              size=room_size,
                              shape='rectangle',
                              is_background=room.get('is_background', False))
                
                # Connect to gravity well with curved corridor
                graph.add_edge(gravity_well_name, node_name,
                              corridor_type='curved', width=8)
                
                # Connect adjacent rooms in ring
                if rooms_count > 1:
                    next_room_idx = (i + 1) % rooms_count
                    if next_room_idx < len(ring_rooms):
                        next_room = ring_rooms[next_room_idx]
                        next_node_name = f"{next_room['type']}_{next_room['id']}"
                        graph.add_edge(node_name, next_node_name,
                                      corridor_type='ring', width=6)
        
        return graph
    
    def _generate_linear_spine_layout(self, graph: nx.Graph, all_rooms: List[Dict], 
                                    config: Dict, location_data: Dict) -> nx.Graph:
        """Generate linear spine layout for ships"""
        sections = config['sections']
        section_length = 150
        total_length = len(sections) * section_length
        
        # Main spine corridor
        graph.add_node('main_spine',
                      pos=(0, 0),
                      room_type='corridor',
                      name='Main Corridor',
                      size=(total_length, 25),
                      shape='corridor',
                      visible=False)
        
        # Organize facilities by section
        bow_facilities = [sl for sl in all_rooms if sl['type'] in ['bridge', 'sensors', 'weapons', 'control']]
        mid_facilities = [sl for sl in all_rooms if sl['type'] in ['quarters', 'medbay', 'lounge', 'residential']]
        stern_facilities = [sl for sl in all_rooms if sl['type'] in ['engine', 'engineering', 'cargo', 'power']]
        
        section_facilities = [bow_facilities, mid_facilities, stern_facilities]
        
        for section_idx, (section_name, facilities) in enumerate(zip(sections, section_facilities)):
            section_x = -total_length // 2 + section_idx * section_length + section_length // 2
            
            for i, facility in enumerate(facilities):
                y_offset = (i - len(facilities) // 2) * 60
                side_offset = 40 if i % 2 == 0 else -40
                
                node_name = f"{facility['type']}_{facility['id']}"
                graph.add_node(node_name,
                              pos=(section_x, y_offset + side_offset),
                              room_type=facility['type'],
                              name=facility['name'],
                              size=(60, 50),
                              shape='rectangle',
                              is_background=facility.get('is_background', False))
                
                graph.add_edge('main_spine', node_name,
                              corridor_type='branch', width=10)
        
        return graph
    
    def _generate_generic_layout(self, graph: nx.Graph, sub_locations: List[Dict], 
                               config: Dict, location_data: Dict) -> nx.Graph:
        """Generate generic layout fallback"""
        return self._generate_compact_linear_layout(graph, sub_locations, config, location_data)
    
    def create_holographic_image(self, width: int, height: int, location_data: Dict, 
                               graph: nx.Graph) -> Image.Image:
        """Create the main holographic blueprint image"""
        # Create image with deep space background
        image = Image.new('RGB', (width, height), self.colors['background'])
        draw = ImageDraw.Draw(image)
        
        # Add subtle starfield background
        self._draw_starfield(draw, width, height, location_data['location_id'])
        
        # Draw technical grid
        self._draw_technical_grid(draw, width, height)
        
        # Draw the facility layout
        self._draw_facility_from_graph(draw, graph, width, height)
        
        # Add holographic effects
        image = self._apply_holographic_effects(image)
        
        # Draw technical annotations and labels
        self._draw_technical_annotations(image, location_data, graph)
        
        return image
    
    def _draw_starfield(self, draw: ImageDraw.ImageDraw, width: int, height: int, seed: int):
        """Draw subtle starfield background"""
        random.seed(seed)
        star_count = min(100, width * height // 10000)
        
        for _ in range(star_count):
            x = random.randint(0, width)
            y = random.randint(0, height)
            brightness = random.randint(30, 80)
            color = f"#{brightness:02x}{brightness:02x}{brightness + 20:02x}"
            draw.point((x, y), fill=color)
    
    def _draw_technical_grid(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw technical blueprint grid"""
        # Major grid lines every 100 pixels
        for x in range(0, width, 100):
            draw.line([(x, 0), (x, height)], fill=self.colors['grid_major'], width=1)
        for y in range(0, height, 100):
            draw.line([(0, y), (width, y)], fill=self.colors['grid_major'], width=1)
        
        # Minor grid lines every 20 pixels
        for x in range(0, width, 20):
            draw.line([(x, 0), (x, height)], fill=self.colors['grid_minor'], width=1)
        for y in range(0, height, 20):
            draw.line([(0, y), (width, y)], fill=self.colors['grid_minor'], width=1)
        
        # Grid intersection dots
        for x in range(0, width, 100):
            for y in range(0, height, 100):
                draw.ellipse([x-2, y-2, x+2, y+2], fill=self.colors['grid_dots'])
    
    def _draw_facility_from_graph(self, draw: ImageDraw.ImageDraw, graph: nx.Graph, 
                                width: int, height: int):
        """Draw the facility layout from the NetworkX graph"""
        # Note: Positions are already centered by _center_layout_in_canvas()
        # No need to add canvas center again
        
        # First pass: Draw corridors (edges)
        for edge in graph.edges(data=True):
            node1, node2, edge_data = edge
            
            if node1 not in graph.nodes or node2 not in graph.nodes:
                continue
                
            pos1 = graph.nodes[node1]['pos']
            pos2 = graph.nodes[node2]['pos']
            
            x1, y1 = pos1[0], pos1[1]
            x2, y2 = pos2[0], pos2[1]
            
            corridor_width = edge_data.get('width', 15)
            self._draw_holographic_corridor(draw, x1, y1, x2, y2, corridor_width)
        
        # Second pass: Draw rooms (nodes)
        for node_name, node_data in graph.nodes(data=True):
            if node_data.get('visible', True):  # Skip invisible nodes like corridor connectors
                pos = node_data['pos']
                x, y = pos[0], pos[1]
                
                # Add node_name to node_data for background room detection
                node_data_with_id = node_data.copy()
                node_data_with_id['node_id'] = node_name
                self._draw_holographic_room(draw, x, y, node_data_with_id)
    
    def _draw_holographic_corridor(self, draw: ImageDraw.ImageDraw, x1: int, y1: int, 
                                 x2: int, y2: int, width: int):
        """Draw a holographic corridor between two points with improved routing"""
        # For short distances, draw direct connection
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance < 50:  # Very close, draw direct
            self._draw_corridor_segment(draw, x1, y1, x2, y2, width)
            return
        
        # For longer distances, create L-shaped corridor to avoid room overlap
        if abs(dx) > abs(dy):
            # Horizontal first, then vertical
            mid_x = x1 + dx * 0.7  # 70% of the way horizontally
            mid_y = y1
            
            # Draw horizontal segment
            self._draw_corridor_segment(draw, x1, y1, mid_x, mid_y, width)
            # Draw vertical segment
            self._draw_corridor_segment(draw, mid_x, mid_y, x2, y2, width)
        else:
            # Vertical first, then horizontal
            mid_x = x1
            mid_y = y1 + dy * 0.7  # 70% of the way vertically
            
            # Draw vertical segment
            self._draw_corridor_segment(draw, x1, y1, mid_x, mid_y, width)
            # Draw horizontal segment
            self._draw_corridor_segment(draw, mid_x, mid_y, x2, y2, width)
    
    def _draw_corridor_segment(self, draw: ImageDraw.ImageDraw, x1: int, y1: int, 
                             x2: int, y2: int, width: int):
        """Draw a single corridor segment"""
        # Calculate perpendicular offset for corridor width
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
            
        # Unit perpendicular vector
        perp_x = -dy / length * (width // 2)
        perp_y = dx / length * (width // 2)
        
        # Corridor outline points
        points = [
            (x1 + perp_x, y1 + perp_y),
            (x1 - perp_x, y1 - perp_y),
            (x2 - perp_x, y2 - perp_y),
            (x2 + perp_x, y2 + perp_y)
        ]
        
        # Draw corridor fill
        draw.polygon(points, fill=self.colors['corridor'], outline=self.colors['corridor_outline'], width=1)
        
        # Draw center line
        draw.line([(x1, y1), (x2, y2)], fill=self.colors['cyan_glow'], width=1)
    
    def _draw_holographic_room(self, draw: ImageDraw.ImageDraw, x: int, y: int, room_data: Dict):
        """Draw a holographic room with appropriate shape and styling"""
        room_type = room_data['room_type']
        size = room_data['size']
        shape = room_data['shape']
        name = room_data['name']
        node_id = room_data.get('node_id', '')
        
        # Get room color and adjust brightness for background rooms
        color_key = self.room_colors.get(room_type, 'special')
        room_color = self.colors[color_key]
        
        # Dim background rooms to make actual sub-locations more prominent
        is_background = '_bg_' in node_id
        if is_background:
            # Convert hex color to RGB, reduce brightness, convert back
            if room_color.startswith('#'):
                r = int(room_color[1:3], 16)
                g = int(room_color[3:5], 16) 
                b = int(room_color[5:7], 16)
                # Reduce brightness by 40%
                r = int(r * 0.6)
                g = int(g * 0.6)
                b = int(b * 0.6)
                room_color = f"#{r:02x}{g:02x}{b:02x}"
        
        # Draw based on shape
        if shape == 'circle':
            self._draw_circular_room(draw, x, y, size, room_color, name, is_background)
        elif shape == 'hexagon':
            self._draw_hexagonal_room(draw, x, y, size, room_color, name, is_background)
        elif shape == 'octagon':
            self._draw_octagonal_room(draw, x, y, size, room_color, name, is_background)
        else:  # rectangle
            self._draw_rectangular_room(draw, x, y, size, room_color, name, is_background)
    
    def _draw_rectangular_room(self, draw: ImageDraw.ImageDraw, x: int, y: int, 
                             size: Tuple[int, int], color: str, name: str, is_background: bool = False):
        """Draw rectangular room with holographic styling"""
        w, h = size
        left = x - w // 2
        top = y - h // 2
        right = left + w
        bottom = top + h
        
        # Room outline with glow effect
        for width in range(3, 0, -1):
            alpha = int(255 * (width / 3) * 0.8)
            glow_color = color + f"{alpha:02x}" if len(color) == 7 else color
            draw.rectangle([left-width, top-width, right+width, bottom+width], 
                          outline=glow_color, width=width)
        
        # Main room outline - thicker border and additional effects for actual sub-locations
        if not is_background:
            # Outer glow for actual sub-locations
            draw.rectangle([left-2, top-2, right+2, bottom+2], outline=self.colors['glow_bright'], width=1)
            draw.rectangle([left-1, top-1, right+1, bottom+1], outline=color, width=2)
            # Inner bright border
            draw.rectangle([left+2, top+2, right-2, bottom-2], outline=self.colors['glow_bright'], width=1)
            # Corner accent marks for actual sub-locations
            corner_size = 4
            corners = [(left, top), (right, top), (left, bottom), (right, bottom)]
            for cx, cy in corners:
                draw.ellipse([cx-corner_size, cy-corner_size, cx+corner_size, cy+corner_size], 
                            fill=self.colors['glow_bright'])
        else:
            # Standard border for background rooms
            draw.rectangle([left, top, right, bottom], outline=color, width=1)
        
        # Corner reinforcement dots only for background rooms (actual sub-locations already have corner accents)
        if is_background:
            corner_size = 2
            corners = [(left, top), (right, top), (left, bottom), (right, bottom)]
            for cx, cy in corners:
                draw.ellipse([cx-corner_size, cy-corner_size, cx+corner_size, cy+corner_size], 
                            fill=self.colors['cyan_dark'])
        
        # Add internal details based on room size
        if w > 60 and h > 40:
            self._add_room_internals(draw, left, top, w, h, color)
        
        # Room label
        self._draw_holographic_text(draw, x, y, name, self.colors['text_primary'])
    
    def _draw_circular_room(self, draw: ImageDraw.ImageDraw, x: int, y: int, 
                          size: Tuple[int, int], color: str, name: str, is_background: bool = False):
        """Draw circular room with holographic styling"""
        radius = size[0] // 2
        
        # Glow effect
        for r in range(radius + 3, radius, -1):
            alpha = int(255 * ((radius + 3 - r) / 3) * 0.6)
            glow_color = color + f"{alpha:02x}" if len(color) == 7 else color
            draw.ellipse([x-r, y-r, x+r, y+r], outline=glow_color, width=2)
        
        # Main circle
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], outline=color, width=2)
        
        # Center point
        draw.ellipse([x-3, y-3, x+3, y+3], fill=self.colors['primary_cyan'])
        
        # Radial lines for technical appearance
        for angle in range(0, 360, 45):
            end_x = x + (radius - 10) * math.cos(math.radians(angle))
            end_y = y + (radius - 10) * math.sin(math.radians(angle))
            draw.line([(x, y), (end_x, end_y)], fill=self.colors['cyan_dark'], width=1)
        
        # Room label
        self._draw_holographic_text(draw, x, y + radius + 15, name, self.colors['text_primary'])
    
    def _draw_hexagonal_room(self, draw: ImageDraw.ImageDraw, x: int, y: int, 
                           size: Tuple[int, int], color: str, name: str, is_background: bool = False):
        """Draw hexagonal room with holographic styling"""
        radius = size[0] // 2
        
        # Calculate hexagon points
        points = []
        for i in range(6):
            angle = i * math.pi / 3
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))
        
        # Glow effect
        for width in range(3, 0, -1):
            alpha = int(255 * (width / 3) * 0.7)
            glow_color = color + f"{alpha:02x}" if len(color) == 7 else color
            draw.polygon(points, outline=glow_color, width=width)
        
        # Main hexagon
        draw.polygon(points, outline=color, width=2)
        
        # Center and radial lines
        draw.ellipse([x-2, y-2, x+2, y+2], fill=self.colors['primary_cyan'])
        for px, py in points:
            draw.line([(x, y), (px, py)], fill=self.colors['cyan_dark'], width=1)
        
        # Room label
        self._draw_holographic_text(draw, x, y, name, self.colors['text_primary'])
    
    def _draw_octagonal_room(self, draw: ImageDraw.ImageDraw, x: int, y: int, 
                           size: Tuple[int, int], color: str, name: str, is_background: bool = False):
        """Draw octagonal room with holographic styling"""
        radius = size[0] // 2
        
        # Calculate octagon points
        points = []
        for i in range(8):
            angle = i * math.pi / 4
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))
        
        # Glow effect
        for width in range(3, 0, -1):
            alpha = int(255 * (width / 3) * 0.7)
            glow_color = color + f"{alpha:02x}" if len(color) == 7 else color
            draw.polygon(points, outline=glow_color, width=width)
        
        # Main octagon
        draw.polygon(points, outline=color, width=2)
        
        # Room label
        self._draw_holographic_text(draw, x, y, name, self.colors['text_primary'])
    
    def _add_room_internals(self, draw: ImageDraw.ImageDraw, left: int, top: int, 
                          width: int, height: int, color: str):
        """Add internal details to larger rooms"""
        # Add some technical elements inside the room
        center_x = left + width // 2
        center_y = top + height // 2
        
        # Internal grid pattern
        if width > 100 and height > 80:
            for x in range(left + 20, left + width - 20, 20):
                draw.line([(x, top + 10), (x, top + height - 10)], 
                         fill=self.colors['cyan_dark'], width=1)
            for y in range(top + 20, top + height - 20, 20):
                draw.line([(left + 10, y), (left + width - 10, y)], 
                         fill=self.colors['cyan_dark'], width=1)
        
        # Equipment markers
        if width > 80 and height > 60:
            equipment_positions = [
                (left + 15, top + 15),
                (left + width - 15, top + 15),
                (left + 15, top + height - 15),
                (left + width - 15, top + height - 15)
            ]
            
            for ex, ey in equipment_positions:
                draw.rectangle([ex-3, ey-3, ex+3, ey+3], 
                              fill=self.colors['glow_soft'], outline=color, width=1)
    
    def _draw_holographic_text(self, draw: ImageDraw.ImageDraw, x: int, y: int, 
                             text: str, color: str, font_size: int = 12):
        """Draw holographic-styled text with glow effect"""
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Text with glow effect
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = x - text_width // 2
        text_y = y - text_height // 2
        
        # Glow effect
        for offset in [(1, 1), (-1, -1), (1, -1), (-1, 1), (0, 1), (0, -1), (1, 0), (-1, 0)]:
            draw.text((text_x + offset[0], text_y + offset[1]), text, 
                     fill=self.colors['background'], font=font)
        
        # Main text
        draw.text((text_x, text_y), text, fill=color, font=font)
    
    def _apply_holographic_effects(self, image: Image.Image) -> Image.Image:
        """Apply holographic visual effects to the image"""
        # Create a slight blur for glow effect
        glow_image = image.filter(ImageFilter.GaussianBlur(radius=1))
        
        # Blend original with glow
        blended = Image.blend(image, glow_image, 0.3)
        
        return blended
    
    def _draw_technical_annotations(self, image: Image.Image, location_data: Dict, graph: nx.Graph):
        """Draw technical annotations and facility information"""
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        try:
            title_font = ImageFont.truetype("arial.ttf", 24)
            subtitle_font = ImageFont.truetype("arial.ttf", 14)
            small_font = ImageFont.truetype("arial.ttf", 10)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Title header
        title_text = f"FACILITY BLUEPRINT - {location_data['name'].upper()}"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        
        # Header background
        header_height = 60
        draw.rectangle([0, 0, width, header_height], 
                      fill=self.colors['background_deep'], 
                      outline=self.colors['primary_cyan'], width=2)
        
        # Title
        draw.text(((width - title_width) // 2, 10), title_text, 
                 fill=self.colors['text_highlight'], font=title_font)
        
        # Subtitle with specs - highlight faction information
        faction = location_data.get('faction', 'Independent')
        is_derelict = location_data.get('is_derelict', False)
        
        # Base specifications
        specs = f"TYPE: {location_data['location_type'].upper()} | POP: {location_data['population']:,} | WEALTH: {location_data['wealth_level']}"
        
        # Add faction with color coding
        faction_text = ""
        faction_color = self.colors['text_secondary']
        
        if is_derelict:
            faction_text = " | STATUS: DERELICT/ABANDONED"
            faction_color = self.colors['cyan_glow']  # Corrupted green for derelict
        elif faction and faction != 'Independent':
            faction_text = f" | FACTION: {faction.upper()}"
            # Use faction-specific colors
            if faction.lower() == 'loyalist':
                faction_color = self.colors['glow_bright']  # Federal white
            elif faction.lower() == 'outlaw':
                faction_color = self.colors['glow_bright']  # Outlaw orange
            else:
                faction_color = self.colors['primary_cyan']  # Default cyan
        else:
            faction_text = " | FACTION: INDEPENDENT"
            faction_color = self.colors['text_secondary']
        
        # Draw base specs
        spec_bbox = draw.textbbox((0, 0), specs, font=subtitle_font)
        spec_width = spec_bbox[2] - spec_bbox[0]
        draw.text(((width - spec_width) // 2, 35), specs, 
                 fill=self.colors['text_secondary'], font=subtitle_font)
        
        # Draw faction information with appropriate color (smaller text)
        faction_bbox = draw.textbbox((0, 0), faction_text, font=small_font)
        faction_width = faction_bbox[2] - faction_bbox[0]
        faction_x = (width + spec_width) // 2  # Position after the base specs
        draw.text((faction_x, 37), faction_text, 
                 fill=faction_color, font=small_font)
        
        # Generate improved room legend
        self.draw_improved_legend(draw, width, height, graph, location_data, 
                                subtitle_font, small_font)
        
        # Scale indicator
        scale_text = "SCALE: 1 UNIT = 20 PIXELS | GRID: 100PX MAJOR"
        draw.text((10, height - 20), scale_text, 
                 fill=self.colors['text_annotation'], font=small_font)
        
        # Timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y.%m.%d %H:%M")
        draw.text((10, height - 35), f"GENERATED: {timestamp}", 
                 fill=self.colors['text_annotation'], font=small_font)
    
    def draw_improved_legend(self, draw, width: int, height: int, graph, location_data: Dict, 
                           subtitle_font, small_font):
        """Draw an improved, dynamically-sized legend that handles text overflow properly"""
        
        # Prepare room data
        actual_sub_locations = []
        background_rooms = []
        
        for node_name, node_data in graph.nodes(data=True):
            if node_data.get('visible', True):
                # Check if this is a background room
                is_background_room = ('_bg_' in node_name or 
                                    node_data.get('is_background', False) or
                                    node_name in ['central_plaza', 'central_hub', 'main_terminal', 
                                                 'entrance_airlock', 'docking_pad', 'main_spine', 'main_corridor'])
                
                if is_background_room:
                    background_rooms.append((node_name, node_data))
                else:
                    actual_sub_locations.append((node_name, node_data))
        
        # Calculate required dimensions
        max_text_width = 0
        line_height = 12
        y_needed = 25  # Header space
        
        # Faction status line
        faction = location_data.get('faction', 'Independent')
        is_derelict = location_data.get('is_derelict', False)
        y_needed += 20
        
        # Sub-locations section
        if actual_sub_locations:
            y_needed += 18  # Section header
            display_count = min(8, len(actual_sub_locations))  # Show more items
            y_needed += display_count * line_height
            
            # Calculate max text width for sub-locations
            for i, (node_name, node_data) in enumerate(actual_sub_locations[:display_count]):
                room_name = self.truncate_text(node_data['name'], 18)
                room_type = node_data['room_type'].upper()[:8] 
                text = f"⬥ {room_name} - {room_type}"
                bbox = draw.textbbox((0, 0), text, font=small_font)
                text_width = bbox[2] - bbox[0]
                max_text_width = max(max_text_width, text_width + 30)  # +30 for color indicator
        
        # Background rooms section  
        if background_rooms and len(actual_sub_locations) < 8:
            remaining_space = 8 - len(actual_sub_locations)
            if remaining_space > 0:
                y_needed += 18  # Section header
                display_count = min(remaining_space, len(background_rooms))
                y_needed += display_count * 10  # Smaller spacing for background
                
                # Calculate max text width for background rooms
                for i, (node_name, node_data) in enumerate(background_rooms[:display_count]):
                    room_name = self.truncate_text(node_data['name'], 15)
                    room_type = node_data['room_type'].upper()[:6]
                    text = f"• {room_name} - {room_type}"
                    bbox = draw.textbbox((0, 0), text, font=small_font)
                    text_width = bbox[2] - bbox[0]
                    max_text_width = max(max_text_width, text_width + 25)
        
        # Set legend dimensions with proper margins
        legend_width = max(200, max_text_width + 20)  # Minimum 200px, expand as needed
        legend_height = max(130, y_needed + 15)  # Minimum 130px, expand as needed
        
        # Position legend (right side, but ensure it fits)
        legend_x = max(20, width - legend_width - 20)  # Leave 20px margin from edge
        legend_y = max(20, height - legend_height - 50)  # Leave space for scale/timestamp
        
        # Draw legend background
        draw.rectangle([legend_x, legend_y, legend_x + legend_width, legend_y + legend_height],
                      fill=self.colors['background_deep'], 
                      outline=self.colors['primary_cyan'], width=2)
        
        # Legend header
        legend_header = "ROOM DIRECTORY"
        draw.text((legend_x + 10, legend_y + 5), legend_header, 
                 fill=self.colors['text_highlight'], font=subtitle_font)
        
        # Faction status
        y_offset = 22
        faction_status, status_color = self.get_faction_status_info(faction, is_derelict)
        draw.text((legend_x + 10, legend_y + y_offset), faction_status, 
                 fill=status_color, font=small_font)
        y_offset += 20
        
        # Display actual sub-locations
        if actual_sub_locations:
            draw.text((legend_x + 10, legend_y + y_offset), "ACTIVE SUB-LOCATIONS:", 
                     fill=self.colors['text_highlight'], font=small_font)
            y_offset += 15
            
            for i, (node_name, node_data) in enumerate(actual_sub_locations[:8]):
                room_name = self.truncate_text(node_data['name'], 18)
                room_type = node_data['room_type'].upper()[:8]
                
                # Color indicator with bright border
                color_key = self.room_colors.get(node_data['room_type'], 'special')
                room_color = self.colors[color_key]
                
                # Draw bright border around indicators
                draw.rectangle([legend_x + 8, legend_y + y_offset - 2, 
                               legend_x + 17, legend_y + y_offset + 10], 
                              outline=self.colors['glow_bright'], width=1)
                draw.rectangle([legend_x + 10, legend_y + y_offset, 
                               legend_x + 15, legend_y + y_offset + 8], 
                              fill=room_color)
                
                # Room text (ensure it fits within legend width)
                entry_text = f"⬥ {room_name} - {room_type}"
                self.draw_fitted_text(draw, legend_x + 22, legend_y + y_offset, entry_text,
                                    legend_width - 32, self.colors['text_highlight'], small_font)
                
                y_offset += line_height
        
        # Display background facility rooms if space available
        if background_rooms and len(actual_sub_locations) < 8:
            remaining_space = 8 - len(actual_sub_locations)
            if remaining_space > 0:
                draw.text((legend_x + 10, legend_y + y_offset), "FACILITY SYSTEMS:", 
                         fill=self.colors['text_secondary'], font=small_font)
                y_offset += 15
                
                for i, (node_name, node_data) in enumerate(background_rooms[:remaining_space]):
                    room_name = self.truncate_text(node_data['name'], 15)
                    room_type = node_data['room_type'].upper()[:6]
                    
                    # Dimmed color indicator
                    color_key = self.room_colors.get(node_data['room_type'], 'special')
                    room_color = self.colors[color_key]
                    
                    # Convert to dimmer version
                    if room_color.startswith('#'):
                        r, g, b = int(room_color[1:3], 16), int(room_color[3:5], 16), int(room_color[5:7], 16)
                        r, g, b = int(r * 0.5), int(g * 0.5), int(b * 0.5)
                        room_color = f"#{r:02x}{g:02x}{b:02x}"
                    
                    draw.rectangle([legend_x + 10, legend_y + y_offset, 
                                   legend_x + 15, legend_y + y_offset + 8], 
                                  fill=room_color)
                    
                    # Room text
                    entry_text = f"• {room_name} - {room_type}"
                    self.draw_fitted_text(draw, legend_x + 20, legend_y + y_offset, entry_text,
                                        legend_width - 30, self.colors['text_annotation'], small_font)
                    
                    y_offset += 10
    
    def truncate_text(self, text: str, max_length: int) -> str:
        """Intelligently truncate text while preserving readability"""
        if len(text) <= max_length:
            return text
        
        # Try to break at word boundaries
        if ' ' in text and max_length > 8:
            words = text.split()
            result = words[0]
            for word in words[1:]:
                if len(result + ' ' + word) <= max_length - 3:  # Leave space for "..."
                    result += ' ' + word
                else:
                    break
            return result + "..." if len(result) < len(text) else result
        
        # Fallback to simple truncation
        return text[:max_length-3] + "..." if len(text) > max_length else text
    
    def get_faction_status_info(self, faction: str, is_derelict: bool) -> tuple:
        """Get faction status text and color"""
        if is_derelict:
            return "⚠ Derelict", self.colors['cyan_glow']
        elif faction and faction != 'Independent':
            faction_emoji = "●" if faction.lower() == 'loyalist' else "●" if faction.lower() == 'outlaw' else "●"
            return f"{faction_emoji} {faction.title()}", self.colors['primary_cyan']
        else:
            return "◦ Independent", self.colors['text_annotation']
    
    def draw_fitted_text(self, draw, x: int, y: int, text: str, max_width: int, color, font):
        """Draw text that fits within the specified width, truncating if necessary"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            draw.text((x, y), text, fill=color, font=font)
        else:
            # Truncate text to fit
            truncated = text
            while truncated:
                bbox = draw.textbbox((0, 0), truncated, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    break
                truncated = truncated[:-1]
            
            if len(truncated) < len(text) - 3:
                truncated = truncated[:-3] + "..."
            
            draw.text((x, y), truncated, fill=color, font=font)
    
    def generate_holographic_floormap(self, location_id: int) -> Optional[str]:
        """
        Generate a holographic blueprint-style floormap for the given location
        Returns the file path, or None if location not found
        """
        # Check cache first
        cached_path = self.load_cached_floormap(location_id)
        if cached_path:
            return cached_path
        
        # Get location data
        location_data = self.get_location_data(location_id)
        if not location_data:
            return None
        
        # Apply faction-specific color scheme
        self.apply_faction_color_scheme(location_data)
        
        # Get sub-locations
        sub_locations = self.get_sub_locations(location_id)
        print(f"DEBUG: Found {len(sub_locations)} sub-locations for location {location_id}")
        for sub_loc in sub_locations:
            print(f"  - {sub_loc['name']} ({sub_loc['type']})")
        
        # Generate layout graph
        try:
            graph = self.generate_layout_graph(location_data['location_type'], 
                                             sub_locations, location_data)
            print(f"DEBUG: Generated graph with {len(graph.nodes)} nodes")
        except Exception as e:
            print(f"ERROR in generate_layout_graph: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Determine image size based on location type, complexity, and population
        location_type = location_data['location_type']
        population = location_data['population']
        wealth = location_data['wealth_level']
        room_count = len(graph.nodes)
        
        # Calculate the actual bounds of all rooms in the layout first
        layout_bounds = self._calculate_layout_bounds(graph)
        layout_width = layout_bounds['max_x'] - layout_bounds['min_x']
        layout_height = layout_bounds['max_y'] - layout_bounds['min_y']
        
        # Calculate dynamic sizing factors - improved scaling for larger populations
        population_factor = min(4.0, 1.0 + (population / 50))  # Scale up to 4.0x for large populations (improved from /100)
        wealth_factor = min(1.5, 1.0 + (wealth / 10))  # Scale up to 1.5x for wealthy locations  
        complexity_factor = min(2.0, 1.0 + (room_count / 15))  # Scale up to 2.0x for complex layouts
        
        # Special scaling for very large space stations
        if location_type == 'space_station' and population >= 1500:
            population_factor = min(5.0, population_factor * 1.3)  # Extra boost for major stations
        
        # Calculate content-based dimensions with appropriate padding
        content_padding = 200  # Base padding around content
        
        # Add additional padding based on location type and scale factors
        type_padding_multipliers = {
            'colony': 1.4,
            'space_station': 1.6, 
            'gate': 1.0,
            'outpost': 0.8,
            'ship': 0.9
        }
        
        padding_multiplier = type_padding_multipliers.get(location_type, 1.0)
        total_scale = population_factor * wealth_factor * complexity_factor
        
        # Calculate final padding
        final_padding = int(content_padding * padding_multiplier * min(total_scale, 2.0))
        
        # Calculate canvas size based on actual content size plus padding
        width = int(layout_width + final_padding * 2)
        height = int(layout_height + final_padding * 2)
        
        # Ensure reasonable limits
        sub_location_count = len([room for room in graph.nodes() if not graph.nodes[room].get('is_background', False)])
        min_width = max(800, sub_location_count * 60)  # Reduced minimum scaling for better fit
        min_height = max(600, sub_location_count * 45)  # Reduced minimum scaling for better fit
        
        width = min(max(width, min_width), 3000)   # Between calculated minimum and 3000px
        height = min(max(height, min_height), 2500)  # Between calculated minimum and 2500px
        
        # Center the layout in the canvas
        self._center_layout_in_canvas(graph, layout_bounds, width, height)
        
        # Create holographic image
        image = self.create_holographic_image(width, height, location_data, graph)
        
        # Save the floormap
        filepath = self.get_floormap_path(location_data['location_id'])
        image.save(filepath, 'PNG', quality=95)
        
        return filepath