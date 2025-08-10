"""
Stat System - Handles character stat calculations including equipment and consumable modifiers
"""

import json
from datetime import datetime
from typing import Dict, Tuple, List
from utils.item_config import ItemConfig


class StatSystem:
    def __init__(self, db):
        self.db = db

    def get_base_stats(self, user_id: int) -> Dict[str, int]:
        """Get base character stats from the database"""
        char_data = self.db.execute_query(
            "SELECT hp, max_hp, engineering, navigation, combat, medical, defense FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return {}
        
        hp, max_hp, engineering, navigation, combat, medical, defense = char_data
        
        return {
            'hp': hp,
            'max_hp': max_hp,
            'engineering': engineering,
            'navigation': navigation,
            'combat': combat,
            'medical': medical,
            'defense': defense
        }

    def get_equipment_modifiers(self, user_id: int) -> Dict[str, int]:
        """Get stat modifiers from equipped items"""
        # Get all equipped items
        equipped_items = self.db.execute_query(
            '''SELECT i.item_name, ce.slot_name
               FROM character_equipment ce
               JOIN inventory i ON ce.item_id = i.item_id
               WHERE ce.user_id = %s''',
            (user_id,),
            fetch='all'
        )
        
        total_modifiers = {}
        
        for item_name, slot_name in equipped_items:
            # Get stat modifiers for this item from ItemConfig
            modifiers = ItemConfig.get_stat_modifiers(item_name)
            
            # Handle special slots for paired items
            if slot_name.endswith('_both'):
                # Paired items (like gloves or boots) apply full effect
                for stat, value in modifiers.items():
                    total_modifiers[stat] = total_modifiers.get(stat, 0) + value
            else:
                # Regular single-slot items
                for stat, value in modifiers.items():
                    total_modifiers[stat] = total_modifiers.get(stat, 0) + value
        
        return total_modifiers

    def get_consumable_modifiers(self, user_id: int) -> Dict[str, int]:
        """Get stat modifiers from active consumable effects"""
        current_time = datetime.utcnow()
        
        # Clean up expired modifiers first
        self.db.execute_query(
            "DELETE FROM active_stat_modifiers WHERE expires_at < %s",
            (current_time,)
        )
        
        # Get active consumable modifiers
        active_modifiers = self.db.execute_query(
            '''SELECT stat_name, modifier_value
               FROM active_stat_modifiers
               WHERE user_id = %s AND source_type = 'consumable' 
               AND (expires_at IS NULL OR expires_at > %s)''',
            (user_id, current_time),
            fetch='all'
        )
        
        total_modifiers = {}
        for stat_name, modifier_value in active_modifiers:
            total_modifiers[stat_name] = total_modifiers.get(stat_name, 0) + modifier_value
        
        return total_modifiers

    def calculate_effective_stats(self, user_id: int) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Calculate effective stats including all modifiers
        
        Returns:
            Tuple of (base_stats, effective_stats)
        """
        base_stats = self.get_base_stats(user_id)
        if not base_stats:
            return {}, {}
        
        equipment_mods = self.get_equipment_modifiers(user_id)
        consumable_mods = self.get_consumable_modifiers(user_id)
        
        effective_stats = base_stats.copy()
        
        # Apply equipment modifiers
        for stat, value in equipment_mods.items():
            if stat in effective_stats:
                effective_stats[stat] += value
        
        # Apply consumable modifiers
        for stat, value in consumable_mods.items():
            if stat in effective_stats:
                effective_stats[stat] += value
        
        # Ensure stats don't go below 0
        for stat in effective_stats:
            effective_stats[stat] = max(0, effective_stats[stat])
        
        return base_stats, effective_stats

    def get_stat_modifiers_summary(self, user_id: int) -> Dict[str, Dict[str, int]]:
        """
        Get a summary of all active stat modifiers by source
        
        Returns:
            Dict with 'equipment' and 'consumable' keys containing modifier dicts
        """
        return {
            'equipment': self.get_equipment_modifiers(user_id),
            'consumable': self.get_consumable_modifiers(user_id)
        }

    def equip_item(self, user_id: int, item_id: int, item_name: str) -> bool:
        """
        Equip an item to the appropriate slot
        
        Returns:
            True if successful, False if failed
        """
        # Check if item is equippable and get equipment slot
        slot = ItemConfig.get_equipment_slot(item_name)
        is_equippable = ItemConfig.is_equippable(item_name)
        
        # If not found in predefined items, check custom item metadata
        if not is_equippable or not slot:
            custom_item = self.db.execute_query(
                "SELECT metadata FROM inventory WHERE item_id = %s AND item_name = %s",
                (item_id, item_name),
                fetch='one'
            )
            if custom_item and custom_item[0]:
                try:
                    import json
                    metadata = json.loads(custom_item[0])
                    if not is_equippable:
                        is_equippable = metadata.get('equippable', False)
                    if not slot:
                        slot = metadata.get('equipment_slot')
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # Final validation
        if not is_equippable or not slot:
            return False
        
        # Handle paired items (hands_both, feet_both, legs_both)
        if slot.endswith('_both'):
            base_slot = slot.replace('_both', '')
            slots_to_check = [f"{base_slot}_left", f"{base_slot}_right"]
            
            # Automatically unequip any conflicting items
            for check_slot in slots_to_check:
                existing = self.db.execute_query(
                    "SELECT equipment_id FROM character_equipment WHERE user_id = %s AND slot_name = %s",
                    (user_id, check_slot),
                    fetch='one'
                )
                if existing:
                    # Unequip the conflicting item
                    self.db.execute_query(
                        "DELETE FROM character_equipment WHERE user_id = %s AND slot_name = %s",
                        (user_id, check_slot)
                    )
            
            # Equip to both slots
            for slot_name in slots_to_check:
                self.db.execute_query(
                    '''INSERT INTO character_equipment (user_id, slot_name, item_id)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, slot_name) DO UPDATE SET
                       item_id = EXCLUDED.item_id,
                       equipped_at = NOW()''',
                    (user_id, slot_name, item_id)
                )
        else:
            # Regular single slot
            # Check if slot is occupied
            existing = self.db.execute_query(
                "SELECT equipment_id FROM character_equipment WHERE user_id = %s AND slot_name = %s",
                (user_id, slot),
                fetch='one'
            )
            if existing:
                return False  # Slot occupied
            
            # Equip the item
            self.db.execute_query(
                '''INSERT INTO character_equipment (user_id, slot_name, item_id)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, slot_name) DO UPDATE SET
                   item_id = EXCLUDED.item_id,
                   equipped_at = NOW()''',
                (user_id, slot, item_id)
            )
        
        return True

    def unequip_item(self, user_id: int, slot_name: str) -> bool:
        """
        Unequip an item from a specific slot
        
        Returns:
            True if successful, False if slot was empty
        """
        # Check if slot has an item
        existing = self.db.execute_query(
            "SELECT equipment_id FROM character_equipment WHERE user_id = %s AND slot_name = %s",
            (user_id, slot_name),
            fetch='one'
        )
        
        if not existing:
            return False  # Nothing to unequip
        
        # Handle paired items - if this is a left/right slot, check for the pair
        if slot_name.endswith('_left') or slot_name.endswith('_right'):
            base_name = slot_name.rsplit('_', 1)[0]
            pair_slot = f"{base_name}_{'right' if slot_name.endswith('_left') else 'left'}"
            
            # Get the item from the current slot
            current_item = self.db.execute_query(
                '''SELECT i.item_name
                   FROM character_equipment ce
                   JOIN inventory i ON ce.item_id = i.item_id
                   WHERE ce.user_id = %s AND ce.slot_name = %s''',
                (user_id, slot_name),
                fetch='one'
            )
            
            if current_item:
                item_name = current_item[0]
                item_slot = ItemConfig.get_equipment_slot(item_name)
                
                # If this is a paired item, unequip from both slots
                if item_slot and item_slot.endswith('_both'):
                    self.db.execute_query(
                        "DELETE FROM character_equipment WHERE user_id = %s AND slot_name IN (%s, %s)",
                        (user_id, slot_name, pair_slot)
                    )
                    return True
        
        # Regular single slot unequip
        self.db.execute_query(
            "DELETE FROM character_equipment WHERE user_id = %s AND slot_name = %s",
            (user_id, slot_name)
        )
        
        return True

    def get_equipped_items(self, user_id: int) -> Dict[str, Dict]:
        """
        Get all equipped items organized by slot
        
        Returns:
            Dict with slot names as keys and item info as values
        """
        equipped_items = self.db.execute_query(
            '''SELECT ce.slot_name, i.item_name, i.description, i.item_id
               FROM character_equipment ce
               JOIN inventory i ON ce.item_id = i.item_id
               WHERE ce.user_id = %s
               ORDER BY ce.slot_name''',
            (user_id,),
            fetch='all'
        )
        
        result = {}
        for slot_name, item_name, description, item_id in equipped_items:
            result[slot_name] = {
                'name': item_name,
                'description': description,
                'item_id': item_id,
                'modifiers': ItemConfig.get_stat_modifiers(item_name)
            }
        
        return result

    def add_consumable_modifier(self, user_id: int, item_name: str, stat_modifiers: Dict[str, int], 
                               duration_seconds: int = None) -> bool:
        """
        Add temporary stat modifiers from a consumable item
        
        Args:
            user_id: Character ID
            item_name: Name of the consumed item
            stat_modifiers: Dict of stat_name -> modifier_value
            duration_seconds: Duration in seconds (None for permanent)
        
        Returns:
            True if successful
        """
        expires_at = None
        if duration_seconds:
            from datetime import timedelta
            expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
        
        # Add each stat modifier
        for stat_name, modifier_value in stat_modifiers.items():
            self.db.execute_query(
                '''INSERT INTO active_stat_modifiers 
                   (user_id, modifier_type, stat_name, modifier_value, source_type, source_item_name, expires_at)
                   VALUES (%s, 'buff', %s, %s, 'consumable', %s, %s)''',
                (user_id, stat_name, modifier_value, item_name, expires_at)
            )
        
        return True

    def format_stat_display(self, base_value: int, effective_value: int) -> str:
        """
        Format stat for display showing base and modifier
        
        Args:
            base_value: Base stat value
            effective_value: Effective stat value (base + modifiers)
        
        Returns:
            Formatted string like "15 (+3)" or "12" if no modifier
        """
        modifier = effective_value - base_value
        
        if modifier == 0:
            return str(base_value)
        elif modifier > 0:
            return f"{base_value} (+{modifier})"
        else:
            return f"{base_value} ({modifier})"  # modifier is already negative
    
    def calculate_damage_reduction(self, user_id: int, incoming_damage: int) -> Tuple[int, int]:
        """
        Calculate damage reduction based on character's defense stat
        
        Args:
            user_id: Character ID
            incoming_damage: Original damage amount
            
        Returns:
            Tuple of (final_damage, damage_reduced)
        """
        if incoming_damage <= 0:
            return 0, 0
        
        # Get effective defense stat
        base_stats, effective_stats = self.calculate_effective_stats(user_id)
        
        if not effective_stats:
            return incoming_damage, 0
        
        defense_value = effective_stats.get('defense', 0)
        
        if defense_value <= 0:
            return incoming_damage, 0
        
        # Cap defense at 90% reduction
        defense_percentage = min(defense_value, 90)
        
        # Calculate damage reduction
        damage_reduced = (incoming_damage * defense_percentage) / 100
        damage_reduced = round(damage_reduced)  # Round to nearest whole number
        
        final_damage = max(0, incoming_damage - damage_reduced)
        
        return final_damage, damage_reduced