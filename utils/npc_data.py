# utils/npc_data.py
import random
from typing import List, Dict, Tuple

# NPC Name Lists
FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn", "Blake", "Cameron",
    "Sage", "River", "Phoenix", "Rowan", "Kai", "Skylar", "Emery", "Dakota", "Charlie", "Finley",
    "Zara", "Vera", "Nova", "Luna", "Iris", "Vale", "Wren", "Sage", "Echo", "Raven",
    "Marcus", "Elena", "Viktor", "Anya", "Dmitri", "Katya", "Yuki", "Kenji", "Akira", "Sato",
    "Chen", "Wei", "Mei", "Jin", "Raj", "Priya", "Dev", "Nala", "Zain", "Layla",
    "Omar", "Fatima", "Hassan", "Amara", "Kofi", "Nia", "Kwame", "Adah", "Lars", "Astrid",
    "Erik", "Ingrid", "Soren", "Freya", "Kai", "Nora", "Finn", "Saga", "Cruz", "Diego",
    "Carmen", "Sofia", "Mateo", "Lucia", "Ezra", "Thea", "Arlo", "Zoe", "Milo", "Cora"
]

LAST_NAMES = [
    "Vega", "Cross", "Stone", "Vale", "West", "Kane", "Grey", "Sharp", "Swift", "Black",
    "White", "Steel", "Storm", "Frost", "Burns", "Reed", "Fox", "Wolf", "Hawk", "Raven",
    "Chen", "Zhang", "Wang", "Li", "Liu", "Yang", "Zhao", "Wu", "Zhou", "Xu",
    "Petrov", "Volkov", "Sokolov", "Popov", "Morozov", "Vasiliev", "Fedorov", "Mikhailov",
    "Tanaka", "Suzuki", "Watanabe", "Ito", "Yamamoto", "Nakamura", "Kobayashi", "Saito",
    "Singh", "Patel", "Kumar", "Sharma", "Gupta", "Verma", "Agarwal", "Jain",
    "Hassan", "Ahmed", "Ali", "Omar", "Said", "Ibrahim", "Mahmoud", "Youssef",
    "Okonkwo", "Adeola", "Chike", "Amara", "Kwaku", "Asante", "Nkomo", "Banda",
    "Larsen", "Hansen", "Nielsen", "Andersen", "Petersen", "Kristensen", "Rasmussen",
    "Rodriguez", "Martinez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres"
]

SHIP_PREFIXES = [
    "Stellar", "Cosmic", "Void", "Nova", "Nebula", "Solar", "Lunar", "Astro", "Quantum", "Plasma",
    "Iron", "Steel", "Titanium", "Crystal", "Diamond", "Golden", "Silver", "Copper", "Neon",
    "Swift", "Fast", "Quick", "Rapid", "Lightning", "Thunder", "Storm", "Wind", "Gale",
    "Free", "Wild", "Brave", "Bold", "Fierce", "Strong", "Mighty", "Grand", "Royal", "Noble"
]

SHIP_SUFFIXES = [
    "Runner", "Trader", "Wanderer", "Explorer", "Pioneer", "Voyager", "Drifter", "Nomad",
    "Wing", "Blade", "Arrow", "Spear", "Lance", "Sword", "Shield", "Guard", "Defender",
    "Star", "Comet", "Meteor", "Eclipse", "Dawn", "Dusk", "Horizon", "Beacon", "Light",
    "Dream", "Hope", "Fortune", "Destiny", "Journey", "Quest", "Adventure", "Discovery"
]

SHIP_TYPES = [
    "Light Freighter", "Heavy Freighter", "Cargo Hauler", "Survey Vessel", "Scout Ship",
    "Mining Vessel", "Research Ship", "Transport", "Courier", "Patrol Craft"
]

