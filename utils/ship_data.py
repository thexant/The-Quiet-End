# utils/ship_data.py
import random
import json

# Ship type definitions with tier classifications
SHIP_TYPES = {
    # Tier 1 - Basic Ships (Starting vessels)
    "Hauler": {
        "tier": 1,
        "class": "Cargo",
        "base_stats": {
            "cargo_capacity": 150,
            "speed_rating": 4,
            "combat_rating": 5,
            "fuel_efficiency": 7,
            "hull_strength": 100,
            "upgrade_slots": 3
        }
    },
    "Scout": {
        "tier": 1,
        "class": "Recon",
        "base_stats": {
            "cargo_capacity": 50,
            "speed_rating": 8,
            "combat_rating": 8,
            "fuel_efficiency": 9,
            "hull_strength": 80,
            "upgrade_slots": 3
        }
    },
    "Shuttle": {
        "tier": 1,
        "class": "Transport",
        "base_stats": {
            "cargo_capacity": 80,
            "speed_rating": 6,
            "combat_rating": 3,
            "fuel_efficiency": 8,
            "hull_strength": 90,
            "upgrade_slots": 3
        }
    },
    
    # Tier 2 - Improved Ships
    "Heavy Hauler": {
        "tier": 2,
        "class": "Bulk Cargo",
        "base_stats": {
            "cargo_capacity": 300,
            "speed_rating": 3,
            "combat_rating": 10,
            "fuel_efficiency": 5,
            "hull_strength": 150,
            "upgrade_slots": 4
        }
    },
    "Fast Courier": {
        "tier": 2,
        "class": "Express",
        "base_stats": {
            "cargo_capacity": 100,
            "speed_rating": 9,
            "combat_rating": 12,
            "fuel_efficiency": 7,
            "hull_strength": 90,
            "upgrade_slots": 4
        }
    },

    # Tier 3 - Specialized Ships
    "Armed Trader": {
        "tier": 3,
        "class": "Combat Merchant",
        "base_stats": {
            "cargo_capacity": 200,
            "speed_rating": 6,
            "combat_rating": 20,
            "fuel_efficiency": 6,
            "hull_strength": 120,
            "upgrade_slots": 5
        }
    },
    "Explorer": {
        "tier": 3,
        "class": "Long Range",
        "base_stats": {
            "cargo_capacity": 120,
            "speed_rating": 7,
            "combat_rating": 15,
            "fuel_efficiency": 10,
            "hull_strength": 110,
            "upgrade_slots": 5
        }
    },

    # Tier 4 - Advanced Ships
    "Blockade Runner": {
        "tier": 4,
        "class": "Stealth Cargo",
        "base_stats": {
            "cargo_capacity": 180,
            "speed_rating": 10,
            "combat_rating": 18,
            "fuel_efficiency": 8,
            "hull_strength": 140,
            "upgrade_slots": 6
        }
    },
    "Corvette": {
        "tier": 4,
        "class": "Light Warship",
        "base_stats": {
            "cargo_capacity": 100,
            "speed_rating": 8,
            "combat_rating": 30,
            "fuel_efficiency": 5,
            "hull_strength": 200,
            "upgrade_slots": 6
        }
    },

    # Tier 5 - Premium Ships
    "Luxury Yacht": {
        "tier": 5,
        "class": "Executive",
        "base_stats": {
            "cargo_capacity": 150,
            "speed_rating": 7,
            "combat_rating": 12,
            "fuel_efficiency": 6,
            "hull_strength": 180,
            "upgrade_slots": 7
        }
    },
    "Research Vessel": {
        "tier": 5,
        "class": "Science",
        "base_stats": {
            "cargo_capacity": 200,
            "speed_rating": 5,
            "combat_rating": 10,
            "fuel_efficiency": 8,
            "hull_strength": 160,
            "upgrade_slots": 7
        }
    }
}

