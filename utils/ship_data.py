# utils/ship_data.py
import random
STARTER_SHIP_CLASSES = {
    "Hauler": {
        "exterior": [
            "A squat, heavy-duty hauler with modular cargo pods welded on at odd angles. Faded hazard stripes mark the hull edges.",
            "This workhorse freighter sports a battered nose cone and mismatched panels scavenged from sister ships.",
            "A utilitarian bulk carrier with visible patch welds running along its cargo bay doors. One engine nacelle rattles slightly on idle.",
            "A tired old hauler bristling with external tie-down points and half-faded registry markings. A maintenance drone is parked on its dorsal spine.",
            "A blocky freight mover with a huge belly clamp rig for oversized loads. Layers of old company logos peel off around the airlock hatch."
        ],
        "interior": [
            "Steel deck plating creaks underfoot. A battered cargo loader sits idle near the bay door, surrounded by coiled tie-down straps.",
            "The crew corridor smells faintly of machine oil. A single faded sticker reading 'KEEP CLOSED' peels off the main access hatch.",
            "Half the cargo hold is partitioned with netting and old shipping crates doubling as tables and benches.",
            "The galley consists of a dented hotplate and a magnetic mug rack screwed to the bulkhead. The hum of the power core is constant.",
            "Bunks line the wall opposite a row of battered cargo lockers. A single flickering strip light struggles to keep the space lit."
        ]
    },
    "Scout": {
        "exterior": [
            "A slim, angular scout with an extended sensor boom and an asymmetrical dorsal fin housing extra comms gear.",
            "A lightly armored recon ship, hull pitted from micro impacts. A faded mission tally is stenciled under the cockpit.",
            "A compact long-range scout with engine vents bristling with extra shielding. A painted logo of a howling wolf is visible near the nose.",
            "A vintage survey vessel upgraded with bolt-on thruster pods and a small external drone cradle under the keel.",
            "A recon skiff with a stubby nose cone and a retractable sensor mast folded tight along its spine."
        ],
        "interior": [
            "The cockpit doubles as living quarters, cluttered with star charts, thermal blankets, and half-finished protein bars.",
            "A bank of modular displays flickers softly. A single pilot’s couch faces a broad viewport scratched by years of debris hits.",
            "Stacks of data cartridges and sample canisters are bungee-corded to the bulkhead for quick access.",
            "The narrow passage to the sleeping berth is lined with spools of cabling and spare fuses taped to the wall.",
            "An old insulated thermos floats near the navigation console, wedged between a cracked comms panel and a battered control stick."
        ]
    },
    "Courier": {
        "exterior": [
            "A sleek courier skiff with smoothed-over seams for minimal drag and oversized engine vents for sudden boosts.",
            "A decommissioned corporate runner with residual branding ghosting through its fresh matte-black paint.",
            "An arrowhead-shaped data courier with reinforced aft plating and a discreet heat signature diffuser bolted to the tail.",
            "This express ship shows field modifications — extra maneuvering thrusters and jury-rigged armor plating over key conduits.",
            "A nimble courier with a long, narrow hull and a blunt nosecone optimized for rapid gate jumps."
        ],
        "interior": [
            "The cockpit is all hard edges and tight spaces — padded crash webbing lines the pilot seat while a slim cargo pod clicks locked behind it.",
            "Rows of encryption nodes blink along a bulkhead beside a climate-controlled data vault just large enough for a single crate.",
            "A half-empty energy drink can floats by a sticker reading 'DON'T TOUCH — CAPTAIN'S'.",
            "Minimal bedding is rolled tight behind the seat; there's just enough room to stretch out during long transits.",
            "Thin insulation panels line the narrow corridor to the engine room, covered in scribbled maintenance notes and system readouts."
        ]
    },
    "Shuttle": {
        "exterior": [
            "A stubby commuter shuttle with retractable airfoils and multiple docking collars welded along its flanks.",
            "An old planetary ferry, retrofitted with extra fuel tanks strapped to its undercarriage and a pair of external tool lockers.",
            "A standard short-hop shuttle painted in mismatched livery panels from at least three prior operators.",
            "This shuttle’s side hatch is fitted with a makeshift ramp extension — clearly fabricated in some colony machine shop.",
            "A durable transfer shuttle with reinforced landing struts and an extendable cargo crane mounted near the aft airlock."
        ],
        "interior": [
            "Rows of old passenger seats have been replaced with modular jump seats bolted to deck rails for easy reconfiguration.",
            "An emergency kit rattles in its bracket by the main hatch, next to a cracked viewport half covered with duct tape.",
            "Folded blankets and old duffel bags are stowed above the rear seats where a small comms console hums quietly.",
            "Bright hazard striping marks the deck near the rear ramp, worn down by years of boots, crates, and tool carts.",
            "A battered maintenance locker rattles with spare parts, emergency breather masks, and an ancient first aid kit."
        ]
    }
}