# Dynamic NPC Radio Messages
RADIO_MESSAGES = [
    # Navigation and travel
    "This is {callsign}, approaching {location} for scheduled docking.",
    "{callsign} to any station, requesting updated navigation data for the {system} system.",
    "Transit Control, this is {callsign} reporting successful corridor transit to {location}.",
    "{callsign} here, experiencing minor navigation drift. Recalibrating course to {location}.",
    "Any vessels near {location}? This is {callsign}, could use an updated traffic report.",
    
    # Trade and business
    "Commercial traffic, this is {callsign} with cargo manifest for {location}. ETA fifteen minutes.",
    "{callsign} calling {location} Station, requesting priority docking for time-sensitive cargo.",
    "This is Captain {name} aboard {ship}, seeking trade opportunities at {location}.",
    "{callsign} to merchant vessels, anyone interested in bulk cargo exchange at {location}?",
    "Trading stop setup! {callsign} offering competitive rates on manufactured goods.",
    
    # Social and casual
    "Good morning spacerfarers! {callsign} broadcasting from {location}. Beautiful view of {system} today.",
    "{callsign} here, taking a break at {location}. Great fuel prices and decent food!",
    "This is {callsign}, just wanted to say the staff at {location} are incredibly helpful.",
    "Any familiar voices out there? {callsign} getting lonely on these long hauls.",
    "Captain {name} logging off for rest cycle. {callsign} will be monitoring emergency frequencies.",
    
    # Technical and maintenance
    "{callsign} requesting mechanic availability at {location}. Minor engine calibration needed.",
    "This is {callsign}, completed system diagnostics. All green across the board.",
    "{callsign} to technical services, seeking recommendation for fuel injector replacement.",
    "Engineering check complete! {callsign} ready for next sector transit.",
    "This is {callsign}, anyone else experiencing minor comm static in the {system} system?",
    
    # Weather and conditions
    "{callsign} reporting clear space lanes between {location} and nearby systems.",
    "Solar activity elevated in {system}. This is {callsign} advising caution for sensitive cargo.",
    "{callsign} here, corridor conditions nominal for next six hours. Safe travels everyone.",
    "This is {callsign}, minor electromagnetic interference detected near {location}.",
    
    # Emergency and assistance
    "{callsign} standing by on emergency frequencies while docked at {location}.",
    "This is {callsign}, offering assistance to any vessels experiencing navigation difficulties.",
    "{callsign} to all ships, maintain safe following distance in {system} space lanes.",
    "Captain {name} aboard {callsign}, monitoring distress frequencies during rest stop.",
    
    # Personal and flavor
    "This is {callsign}, celebrating another successful trade run! Round of drinks on me at {location}!",
    "{callsign} here, family sends their regards from the Core Worlds. Missing home today.",
    "Captain {name} logging personal note: {location} has the best coffee in three systems.",
    "{callsign} to old friends, still flying the trade routes. Hope to cross paths again soon.",
    "This is {callsign}, teaching the new crew member about proper radio etiquette. Wave hello everyone!",
    
    "This is {callsign} to anyone on this frequency... My nav-computer is cycling, showing a corridor that shouldn't be here. Is... is anyone else seeing this?",
    "{callsign} requesting updated corridor stability data. My last chart is three cycles old and I don't trust it. Anything more recent would be appreciated.",
    "This is {callsign}, making my approach to {location}. Looks like another one of your docking lights is out. You guys should really get that fixed before someone clips the bay.",
    "{callsign} here. If anyone's docked at {location} and has a compatible power socket, I'd trade a week's worth of rations for a few hours of charge.",
    "This is {name} signing off for a sleep cycle. The silence out here... it gets to you. Stay sane, everyone.",
    "{callsign} reporting heavy static fog building near {location}. Visibility is near zero. I'm going to hold my position until it clears."
    "Mayday, Mayday, Mayday. This is {callsign}. Hull breach in sector... ... Life support failing. Anyone... .",
    "To any vessel on this frequency, this is {ship}. Our navigator is dead—radiation exposure. We are flying blind. We don't know where this corridor will exit. Requesting... requesting any navigational assistance. Please.",
    "We have a confirmed Vacuum Bloom outbreak in the cargo bay. We've sealed the doors, but the air smells sweet... rotten. We're requesting immediate decontamination protocols at {location}, assuming we make it that far.",
    "My Geiger counter is screaming. The radiation in this corridor is off the charts. The hull is groaning... I think the shielding is failing. It's getting hot in here.",
    "This is {callsign}. We're low on fuel, but we picked up a refugee pod. They're out of food and water. We don't have enough for everyone. I have to make a choice. I... I don't know what to do.",
    "My contract at {location} was terminated. No pay. I'm out of fuel and options. I'll take any work. Anything. Please.",
    "Reporting from {location}: Disease outbreak contained, but medical supplies are critically low. Send doctors or diagnostics. This is {callsign} signing off.",
    "This is {callsign}, reports of unexpected Corridor collapse near the old {system} jump point. Verify your navigation data twice before jumping.",
    "Witnessed a ship vanish mid-transit. Just... gone. This is {callsign} still shaking from the sight. Corridors are a fickle mistress.",
    "Days blur into weeks out here. This is {callsign}, just a voice in the dark. Anyone else feel it? The quiet end.",
    "Overheard some disturbing chatter from a pilot who spent too long in a storm. Mentioned 'voices in the static'."
    "Emergency broadcast: This is {callsign}, my ship is adrift. Power failing. I'm dumping all non-essentials. If you hear explosions, it's just my life savings going out the airlock. Farewell."
]