# Ship descriptions - truncated format
# Ship descriptions - expanded format
# Ship descriptions - expanded format
SHIP_DESCRIPTIONS = {
    # Tier 1
    "Hauler": {
        "exterior": [
            "A squat, heavy-duty hauler with modular cargo pods bolted to its frame.",
            "Its hull is a patchwork of mismatched plates, hinting at countless repairs.",
            "The cockpit is a small, armored viewport on an otherwise windowless chassis.",
            "Numerous docking clamps and magnetic grapples adorn its outer hull.",
            "The engine assembly is massive and exposed, designed for power over grace."
        ],
        "interior": [
            "Steel deck plating creaks underfoot, worn smooth by years of use.",
            "The air smells of ozone, hydraulic fluid, and stale coffee.",
            "Bunks are little more than hammocks stuffed into alcoves in the wall.",
            "The main cargo bay is a cavernous, echoing space with a complex web of restraints.",
            "Warning labels and hastily-scrawled maintenance notes cover most surfaces."
        ]
    },
    "Scout": {
        "exterior": [
            "A sleek, arrow-headed ship with a panoramic cockpit.",
            "Its hull is covered in sensor arrays and communication dishes.",
            "The engines are oversized for its frame, promising extreme speed.",
            "Landing gear is minimal, designed for fast deployment and retrieval.",
            "The ship's profile is low and angular to minimize its sensor signature."
        ],
        "interior": [
            "The cockpit is dominated by holographic displays and sensor feeds.",
            "It's a cramped, two-person space designed for efficiency, not comfort.",
            "A small galley and sleeping pods are tucked away behind the main console.",
            "Wiring is exposed in neat bundles, allowing for easy field repairs.",
            "The air is cool and filtered, with the faint hum of advanced electronics."
        ]
    },
    "Shuttle": {
        "exterior": [
            "A boxy, functional design prioritizing passenger space over aesthetics.",
            "Large viewports run along both sides of the fuselage.",
            "Its paint scheme is simple and utilitarian, often bearing a transit authority logo.",
            "A wide, extendable ramp allows for easy boarding and disembarking.",
            "The docking collar is prominent and well-used, a focal point of its design."
        ],
        "interior": [
            "Rows of simple, durable plastic seats fill the main cabin.",
            "The floor is covered in a worn, non-slip material.",
            "Overhead compartments provide space for personal luggage.",
            "The cockpit is small and separated from the cabin by a simple bulkhead and door.",
            "The air has a faint, sterile scent of recycled air and cleaning agents."
        ]
    },
    # Tier 2
    "Heavy Hauler": {
        "exterior": [
            "A colossal, brutish vessel comprised mostly of external cargo scaffolding.",
            "Its paint is scarred and faded from atmospheric entries and micrometeoroid impacts.",
            "Dozens of running lights illuminate its massive frame to prevent collisions.",
            "The bridge is a heavily armored tower offering a commanding view of its surroundings.",
            "Four immense engine pods work in unison to propel its bulk through space."
        ],
        "interior": [
            "Long, brightly-lit corridors connect the various sections of the ship.",
            "The crew quarters are spartan but functional, built for a large, rotating crew.",
            "A dedicated workshop area is filled with tools and spare parts.",
            "The cargo management console looks more complex than the helm of a smaller ship.",
            "A low, constant vibration from the engines is a permanent feature of life aboard."
        ]
    },
    "Fast Courier": {
        "exterior": [
            "A narrow, aerodynamic frame built for speed and little else.",
            "The engine section makes up nearly half the ship's total mass.",
            "Its hull is smooth and displays the branding of a high-speed delivery service.",
            "Small, powerful maneuvering thrusters are placed all along the chassis for rapid adjustments.",
            "The cockpit is a bubble of reinforced glass fused seamlessly with the forward hull."
        ],
        "interior": [
            "The cockpit is a single, high-tech seat surrounded by controls and displays.",
            "There are no creature comforts; space is dedicated to the pilot and vital systems.",
            "Behind the cockpit is a small, secure cargo hold, just large enough for high-value parcels.",
            "A single fold-down bunk and a nutrient paste dispenser serve as the living quarters.",
            "The constant, high-pitched whine of an overclocked power core fills the small cabin."
        ]
    },
    # Tier 3
    "Armed Trader": {
        "exterior": [
            "The silhouette of a mid-size freighter, but with added, often aftermarket, armor plates.",
            "Retractable turret hardpoints are visible along its dorsal spine and ventral side.",
            "The bridge is more heavily armored than a standard hauler's.",
            "Scorch marks from near-misses often mar the paint near the weapon emplacements.",
            "The engines have been modified for slightly more power to compensate for the added mass."
        ],
        "interior": [
            "The cargo bay features reinforced walls and dedicated storage for munitions.",
            "Weapon maintenance stations are common sights in the engineering bay.",
            "The bridge has integrated tactical displays alongside the standard navigation and cargo manifests.",
            "Corridors are narrower than a typical freighter to allow for thicker hull reinforcement.",
            "There's a persistent smell of gun oil and ozone from the energy weapon capacitors."
        ]
    },
    "Explorer": {
        "exterior": [
            "Its hull is studded with a diverse array of sensor equipment and scanner dishes.",
            "A large, forward-facing panoramic viewport offers a commanding view for observation.",
            "It features oversized fuel tanks and a robust, efficient engine for long-duration travel.",
            "A versatile robotic arm is folded neatly against the hull, ready for sample collection.",
            "The landing gear is tall and wide-set, designed for stability on uneven, unknown terrain."
        ],
        "interior": [
            "The bridge is a combination of a pilot's station and a scientific analysis hub.",
            "A compact but well-equipped laboratory sits just behind the main cockpit.",
            "Living quarters are designed for long-term comfort, with a proper galley and recreation area.",
            "Storage is filled with scientific instruments, spare parts, and survey drones.",
            "The walls are lined with monitors displaying star charts and sensor data."
        ]
    },
    # Tier 4
    "Blockade Runner": {
        "exterior": [
            "A sleek, angular design with a hull made of matte-black, radar-absorbent materials.",
            "There are very few running lights, and those that exist are small and recessed.",
            "The engine exhausts are baffled and shielded to minimize its thermal signature.",
            "Its profile is flat and wide, designed to be difficult to detect from most angles.",
            "All weapon ports and docking hatches are flush with the hull to maintain its stealth profile."
        ],
        "interior": [
            "The lighting is exclusively low-intensity red or blue to preserve the crew's night vision.",
            "The bridge is focused on electronic warfare, sensor-ghosting, and silent running protocols.",
            "Hidden, shielded cargo bays are built directly into the ship's frame and are invisible to the eye.",
            "Hallways are narrow and lined with sound-dampening materials.",
            "The ship is eerily quiet, with the loudest sound being the hum of the life support system."
        ]
    },
    "Corvette": {
        "exterior": [
            "Its design is purely for combat, with an aggressive, predatory silhouette.",
            "The hull is thick with military-grade armor plating and bristles with weapon emplacements.",
            "Powerful combat thrusters give it exceptional agility for its size.",
            "It bears the stark insignia of a planetary navy or corporate security force.",
            "A spinal-mounted main gun runs much of the ship's length."
        ],
        "interior": [
            "Instead of a bridge, it has a Combat Information Center (CIC) deep within the hull.",
            "The corridors are bare metal, designed for utility and rapid damage control.",
            "Crew quarters are tight, efficient bunks known as 'hot racks'.",
            "The air is thick with the smell of recycled air, energy conduits, and hardworking machinery.",
            "Damage control lockers are located at every intersection."
        ]
    },
    # Tier 5
    "Luxury Yacht": {
        "exterior": [
            "A vision of elegance, with a gleaming white hull and sweeping, graceful curves.",
            "Large, tinted viewports offer stunning panoramic views of space.",
            "It features no visible weaponry or industrial equipment, prioritizing aesthetics.",
            "The engines are powerful but designed to be whisper-quiet, leaving only a faint shimmer.",
            "A retractable sun deck can be deployed when orbiting scenic worlds."
        ],
        "interior": [
            "The main cabin is an open-plan lounge with a fully stocked bar and plush seating.",
            "Floors are made of polished rare wood or high-end composites.",
            "Guest cabins are spacious suites, each with a private bathroom and viewport.",
            "Holographic art pieces shimmer on the walls, changing based on the owner's mood.",
            "The bridge itself is a masterpiece of design, with chrome details and custom leather chairs."
        ]
    },
    "Research Vessel": {
        "exterior": [
            "A large, modular vessel that looks more like a mobile starbase than a ship.",
            "A colossal, primary sensor array dominates the forward section.",
            "It features multiple docking ports for smaller, specialized science craft and sensor drones.",
            "The hull is covered in manipulator arms, sample collectors, and observational instruments.",
            "Its structure seems almost skeletal, with modules connected by reinforced spars."
        ],
        "interior": [
            "Contains multiple, dedicated laboratories for fields like biology, astrophysics, and xenotechnology.",
            "A massive, humming computer core is visible behind a shielded glass wall in the science bay.",
            "The crew quarters are comfortable and academic, resembling a high-tech university dormitory.",
            "An extensive, onboard digital library and sensor database is the ship's central feature.",
            "A zero-gravity specimen bay allows for the safe handling of unusual materials."
        ]
    }
}

