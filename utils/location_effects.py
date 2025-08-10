# utils/location_effects.py
from typing import Dict, List, Optional, Any
from datetime import datetime
from utils.datetime_utils import safe_datetime_parse

class LocationEffectsManager:
    """Utility class for managing and querying location effects"""
    
    def __init__(self, database):
        self.db = database
    
    def get_travel_modifiers(self, location_id: int) -> Dict[str, Any]:
        """Get travel-related effects for a location"""
        effects = self.db.get_active_location_effects(location_id)
        
        modifiers = {
            'travel_danger': 0,
            'travel_delay': 0,
            'travel_ban': False,
            'fuel_efficiency': 1.0,
            'travel_bonus': 0
        }
        
        for effect_type, effect_value, source_event, created_at, expires_at in effects:
            if effect_type == 'travel_danger':
                modifiers['travel_danger'] += int(effect_value)
            elif effect_type == 'travel_delay':
                modifiers['travel_delay'] += int(effect_value)
            elif effect_type == 'travel_ban':
                modifiers['travel_ban'] = bool(effect_value)
            elif effect_type == 'fuel_efficiency':
                modifiers['fuel_efficiency'] *= float(effect_value)
            elif effect_type == 'travel_bonus':
                modifiers['travel_bonus'] += int(effect_value)
        
        return modifiers
    
    def get_economic_modifiers(self, location_id: int) -> Dict[str, Any]:
        """Get economy-related effects for a location"""
        effects = self.db.get_active_location_effects(location_id)
        
        modifiers = {
            'wealth_bonus': 0,
            'efficiency_bonus': 0,
            'job_bonus': 0,
            'upgrade_discount': 0.0,
            'price_modifier': 1.0
        }
        
        for effect_type, effect_value, source_event, created_at, expires_at in effects:
            if effect_type == 'wealth_bonus':
                modifiers['wealth_bonus'] += int(effect_value)
            elif effect_type == 'efficiency_bonus':
                modifiers['efficiency_bonus'] += int(effect_value)
            elif effect_type == 'job_bonus':
                modifiers['job_bonus'] += int(effect_value)
            elif effect_type == 'upgrade_discount':
                modifiers['upgrade_discount'] += float(effect_value)
            elif effect_type == 'price_modifier':
                modifiers['price_modifier'] *= float(effect_value)
        
        return modifiers
    
    def get_danger_level(self, location_id: int) -> int:
        """Get current danger level from active effects"""
        effects = self.db.get_active_location_effects(location_id)
        danger_level = 0
        
        for effect_type, effect_value, source_event, created_at, expires_at in effects:
            if effect_type == 'danger_level':
                danger_level += int(effect_value)
        
        return max(0, danger_level)
    
    def get_active_effect_descriptions(self, location_id: int) -> List[str]:
        """Get human-readable descriptions of active effects"""
        effects = self.db.get_active_location_effects(location_id)
        descriptions = []
        
        effect_descriptions = {
            'travel_danger': "⚠️ Increased travel danger",
            'travel_delay': "⏱️ Travel delays expected", 
            'travel_ban': "🚫 Travel restrictions in effect",
            'travel_bonus': "✈️ Enhanced travel efficiency",
            'fuel_efficiency': "⛽ Fuel efficiency modified",
            'wealth_bonus': "💰 Economic prosperity boost",
            'efficiency_bonus': "⚡ Improved operational efficiency",
            'job_bonus': "👷 Enhanced job opportunities",
            'upgrade_discount': "🔧 Equipment upgrade discounts",
            'danger_level': "💀 Elevated security threat",
            'security_bonus': "🛡️ Enhanced security presence"
        }
        
        for effect_type, effect_value, source_event, created_at, expires_at in effects:
            if effect_type in effect_descriptions:
                desc = effect_descriptions[effect_type]
                if expires_at:
                    expire_time = safe_datetime_parse(expires_at)
                    time_left = expire_time - datetime.now()
                    total_seconds = max(0, int(time_left.total_seconds()))
                    hours_left = total_seconds // 3600
                    minutes_left = (total_seconds % 3600) // 60
                    
                    if hours_left > 0:
                        desc += f" ({hours_left}h {minutes_left}m remaining)"
                    elif minutes_left > 0:
                        desc += f" ({minutes_left}m remaining)"
                    else:
                        desc += " (expires soon)"
                descriptions.append(f"{desc} - *{source_event}*")
        
        return descriptions
    
    def has_effect(self, location_id: int, effect_type: str) -> bool:
        """Check if a location has a specific type of effect active"""
        effects = self.db.get_active_location_effects(location_id)
        
        for eff_type, effect_value, source_event, created_at, expires_at in effects:
            if eff_type == effect_type:
                return True
        return False
    
    def cleanup_all_expired_effects(self) -> int:
        """Clean up all expired effects and return count removed"""
        return self.db.cleanup_expired_effects()