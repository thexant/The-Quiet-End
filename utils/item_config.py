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
            "base_value": 50,
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
            "effect_value": 60,
            "single_use": True,
            "rarity": "uncommon"
        },
        "Combat Stims": {
            "type": "medical",
            "description": "Performance enhancing drugs that provide temporary benefits",
            "base_value": 80,
            "usage_type": "temp_boost",
            "effect_value": 10,
            "effect_duration": 3600,  # 1 hour in seconds
            "single_use": True,
            "rarity": "uncommon"
        },
        "Radiation Treatment": {
            "type": "medical",
            "description": "Treats radiation exposure and poisoning",
            "base_value": 120,
            "usage_type": "cure_condition",
            "effect_value": "radiation",
            "single_use": True,
            "rarity": "rare"
        },
        "Basic Tools": {
            "type": "equipment",
            "description": "Standard repair tools for basic maintenance",
            "base_value": 50,
            "usage_type": "repair_hull",
            "effect_value": 5,
            "uses_remaining": 5,
            "rarity": "common"
        },

        "Emergency Beacon": {
            "type": "equipment", 
            "description": "One-time use distress signal broadcaster",
            "base_value": 200,
            "usage_type": "emergency_beacon",
            "effect_value": 1,
            "single_use": True,
            "rarity": "uncommon"
        },

        "Data Beacon": {
            "type": "equipment",
            "description": "Transmits data packets through radio networks",
            "base_value": 150,
            "usage_type": "data_beacon", 
            "effect_value": 1,
            "single_use": True,
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

        "Signal Booster": {
            "type": "equipment", 
            "description": "Temporarily amplifies radio transmission power",
            "base_value": 250,
            "usage_type": "signal_boost",
            "effect_value": 50,  # +50% range
            "effect_duration": 3600,  # 1 hour
            "single_use": True,
            "rarity": "uncommon"
        },
        # Consumable Items
        "Emergency Rations": {
            "type": "consumable",
            "description": "Basic food supplies that restore energy",
            "base_value": 20,
            "usage_type": "restore_energy",
            "effect_value": 15,
            "single_use": True,
            "rarity": "common"
        },
        "Protein Bars": {
            "type": "consumable",
            "description": "High-energy manufactured food",
            "base_value": 15,
            "usage_type": "restore_energy", 
            "effect_value": 10,
            "single_use": True,
            "rarity": "common"
        },
        "Stimulant Pack": {
            "type": "consumable",
            "description": "Reduces fatigue and improves alertness temporarily",
            "base_value": 45,
            "usage_type": "temp_boost",
            "effect_value": 5,
            "effect_duration": 1800,  # 30 minutes
            "single_use": True,
            "rarity": "uncommon"
        },
        
        # Equipment Items
        "Repair Kit": {
            "type": "equipment",
            "description": "Tools for repairing ship hull damage",
            "base_value": 100,
            "usage_type": "repair_hull",
            "effect_value": 30,
            "uses_remaining": 3,
            "rarity": "common"
        },
        "Emergency Beacon": {
            "type": "equipment",
            "description": "One-time use distress signal broadcaster",
            "base_value": 200,
            "usage_type": "emergency_signal",
            "effect_value": 1,
            "single_use": True,
            "rarity": "uncommon"
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
            "base_value": 30,
            "usage_type": "restore_fuel",
            "effect_value": 25,
            "single_use": True,
            "rarity": "common"
        },
        "High-Grade Fuel": {
            "type": "fuel",
            "description": "Premium fuel with improved efficiency",
            "base_value": 75,
            "usage_type": "restore_fuel",
            "effect_value": 50,
            "single_use": True,
            "rarity": "uncommon"
        },
        
        # Trade Items (RP/Narrative only)
        "Data Chip": {
            "type": "trade",
            "description": "Contains valuable information or entertainment",
            "base_value": 40,
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
        "Artifact": {
            "type": "trade",
            "description": "Artifact from a lost colony",
            "base_value": 500,
            "usage_type": "narrative",
            "effect_value": "mysterious",
            "single_use": False,
            "rarity": "legendary"
        },
        # Add this entry to the ITEM_DEFINITIONS dictionary
        "Personal Log": {
            "type": "equipment",
            "description": "A digital logbook for recording personal entries and memories",
            "base_value": 120,
            "usage_type": "personal_log",
            "effect_value": 1,
            "single_use": False,
            "rarity": "uncommon"
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
        }
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

        "Neural Interface Hack": {
            "type": "software",
            "description": "Illegal consciousness enhancement technology",
            "base_value": 4500,
            "usage_type": "temp_boost",
            "effect_value": 15,
            "effect_duration": 7200,  # 2 hours
            "single_use": True,
            "rarity": "rare"
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
            "usage_type": "restore_energy",
            "effect_value": 25,
            "single_use": True,
            "rarity": "uncommon"
        },

        "Federal Comm Codes": {
            "type": "data",
            "description": "Access codes for federal communication networks",
            "base_value": 3000,
            "usage_type": "comm_access",
            "effect_value": "federal_channels",
            "single_use": False,
            "rarity": "rare"
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

        "Federal Permit": {
            "type": "documents",
            "description": "Authorization for restricted activities in federal space",
            "base_value": 1500,
            "usage_type": "permit_access", 
            "effect_value": "restricted_zones",
            "single_use": False,
            "rarity": "rare"
        },

        "Military Scanner Array": {
            "type": "equipment",
            "description": "Advanced military-grade scanning equipment",
            "base_value": 2500,
            "usage_type": "search_boost",
            "effect_value": 40,  # +40% search success rate
            "uses_remaining": 15,
            "rarity": "rare"
        },

        "Federal Security Override": {
            "type": "software",
            "description": "Authorized security bypass codes for federal personnel",
            "base_value": 5000,
            "usage_type": "security_override",
            "effect_value": "federal_bypass",
            "uses_remaining": 3,
            "rarity": "legendary"
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
    def get_item_definition(cls, item_name: str) -> Dict[str, Any]:
        """Get item definition by name"""
        return cls.ITEM_DEFINITIONS.get(item_name, {})
    
    @classmethod
    def get_items_by_type(cls, item_type: str) -> List[str]:
        """Get all item names of a specific type"""
        return [name for name, data in cls.ITEM_DEFINITIONS.items() 
                if data.get("type") == item_type]
    
    @classmethod
    def get_items_by_rarity(cls, rarity: str) -> List[str]:
        """Get all item names of a specific rarity"""
        return [name for name, data in cls.ITEM_DEFINITIONS.items()
                if data.get("rarity") == rarity]
    
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