# Component upgrade definitions
# Component upgrade definitions
COMPONENT_UPGRADES = {
    "engine": {
        "name": "Engine Systems",
        "levels": {
            1: {"bonus": 10, "description": "Basic tune-up"},
            2: {"bonus": 20, "description": "Performance optimization"},
            3: {"bonus": 35, "description": "Advanced fuel injection"},
            4: {"bonus": 50, "description": "Plasma core enhancement"},
            5: {"bonus": 70, "description": "Quantum drive integration"}
        },
        "affects": ["speed_rating", "fuel_efficiency"]
    },
    "hull": {
        "name": "Hull Reinforcement",
        "levels": {
            1: {"bonus": 15, "description": "Reinforced plating"},
            2: {"bonus": 30, "description": "Structural bracing"},
            3: {"bonus": 50, "description": "Ablative armor layers"},
            4: {"bonus": 75, "description": "Composite material refit"},
            5: {"bonus": 100, "description": "Full molecular hardening"}
        },
        "affects": ["hull_strength", "cargo_capacity"]
    },
    "systems": {
        "name": "Onboard Systems",
        "levels": {
            1: {"bonus": 5, "description": "Basic sensor calibration"},
            2: {"bonus": 10, "description": "Improved navigation computer"},
            3: {"bonus": 18, "description": "Enhanced scanner suite"},
            4: {"bonus": 25, "description": "AI-assisted targeting"},
            5: {"bonus": 40, "description": "Advanced electronic warfare package"}
        },
        "affects": ["combat_rating"]
    }
}