# Location-specific actions for dynamic NPCs
LOCATION_ACTIONS = {
    'colony': [
        "{name} haggles with local farmers over agricultural exports.",
        "{name} visits the colonial administration office to update shipping permits.",
        "{name} samples local cuisine at a popular restaurant.",
        "{name} attends a community gathering to learn about local news.",
        "{name} inspects warehouses for potential cargo opportunities.",
        "{name} negotiates with colony officials about bulk supply contracts.",
        "{name} takes a tour of the manufacturing facilities.",
        "{name} meets with local merchants to discuss trade partnerships."
    ],
    'space_station': [
        "{name} refuels the {ship} at the station's fuel depot.",
        "{name} browses the station's market for rare components.",
        "{name} enjoys a drink at the station bar, sharing travel stories.",
        "{name} conducts routine maintenance checks on the {ship}.",
        "{name} updates navigation charts at the station's data terminal.",
        "{name} negotiates docking fees with station administration.",
        "{name} attends a trader's meeting in the station's conference room.",
        "{name} gets a medical checkup at the station's clinic."
    ],
    'outpost': [
        "{name} refills water reserves and checks emergency supplies.",
        "{name} transmits a status report to distant corporate headquarters.",
        "{name} performs essential repairs using outpost facilities.",
        "{name} shares news from other systems with outpost personnel.",
        "{name} reviews star charts with the outpost navigator.",
        "{name} restocks provisions for the next leg of the journey.",
        "{name} uploads system telemetry data to the outpost computers.",
        "{name} coordinates with outpost traffic control for departure clearance."
    ],
    'gate': [
        "{name} submits corridor transit applications to gate control.",
        "{name} pays transit fees and updates travel documentation.",
        "{name} waits in the transit queue, monitoring gate status.",
        "{name} performs pre-transit safety checks on the {ship}.",
        "{name} reviews destination information at the gate's data kiosk.",
        "{name} coordinates with other vessels for convoy transit."
        
    ]
}

# Static NPC occupations based on location type and wealth
OCCUPATIONS = {
    'colony': {
        'low_wealth': ["Farmer", "Laborer", "Maintenance Worker", "Security Guard", "Shop Clerk"],
        'mid_wealth': ["Engineer", "Teacher", "Medic", "Administrator", "Merchant", "Technician"],
        'high_wealth': ["Research Director", "Corporate Executive", "Master Engineer", "Colony Administrator", "Trade Coordinator"]
    },
    'space_station': {
        'low_wealth': ["Dock Worker", "Janitor", "Security Officer", "Food Service", "Cargo Handler"],
        'mid_wealth': ["Flight Controller", "Systems Analyst", "Medical Officer", "Quartermaster", "Communications Specialist"],
        'high_wealth': ["Station Commander", "Chief Engineer", "Corporate Liaison", "Diplomatic Attaché", "Trade Commission Director"]
    },
    'outpost': {
        'low_wealth': ["Monitor Technician", "Supply Clerk", "Maintenance Specialist"],
        'mid_wealth': ["Outpost Manager", "Communications Officer", "Safety Coordinator"],
        'high_wealth': ["Sector Coordinator", "Research Supervisor", "Strategic Operations Director"]
    },
    'gate': {
        'low_wealth': ["Transit Operator", "Gate Technician", "Traffic Monitor"],
        'mid_wealth': ["Gate Supervisor", "Transit Coordinator", "Systems Engineer"], 
        'high_wealth': ["Gate Commander", "Network Administrator", "Corridor Operations Director"]
    }
}

PERSONALITIES = [
    "Friendly and talkative", "Quiet and reserved", "Experienced and wise", "Young and enthusiastic",
    "Gruff but helpful", "Mysterious and cryptic", "Cheerful and optimistic", "Cynical but honest",
    "Professional and efficient", "Eccentric and quirky", "Cautious and careful", "Bold and adventurous"
]

TRADE_SPECIALTIES = [
    "Rare minerals", "Technical components", "Cultural artifacts", "Medical supplies", "Information",
    "Luxury goods", "Industrial equipment", "Exotic materials", "Historical items", "Contraband"
]

def generate_npc_name() -> Tuple[str, str]:
    """Generate a random first and last name for an NPC"""
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

def generate_ship_name() -> str:
    """Generate a random ship name"""
    return f"{random.choice(SHIP_PREFIXES)} {random.choice(SHIP_SUFFIXES)}"

def get_random_radio_message() -> str:
    """Get a random radio message template"""
    return random.choice(RADIO_MESSAGES)

def get_location_action(location_type: str) -> str:
    """Get a random action appropriate for the location type"""
    actions = LOCATION_ACTIONS.get(location_type, LOCATION_ACTIONS['outpost'])
    return random.choice(actions)

def get_occupation(location_type: str, wealth_level: int) -> str:
    """Get an appropriate occupation based on location type and wealth"""
    occupations = OCCUPATIONS.get(location_type, OCCUPATIONS['outpost'])
    
    if wealth_level <= 3:
        wealth_category = 'low_wealth'
    elif wealth_level <= 7:
        wealth_category = 'mid_wealth'
    else:
        wealth_category = 'high_wealth'
    
    return random.choice(occupations[wealth_category])