# utils/item_effects.py
# Add this new file to your utils folder

import json
from datetime import datetime, timezone, timedelta
from utils.datetime_utils import safe_datetime_parse
class ItemEffectChecker:
    """Helper class to check for active item effects"""
    
    LOCAL_TZ = timezone(timedelta(hours=-6))
    
    def __init__(self, db):
        self.db = db
    def has_security_bypass(self, user_id):
        """Check if user has active Forged Transit Papers - Fixed timezone"""
        bypass_check = self.db.execute_query(
            """SELECT metadata FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Security Bypass'
               AND metadata IS NOT NULL""",
            (user_id,),
            fetch='one'
        )
        
        if bypass_check and bypass_check[0]:
            metadata = json.loads(bypass_check[0])
            if 'active_until' in metadata:
                expire_time = safe_datetime_parse(metadata['active_until'])
                # Ensure timezone awareness
                if expire_time.tzinfo is None:
                    expire_time = expire_time.replace(tzinfo=timezone.utc)
                
                # Compare with local time
                current_time = datetime.now(self.LOCAL_TZ)
                return expire_time > current_time
        return False
    
    def has_federal_access(self, user_id):
        """Check if user has Federal ID Card"""
        access_check = self.db.execute_query(
            """SELECT item_id FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Federal Access'""",
            (user_id,),
            fetch='one'
        )
        return bool(access_check)
    
    def has_security_override(self, user_id):
        """Check if user has active Federal Security Override"""
        override_check = self.db.execute_query(
            """SELECT metadata FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Security Override'""",
            (user_id,),
            fetch='one'
        )
        
        if override_check and override_check[0]:
            metadata = json.loads(override_check[0])
            expire_time = safe_datetime_parse(metadata['active_until'])
            # Ensure timezone awareness
            if expire_time and expire_time.tzinfo is None:
                expire_time = expire_time.replace(tzinfo=timezone.utc)
            
            # Compare with local time
            current_time = datetime.now(self.LOCAL_TZ)
            return expire_time > current_time
        return False
    
    def get_federal_comm_channels(self, user_id):
        """Get available federal communication channels"""
        comm_check = self.db.execute_query(
            """SELECT metadata FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Federal Communications'""",
            (user_id,),
            fetch='one'
        )
        
        if comm_check and comm_check[0]:
            try:
                metadata = json.loads(comm_check[0])
                return metadata.get('comm_channels', [])
            except json.JSONDecodeError:
                return []
        return []
    
    def has_federal_permit(self, user_id):
        """Check if user has Federal Permit for restricted zones"""
        permit_check = self.db.execute_query(
            """SELECT item_id FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Federal Permit'""",
            (user_id,),
            fetch='one'
        )
        return bool(permit_check)
    
    def get_scanner_boost(self, user_id):
        """Get active scanner array boost percentage"""
        scanner_check = self.db.execute_query(
            """SELECT metadata FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Scanner Array'""",
            (user_id,),
            fetch='one'
        )
        
        if scanner_check and scanner_check[0]:
            try:
                metadata = json.loads(scanner_check[0])
                expire_time = safe_datetime_parse(metadata['active_until'])
                # Ensure timezone awareness
                if expire_time and expire_time.tzinfo is None:
                    expire_time = expire_time.replace(tzinfo=timezone.utc)
                
                # Compare with local time
                current_time = datetime.now(self.LOCAL_TZ)
                if expire_time > current_time:
                    return metadata.get('boost_value', 0)
            except (json.JSONDecodeError, KeyError):
                pass
        return 0
    
    def get_combat_boost(self, user_id):
        """Get active combat stim boost"""
        stim_check = self.db.execute_query(
            """SELECT metadata FROM inventory 
               WHERE owner_id = %s AND item_name = 'Active: Combat Stims'""",
            (user_id,),
            fetch='one'
        )
        
        if stim_check and stim_check[0]:
            metadata = json.loads(stim_check[0])
            expire_time = safe_datetime_parse(metadata['active_until'])
            # Ensure timezone awareness
            if expire_time and expire_time.tzinfo is None:
                expire_time = expire_time.replace(tzinfo=timezone.utc)
            
            # Compare with local time
            current_time = datetime.now(self.LOCAL_TZ)
            if expire_time > current_time:
                return metadata.get('boost_value', 0)
        return 0
    
    def cleanup_expired_effects(self):
        """Remove expired temporary effects"""
        self.db.execute_query(
            """DELETE FROM inventory 
               WHERE item_name LIKE 'Active:%' 
               AND metadata LIKE '%active_until%'
               AND CAST(metadata->>'active_until' AS TIMESTAMP) < NOW()"""
        )
        
    def get_all_active_effects(self, user_id):
        """Get summary of all active effects for a user"""
        effects = []
        
        # Check each effect type
        if self.has_security_bypass(user_id):
            effects.append("🎫 Security Bypass (Forged Papers)")
        
        if self.has_federal_access(user_id):
            effects.append("🆔 Federal Access (ID Card)")
        
        if self.has_security_override(user_id):
            effects.append("🔓 Security Override (Temporary)")
        
        comms = self.get_federal_comm_channels(user_id)
        if comms:
            effects.append(f"📡 Federal Comms ({len(comms)} channels)")
        
        if self.has_federal_permit(user_id):
            effects.append("📜 Federal Permit (Restricted Zones)")
        
        scanner = self.get_scanner_boost(user_id)
        if scanner > 0:
            effects.append(f"🔍 Scanner Boost (+{scanner}%)")
        
        combat = self.get_combat_boost(user_id)
        if combat > 0:
            effects.append(f"💉 Combat Stims (+{combat})")
        
        return effects