# Special modifications catalog
SPECIAL_MODIFICATIONS = {
    "universal": [  # Available to all ship types
        {
            "name": "Smuggler Compartment",
            "description": "Hidden cargo space undetectable by standard scans",
            "effect": "+20 stealth cargo capacity",
            "min_tier": 1,
            "cost_multiplier": 1.0
        },
        # Add more universal mods...
    ],
    "cargo_specialist": [  # For cargo-focused ships
        {
            "name": "Magnetic Clamps",
            "description": "External cargo attachment system",
            "effect": "+30% cargo capacity",
            "min_tier": 2,
            "cost_multiplier": 0.8
        },
        # Add more cargo mods...
    ],
    "combat_specialist": [  # For combat ships
        {
            "name": "Targeting Computer",
            "description": "Advanced weapon targeting system",
            "effect": "+25% weapon accuracy",
            "min_tier": 3,
            "cost_multiplier": 1.2
        },
        # Add more combat mods...
    ],
    # Add more specialization categories...
}

# Cosmetic customization options
COSMETIC_OPTIONS = {
    "paint_jobs": [
        {"name": "Midnight Black", "cost": 500, "description": "Stealth black coating"},
        {"name": "Arctic White", "cost": 500, "description": "Clean white finish"},
        {"name": "Matte Gray", "cost": 600, "description": "Non-reflective gray"},
        {"name": "Desert Tan", "cost": 700, "description": "Sand-colored camouflage"},
        {"name": "Military Green", "cost": 750, "description": "Standard military paint"},
        {"name": "Hazard Orange", "cost": 800, "description": "High-visibility safety orange"},
        {"name": "Racing Red", "cost": 1000, "description": "High-visibility red"},
        {"name": "Deep Space Blue", "cost": 1000, "description": "Dark blue with sparkle effect"},
        {"name": "Nebula Purple", "cost": 1500, "description": "Deep purple with shimmer"},
        {"name": "Chrome Finish", "cost": 2000, "description": "Reflective chrome coating"}
    ],
    "decals": [
        {"name": "Warning Labels", "cost": 150, "description": "Hazard warnings"},
        {"name": "Lucky Numbers", "cost": 200, "description": "Your lucky numbers"},
        {"name": "Racing Stripes", "cost": 300, "description": "Classic speed stripes"},
        {"name": "Corporate Logo", "cost": 400, "description": "Your company branding"},
        {"name": "Skull & Crossbones", "cost": 500, "description": "Pirate insignia"},
        {"name": "Flame Pattern", "cost": 600, "description": "Stylized flames on hull"},
        {"name": "Tribal Design", "cost": 700, "description": "Geometric tribal patterns"},
        {"name": "Star Map", "cost": 800, "description": "Constellation patterns"},
        {"name": "Military Insignia", "cost": 900, "description": "Rank and unit markings"},
        {"name": "Circuit Pattern", "cost": 1000, "description": "Tech-style circuit design"}
    ],
    "interior_themes": [
        {"name": "Minimalist", "cost": 1000, "description": "Clean and functional"},
        {"name": "Military Spec", "cost": 1500, "description": "Spartan and durable"},
        {"name": "Retro-Future", "cost": 1800, "description": "Chrome and wood paneling"},
        {"name": "Luxury", "cost": 2000, "description": "Plush seating and high-end finishes"},
        {"name": "Alien-Inspired", "cost": 2500, "description": "Bioluminescent lighting and organic shapes"}
    ],
    "name_plates": [
        {"name": "Standard Issue", "cost": 100, "description": "Basic ship identification letters."},
        {"name": "Engraved Steel", "cost": 300, "description": "Deeply engraved lettering."},
        {"name": "Holographic", "cost": 750, "description": "A shimmering, holographic name display."},
        {"name": "Gilded", "cost": 1200, "description": "Gold-leaf lettering for a touch of class."}
    ]
}