SHIP_NAME_PARTS = {
    "adjectives": [
        "Stellar", "Orbital", "Solar", "Horizon", "Vector", "Atlas", "Pioneer", "Trailblazer", "Outbound",
        "Celestial", "Quantum", "Radiant", "Core", "Axial", "Forward", "Nova", "Prime", "Linear", "Transit",
        "Galactic", "Echo", "Modular", "Interim", "Baseline", "Nominal", "Standard", "Common", "Fleet",
        "Reliable", "Cargo", "Relay", "Circuit", "Pathfinder", "Waypoint", "Surveyor", "Utility",
        "Longrange", "Shorthaul", "Regional", "Terminal", "Dockside", "Starbound", "Deepfield", "Drift",
        "Luminous", "Polaris", "Vanguard", "Zenith", "Apex", "Orbiting", "Static", "Mobile", "Remote",
        "Proxima", "Polar", "Equatorial", "Kepler", "Farpoint", "Radial", "Inclined", "Incline", "Ascend",
        "Nomad", "Ranger", "Patrol", "Beacon", "Grid", "Nodal", "Array", "Cascade", "Pulse", "Spectral",
        "Phase", "Vectorial", "Infra", "Ultra", "Gamma", "Delta", "Beta", "Alpha", "Coreline", "Skyline",
        "Stratos", "Voidline", "Span", "Traverse", "Sector", "Module", "Unitary", "Chassis"
    ],

    "nouns": [
        "Courier", "Hauler", "Freighter", "Runner", "Carrier", "Relay", "Packet", "Array", "Hopper", "Vector",
        "Pioneer", "Orbiter", "Platform", "Liner", "Prowler", "Vessel", "Shuttle", "Clipper", "Module",
        "Beacon", "Transit", "Passage", "Galleon", "Horizon", "Outrider", "Surveyor", "Anchor", "Node",
        "Hub", "Depot", "Outpost", "Terminal", "Path", "Route", "Link", "Channel", "Circuit", "Axis",
        "Core", "Hull", "Frame", "Spur", "Grid", "Chain", "Relay", "Spoke", "Span", "Spanline", "Matrix",
        "Conduit", "Strut", "Brace", "Pylon", "Bridge", "Dock", "Port", "Platform", "Yard", "Depot",
        "Launch", "Array", "Sector", "Cell", "Unit", "Block", "Segment", "Strand", "Thread", "Cable",
        "Conveyor", "Lift", "Cargo", "Manifest", "Courier", "Manifest", "Manifestor", "Hauler", "Tram",
        "Transit", "Traverse", "Cradle", "Pod", "Capsule", "Gondola", "Bay", "Hold", "Spanner", "Rig",
        "Tug", "Tow", "Tender"
    ]
}


def generate_random_ship_name():
    """Generates a random ship name."""
    if random.random() > 0.5:
        return f"{random.choice(SHIP_NAME_PARTS['adjectives'])} {random.choice(SHIP_NAME_PARTS['nouns'])}"
    else:
        return f"The {random.choice(SHIP_NAME_PARTS['nouns'])}"

def get_random_starter_ship():
    """Returns a random ship type, name, and descriptions."""
    ship_type = random.choice(list(STARTER_SHIP_CLASSES.keys()))
    ship_name = generate_random_ship_name()
    exterior_desc = random.choice(STARTER_SHIP_CLASSES[ship_type]["exterior"])
    interior_desc = random.choice(STARTER_SHIP_CLASSES[ship_type]["interior"])
    return ship_type, ship_name, exterior_desc, interior_desc