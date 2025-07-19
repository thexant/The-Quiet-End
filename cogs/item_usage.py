import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid
import random

class ItemUsageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    def get_narrative_usage_message(self, character_name, item_name):
        """Generate varied narrative usage messages"""
        messages = [
            f"**{character_name}** uses **{item_name}**."
        ]
        return random.choice(messages)
        
    @app_commands.command(name="use", description="Use an item from your inventory")
    @app_commands.describe(item_name="Name of the item to use")
    async def use_item(self, interaction: discord.Interaction, item_name: str):
        # MODIFY THIS QUERY TO INCLUDE CHARACTER NAME
        char_data = self.db.execute_query(
            "SELECT user_id, current_location, hp, max_hp, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("You don't have a character!", ephemeral=True)
            return
        
        # UPDATE THIS LINE TO INCLUDE CHARACTER NAME
        user_id, current_location, current_hp, max_hp, character_name = char_data
        
        # Find item in inventory
        item_data = self.db.execute_query(
            '''SELECT item_id, item_name, item_type, quantity, description, value, metadata
               FROM inventory 
               WHERE owner_id = ? AND LOWER(item_name) LIKE LOWER(?) AND quantity > 0''',
            (interaction.user.id, f"%{item_name}%"),
            fetch='one'
        )
        
        if not item_data:
            await interaction.response.send_message(f"You don't have any '{item_name}' in your inventory.", ephemeral=True)
            return
        
        item_id, actual_name, item_type, quantity, description, value, metadata_str = item_data
        
        # Parse metadata
        try:
            metadata = json.loads(metadata_str) if metadata_str else {}
        except json.JSONDecodeError:
            metadata = {}
        
        usage_type = metadata.get("usage_type")
        
        # REPLACE THE EXISTING NARRATIVE ITEM HANDLING WITH THIS
        if not usage_type or usage_type == "narrative":
            if usage_type == "narrative" or not usage_type:
                # Get uses_remaining for narrative items
                uses_remaining = metadata.get("uses_remaining")
                single_use = metadata.get("single_use", False)
                
                # Check if item has uses remaining
                if uses_remaining is not None and uses_remaining <= 0:
                    embed = discord.Embed(
                        title="❌ Item Depleted",
                        description=f"**{actual_name}** has no uses remaining.",
                        color=0xff4444
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                # Generate narrative usage message with character name
                usage_message = self.get_narrative_usage_message(character_name, actual_name)
                
                embed = discord.Embed(
                    title="📖 Narrative Item Used",
                    description=f"{usage_message}\n\n*{description}*",
                    color=0x4169E1
                )
                
                # Handle uses system for narrative items
                item_consumed = False
                uses_text = ""
                
                if single_use or uses_remaining == 1:
                    # Remove item completely
                    if quantity == 1:
                        self.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (item_id,))
                    else:
                        self.db.execute_query(
                            "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?",
                            (item_id,)
                        )
                    item_consumed = True
                    uses_text = "This item has been consumed."
                    
                elif uses_remaining is not None and uses_remaining > 1:
                    # Decrease uses remaining
                    new_uses = uses_remaining - 1
                    metadata["uses_remaining"] = new_uses
                    new_metadata = json.dumps(metadata)
                    
                    self.db.execute_query(
                        "UPDATE inventory SET metadata = ? WHERE item_id = ?",
                        (new_metadata, item_id)
                    )
                    
                    if new_uses == 1:
                        uses_text = f"**1 use remaining** - this item will be consumed on next use."
                    else:
                        uses_text = f"**{new_uses} uses remaining**"
                        
                elif uses_remaining is None:
                    # Unlimited uses
                    uses_text = "This item can be used repeatedly."
                
                if uses_text:
                    embed.add_field(name="Usage", value=uses_text, inline=False)
                
                # Add flavor text about roleplay usage
                embed.add_field(
                    name="Effect", 
                    value="The narrative effects of using this item are determined through roleplay.", 
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=False)
                return
        
        # REST OF THE METHOD REMAINS THE SAME
        # Check if item has uses remaining
        uses_remaining = metadata.get("uses_remaining")
        if uses_remaining is not None and uses_remaining <= 0:
            await interaction.response.send_message(f"**{actual_name}** has no uses remaining.", ephemeral=True)
            return
        
        # Apply item effect
        result = await self._apply_item_effect(interaction.user.id, usage_type, metadata, actual_name, item_id)

        if not result["success"]:
            await interaction.response.send_message(result["message"], ephemeral=True)
            return

        # Check if this requires special interaction
        if result.get("requires_interaction"):
            embed = result.get("embed")
            view = result.get("view")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Update inventory
        single_use = metadata.get("single_use", False)
        if single_use or (uses_remaining and uses_remaining <= 1):
            # Remove item completely
            if quantity == 1:
                self.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (item_id,))
            else:
                self.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?", 
                    (item_id,)
                )
        elif uses_remaining:
            # Decrease uses remaining
            metadata["uses_remaining"] = uses_remaining - 1
            new_metadata = json.dumps(metadata)
            self.db.execute_query(
                "UPDATE inventory SET metadata = ? WHERE item_id = ?",
                (new_metadata, item_id)
            )
        
        # Create success embed
        embed = discord.Embed(
            title="✅ Item Used",
            description=f"Successfully used **{actual_name}**",
            color=0x00ff00
        )
        embed.add_field(name="Effect", value=result["message"], inline=False)
        
        # Add remaining uses info
        if uses_remaining and uses_remaining > 1:
            embed.add_field(name="Uses Remaining", value=str(uses_remaining - 1), inline=True)
        elif not single_use and quantity > 1:
            embed.add_field(name="Quantity Remaining", value=str(quantity - 1), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _apply_item_effect(self, user_id: int, usage_type: str, metadata: Dict[str, Any], item_name: str, item_id: int) -> Dict[str, Any]:
        """Apply the effect of using an item"""
        effect_value = metadata.get("effect_value")
        
        if usage_type == "heal_hp":
            # Heal HP
            char_data = self.db.execute_query(
                "SELECT hp, max_hp FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            if not char_data:
                return {"success": False, "message": "Character not found"}
            
            current_hp, max_hp = char_data
            heal_amount = min(effect_value, max_hp - current_hp)
            
            if heal_amount <= 0:
                return {"success": False, "message": "You are already at full health!"}
            
            self.db.execute_query(
                "UPDATE characters SET hp = hp + ? WHERE user_id = ?",
                (heal_amount, user_id)
            )
            
            return {"success": True, "message": f"Restored {heal_amount} HP"}
        
        elif usage_type == "restore_fuel":
            # Restore ship fuel
            ship_data = self.db.execute_query(
                "SELECT current_fuel, fuel_capacity FROM ships WHERE owner_id = ?",
                (user_id,), fetch='one'
            )
            if not ship_data:
                return {"success": False, "message": "No ship found"}
            
            current_fuel, fuel_capacity = ship_data
            fuel_amount = min(effect_value, fuel_capacity - current_fuel)
            
            if fuel_amount <= 0:
                return {"success": False, "message": "Ship fuel tank is already full!"}
            
            self.db.execute_query(
                "UPDATE ships SET current_fuel = current_fuel + ? WHERE owner_id = ?",
                (fuel_amount, user_id)
            )
            
            return {"success": True, "message": f"Restored {fuel_amount} fuel units"}
        
        elif usage_type == "repair_hull":
            # Repair ship hull
            ship_data = self.db.execute_query(
                "SELECT hull_integrity, max_hull FROM ships WHERE owner_id = ?",
                (user_id,), fetch='one'
            )
            if not ship_data:
                return {"success": False, "message": "No ship found"}
            
            current_hull, max_hull = ship_data
            repair_amount = min(effect_value, max_hull - current_hull)
            
            if repair_amount <= 0:
                return {"success": False, "message": "Ship hull is already at maximum integrity!"}
            
            self.db.execute_query(
                "UPDATE ships SET hull_integrity = hull_integrity + ? WHERE owner_id = ?",
                (repair_amount, user_id)
            )
            
            return {"success": True, "message": f"Repaired {repair_amount} hull integrity"}
        
        elif usage_type == "restore_energy":
            # This could restore a future energy/stamina system
            return {"success": True, "message": f"Restored energy (+{effect_value})"}
        
        elif usage_type == "temp_boost":
            # Temporary boost - could be implemented with a buffs system later
            duration = metadata.get("effect_duration", 3600)
            return {"success": True, "message": f"Gained temporary boost (+{effect_value}) for {duration//60} minutes"}
        elif usage_type == "deploy_repeater":
            # Deploy radio repeater
            char_data = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            
            if not char_data or not char_data[0]:
                return {"success": False, "message": "Cannot deploy repeater while stranded in space!"}
            
            location_id = char_data[0]
            
            # Check if there's already a repeater at this location
            existing_repeater = self.db.execute_query(
                "SELECT repeater_id FROM repeaters WHERE location_id = ? AND is_active = 1",
                (location_id,), fetch='one'
            )
            
            if existing_repeater:
                return {"success": False, "message": "There is already an active repeater at this location!"}
            
            # Deploy the repeater
            self.db.execute_query(
                '''INSERT INTO repeaters (location_id, owner_id, repeater_type, receive_range, transmit_range, is_active)
                   VALUES (?, ?, 'portable', 10, 8, 1)''',
                (location_id, user_id)
            )
            
            location_name = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (location_id,), fetch='one'
            )[0]
            
            return {"success": True, "message": f"Portable radio repeater deployed at {location_name}! This will extend radio coverage for all players in the area."}

        elif usage_type == "signal_boost":
            # Signal booster - narrative effect for now
            return {"success": True, "message": f"Signal booster activated! Radio transmission power increased by {effect_value}% for the next hour."}    
        elif usage_type == "emergency_beacon":
            # Emergency beacon - deploy with custom message
            char_data = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            
            if not char_data or not char_data[0]:
                return {"success": False, "message": "Cannot deploy beacon while stranded in space!"}
            
            location_id = char_data[0]
            
            # Create beacon configuration view
            from cogs.beacon_system import BeaconView
            view = BeaconView(self.bot, user_id, "emergency_beacon", location_id, item_id)
            
            embed = discord.Embed(
                title="🆘 Emergency Beacon Configuration",
                description="Configure your emergency beacon before deployment.",
                color=0xff0000
            )
            embed.add_field(
                name="📡 Beacon Specifications",
                value="• **Transmissions:** 3 times over 40 minutes\n• **Range:** Full galactic radio network\n• **Signal:** High-priority emergency frequency",
                inline=False
            )
            embed.add_field(
                name="⚠️ Important",
                value="The beacon will continue transmitting even if you leave the area. Choose your message carefully.",
                inline=False
            )
            
            # This needs to be handled by returning a special response that the calling code can handle
            return {
                "success": True, 
                "message": "Beacon ready for configuration",
                "requires_interaction": True,
                "embed": embed,
                "view": view
            }

        elif usage_type == "news_beacon":
            # News beacon - inject data into news stream
            char_data = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            
            if not char_data or not char_data[0]:
                return {"success": False, "message": "Cannot deploy news beacon while stranded in space!"}
            
            location_id = char_data[0]
            
            # Create news beacon configuration view
            from cogs.beacon_system import BeaconView
            view = BeaconView(self.bot, user_id, "news_beacon", location_id, item_id)
            
            embed = discord.Embed(
                title="📰 News Data-Stream Injection",
                description="Prepare your data for injection into the official news stream.",
                color=0x00bfff
            )
            embed.add_field(
                name="📡 Injection Specifications",
                value="• **Target:** Galactic News Network\n• **Method:** Unauthorized data-stream injection\n• **Delay:** Realistic transmission delays apply",
                inline=False
            )
            embed.add_field(
                name="⚠️ Legal Notice",
                value="Unauthorized news injection may attract regulatory attention. Galactic News Network is not responsible for injected content.",
                inline=False
            )
            
            return {
                "success": True,
                "message": "News injection beacon ready for configuration", 
                "requires_interaction": True,
                "embed": embed,
                "view": view
            }
        elif usage_type == "upgrade_ship":
            # Permanent ship upgrade
            upgrade_parts = str(effect_value).split(":")
            if len(upgrade_parts) != 2:
                return {"success": False, "message": "Invalid upgrade configuration"}
            
            upgrade_type, upgrade_value = upgrade_parts
            upgrade_value = int(upgrade_value)
            
            if upgrade_type == "fuel_efficiency":
                self.db.execute_query(
                    "UPDATE ships SET fuel_efficiency = fuel_efficiency + ? WHERE owner_id = ?",
                    (upgrade_value, user_id)
                )
                return {"success": True, "message": f"Ship fuel efficiency improved by {upgrade_value}"}
            
            elif upgrade_type == "max_hull":
                self.db.execute_query(
                    "UPDATE ships SET max_hull = max_hull + ?, hull_integrity = hull_integrity + ? WHERE owner_id = ?",
                    (upgrade_value, upgrade_value, user_id)
                )
                return {"success": True, "message": f"Ship hull capacity increased by {upgrade_value}"}
        
        elif usage_type == "emergency_signal":
            # Emergency beacon - could trigger admin notification or spawn rescue event
            return {"success": True, "message": "Emergency signal transmitted! Help may be on the way..."}
        elif usage_type == "personal_log":
            # Handle personal log usage
            char_data = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user_id,), fetch='one'
            )
            
            if not char_data:
                return {"success": False, "message": "Character not found"}
            
            char_name = char_data[0]
            
            # Get or create logbook ID
            logbook_id = metadata.get("logbook_id")
            if not logbook_id:
                # Generate new logbook ID and update metadata
                logbook_id = str(uuid.uuid4())
                metadata["logbook_id"] = logbook_id
                
                # Update item metadata in database
                self.db.execute_query(
                    "UPDATE inventory SET metadata = ? WHERE item_id = ?",
                    (json.dumps(metadata), item_id)
                )
            
            # Create personal log interface
            from utils.views import PersonalLogMainView
            view = PersonalLogMainView(self.bot, user_id, logbook_id, char_name)
            
            embed = discord.Embed(
                title="📖 Personal Logbook Interface",
                description=f"**{item_name}**\nAccess your personal logs and create new entries.",
                color=0x4169E1
            )
            
            embed.add_field(
                name="📋 Logbook ID", 
                value=f"`{logbook_id[:8]}...`",
                inline=True
            )
            
            # Count existing entries
            entry_count = self.db.execute_query(
                "SELECT COUNT(*) FROM logbook_entries WHERE logbook_id = ?",
                (logbook_id,),
                fetch='one'
            )[0]
            
            embed.add_field(
                name="📊 Total Entries",
                value=str(entry_count),
                inline=True
            )
            
            return {
                "success": True,
                "message": "Personal log interface activated",
                "requires_interaction": True,
                "embed": embed,
                "view": view
            }
        else:
            return {"success": False, "message": f"Unknown usage type: {usage_type}"}

async def setup(bot):
    await bot.add_cog(ItemUsageCog(bot))