# Ship condition effects
# Ship condition effects
CONDITION_EFFECTS = {
    "excellent": {
        "range": (90, 100),
        "description": "Ship in pristine condition",
        "effects": {
            "upgrade_cost_modifier": 1.0,
            "trade_value_modifier": 1.0,
            "breakdown_chance": 0.01
        }
    },
    "good": {
        "range": (70, 89),
        "description": "Well-maintained vessel",
        "effects": {
            "upgrade_cost_modifier": 1.15,
            "trade_value_modifier": 0.85,
            "breakdown_chance": 0.05
        }
    },
    "fair": {
        "range": (50, 69),
        "description": "Shows signs of wear and tear",
        "effects": {
            "upgrade_cost_modifier": 1.30,
            "trade_value_modifier": 0.70,
            "breakdown_chance": 0.10
        }
    },
    "poor": {
        "range": (20, 49),
        "description": "Significant damage, systems unreliable",
        "effects": {
            "upgrade_cost_modifier": 1.60,
            "trade_value_modifier": 0.50,
            "breakdown_chance": 0.25
        }
    },
    "critical": {
        "range": (0, 19),
        "description": "Barely holding together, catastrophic failure imminent",
        "effects": {
            "upgrade_cost_modifier": 2.50,
            "trade_value_modifier": 0.20,
            "breakdown_chance": 0.50
        }
    }
}





SPECIAL_MODIFICATIONS = {
    "universal": [
        {
            "name": "Smuggler Compartment",
            "description": "Hidden cargo space undetectable by standard scans",
            "effect": "+20 stealth cargo capacity",
            "min_tier": 1,
            "cost_multiplier": 1.0
        },
        {
            "name": "Emergency Booster",
            "description": "One-use speed boost for emergencies",
            "effect": "+50% speed for one jump",
            "min_tier": 2,
            "cost_multiplier": 0.8
        },
        {
            "name": "Shield Generator",
            "description": "Basic energy shielding system",
            "effect": "+20% damage reduction",
            "min_tier": 3,
            "cost_multiplier": 1.4
        }
    ],
    "cargo_specialist": [
        {
            "name": "Magnetic Clamps",
            "description": "External cargo attachment system",
            "effect": "+30% cargo capacity",
            "min_tier": 2,
            "cost_multiplier": 0.8
        },
        {
            "name": "Automated Cargo Sorter",
            "description": "Robotic system for rapid loading and unloading",
            "effect": "-20% port loading times",
            "min_tier": 3,
            "cost_multiplier": 1.1
        }
    ],
    "combat_specialist": [
        {
            "name": "Targeting Computer",
            "description": "Advanced weapon targeting system",
            "effect": "+25% weapon accuracy",
            "min_tier": 3,
            "cost_multiplier": 1.2
        },
        {
            "name": "Cloaking Device",
            "description": "Basic stealth technology to avoid encounters",
            "effect": "Avoid 30% of random encounters",
            "min_tier": 4,
            "cost_multiplier": 1.8
        }
    ],
    "speed_specialist": [
        {
            "name": "Afterburner Kit",
            "description": "High-performance engine modification",
            "effect": "+2 speed rating",
            "min_tier": 2,
            "cost_multiplier": 1.1
        },
        {
            "name": "Streamlined Hull",
            "description": "Aerodynamic hull modifications",
            "effect": "+15% base speed, -10% cargo capacity",
            "min_tier": 3,
            "cost_multiplier": 1.3
        }
    ],
    "exploration_specialist": [
        {
            "name": "Long-Range Scanners",
            "description": "Advanced sensor array for deep space",
            "effect": "+50% scan range, reveal hidden locations",
            "min_tier": 3,
            "cost_multiplier": 1.5
        },
        {
            "name": "Extended Fuel Tanks",
            "description": "Additional fuel storage capacity",
            "effect": "+40% fuel capacity",
            "min_tier": 2,
            "cost_multiplier": 0.9
        }
    ]
}

