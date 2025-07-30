import random
import json
from typing import Dict, List, Tuple, Any

class ItemConfig:
    """Configuration system for items with usage effects and spawn rates"""
    
    # Item definitions with usage properties
    ITEM_DEFINITIONS = {
        # Medical Items
        "Basic Med Kit": {
            "type": "medical",
            "description": "Basic medical supplies for treating minor injuries",
            "base_value": 75,
            "usage_type": "heal_hp",
            "effect_value": 25,
            "single_use": True,
            "rarity": "common"
        },
        "Advanced Med Kit": {
            "type": "medical", 
            "description": "High-quality medical supplies for serious injuries",
            "base_value": 150,
            "usage_type": "heal_hp",
            "effect_value": 50,
            "single_use": True,
            "rarity": "uncommon"
        },
        "Painkillers": {
            "type": "medical",
            "description": "Standard issue pain relief medication",
            "base_value": 20,
            "usage_type": "heal_hp",
            "effect_value": 10,
            "single_use": True,
            "rarity": "common"
        },
        "Field Dressing": {
            "type": "medical",
            "description": "Basic bandages and antiseptic for wounds",
            "base_value": 50,
            "usage_type": "heal_hp",
            "effect_value": 20,
            "single_use": True,
            "rarity": "common"
        },
        "Trauma Kit": {
            "type": "medical",
            "description": "Comprehensive supplies for critical, life-threatening injuries. Contains auto-sutures and blood plasma.",
            "base_value": 300,
            "usage_type": "heal_hp",
            "effect_value": 100,
            "single_use": True,
            "rarity": "rare"
        },
        "Suture Kit": {
            "type": "medical",
            "description": "A sterile kit for closing deep wounds. Requires a steady hand.",
            "base_value": 100,
            "usage_type": "heal_hp",
            "effect_value": 35,
            "single_use": True,
            "rarity": "uncommon"
        },
        "Antibiotics": {
            "type": "medical",
            "description": "Broad-spectrum antibiotics to fight infections.",
            "base_value": 40,
            "usage_type": "heal_hp",
            "effect_value": 15,
            "single_use": True,
            "rarity": "common"
        },
        "Coagulant Spray": {
            "type": "medical",
            "description": "Stops bleeding quickly with a pressurized clotting agent.",
            "base_value": 60,
            "usage_type": "heal_hp",
            "effect_value": 20,
            "single_use": True,
            "rarity": "common"
        },
        # Special Items
        "Emergency Beacon": {
            "type": "equipment",
            "description": "One-time use distress signal broadcaster",
            "base_value": 200,
            "usage_type": "emergency_signal",
            "effect_value": 1,
            "single_use": True,
            "rarity": "uncommon"
        },
        "Radio Beacon": {
            "type": "equipment",
            "description": "One-time use radio broadcaster that repeats messages hourly for 6 hours",
            "base_value": 250,
            "usage_type": "radio_beacon",
            "effect_value": 1,
            "single_use": True,
            "rarity": "uncommon"
        },
        "Personal Log": {
            "type": "equipment",
            "description": "A digital logbook for recording personal entries and memories",
            "base_value": 120,
            "usage_type": "personal_log",
            "effect_value": 1,
            "single_use": False,
            "rarity": "uncommon"
        },

        "News Beacon": {
            "type": "equipment",
            "description": "Broadcasts news updates to the network",
            "base_value": 300,
            "usage_type": "news_beacon",
            "effect_value": 1,
            "single_use": True,
            "rarity": "rare"
        },
        "Portable Radio Repeater": {
            "type": "equipment",
            "description": "Deployable radio repeater that extends communication range",
            "base_value": 800,
            "usage_type": "deploy_repeater",
            "effect_value": 1,
            "single_use": True,
            "rarity": "rare"
        },

        # Consumable Items
        "Emergency Rations": {
            "type": "consumable",
            "description": "Basic food supplies that restore energy",
            "base_value": 10,
            "usage_type": "heal_hp",
            "effect_value": 15,
            "single_use": True,
            "rarity": "common"
        },

        "Space Soda": {
            "type": "consumable",
            "description": "Sweet and fizzy space soda",
            "base_value": 5,
            "usage_type": "heal_hp",
            "effect_value": 1,
            "single_use": True,
            "rarirty": "common"
        },
        "Canned Stew": {
            "type": "consumable",
            "description": "A dented tin of mass-produced stew. Smells metallic.",
            "base_value": 6,
            "usage_type": "heal_hp",
            "effect_value": 10,
            "single_use": True,
            "rarity": "common"
        },



        "Dried Fruit Pack": {
            "type": "consumable",
            "description": "Sealed pouch of dehydrated fruit slices. Chewy but edible.",
            "base_value": 8,
            "usage_type": "heal_hp",
            "effect_value": 8,
            "single_use": True,
            "rarity": "common"
        },

        "Vitamin Tablets": {
            "type": "consumable",
            "description": "Synthetic vitamin pills to stave off deficiencies.",
            "base_value": 4,
            "usage_type": "heal_hp",
            "effect_value": 3,
            "single_use": True,
            "rarity": "common"
        },

        "Protein Bars": {
            "type": "consumable",
            "description": "High-energy manufactured food",
            "base_value": 5,
            "usage_type": "heal_hp", 
            "effect_value": 10,
            "single_use": True,
            "rarity": "common"
        },
        "Processed Snack Bag": {
            "type": "consumable",
            "description": "A sealed bag of salty, preserved snack bits.",
            "base_value": 4,
            "usage_type": "heal_hp",
            "effect_value": 5,
            "single_use": True,
            "rarity": "common"
        },
        "Meal Replacement Drink": {
            "type": "consumable",
            "description": "Convenient bottled drink containing balanced nutrients for busy spacefarers.",
            "base_value": 7,
            "usage_type": "heal_hp",
            "effect_value": 8,
            "single_use": True,
            "rarity": "common"
        },
        "Chocolate Meal Replacement Drink": {
            "type": "consumable",
            "description": "Convenient bottled drink containing balanced nutrients for busy spacefares. In chocolate flavor!.",
            "base_value": 7,
            "usage_type": "heal_hp",
            "effect_value": 8,
            "single_use": True,
            "rarity": "common"
        },
        "Instant Noodles": {
            "type": "consumable",
            "description": "Popular quick meal, just add hot water. Slightly stale.",
            "base_value": 6,
            "usage_type": "heal_hp",
            "effect_value": 8,
            "single_use": True,
            "rarity": "common"
        },
        "Nutrient Paste": {
            "type": "consumable",
            "description": "A bland, synthetic paste containing essential daily nutrients. Tastes like nothing.",
            "base_value": 8,
            "usage_type": "heal_hp",
            "effect_value": 12,
            "single_use": True,
            "rarity": "common"
        },
        "Filtered Water": {
            "type": "consumable",
            "description": "Recycled and filtered water, safe for consumption. Has a faint metallic taste.",
            "base_value": 3,
            "usage_type": "heal_hp",
            "effect_value": 5,
            "single_use": True,
            "rarity": "common"
        },
        "Expired Ration Pack": {
            "type": "consumable",
            "description": "Military surplus food, long past its expiration date. A gamble.",
            "base_value": 1,
            "usage_type": "heal_hp",
            "effect_value": 3,
            "single_use": True,
            "rarity": "common"
        },
        # Repair Items
        "Repair Kit": {
            "type": "equipment",
            "description": "Tools for repairing ship hull damage",
            "base_value": 100,
            "usage_type": "repair_hull",
            "effect_value": 30,
            "uses_remaining": 3,
            "rarity": "common"
        },
        "Basic Tools": {
            "type": "equipment",
            "description": "Standard repair tools for basic maintenance",
            "base_value": 250,
            "usage_type": "repair_hull",
            "effect_value": 5,
            "uses_remaining": 5,
            "rarity": "common"
        },
        "Hull Patch": {
            "type": "equipment",
            "description": "An adhesive, self-sealing patch for minor hull breaches. A temporary fix.",
            "base_value": 80,
            "usage_type": "repair_hull",
            "effect_value": 20,
            "single_use": True,
            "rarity": "common"
        },
        "Welding Kit": {
            "type": "equipment",
            "description": "A portable plasma welder for more serious hull repairs.",
            "base_value": 400,
            "usage_type": "repair_hull",
            "effect_value": 25,
            "uses_remaining": 4,
            "rarity": "uncommon"
        },
        "Scrap Metal": {
            "type": "trade",
            "description": "Salvaged metal plating and components. Not useful on its own, but valuable for trade or fabrication.",
            "base_value": 20,
            "usage_type": "narrative",
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "common"
        },
        "Sealant Foam": {
            "type": "equipment",
            "description": "Expanding foam for sealing microfractures in the hull.",
            "base_value": 90,
            "usage_type": "repair_hull",
            "effect_value": 15,
            "uses_remaining": 2,
            "rarity": "common"
        },
        "Multi-Tool": {
            "type": "equipment",
            "description": "A basic powered tool for a range of small repairs.",
            "base_value": 200,
            "usage_type": "repair_hull",
            "effect_value": 10,
            "uses_remaining": 5,
            "rarity": "common"
        },
        "Scanner Module": {
            "type": "equipment",
            "description": "Improves search effectiveness when used",
            "base_value": 300,
            "usage_type": "search_boost",
            "effect_value": 25,  # +25% search success rate
            "uses_remaining": 10,
            "rarity": "rare"
        },
        
        # Fuel Items
        "Fuel Cell": {
            "type": "fuel",
            "description": "Portable fuel container for ship refueling",
            "base_value": 45,
            "usage_type": "restore_fuel",
            "effect_value": 15,
            "single_use": True,
            "rarity": "common"
        },
        "Refined Fuel Pod": {
            "type": "fuel",
            "description": "Small but clean-burning fuel supply.",
            "base_value": 55,
            "usage_type": "restore_fuel",
            "effect_value": 20,
            "single_use": True,
            "rarity": "uncommon"
        },

        "Low-Grade Fuel Canister": {
            "type": "fuel",
            "description": "Cheap, low-output fuel supply",
            "base_value": 20,
            "usage_type": "restore_fuel",
            "effect_value": 10,
            "single_use": True,
            "rarity": "common"
        },
        "Impure Fuel Slurry": {
            "type": "fuel",
            "description": "A low-grade, poorly refined fuel. Prone to causing engine residue.",
            "base_value": 10,
            "usage_type": "restore_fuel",
            "effect_value": 3,
            "single_use": True,
            "rarity": "common"
        },
        "High-Grade Fuel Cell": {
            "type": "fuel",
            "description": "Premium fuel cell with increased capacity",
            "base_value": 75,
            "usage_type": "restore_fuel",
            "effect_value": 25,
            "single_use": True,
            "rarity": "uncommon"
        },
        
        # Trade / Generic Items
        "Data Chip": {
            "type": "trade",
            "description": "Contains valuable information or entertainment",
            "base_value": 40,
            "usage_type": "narrative",
            "effect_value": "information",
            "single_use": False,
            "rarity": "common"
        },
        "Printed Manuals": {
            "type": "trade",
            "description": "Old printed maintenance or survival manuals. Some pages missing.",
            "base_value": 20,
            "usage_type": "narrative",
            "effect_value": "information",
            "single_use": False,
            "rarity": "common"
        },
        "Rare Minerals": {
            "type": "trade",
            "description": "Valuable crystalline formations with unique properties",
            "base_value": 150,
            "usage_type": "narrative", 
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "rare"
        },
        "Packaging Foil": {
            "type": "trade",
            "description": "Bulk roll of durable synthetic foil used for food storage or insulation.",
            "base_value": 30,
            "usage_type": "narrative",
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "common"
        },
        "Artifact": {
            "type": "trade",
            "description": "Artifact from a lost colony",
            "base_value": 500,
            "usage_type": "narrative",
            "effect_value": "mysterious",
            "single_use": False,
            "rarity": "legendary"
        },
        "Personal Trinket": {
            "type": "trade",
            "description": "A keepsake from another life. Was sentimental to someone at one point, now it might just be junk.",
            "base_value": 50,
            "usage_type": "narrative",
            "effect_value": "mysterious",
            "single_use": False,
            "rarity": "rare"
        },
        "Scrap Electronics": {
            "type": "trade",
            "description": "Broken circuit boards and fried components. Some parts might be salvageable.",
            "base_value": 30,
            "usage_type": "narrative",
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "common"
        },
        "Scarp Mechanical Parts": {
            "type": "trade",
            "description": "Screws, nuts, bolts, gears and other miscellaneous mechanical parts.",
            "base_value": 30,
            "usage_type": "narrative",
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "common"
        },
        "Synthetic Textiles": {
            "type": "trade",
            "description": "A bolt of durable, multi-purpose fabric used for clothing and repairs.",
            "base_value": 60,
            "usage_type": "narrative",
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "common"
        },
        "Encrypted Data Drive": {
            "type": "trade",
            "description": "Contains sensitive information. No telling what’s on it.",
            "base_value": 120,
            "usage_type": "narrative",
            "effect_value": "information",
            "single_use": False,
            "rarity": "uncommon"
        },
        "Processed Alloys": {
            "type": "trade",
            "description": "Refined metal, ready for manufacturing or trade.",
            "base_value": 80,
            "usage_type": "narrative",
            "effect_value": "valuable",
            "single_use": False,
            "rarity": "common"
        },
        # Upgrade Items
        "Engine Booster": {
            "type": "upgrade",
            "description": "Permanently improves ship fuel efficiency",
            "base_value": 800,
            "usage_type": "upgrade_ship",
            "effect_value": "fuel_efficiency:5",
            "single_use": True,
            "rarity": "rare"
        },
        "Hull Reinforcement": {
            "type": "upgrade", 
            "description": "Permanently increases maximum hull integrity",
            "base_value": 1200,
            "usage_type": "upgrade_ship",
            "effect_value": "max_hull:25",
            "single_use": True,
            "rarity": "rare"
        },
        # Black Market Exclusive Items
        "Forged Transit Papers": {
            "type": "documents",
            "description": "Fake identification documents that can bypass some security checks",
            "base_value": 2500,
            "usage_type": "bypass_security",
            "effect_value": 1,
            "single_use": True,
            "rarity": "rare"
        },

        "Identity Scrubber": {
            "type": "service", 
            "description": "Illegal device that erases identity records from databases",
            "base_value": 8000,
            "usage_type": "scrub_identity",
            "effect_value": 1,
            "single_use": True,
            "rarity": "legendary"
        },

        "Stolen Data Chips": {
            "type": "data",
            "description": "Information of questionable origin, potentially valuable",
            "base_value": 1800,
            "usage_type": "narrative",
            "effect_value": "stolen_information",
            "single_use": False,
            "rarity": "uncommon"
        },

        "Unmarked Credits": {
            "type": "currency",
            "description": "Untraceable digital currency for discrete transactions", 
            "base_value": 2000,
            "usage_type": "add_credits",
            "effect_value": 1500,
            "single_use": True,
            "rarity": "rare"
        },

        "Weapon System Override": {
            "type": "software",
            "description": "Bypasses weapon safety protocols - highly illegal",
            "base_value": 6000,
            "usage_type": "upgrade_ship",
            "effect_value": "weapon_override:1",
            "single_use": True,
            "rarity": "legendary"
        },


        # Federal Depot Exclusive Items
        "Federal ID Card": {
            "type": "documents",
            "description": "Official federal identification providing access to restricted areas",
            "base_value": 1200,
            "usage_type": "federal_access",
            "effect_value": 1,
            "single_use": False,
            "rarity": "uncommon"
        },

        "Military Rations": {
            "type": "consumable",
            "description": "High-quality preserved food with extended shelf life",
            "base_value": 35,
            "usage_type": "restore_hp",
            "effect_value": 25,
            "single_use": True,
            "rarity": "uncommon"
        },

        "Loyalty Certification": {
            "type": "documents", 
            "description": "Official proof of federal allegiance and good standing",
            "base_value": 800,
            "usage_type": "reputation_boost",
            "effect_value": "federal:5",
            "single_use": True,
            "rarity": "uncommon"
        },
        
        "Military Repair Drone": {
            "type": "equipment",
            "description": "A small drone capable of performing high end repairs.",
            "base_value": 4000,
            "usage_type": "repair_hull",
            "effect_value": 80,
            "uses_remaining": 5,
            "rarity": "rare"
        },

        "Military Fuel Cell": {
            "type": "fuel",
            "description": "High Grade, multi-use Military fuel cell.",
            "base_value": 2500,
            "usage_type": "restore_fuel",
            "effect_value": 75,
            "uses_remaining": 5,
            "rarity": "rare"
        },


        "Combat Stim Injector": {
            "type": "medical",
            "description": "Military-grade combat enhancement drugs",
            "base_value": 400,
            "usage_type": "combat_boost",
            "effect_value": 20,
            "effect_duration": 1800,  # 30 minutes
            "single_use": True,
            "rarity": "rare"
        },

        "Emergency Medical Pod": {
            "type": "medical",
            "description": "Automated medical treatment system for critical injuries",
            "base_value": 800,
            "usage_type": "heal_hp",
            "effect_value": 100,  # Full heal
            "single_use": True,
            "rarity": "legendary"
        },

        # Equipment Items - Stat Modifying Gear
        "Neural Interface Headset": {
            "type": "equipment",
            "description": "Advanced neural interface that enhances cognitive processing",
            "base_value": 2500,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"engineering": 3, "medical": 2},
            "rarity": "rare"
        },
        "Navigational Aide Headset": {
            "type": "equipment",
            "description": "An advanced headset that provides navigational guidance and assistance.",
            "base_value": 2750,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"navigation": 4},
            "rarity": "rare"
        },
        "Tactical Goggles": {
            "type": "equipment", 
            "description": "Military-grade targeting and analysis goggles",
            "base_value": 1200,
            "equippable": True,
            "equipment_slot": "eyes",
            "stat_modifiers": {"combat": 2, "navigation": 1},
            "rarity": "uncommon"
        },
        "Reinforced Vest": {
            "type": "equipment",
            "description": "Armored vest that provides protection and confidence",
            "base_value": 1800,
            "equippable": True,
            "equipment_slot": "torso", 
            "stat_modifiers": {"hp": 20, "combat": 1},
            "rarity": "uncommon"
        },
        "Shoulder Plate (Left)": {
            "type": "equipment",
            "description": "A reinforced metal shoulder plating, for industrial or combat use.",
            "base_value": 1200,
            "equippable": True,
            "equipment_slot": "arms_left",
            "stat_modifiers": {"defense": 4},
            "rarity": "rare"
        },
        "Exo Arm (Left)": {
            "type": "equipment",
            "description": "Mechanical arm augment with enhanced strength and precision",
            "base_value": 5000,
            "equippable": True,
            "equipment_slot": "arms_left",
            "stat_modifiers": {"engineering": 4, "combat": 2},
            "rarity": "rare"
        },
        "Exo Arm (Right)": {
            "type": "equipment",
            "description": "Mechanical arm augment with enhanced strength and precision",
            "base_value": 5000,
            "equippable": True,
            "equipment_slot": "arms_right", 
            "stat_modifiers": {"engineering": 4, "combat": 2},
            "rarity": "rare"
        },
        "Pilot's Gloves": {
            "type": "equipment",
            "description": "Specialized gloves that improve ship handling",
            "base_value": 800,
            "equippable": True,
            "equipment_slot": "hands_both",  # Special case for paired items
            "stat_modifiers": {"navigation": 3},
            "rarity": "common"
        },
        "Medical Scanner Glove (Left)": {
            "type": "equipment",
            "description": "Medical diagnostic glove with built-in sensors",
            "base_value": 1500,
            "equippable": True,
            "equipment_slot": "hands_left",
            "stat_modifiers": {"medical": 3},
            "rarity": "uncommon"
        },
        "Tool Grip Glove (Right)": {
            "type": "equipment",
            "description": "Enhanced grip glove for precision engineering work",
            "base_value": 900,
            "equippable": True,
            "equipment_slot": "hands_right",
            "stat_modifiers": {"engineering": 2},
            "rarity": "common"
        },
        "Combat Leg Brace (Left)": {
            "type": "equipment",
            "description": "Reinforced leg brace that improves stability in combat",
            "base_value": 1100,
            "equippable": True,
            "equipment_slot": "legs_left",
            "stat_modifiers": {"combat": 2},
            "rarity": "uncommon"
        },
        "Navigation Leg Brace (Right)": {
            "type": "equipment", 
            "description": "Leg brace with built-in navigation sensors",
            "base_value": 1100,
            "equippable": True,
            "equipment_slot": "legs_right",
            "stat_modifiers": {"navigation": 2},
            "rarity": "uncommon"
        },
        "Magnetic Boots": {
            "type": "equipment",
            "description": "Boots with magnetic soles for zero-g movement",
            "base_value": 1400,
            "equippable": True,
            "equipment_slot": "feet_both",  # Special case for paired items
            "stat_modifiers": {"navigation": 2, "engineering": 1},
            "rarity": "uncommon"
        },

        # Armor Items with Defense
        "Military Helmet": {
            "type": "equipment",
            "description": "Combat-grade protective helmet with reinforced plating",
            "base_value": 950,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 8},
            "rarity": "uncommon"
        },
        "Safety Goggles": {
            "type": "equipment", 
            "description": "Transparent protective goggles for industrial use.",
            "base_value": 80,
            "equippable": True,
            "equipment_slot": "eyes",
            "stat_modifiers": {"defense": 1},
            "rarity": "common"
        },
        "Ballistic Vest": {
            "type": "equipment",
            "description": "Heavy ballistic protection vest with ceramic plates",
            "base_value": 2100,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 15, "max_hp": 10},
            "rarity": "rare"
        },
        "Light Tactical Vest": {
            "type": "equipment",
            "description": "Lightweight tactical vest offering moderate protection",
            "base_value": 1750,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 8, "navigation": 1},
            "rarity": "uncommon"
        },
        "Armored Gloves": {
            "type": "equipment",
            "description": "Heavy-duty protective gloves with reinforced knuckles",
            "base_value": 400,
            "equippable": True,
            "equipment_slot": "hands_both",
            "stat_modifiers": {"defense": 4, "combat": 1},
            "rarity": "uncommon"
        },
        "Shin Guards": {
            "type": "equipment",
            "description": "Protective leg armor for hazardous environments",
            "base_value": 320,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 3},
            "rarity": "common"
        },
        "Knee Pads": {
            "type": "equipment",
            "description": "Reinforced knee guards for mobile operations",
            "base_value": 275,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 2},
            "rarity": "common"
        },
        "Combat Boots": {
            "type": "equipment",
            "description": "Military-grade boots with steel toe protection",
            "base_value": 1600,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 5, "combat": 1},
            "rarity": "uncommon"
        },
        "Powered Exoskeleton": {
            "type": "equipment",
            "description": "Full-body powered armor with integrated life support",
            "base_value": 15000,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 30, "engineering": 3, "max_hp": 25},
            "rarity": "legendary"
        },

        # Cosmetic Clothing Items (0 Defense)
        "Casual Cap": {
            "type": "clothing",
            "description": "A simple baseball cap for everyday wear",
            "base_value": 25,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Gateworker Slacks": {
            "type": "clothing",
            "description": "Standard-issue Gate Technician pants with reinforced seams.",
            "base_value": 60,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Clown Mask": {
            "type": "clothing",
            "description": "A rubber clown mask, complete with a wig made of synthetic hairs.",
            "base_value": 160,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 0},
            "rarity": "rare"
        },
        "Platform Boots": {
            "type": "clothing",
            "description": "Clunky, elevated boots popular with urban youth.",
            "base_value": 90,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "uncommon"
        },
        "Vintage Flight Cap": {
            "type": "clothing",
            "description": "Replica of an old-Earth pilot’s cap, complete with faux leather straps.",
            "base_value": 50,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Checkered Pants": {
            "type": "clothing",
            "description": "Loud patterned pants, a favorite among station performers and eccentrics.",
            "base_value": 80,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "uncommon"
        },
        "Crop Top": {
            "type": "clothing",
            "description": "A minimalist top. Popular in warmer colonies.",
            "base_value": 55,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Polo Shirt": {
            "type": "clothing",
            "description": "Synthetic-collar shirt with a faded logo printed on the chest.",
            "base_value": 50,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Folded Bandana": {
            "type": "clothing",
            "description": "A thin band of cloth tied around the head, often used to keep sweat out of optics.",
            "base_value": 25,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Tuxedo Graphic T-Shirt": {
            "type": "clothing",
            "description": "A printed tee that looks like formalwear from ten meters away. Maybe.",
            "base_value": 60,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 0},
            "rarity": "uncommon"
        },
        "Clown Shoes": {
            "type": "clothing",
            "description": "Oversized red shoes that squeak with each step. You wear these, you live with the consequences.",
            "base_value": 140,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "rare"
        },
        "Cargo Jorts": {
            "type": "clothing",
            "description": "A pair of denim cargo shorts.",
            "base_value": 95,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "rare"
        },
        "Stylish Sunglasses": {
            "type": "clothing",
            "description": "Fashionable sunglasses that make you look cool",
            "base_value": 40,
            "equippable": True,
            "equipment_slot": "eyes", 
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Casual Shirt": {
            "type": "clothing",
            "description": "Comfortable everyday clothing",
            "base_value": 50,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Work Gloves": {
            "type": "clothing",
            "description": "Basic work gloves for manual labor",
            "base_value": 30,
            "equippable": True,
            "equipment_slot": "hands_both",
            "stat_modifiers": {"defense": 0, "engineering": 1},
            "rarity": "common"
        },
        "Work Pants": {
            "type": "clothing",
            "description": "Formal pants for professional appearances",
            "base_value": 80,
            "equippable": True,
            "equipment_slot": "legs_left",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },        
        "Insulated Boots": {
            "type": "clothing",
            "description": "Thick boots for warmth.",
            "base_value": 80,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Sweatpants": {
            "type": "clothing",
            "description": "Basic fabric sweatpants.",
            "base_value": 40,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Formal Shoes": {
            "type": "clothing",
            "description": "Polished shoes for formal occasions",
            "base_value": 120,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Cowboy Hat": {
            "type": "clothing",
            "description": "A wide brimmed cowboy hat.",
            "base_value": 75,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Leather Jacket": {
            "type": "clothing",
            "description": "A slick leather jacket.",
            "base_value": 110,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Casual Skirt": {
            "type": "clothing",
            "description": "A casual skirt made of synthetic fabric.",
            "base_value": 60,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Shutter Shades": {
            "type": "clothing",
            "description": "A relic of another time.",
            "base_value": 90,
            "equippable": True,
            "equipment_slot": "eyes",
            "stat_modifiers": {"defense": 0},
            "rarity": "rare"
        },
        
        # Work/Industrial Clothing (better for gates/outposts)
        "Safety Helmet": {
            "type": "clothing",
            "description": "Hard hat for industrial work environments",
            "base_value": 45,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 1, "engineering": 1},
            "rarity": "common"
        },
        "Work Coveralls": {
            "type": "clothing",
            "description": "Durable jumpsuit for mechanical work",
            "base_value": 85,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 1, "engineering": 2},
            "rarity": "common"
        },
        "Steel-Toe Boots": {
            "type": "clothing",
            "description": "Heavy-duty boots with reinforced toes",
            "base_value": 65,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 2},
            "rarity": "common"
        },
        "Reflective Vest": {
            "type": "clothing",
            "description": "High-visibility safety vest for hazardous areas",
            "base_value": 40,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 1},
            "rarity": "common"
        },
        
        # Casual/Civilian Clothing (better for colonies)
        "Designer Jacket": {
            "type": "clothing",
            "description": "Fashionable jacket with synthetic fur lining",
            "base_value": 150,
            "equippable": True,
            "equipment_slot": "torso",
            "stat_modifiers": {"defense": 0},
            "rarity": "uncommon"
        },
        "Comfortable Sneakers": {
            "type": "clothing",
            "description": "Soft, cushioned shoes for everyday wear",
            "base_value": 70,
            "equippable": True,
            "equipment_slot": "feet_both",
            "stat_modifiers": {"defense": 0, "navigation": 1},
            "rarity": "common"
        },
        "Casual Jeans": {
            "type": "clothing",
            "description": "Classic denim pants in good condition",
            "base_value": 90,
            "equippable": True,
            "equipment_slot": "legs_both",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        "Soft Scarf": {
            "type": "clothing",
            "description": "Warm knitted scarf for comfort",
            "base_value": 35,
            "equippable": True,
            "equipment_slot": "head",
            "stat_modifiers": {"defense": 0},
            "rarity": "common"
        },
        # Consumable Stat Modifiers
        "Performance Stimulant": {
            "type": "consumable",
            "description": "Chemical stimulant that temporarily enhances all abilities",
            "base_value": 300,
            "usage_type": "stat_modifier",
            "stat_modifiers": {"hp": 10, "engineering": 2, "navigation": 2, "combat": 2, "medical": 2},
            "modifier_duration": 3600,  # 1 hour
            "single_use": True,
            "rarity": "rare"
        },
        "Focus Pills": {
            "type": "consumable",
            "description": "Medication that improves concentration and technical skills",
            "base_value": 150,
            "usage_type": "stat_modifier", 
            "stat_modifiers": {"engineering": 3, "medical": 3},
            "modifier_duration": 1800,  # 30 minutes
            "single_use": True,
            "rarity": "uncommon"
        },
        "Recycled Brew": {
            "type": "consumable",
            "description": "Cheap, dubious alcohol distilled from reclaimed water. Tastes like regret. Gets you drunk.",
            "base_value": 30,
            "usage_type": "stat_modifier",
            "stat_modifiers": {"navigation": -5},
            "modifier_duration": 300,  # 15 minutes
            "single_use": True,
            "rarity": "common"
        },
        "Synthetic Coffee": {
            "type": "consumable",
            "description": "A bitter cup of lab-grown coffee substitute. Keeps you awake, at least.",
            "base_value": 30,
            "usage_type": "stat_modifier",
            "stat_modifiers": {"navigation": 1},
            "modifier_duration": 900,  # 45 minutes
            "single_use": True,
            "rarity": "common"
        },
        "Energy Drink": {
            "type": "consumable",
            "description": "Energy drink. High in caffeine, low in everything else.",
            "base_value": 40,
            "usage_type": "stat_modifier",
            "stat_modifiers": {"combat": 1, "medical": -2},
            "modifier_duration": 300,  # 15 minutes
            "single_use": True,
            "rarity": "common"
        },
        "Combat Adrenaline Shot": {
            "type": "consumable",
            "description": "Emergency injection that boosts combat effectiveness",
            "base_value": 200,
            "usage_type": "stat_modifier",
            "stat_modifiers": {"combat": 5, "hp": 15},
            "modifier_duration": 900,  # 15 minutes
            "single_use": True,
            "rarity": "uncommon"
        },
        "Navigator 'Juice'": {
            "type": "consumable", 
            "description": "A very special juice of secret origin that sharpens navigation skills",
            "base_value": 50,
            "usage_type": "stat_modifier",
            "stat_modifiers": {"navigation": 2},
            "modifier_duration": 2700,  # 45 minutes
            "single_use": True,
            "rarity": "common"
        }
    }
    
    BLACK_MARKET_EXCLUSIVE = [
        "Forged Transit Papers",
        "Identity Scrubber", 
        "Stolen Data Chips",
        "Unmarked Credits",
        "Weapon System Override",
    ]

    FEDERAL_DEPOT_EXCLUSIVE = [
        "Federal ID Card",
        "Military Rations",
        "Loyalty Certification",
        "Military Repair Drone",
        "Military Fuel Cell",
        "Combat Stim Injector",
        "Emergency Medical Pod"
    ]
    
    
    # Rarity weights for search results
    RARITY_WEIGHTS = {
        "common": 0.60,
        "uncommon": 0.25, 
        "rare": 0.12,
        "legendary": 0.03
    }
    
    # Location type modifiers for item spawns
    LOCATION_SPAWN_MODIFIERS = {
        "colony": {
            "medical": 1.2,
            "consumable": 1.3,
            "equipment": 0.8,  # Less functional equipment
            "clothing": 1.4,   # More casual/civilian clothing
            "fuel": 1.1,
            "trade": 0.8,
            "upgrade": 0.6
        },
        "space_station": {
            "medical": 1.1,
            "consumable": 0.9,
            "equipment": 1.3,
            "clothing": 1.1,   # Mixed clothing types
            "fuel": 1.2,
            "trade": 1.2,
            "upgrade": 1.4
        },
        "outpost": {
            "medical": 0.8,
            "consumable": 1.1,
            "equipment": 1.2,
            "clothing": 0.9,   # Some work clothing
            "fuel": 1.0,
            "trade": 0.7,
            "upgrade": 0.5
        },
        "gate": {
            "medical": 0.6,
            "consumable": 0.7,
            "equipment": 1.3,  # More functional/work equipment
            "clothing": 0.7,   # Less casual clothing, more work garments
            "fuel": 1.3,
            "trade": 0.9,
            "upgrade": 0.8
        }
    }
    
    @classmethod
    def get_items_by_rarity(cls, rarity: str, exclude_exclusive: bool = True) -> list:
        """Get all items of a specific rarity, optionally excluding exclusive items"""
        items = []
        for item_name, item_data in cls.ITEM_DEFINITIONS.items():
            if item_data.get("rarity") == rarity:
                # Skip exclusive items if requested
                if exclude_exclusive:
                    if item_name in cls.BLACK_MARKET_EXCLUSIVE or item_name in cls.FEDERAL_DEPOT_EXCLUSIVE:
                        continue
                items.append(item_name)
        return items

    @classmethod
    def is_exclusive_item(cls, item_name: str) -> tuple[bool, str]:
        """Check if an item is exclusive and return exclusivity type"""
        if item_name in cls.BLACK_MARKET_EXCLUSIVE:
            return True, "black_market"
        elif item_name in cls.FEDERAL_DEPOT_EXCLUSIVE:
            return True, "federal_depot"
        return False, None
    
    
    @classmethod
    def get_item_definition(cls, item_name: str) -> Dict[str, Any]:
        """Get item definition by name"""
        return cls.ITEM_DEFINITIONS.get(item_name, {})
    
    @classmethod
    def get_items_by_type(cls, item_type: str) -> List[str]:
        """Get all item names of a specific type"""
        return [name for name, data in cls.ITEM_DEFINITIONS.items() 
                if data.get("type") == item_type]
    
    
    @classmethod
    def generate_search_loot(cls, location_type: str, wealth_level: int) -> List[Tuple[str, int]]:
        """Generate random items for search results"""
        results = []
        
        # Base chance for finding anything
        base_find_chance = 0.15 + (wealth_level * 0.02)  # 15-35% base chance
        
        if random.random() > base_find_chance:
            return results  # Found nothing
        
        # Number of items to potentially find (1-3)
        num_items = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        
        location_modifiers = cls.LOCATION_SPAWN_MODIFIERS.get(location_type, {})
        
        for _ in range(num_items):
            # Select rarity first
            rarity = random.choices(
                list(cls.RARITY_WEIGHTS.keys()),
                weights=list(cls.RARITY_WEIGHTS.values())
            )[0]
            
            # Get items of this rarity
            rarity_items = cls.get_items_by_rarity(rarity)
            if not rarity_items:
                continue
            
            # Apply location type filtering
            filtered_items = []
            for item_name in rarity_items:
                item_data = cls.ITEM_DEFINITIONS[item_name]
                item_type = item_data["type"]
                
                # Apply location modifier
                spawn_chance = location_modifiers.get(item_type, 1.0)
                if random.random() < spawn_chance:
                    filtered_items.append(item_name)
            
            if filtered_items:
                selected_item = random.choice(filtered_items)
                quantity = 1  # Most items are single quantity
                
                # Some consumables can be found in larger quantities
                if cls.ITEM_DEFINITIONS[selected_item]["type"] == "consumable":
                    quantity = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
                
                results.append((selected_item, quantity))
        
        return results
    
    @classmethod
    def create_item_metadata(cls, item_name: str) -> str:
        """Create JSON metadata for an item"""
        import json
        item_data = cls.get_item_definition(item_name)
        
        if not item_data:
            return "{}"
        
        metadata = {
            "usage_type": item_data.get("usage_type"),
            "effect_value": item_data.get("effect_value"),
            "single_use": item_data.get("single_use", False),
            "uses_remaining": item_data.get("uses_remaining"),
            "effect_duration": item_data.get("effect_duration"),
            "rarity": item_data.get("rarity", "common")
        }
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        return json.dumps(metadata)

    @staticmethod
    def ensure_item_metadata(item_name: str, existing_metadata: str = None) -> str:
        """
        Ensures an item has proper metadata, creating it if missing or invalid.
        
        Args:
            item_name: Name of the item
            existing_metadata: Existing metadata string (JSON) or None
            
        Returns:
            Valid JSON metadata string
        """
        # Return existing metadata if it's valid and not empty
        if existing_metadata:
            try:
                # Test if it's valid JSON
                json.loads(existing_metadata)
                return existing_metadata
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Try to create metadata from ItemConfig definition
        try:
            return ItemConfig.create_item_metadata(item_name)
        except:
            # Fallback to basic metadata for items without definitions
            fallback_metadata = {
                "usage_type": "consumable",
                "effect_value": 10,
                "single_use": True,
                "uses_remaining": 1,
                "rarity": "common"
            }
            return json.dumps(fallback_metadata)

    @classmethod
    def is_equippable(cls, item_name: str) -> bool:
        """Check if an item is equippable"""
        item_data = cls.get_item_definition(item_name)
        return item_data.get("equippable", False)

    @classmethod
    def get_equipment_slot(cls, item_name: str) -> str:
        """Get the equipment slot for an item"""
        item_data = cls.get_item_definition(item_name)
        return item_data.get("equipment_slot")

    @classmethod
    def get_stat_modifiers(cls, item_name: str) -> Dict[str, int]:
        """Get stat modifiers for an item"""
        item_data = cls.get_item_definition(item_name)
        return item_data.get("stat_modifiers", {})

    @classmethod
    def get_modifier_duration(cls, item_name: str) -> int:
        """Get modifier duration for consumable items (in seconds)"""
        item_data = cls.get_item_definition(item_name)
        return item_data.get("modifier_duration", 0)

    @classmethod
    def get_equippable_items(cls) -> List[str]:
        """Get all equippable item names"""
        return [name for name, data in cls.ITEM_DEFINITIONS.items() 
                if data.get("equippable", False)]

    @classmethod
    def get_valid_equipment_slots(cls) -> List[str]:
        """Get all valid equipment slot names"""
        return [
            "head", "eyes", "torso", 
            "arms_left", "arms_right",
            "hands_left", "hands_right", "hands_both",
            "legs_left", "legs_right", "legs_both",
            "feet_left", "feet_right", "feet_both"
        ]