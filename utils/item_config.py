import random
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
        "Recycled Brew": {
            "type": "consumable",
            "description": "Cheap, dubious alcohol distilled from reclaimed water. Tastes like regret.",
            "base_value": 4,
            "usage_type": "heal_hp",
            "effect_value": 2,
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

        "Synthetic Coffee": {
            "type": "consumable",
            "description": "A bitter cup of lab-grown coffee substitute. Keeps you awake, at least.",
            "base_value": 5,
            "usage_type": "heal_hp",
            "effect_value": 2,
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

        "Energy Drink": {
            "type": "consumable",
            "description": "Energy drink. High in caffeine, low in everything else.",
            "base_value": 3,
            "usage_type": "heal_hp",
            "effect_value": 2,
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
            "equipment": 1.0,
            "fuel": 1.1,
            "trade": 0.8,
            "upgrade": 0.6
        },
        "space_station": {
            "medical": 1.1,
            "consumable": 0.9,
            "equipment": 1.3,
            "fuel": 1.2,
            "trade": 1.2,
            "upgrade": 1.4
        },
        "outpost": {
            "medical": 0.8,
            "consumable": 1.1,
            "equipment": 1.2,
            "fuel": 1.0,
            "trade": 0.7,
            "upgrade": 0.5
        },
        "gate": {
            "medical": 0.6,
            "consumable": 0.7,
            "equipment": 1.1,
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