# Random event modifiers for ships
SHIP_EVENTS = {
    "positive": [
        {
            "name": "Efficient Route",
            "description": "Your navigation computer found an optimal path",
            "effect": {"fuel_saved": 10},
            "weight": 30
        },
        {
            "name": "Favorable Solar Winds",
            "description": "Natural phenomena boost your speed",
            "effect": {"fuel_saved": 15, "time_saved": 10},
            "weight": 25
        },
        {
            "name": "Helpful Mechanic",
            "description": "A friendly mechanic offers free tune-up",
            "effect": {"condition_gain": 10},
            "weight": 15
        },
        {
            "name": "Salvage Find",
            "description": "You discover valuable salvage floating in space",
            "effect": {"credits_gained": 500},
            "weight": 10
        }
    ],
    "negative": [
        {
            "name": "Engine Malfunction",
            "description": "Your engine sputters and needs adjustment",
            "effect": {"condition_loss": 10, "fuel_lost": 5},
            "weight": 25
        },
        {
            "name": "Pirates Spotted",
            "description": "You take evasive action to avoid pirates",
            "effect": {"fuel_lost": 20, "time_lost": 15},
            "weight": 20
        },
        {
            "name": "Micro-meteorite Impact",
            "description": "Small debris damaged your hull",
            "effect": {"condition_loss": 5},
            "weight": 20
        },
        {
            "name": "Navigation Error",
            "description": "A calculation error sends you off course",
            "effect": {"fuel_lost": 10, "time_lost": 20},
            "weight": 15
        }
    ],
    "neutral": [
        {
            "name": "Routine Scan",
            "description": "Local authorities performed a standard inspection",
            "effect": {},
            "weight": 50
        },
        {
            "name": "Unusual Signal",
            "description": "You detected a strange, unidentifiable signal, but it vanished.",
            "effect": {},
            "weight": 20
        },
        {
            "name": "Passing Freighter",
            "description": "A massive freighter passes by, its crew giving a friendly wave.",
            "effect": {},
            "weight": 30
        }
    ]
}

# Ship name generation parts - Enhanced
SHIP_NAME_PARTS = {
    "prefixes": [
        "ISS", "TSS", "HMS", "USS", "FSV", "CSV", "ESS", "RMS", "INS", "GSV"
    ],
    "adjectives": [
        # Space-themed
        "Stellar", "Orbital", "Galactic", "Quantum", "Nebula", "Cosmic", "Astral",
        "Celestial", "Lunar", "Solar", "Void", "Starborn", "Interstellar", "Comet's",
        "Asteroid", "Meteor", "Supernova", "Eventide", "Twilight", "Eclipse",

        # Speed/Movement
        "Swift", "Rapid", "Flying", "Soaring", "Drifting", "Gliding", "Racing",
        "Warp", "Arrow", "Dart", "Streak", "Unbound",

        # Power/Strength
        "Mighty", "Powerful", "Invincible", "Unstoppable", "Relentless", "Indomitable",
        "Defiant", "Valiant", "Adamant", "Iron", "Titan's", "Goliath",

        # Exploration
        "Wandering", "Roaming", "Pioneering", "Pathfinding", "Voyaging", "Questing",
        "Far", "Distant", "Endless", "New", "Final", "Forgotten",

        # Colors/Materials
        "Golden", "Silver", "Crimson", "Azure", "Emerald", "Obsidian", "Onyx",
        "Cobalt", "Scarlet", "Ivory", "Jade", "Diamond",

        # Abstract
        "Brave", "Bold", "Lost", "Final", "Last", "First", "Silent", "Lone"
    ],
    "nouns": [
        # Ships/Vessels
        "Voyager", "Pioneer", "Explorer", "Wanderer", "Nomad", "Drifter", "Pathfinder",
        "Cruiser", "Freighter", "Runner", "Glider", "Cutter", "Jumper", "Carrier",

        # Animals/Creatures
        "Phoenix", "Dragon", "Eagle", "Hawk", "Falcon", "Wolf", "Tiger", "Serpent",
        "Leviathan", "Wyvern", "Griffin", "Kraken", "Manticore",

        # Natural phenomena
        "Tempest", "Thunder", "Lightning", "Comet", "Meteor", "Aurora", "Starfall",
        "Storm", "Typhoon", "Hurricane", "Quasar", "Pulsar", "Nebula",

        # Abstract concepts
        "Fortune", "Destiny", "Liberty", "Victory", "Hope", "Dream", "Legacy",
        "Resolve", "Gambit", "Promise", "Horizon", "Odyssey", "Sojourn",

        # Mythological/Historical
        "Excalibur", "Icarus", "Odysseus", "Argonaut", "Valhalla", "Asgard",
        "Ronin", "Samurai", "Spartan", "Valkyrie"
    ],
    "suffixes": [
        "I", "II", "III", "IV", "V", "Alpha", "Beta", "Gamma", "Delta",
        "Prime", "X", "Z", "Mk1", "Mk2", "A", "B", "Plus", "Max", "Omega"
    ]
}

# Market value calculations
MARKET_VALUE_FACTORS = {
    "base_multipliers": {
        1: 1.0,   # Tier 1
        2: 2.2,   # Tier 2
        3: 3.8,   # Tier 3
        4: 5.5,   # Tier 4
        5: 8.0    # Tier 5
    },
    "component_values": {
        "engine_level": 500,
        "hull_level": 600,
        "systems_level": 400
    },
    "mod_value": 3000,  # Per special modification
    "condition_factor": 0.01  # Per condition %
}

# Upgrade item definitions for inventory
# Upgrade item definitions for inventory
UPGRADE_ITEMS = {
    "common": [
        {
            "name": "Basic Fuel Injector",
            "type": "ship_upgrade",
            "upgrade_type": "fuel_efficiency",
            "bonus": 5,
            "description": "Improves fuel efficiency by 5%",
            "value": 500
        },
        {
            "name": "Standard Hull Patch",
            "type": "ship_upgrade",
            "upgrade_type": "hull_strength",
            "bonus": 10,
            "description": "Adds 10 hull points",
            "value": 300
        },
        {
            "name": "Basic Nav Computer",
            "type": "ship_upgrade",
            "upgrade_type": "jump_accuracy",
            "bonus": 5,
            "description": "Improves navigation by 5%",
            "value": 400
        }
    ],
    "uncommon": [
        {
            "name": "Advanced Fuel System",
            "type": "ship_upgrade",
            "upgrade_type": "fuel_efficiency",
            "bonus": 10,
            "description": "Improves fuel efficiency by 10%",
            "value": 1200
        },
        {
            "name": "Cargo Expansion Kit",
            "type": "ship_upgrade",
            "upgrade_type": "cargo_capacity",
            "bonus": 25,
            "description": "Increases cargo space by 25",
            "value": 1800
        },
        {
            "name": "Reinforced Hull Plating",
            "type": "ship_upgrade",
            "upgrade_type": "hull_strength",
            "bonus": 20,
            "description": "Adds 20 hull points",
            "value": 1500
        }
    ],
    "rare": [
        {
            "name": "Quantum Drive Stabilizer",
            "type": "ship_upgrade",
            "upgrade_type": "speed_rating",
            "bonus": 2,
            "description": "Increases speed rating by 2",
            "value": 5000
        },
        {
            "name": "Military Armor Plating",
            "type": "ship_upgrade",
            "upgrade_type": "hull_strength",
            "bonus": 50,
            "description": "Adds 50 hull points",
            "value": 4000
        },
        {
            "name": "Military-Grade Targeting System",
            "type": "ship_upgrade",
            "upgrade_type": "combat_rating",
            "bonus": 15,
            "description": "Increases combat rating by 15",
            "value": 5000
        }
    ],
    "legendary": [
        {
            "name": "Alien Tech Core",
            "type": "ship_upgrade",
            "upgrade_type": "all_systems",
            "bonus": 15,
            "description": "Improves all systems by 15%",
            "value": 15000
        }
    ]
}

def generate_random_ship_name():
    """Enhanced ship name generation with more variety"""
    name_style = random.randint(1, 4)
    
    if name_style == 1:  # Prefix + Adjective + Noun
        prefix = random.choice(SHIP_NAME_PARTS['prefixes'])
        adj = random.choice(SHIP_NAME_PARTS['adjectives'])
        noun = random.choice(SHIP_NAME_PARTS['nouns'])
        return f"{prefix} {adj} {noun}"
    
    elif name_style == 2:  # The + Adjective + Noun
        adj = random.choice(SHIP_NAME_PARTS['adjectives'])
        noun = random.choice(SHIP_NAME_PARTS['nouns'])
        return f"The {adj} {noun}"
    
    elif name_style == 3:  # Adjective + Noun + Suffix
        adj = random.choice(SHIP_NAME_PARTS['adjectives'])
        noun = random.choice(SHIP_NAME_PARTS['nouns'])
        suffix = random.choice(SHIP_NAME_PARTS['suffixes'])
        return f"{adj} {noun} {suffix}"
    
    else:  # Simple Noun or Noun + Suffix
        noun = random.choice(SHIP_NAME_PARTS['nouns'])
        if random.random() > 0.5:
            suffix = random.choice(SHIP_NAME_PARTS['suffixes'])
            return f"{noun} {suffix}"
        return noun

def calculate_ship_value(ship_data: dict) -> int:
    """Calculate market value of a ship based on all factors"""
    # Base value from tier
    tier = ship_data.get('tier', 1)
    base_value = ship_data.get('base_price', 3000)
    
    # Apply tier multiplier
    tier_mult = MARKET_VALUE_FACTORS['base_multipliers'].get(tier, 1.0)
    value = base_value * tier_mult
    
    # Add component values
    for component, level_value in MARKET_VALUE_FACTORS['component_values'].items():
        level = ship_data.get(component, 1)
        value += (level - 1) * level_value
    
    # Add modification values
    mods = ship_data.get('special_mods', [])
    value += len(mods) * MARKET_VALUE_FACTORS['mod_value']
    
    # Apply condition factor
    condition = ship_data.get('condition_rating', 100)
    condition_mult = 0.5 + (condition * MARKET_VALUE_FACTORS['condition_factor'])
    value = int(value * condition_mult)
    
    return max(1000, value)  # Minimum value of 1000

def get_ship_class_bonuses(ship_type: str) -> dict:
    """Get innate bonuses for ship classes"""
    class_bonuses = {
        "Cargo": {
            "cargo_capacity": 1.2,
            "fuel_efficiency": 0.9,
            "speed_rating": 0.8
        },
        "Recon": {
            "speed_rating": 1.3,
            "fuel_efficiency": 1.1,
            "scan_range": 1.5
        },
        "Combat": {
            "combat_rating": 1.4,
            "hull_strength": 1.2,
            "cargo_capacity": 0.7
        },
        "Luxury": {
            "crew_morale": 1.5,
            "passenger_capacity": 1.3,
            "maintenance_cost": 1.2
        }
    }
    
    ship_info = SHIP_TYPES.get(ship_type, {})
    ship_class = ship_info.get('class', 'Standard')
    
    return class_bonuses.get(ship_class, {})
    
def get_random_starter_ship():
    """Generate a random starter ship for new characters"""
    # Get only Tier 1 ships (starter ships)
    starter_ships = [
        ship_type for ship_type, info in SHIP_TYPES.items() 
        if info.get('tier', 1) == 1
    ]
    
    # Randomly select a ship type
    ship_type = random.choice(starter_ships)
    
    # Generate a random ship name
    ship_name = generate_random_ship_name()
    
    # Create exterior description based on ship type
    exterior_descriptions = {
        "Hauler": [
            "A sturdy, boxy vessel with reinforced cargo holds and heavy plating. Its utilitarian design prioritizes function over form.",
            "This well-worn cargo ship bears the scars of countless trading runs. Its bulky frame and external cargo pods maximize storage capacity.",
            "A reliable workhorse with a reinforced hull and multiple cargo bay access points. Built for durability rather than speed."
        ],
        "Scout": [
            "A sleek, dart-shaped vessel with advanced sensor arrays and minimal profile. Built for speed and reconnaissance.",
            "This nimble craft features swept-back wings and a streamlined hull. Its compact design allows for rapid maneuvering.",
            "A lightweight explorer with enhanced thrusters and long-range scanning equipment. Perfect for surveying unknown territories."
        ],
        "Shuttle": [
            "A versatile mid-sized transport with comfortable passenger accommodations and modest cargo space.",
            "This multipurpose vessel balances passenger comfort with practical cargo capacity. A common sight in civilian spacelanes.",
            "A dependable transport craft with reinforced viewports and dual-purpose cargo/passenger bays."
        ]
    }
    
    # Create interior description based on ship type
    interior_descriptions = {
        "Hauler": [
            "The bridge is cramped but functional, with cargo manifest displays dominating the walls. The main corridor leads to expansive cargo holds.",
            "Inside, every inch of space is optimized for storage. The living quarters are minimal, but the cargo management systems are top-notch.",
            "The interior prioritizes cargo space over comfort. Basic amenities line the narrow corridors between massive storage bays."
        ],
        "Scout": [
            "The cockpit features advanced navigation systems and sensor readouts. The compact living space is efficiently designed for long reconnaissance missions.",
            "A high-tech bridge dominates the front section, while the rear houses minimal but comfortable crew quarters and a small cargo area.",
            "The interior is filled with scanning equipment and navigation computers. Every surface serves a purpose in this efficiency-focused design."
        ],
        "Shuttle": [
            "The interior offers a balance of passenger seating and cargo storage. The bridge provides good visibility for atmospheric and space operations.",
            "Comfortable passenger seats line the main cabin, with overhead storage and a separate cargo compartment in the rear.",
            "The versatile interior can be reconfigured for passengers or cargo. Standard amenities make it suitable for various missions."
        ]
    }
    
    # Select random descriptions
    exterior_desc = random.choice(exterior_descriptions.get(ship_type, ["A standard vessel of its class."]))
    interior_desc = random.choice(interior_descriptions.get(ship_type, ["A typical interior layout for this type of ship."]))
    
    return ship_type, ship_name, exterior_desc, interior_desc