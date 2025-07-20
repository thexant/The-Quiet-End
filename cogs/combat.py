# cogs/combat.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from utils.location_utils import get_character_location_status
from utils.item_effects import ItemEffectChecker

class CombatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.npc_counterattack_loop.start()
        self.npc_respawn_loop.start()
        self.cleanup_expired_cooldowns.start()  
        self.cleanup_expired_robberies.start()  

    def cog_unload(self):
        self.npc_counterattack_loop.cancel()
        self.npc_respawn_loop.cancel()
        self.cleanup_expired_cooldowns.cancel()  
        self.cleanup_expired_robberies.cancel()  
    
    
    @tasks.loop(minutes=5)
    async def cleanup_expired_cooldowns(self):
        """Clean up expired PvP cooldowns"""
        try:
            self.db.execute_query(
                "DELETE FROM pvp_cooldowns WHERE expires_at <= datetime('now')"
            )
        except Exception as e:
            print(f"Error cleaning up expired cooldowns: {e}")

    @tasks.loop(minutes=1)
    async def cleanup_expired_robberies(self):
        """Clean up expired robbery attempts and auto-surrender"""
        try:
            expired_robberies = self.db.execute_query(
                """SELECT robbery_id, robber_id, victim_id, location_id, message_id, channel_id
                   FROM pending_robberies 
                   WHERE expires_at <= datetime('now')""",
                fetch='all'
            )
            
            for robbery_data in expired_robberies:
                robbery_id, robber_id, victim_id, location_id, message_id, channel_id = robbery_data
                
                await self._process_automatic_robbery_surrender(
                    robber_id, victim_id, location_id, message_id, channel_id
                )
                
            self.db.execute_query(
                "DELETE FROM pending_robberies WHERE expires_at <= datetime('now')"
            )
            
        except Exception as e:
            print(f"Error cleaning up expired robberies: {e}")

    async def _process_automatic_robbery_surrender(self, robber_id, victim_id, location_id, message_id, channel_id):
        """Process automatic surrender for timed-out robbery"""
        try:
            # Get victim data
            victim_data = self.db.execute_query(
                "SELECT money, name FROM characters WHERE user_id = ?",
                (victim_id,),
                fetch='one'
            )
            
            if not victim_data:
                return
                
            victim_money, victim_name = victim_data
            
            # Get robber name
            robber_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (robber_id,),
                fetch='one'
            )[0]
            
            # Calculate stolen amount (similar to surrender logic)
            steal_percentage = random.uniform(0.2, 0.5)
            stolen_credits = int(victim_money * steal_percentage)
            stolen_credits = max(stolen_credits, min(100, victim_money))
            
            # Transfer credits
            self.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (stolen_credits, victim_id)
            )
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (stolen_credits, robber_id)
            )
            
            # Get and steal some items
            victim_items = self.db.execute_query(
                "SELECT item_name, quantity FROM character_inventory WHERE user_id = ?",
                (victim_id,),
                fetch='all'
            )
            
            stolen_items = []
            if victim_items:
                num_items_to_steal = min(random.randint(1, 3), len(victim_items))
                items_to_steal = random.sample(victim_items, num_items_to_steal)
                
                for item_name, quantity in items_to_steal:
                    stolen_quantity = min(random.randint(1, max(1, quantity // 2)), quantity)
                    stolen_items.append((item_name, stolen_quantity))
                    
                    # Transfer items
                    self.db.execute_query(
                        "UPDATE character_inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                        (stolen_quantity, victim_id, item_name)
                    )
                    self.db.execute_query(
                        """INSERT OR REPLACE INTO character_inventory (user_id, item_name, quantity)
                           VALUES (?, ?, COALESCE((SELECT quantity FROM character_inventory WHERE user_id = ? AND item_name = ?), 0) + ?)""",
                        (robber_id, item_name, robber_id, item_name, stolen_quantity)
                    )
            
            # Clean up zero quantities
            self.db.execute_query("DELETE FROM character_inventory WHERE quantity <= 0")
            
            # Add robbery cooldown
            expire_time = datetime.utcnow() + timedelta(minutes=15)
            self.db.execute_query(
                """INSERT OR REPLACE INTO pvp_cooldowns 
                   (player1_id, player2_id, cooldown_type, expires_at)
                   VALUES (?, ?, 'robbery', ?)""",
                (robber_id, victim_id, expire_time.isoformat())
            )
            
            # Update the message in the channel
            try:
                channel = self.bot.get_channel(channel_id)
                if channel and message_id:
                    message = await channel.fetch_message(message_id)
                    
                    embed = discord.Embed(
                        title="🏳️ AUTOMATIC SURRENDER",
                        description=f"**{victim_name}** froze in fear, allowing **{robber_name}** to take everything!",
                        color=0x888888
                    )
                    embed.add_field(name="Stolen Credits", value=f"{stolen_credits}", inline=True)
                    
                    if stolen_items:
                        items_text = ", ".join([f"{qty}x {item}" for item, qty in stolen_items])
                        embed.add_field(name="Stolen Items", value=items_text, inline=True)
                    
                    embed.add_field(name="Timeout", value="Victim did not respond in time", inline=False)
                    embed.add_field(name="Cooldown", value="15 minutes until next robbery attempt", inline=False)
                    
                    # Create a disabled view
                    view = discord.ui.View()
                    surrender_button = discord.ui.Button(label="Surrender", style=discord.ButtonStyle.danger, emoji="🏳️", disabled=True)
                    fight_button = discord.ui.Button(label="Fight Back", style=discord.ButtonStyle.secondary, emoji="⚔️", disabled=True)
                    view.add_item(surrender_button)
                    view.add_item(fight_button)
                    
                    await message.edit(embed=embed, view=view)
                    
            except (discord.NotFound, discord.Forbidden):
                pass  # Message was deleted or no permissions
                
        except Exception as e:
            print(f"Error processing automatic robbery surrender: {e}")
    
    
    
    
    rob_group = app_commands.Group(name="rob", description="Robbery commands")
    attack_group = app_commands.Group(name="attack", description="Combat commands")

    @attack_group.command(name="npc", description="Initiate combat with an NPC")
    async def attack_npc(self, interaction: discord.Interaction):
        # Check if user has character
        char_data = self.db.execute_query(
            "SELECT current_location, location_status, hp, combat FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You need a character to attack! Use `/character create` first.", 
                ephemeral=True
            )
            return

        current_location, location_status, player_hp, player_combat = char_data

        if not current_location:
            await interaction.response.send_message(
                "You're in deep space and cannot attack anyone here!", 
                ephemeral=True
            )
            return

        if player_hp <= 0:
            await interaction.response.send_message(
                "You're too injured to fight! Heal yourself first.", 
                ephemeral=True
            )
            return

        # Check if already in combat
        existing_combat = self.db.execute_query(
            "SELECT combat_id FROM combat_states WHERE player_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if existing_combat:
            await interaction.response.send_message(
                "You're already in combat! Use `/attack fight` to continue or `/attack flee` to escape.", 
                ephemeral=True
            )
            return

        # Get available NPCs based on docked status
        location_status_info, _ = get_character_location_status(self.db, interaction.user.id)
        is_docked = location_status == "docked"

        if is_docked:
            # Ground combat - get static NPCs
            npcs = self.db.execute_query(
                """SELECT npc_id, name, occupation, alignment, hp, max_hp 
                   FROM static_npcs 
                   WHERE location_id = ? AND is_alive = 1""",
                (current_location,),
                fetch='all'
            )
            combat_type = "ground"
        else:
            # Space combat - get dynamic NPCs
            npcs = self.db.execute_query(
                """SELECT npc_id, name, ship_name, alignment, hp, max_hp 
                   FROM dynamic_npcs 
                   WHERE current_location = ? AND is_alive = 1""",
                (current_location,),
                fetch='all'
            )
            combat_type = "space"

        if not npcs:
            await interaction.response.send_message(
                "No NPCs available to attack at this location!", 
                ephemeral=True
            )
            return

        # Create dropdown with NPCs
        view = NPCAttackSelectView(
            self.bot, interaction.user.id, current_location, npcs, combat_type, is_docked
        )
        
        await interaction.response.send_message(
            f"🎯 **{'Ground' if is_docked else 'Space'} Combat Available**\nChoose an NPC to attack:",
            view=view,
            ephemeral=True
        )
    async def _handle_npc_combat_round(self, interaction, combat_data):
        """Handle NPC combat round (existing logic with minor modifications)"""
        combat_id, target_npc_id, target_npc_type, combat_type, location_id, can_act_time = combat_data

        # Check cooldown (existing logic)
        if can_act_time:
            try:
                can_act_datetime = datetime.fromisoformat(can_act_time)
                current_time = datetime.utcnow()
                if current_time < can_act_datetime:
                    remaining = (can_act_datetime - current_time).total_seconds()
                    if remaining > 300:  # More than 5 minutes is likely an error
                        self.db.execute_query(
                            "UPDATE combat_states SET player_can_act_time = NULL WHERE player_id = ?",
                            (interaction.user.id,)
                        )
                    else:
                        await interaction.response.send_message(
                            f"⏰ You must wait {remaining:.0f} more seconds before attacking again!", 
                            ephemeral=True
                        )
                        return
            except (ValueError, TypeError):
                self.db.execute_query(
                    "UPDATE combat_states SET player_can_act_time = NULL WHERE player_id = ?",
                    (interaction.user.id,)
                )

        # Get player stats
        player_data = self.db.execute_query(
            "SELECT hp, combat, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if not player_data or player_data[0] <= 0:
            await interaction.response.send_message(
                "You're dead and can't keep fighting!", 
                ephemeral=True
            )
            return

        player_hp, player_combat, player_name = player_data

        # Execute combat round (use existing method)
        await self._execute_combat_round(
            interaction, combat_id, target_npc_id, target_npc_type, 
            combat_type, location_id, player_name, player_combat
        )

    async def _handle_pvp_combat_round(self, interaction, combat_data):
        """Handle PvP combat round"""
        combat_id, attacker_id, defender_id, location_id, combat_type, attacker_can_act_time, defender_can_act_time, current_turn = combat_data
        
        # Determine if this user is the attacker or defender
        is_attacker = interaction.user.id == attacker_id
        opponent_id = defender_id if is_attacker else attacker_id
        
        # Check if it's this player's turn
        user_turn = (current_turn == 'attacker' and is_attacker) or (current_turn == 'defender' and not is_attacker)
        
        if not user_turn:
            opponent_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (opponent_id,),
                fetch='one'
            )[0]
            await interaction.response.send_message(
                f"It's {opponent_name}'s turn to act!", 
                ephemeral=True
            )
            return
        
        # Check cooldown
        can_act_time = attacker_can_act_time if is_attacker else defender_can_act_time
        if can_act_time:
            try:
                can_act_datetime = datetime.fromisoformat(can_act_time)
                current_time = datetime.utcnow()
                if current_time < can_act_datetime:
                    remaining = (can_act_datetime - current_time).total_seconds()
                    await interaction.response.send_message(
                        f"⏰ You must wait {remaining:.0f} more seconds before attacking again!", 
                        ephemeral=True
                    )
                    return
            except (ValueError, TypeError):
                pass

        if combat_type == "space":
            # Space combat - use ship stats
            attacker_data = self.db.execute_query(
                """SELECT s.hull_integrity, s.combat_rating, c.name, c.location_status, s.ship_id, s.max_hull
                   FROM characters c
                   JOIN ships s ON c.ship_id = s.ship_id
                   WHERE c.user_id = ?""",
                (attacker_id,),
                fetch='one'
            )
            
            defender_data = self.db.execute_query(
                """SELECT s.hull_integrity, s.combat_rating, c.name, c.location_status, s.ship_id, s.max_hull
                   FROM characters c
                   JOIN ships s ON c.ship_id = s.ship_id
                   WHERE c.user_id = ?""",
                (defender_id,),
                fetch='one'
            )
            
            if not attacker_data or not defender_data:
                await interaction.response.send_message("Error: One or both players don't have ships for space combat!", ephemeral=True)
                return

            attacker_hp, attacker_combat, attacker_name, attacker_status, attacker_ship_id, attacker_max_hp = attacker_data
            defender_hp, defender_combat, defender_name, defender_status, defender_ship_id, defender_max_hp = defender_data
            
        else:
            # Ground combat - use character stats
            attacker_data = self.db.execute_query(
                "SELECT hp, combat, name, location_status FROM characters WHERE user_id = ?",
                (attacker_id,),
                fetch='one'
            )
            
            defender_data = self.db.execute_query(
                "SELECT hp, combat, name, location_status FROM characters WHERE user_id = ?",
                (defender_id,),
                fetch='one'
            )

            if not attacker_data or not defender_data:
                await interaction.response.send_message("Error retrieving character data!", ephemeral=True)
                return

            attacker_hp, attacker_combat, attacker_name, attacker_status = attacker_data
            defender_hp, defender_combat, defender_name, defender_status = defender_data
            attacker_ship_id = defender_ship_id = None
            attacker_max_hp = defender_max_hp = None

            # Check if either player is defeated
            if attacker_hp <= 0 or defender_hp <= 0:
                await self._end_pvp_combat(interaction, combat_id, attacker_id, defender_id, attacker_name, defender_name)
                return

            # Execute PvP combat round
            await self._execute_pvp_combat_round(
                interaction, combat_id, attacker_id, defender_id, 
                attacker_name, defender_name, attacker_combat, defender_combat,
                attacker_hp, defender_hp, combat_type, is_attacker,
                attacker_ship_id if combat_type == "space" else None,
                defender_ship_id if combat_type == "space" else None,
                attacker_max_hp, defender_max_hp
            )

    async def _execute_pvp_combat_round(self, interaction, combat_id, attacker_id, defender_id,
                                       attacker_name, defender_name, attacker_combat, defender_combat,
                                       attacker_hp, defender_hp, combat_type, user_is_attacker,
                                       attacker_ship_id=None, defender_ship_id=None, 
                                       attacker_max_hp=None, defender_max_hp=None):
        """Execute a single round of PvP combat"""
        
        effect_checker = ItemEffectChecker(self.bot)
    
        # Get combat boosts for both players
        attacker_boost = effect_checker.get_combat_boost(attacker_id)
        defender_boost = effect_checker.get_combat_boost(defender_id)
        
        # Apply boosts to combat skills
        effective_attacker_combat = attacker_combat + attacker_boost
        effective_defender_combat = defender_combat + defender_boost
        # Current attacker stats
        # Current attacker stats
        if user_is_attacker:
            attacker_roll = random.randint(1, 20) + effective_attacker_combat  # Changed
            defender_roll = random.randint(1, 20) + effective_defender_combat  # Changed
            current_name = attacker_name
            target_name = defender_name
            target_id = defender_id
            target_ship_id = defender_ship_id
        else:
            attacker_roll = random.randint(1, 20) + effective_defender_combat  # Defender attacking back
            defender_roll = random.randint(1, 20) + effective_attacker_combat  # Attacker defending
            current_name = defender_name
            target_name = attacker_name
            target_id = attacker_id
            target_ship_id = attacker_ship_id

        damage_dealt = 0
        damage_type = "Hull" if combat_type == "space" else "HP"
        
        if attacker_roll > defender_roll:
            # Hit!
            base_damage = random.randint(5, 15)
            skill_bonus = (attacker_combat if user_is_attacker else defender_combat) // 2
            damage_dealt = base_damage + skill_bonus

            # Apply damage based on combat type
            if combat_type == "space":
                # Space combat - hull damage
                self.db.execute_query(
                    "UPDATE ships SET hull_integrity = max(0, hull_integrity - ?) WHERE ship_id = ?",
                    (damage_dealt, target_ship_id)
                )
            else:
                # Ground combat - HP damage
                self.db.execute_query(
                    "UPDATE characters SET hp = max(0, hp - ?) WHERE user_id = ?",
                    (damage_dealt, target_id)
                )
            if user_is_attacker:
                skill_bonus = effective_attacker_combat // 2
            else:
                skill_bonus = effective_defender_combat // 2
            damage_dealt = base_damage + skill_bonus
        # Switch turns
        new_turn = 'defender' if user_is_attacker else 'attacker'
        
        # Set cooldown for current player and update turn
        next_action_time = datetime.utcnow() + timedelta(seconds=10)
        
        if user_is_attacker:
            self.db.execute_query(
                """UPDATE pvp_combat_states 
                   SET attacker_can_act_time = ?, current_turn = ?, last_action_time = ?
                   WHERE combat_id = ?""",
                (next_action_time.isoformat(), new_turn, datetime.utcnow().isoformat(), combat_id)
            )
        else:
            self.db.execute_query(
                """UPDATE pvp_combat_states 
                   SET defender_can_act_time = ?, current_turn = ?, last_action_time = ?
                   WHERE combat_id = ?""",
                (next_action_time.isoformat(), new_turn, datetime.utcnow().isoformat(), combat_id)
            )

        # Check if target is defeated
        if combat_type == "space":
            target_hull = self.db.execute_query(
                "SELECT hull_integrity FROM ships WHERE ship_id = ?",
                (target_ship_id,),
                fetch='one'
            )[0]
            
            if target_hull <= 0:
                await self._end_pvp_combat(interaction, combat_id, attacker_id, defender_id, attacker_name, defender_name, combat_type)
                return
        else:
            target_hp = self.db.execute_query(
                "SELECT hp FROM characters WHERE user_id = ?",
                (target_id,),
                fetch='one'
            )[0]
            
            if target_hp <= 0:
                await self._end_pvp_combat(interaction, combat_id, attacker_id, defender_id, attacker_name, defender_name, combat_type)
                return

        # Create combat result embed with appropriate theming
        combat_title = "🚀 Space Combat Round" if combat_type == "space" else "⚔️ Ground Combat Round"
        embed = discord.Embed(
            title=combat_title,
            color=0xff4444 if damage_dealt == 0 else 0x00ff00
        )
        boost_text = []
        if user_is_attacker and attacker_boost > 0:
            boost_text.append(f"{attacker_name}: +{attacker_boost}")
        elif not user_is_attacker and defender_boost > 0:
            boost_text.append(f"{defender_name}: +{defender_boost}")

        if boost_text:
            embed.add_field(
                name="💉 Combat Stims Active",
                value=" | ".join(boost_text),
                inline=False
            )
        if damage_dealt > 0:
            if combat_type == "space":
                embed.add_field(
                    name="💥 Direct Hit!",
                    value=f"**{current_name}'s ship** deals {damage_dealt} hull damage to **{target_name}'s ship**!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💥 Hit!",
                    value=f"**{current_name}** deals {damage_dealt} damage to **{target_name}**",
                    inline=False
                )
        else:
            if combat_type == "space":
                embed.add_field(
                    name="❌ Missed!",
                    value=f"**{current_name}'s ship** weapons missed their target!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Miss!",
                    value=f"**{current_name}**'s attack missed!",
                    inline=False
                )

        embed.add_field(
            name="🎲 Combat Rolls",
            value=f"{current_name}: {attacker_roll} vs {target_name}: {defender_roll}",
            inline=False
        )

        # Get updated HP/Hull for display
        if combat_type == "space":
            updated_attacker_hull = self.db.execute_query(
                "SELECT hull_integrity FROM ships WHERE ship_id = ?",
                (attacker_ship_id,),
                fetch='one'
            )[0]
            
            updated_defender_hull = self.db.execute_query(
                "SELECT hull_integrity FROM ships WHERE ship_id = ?",
                (defender_ship_id,),
                fetch='one'
            )[0]
            
            embed.add_field(
                name="🛡️ Ship Status",
                value=f"**{attacker_name}'s Ship**: {updated_attacker_hull} Hull\n**{defender_name}'s Ship**: {updated_defender_hull} Hull",
                inline=False
            )
        else:
            updated_attacker_hp = self.db.execute_query(
                "SELECT hp FROM characters WHERE user_id = ?",
                (attacker_id,),
                fetch='one'
            )[0]
            
            updated_defender_hp = self.db.execute_query(
                "SELECT hp FROM characters WHERE user_id = ?",
                (defender_id,),
                fetch='one'
            )[0]
            
            embed.add_field(
                name="❤️ Health Status",
                value=f"**{attacker_name}**: {updated_attacker_hp} HP\n**{defender_name}**: {updated_defender_hp} HP",
                inline=False
            )

        embed.add_field(
            name="⏰ Next Turn",
            value=f"**{target_name}** can act in 10 seconds",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

        # Notify the other player in their location channel
        try:
            opponent_user = interaction.guild.get_member(target_id)
            if opponent_user:
                # Get the location channel for the combat
                location_channel_id = self.db.execute_query(
                    """SELECT location_id FROM pvp_combat_states WHERE combat_id = ?""",
                    (combat_id,),
                    fetch='one'
                )
                
                if location_channel_id and location_channel_id[0]:
                    location_channel_data = self.db.execute_query(
                        "SELECT channel_id FROM locations WHERE location_id = ?",
                        (location_channel_id[0],),
                        fetch='one'
                    )
                    
                    if location_channel_data and location_channel_data[0]:
                        location_channel = interaction.guild.get_channel(location_channel_data[0])
                        if location_channel:
                            await location_channel.send(
                                f"{opponent_user.mention} - It's your turn in combat! Use `/attack fight` to continue fighting **{current_name}**!"
                            )
        except Exception as e:
            print(f"Failed to send combat notification to location channel: {e}")
    async def _end_pvp_combat(self, interaction, combat_id, attacker_id, defender_id, attacker_name, defender_name, combat_type="ground"):
        """End PvP combat and declare winner"""
        
        # Get final HP/Hull values based on combat type
        if combat_type == "space":
            attacker_hull = self.db.execute_query(
                """SELECT s.hull_integrity FROM ships s 
                   JOIN characters c ON s.ship_id = c.ship_id 
                   WHERE c.user_id = ?""",
                (attacker_id,),
                fetch='one'
            )[0]
            
            defender_hull = self.db.execute_query(
                """SELECT s.hull_integrity FROM ships s 
                   JOIN characters c ON s.ship_id = c.ship_id 
                   WHERE c.user_id = ?""",
                (defender_id,),
                fetch='one'
            )[0]
            
            # Determine winner based on hull
            if attacker_hull <= 0 and defender_hull <= 0:
                winner_name = "Draw"
                loser_name = "Both ships"
            elif attacker_hull <= 0:
                winner_name = defender_name
                loser_name = attacker_name
            else:
                winner_name = attacker_name
                loser_name = defender_name
                
            final_status_text = f"**{attacker_name}'s Ship**: {attacker_hull} Hull\n**{defender_name}'s Ship**: {defender_hull} Hull"
            combat_title = "🚀 Space Combat Ended!"
            
        else:
            attacker_hp = self.db.execute_query(
                "SELECT hp FROM characters WHERE user_id = ?",
                (attacker_id,),
                fetch='one'
            )[0]
            
            defender_hp = self.db.execute_query(
                "SELECT hp FROM characters WHERE user_id = ?",
                (defender_id,),
                fetch='one'
            )[0]
            
            # Determine winner based on HP
            if attacker_hp <= 0 and defender_hp <= 0:
                winner_name = "Draw"
                loser_name = "Both players"
            elif attacker_hp <= 0:
                winner_name = defender_name
                loser_name = attacker_name
            else:
                winner_name = attacker_name
                loser_name = defender_name
                
            final_status_text = f"**{attacker_name}**: {attacker_hp} HP\n**{defender_name}**: {defender_hp} HP"
            combat_title = "⚔️ Ground Combat Ended!"
        
        # End combat
        self.db.execute_query(
            "DELETE FROM pvp_combat_states WHERE combat_id = ?",
            (combat_id,)
        )
        
        # Restore location status for both players
        restore_status = "docked" if combat_type == "ground" else "in_space"
        self.db.execute_query(
            "UPDATE characters SET location_status = ? WHERE user_id IN (?, ?)",
            (restore_status, attacker_id, defender_id)
        )
        
        # Create result embed
        if winner_name == "Draw":
            embed = discord.Embed(
                title=f"{combat_title} - DRAW!",
                description="Both combatants have been defeated!",
                color=0x888888
            )
        else:
            embed = discord.Embed(
                title=combat_title,
                description=f"**{winner_name}** has defeated **{loser_name}**!",
                color=0x00ff00
            )
        
        embed.add_field(
            name="Final Status",
            value=final_status_text,
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Notify both players in the location channel
        try:
            location_channel_id = self.db.execute_query(
                "SELECT channel_id FROM locations WHERE location_id = ?",
                (location_id,),  # You'll need to pass this to the function
                fetch='one'
            )
            
            if location_channel_id and location_channel_id[0]:
                location_channel = interaction.guild.get_channel(location_channel_id[0])
                if location_channel:
                    for user_id in [attacker_id, defender_id]:
                        user = interaction.guild.get_member(user_id)
                        if user and user.id != interaction.user.id:
                            await location_channel.send(f"{user.mention} - Combat has ended!", embed=embed)
        except Exception as e:
            print(f"Failed to send combat end notification to location channel: {e}")
    @attack_group.command(name="fight", description="Continue an ongoing fight")
    async def continue_fight(self, interaction: discord.Interaction):
        # Check for NPC combat first
        npc_combat_data = self.db.execute_query(
            """SELECT combat_id, target_npc_id, target_npc_type, combat_type, 
                      location_id, player_can_act_time
               FROM combat_states 
               WHERE player_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        # Check for PvP combat
        pvp_combat_data = self.db.execute_query(
            """SELECT combat_id, attacker_id, defender_id, location_id, combat_type,
                      attacker_can_act_time, defender_can_act_time, current_turn
               FROM pvp_combat_states 
               WHERE attacker_id = ? OR defender_id = ?""",
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )

        if npc_combat_data:
            # Handle NPC combat (existing logic)
            await self._handle_npc_combat_round(interaction, npc_combat_data)
        elif pvp_combat_data:
            # Handle PvP combat
            await self._handle_pvp_combat_round(interaction, pvp_combat_data)
        else:
            await interaction.response.send_message(
                "You're not in combat! Use `/attack npc` or `/attack player` to start a fight.", 
                ephemeral=True
            )
    @attack_group.command(name="player", description="Initiate PvP combat with another player")
    @app_commands.describe(target="The player you want to attack")
    async def attack_player(self, interaction: discord.Interaction, target: discord.Member):
        # Basic validation
        if target.id == interaction.user.id:
            await interaction.response.send_message("You cannot attack yourself!", ephemeral=True)
            return

        # Check if attacker has character
        attacker_data = self.db.execute_query(
            "SELECT current_location, location_status, hp, combat, alignment, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not attacker_data:
            await interaction.response.send_message(
                "You need a character to attack! Use `/character create` first.", 
                ephemeral=True
            )
            return

        # Check if target has character
        target_data = self.db.execute_query(
            "SELECT current_location, location_status, hp, combat, alignment, name FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not target_data:
            await interaction.response.send_message(
                f"{target.display_name} doesn't have a character!", 
                ephemeral=True
            )
            return

        attacker_location, attacker_status, attacker_hp, attacker_combat, attacker_alignment, attacker_name = attacker_data
        target_location, target_status, target_hp, target_combat, target_alignment, target_name = target_data

        # Location and status checks
        if not attacker_location or not target_location:
            await interaction.response.send_message(
                "Both players must be at a location to engage in PvP!", 
                ephemeral=True
            )
            return

        if attacker_location != target_location:
            await interaction.response.send_message(
                "You must be at the same location as your target!", 
                ephemeral=True
            )
            return

        if attacker_status != target_status:
            await interaction.response.send_message(
                "Both players must have the same docked/undocked status!", 
                ephemeral=True
            )
            return

        # Health checks
        if attacker_hp <= 0:
            await interaction.response.send_message(
                "You're too injured to fight! Heal yourself first.", 
                ephemeral=True
            )
            return

        if target_hp <= 0:
            await interaction.response.send_message(
                f"{target_name} is too injured to fight!", 
                ephemeral=True
            )
            return

        # Check if either player is already in combat
        existing_combat = self.db.execute_query(
            """SELECT combat_id FROM combat_states WHERE player_id IN (?, ?)
               UNION
               SELECT combat_id FROM pvp_combat_states WHERE attacker_id IN (?, ?) OR defender_id IN (?, ?)""",
            (interaction.user.id, target.id, interaction.user.id, target.id, interaction.user.id, target.id),
            fetch='one'
        )

        if existing_combat:
            await interaction.response.send_message(
                "One of the players is already in combat!", 
                ephemeral=True
            )
            return

        # Check opt-out status and alignment rules
        can_attack, reason = await self._check_pvp_eligibility(interaction.user.id, target.id, attacker_alignment, target_alignment)
        if not can_attack:
            await interaction.response.send_message(reason, ephemeral=True)
            return

        # Check flee cooldown
        flee_cooldown = self.db.execute_query(
            """SELECT expires_at FROM pvp_cooldowns 
               WHERE ((player1_id = ? AND player2_id = ?) OR (player1_id = ? AND player2_id = ?))
               AND cooldown_type = 'flee' AND expires_at > datetime('now')""",
            (interaction.user.id, target.id, target.id, interaction.user.id),
            fetch='one'
        )

        if flee_cooldown:
            await interaction.response.send_message(
                f"You cannot attack {target_name} for another few minutes due to recent flee cooldown!", 
                ephemeral=True
            )
            return

        # Start PvP combat
        combat_type = "ground" if attacker_status == "docked" else "space"
        
        # Set both players to combat status
        self.db.execute_query(
            "UPDATE characters SET location_status = 'combat' WHERE user_id IN (?, ?)",
            (interaction.user.id, target.id)
        )

        # Create PvP combat state
        self.db.execute_query(
            """INSERT INTO pvp_combat_states 
               (attacker_id, defender_id, location_id, combat_type, attacker_can_act_time)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (interaction.user.id, target.id, attacker_location, combat_type)
        )

        # Get location name
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (attacker_location,),
            fetch='one'
        )[0]

        # Notify both players
        embed = discord.Embed(
            title="⚔️ PvP Combat Initiated!",
            description=f"**{attacker_name}** has attacked **{target_name}** at **{location_name}**!",
            color=0xff4444
        )
        embed.add_field(name="Combat Type", value=combat_type.title(), inline=True)
        embed.add_field(name="Status", value="Both players are now in combat", inline=True)
        embed.add_field(name="Next Action", value=f"{attacker_name} can act first", inline=False)

        await interaction.response.send_message(embed=embed)

        # Send DM to target
        try:
            target_embed = discord.Embed(
                title="⚔️ You're Under Attack!",
                description=f"**{attacker_name}** has initiated PvP combat with you at **{location_name}**!",
                color=0xff4444
            )
            target_embed.add_field(name="Actions", value="Use `/attack fight` to fight back or `/attack flee` to escape!", inline=False)
            await target.send(embed=target_embed)
        except discord.Forbidden:
            pass

    async def _check_pvp_eligibility(self, attacker_id: int, target_id: int, attacker_alignment: str, target_alignment: str) -> tuple[bool, str]:
        """Check if PvP is allowed between two players based on opt-out and alignment rules"""
        
        # Check opt-out status
        opt_out_data = self.db.execute_query(
            "SELECT user_id, opted_out FROM pvp_opt_outs WHERE user_id IN (?, ?)",
            (attacker_id, target_id),
            fetch='all'
        )
        
        opted_out_users = {user_id: opted_out for user_id, opted_out in opt_out_data if opted_out}
        
        # Alignment rules for opt-out
        opposite_alignments = (
            (attacker_alignment == 'loyal' and target_alignment == 'bandit') or
            (attacker_alignment == 'bandit' and target_alignment == 'loyal')
        )
        
        # Check attacker opt-out
        if attacker_id in opted_out_users:
            if not opposite_alignments:
                return False, "You have opted out of PvP and can only attack opposing alignment players!"
        
        # Check target opt-out
        if target_id in opted_out_users:
            if not opposite_alignments:
                return False, "That player has opted out of PvP and can only be attacked by opposing alignment players!"
        
        return True, ""

    def check_pvp_combat_status(self, user_id: int) -> bool:
        """Check if user is in PvP combat"""
        result = self.db.execute_query(
            "SELECT combat_id FROM pvp_combat_states WHERE attacker_id = ? OR defender_id = ?",
            (user_id, user_id),
            fetch='one'
        )
        return result is not None

    def check_any_combat_status(self, user_id: int) -> bool:
        """Check if user is in any combat (NPC or PvP)"""
        npc_combat = self.db.execute_query(
            "SELECT combat_id FROM combat_states WHERE player_id = ?",
            (user_id,),
            fetch='one'
        )
        
        pvp_combat = self.db.execute_query(
            "SELECT combat_id FROM pvp_combat_states WHERE attacker_id = ? OR defender_id = ?",
            (user_id, user_id),
            fetch='one'
        )
        
        return npc_combat is not None or pvp_combat is not None
    @attack_group.command(name="flee", description="Attempt to escape from combat")
    async def flee_combat(self, interaction: discord.Interaction):
        # Check for NPC combat first
        npc_combat_data = self.db.execute_query(
            """SELECT combat_id, target_npc_id, target_npc_type, combat_type
               FROM combat_states 
               WHERE player_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        # Check for PvP combat
        pvp_combat_data = self.db.execute_query(
            """SELECT combat_id, attacker_id, defender_id, location_id, combat_type
               FROM pvp_combat_states 
               WHERE attacker_id = ? OR defender_id = ?""",
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if npc_combat_data:
            # Handle NPC combat flee (existing logic)
            await self._handle_npc_flee(interaction, npc_combat_data)
        elif pvp_combat_data:
            # Handle PvP combat flee
            await self._handle_pvp_flee(interaction, pvp_combat_data)
        else:
            await interaction.response.send_message(
                "You're not in combat!", 
                ephemeral=True
            )

    async def _handle_npc_flee(self, interaction, combat_data):
        """Handle fleeing from NPC combat (existing logic)"""
        combat_id, target_npc_id, target_npc_type, combat_type = combat_data

        # Get player stats for flee attempt
        player_data = self.db.execute_query(
            "SELECT navigation, engineering, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        player_nav, player_eng, player_name = player_data

        # Calculate flee chance based on relevant skills
        if combat_type == "ground":
            flee_skill = player_nav  # Ground evasion
        else:
            flee_skill = player_eng  # Ship maneuvering

        # Base 50% chance + 5% per skill point
        flee_chance = 0.5 + (flee_skill * 0.05)
        flee_chance = min(flee_chance, 0.9)  # Cap at 90%

        flee_roll = random.random()
        
        if flee_roll < flee_chance:
            # Successful escape
            self.db.execute_query(
                "DELETE FROM combat_states WHERE combat_id = ?",
                (combat_id,)
            )
            
            # Restore location status
            self.db.execute_query(
                "UPDATE characters SET location_status = 'docked' WHERE user_id = ?",
                (interaction.user.id,)
            )

            embed = discord.Embed(
                title="🏃 Escape Successful!",
                description=f"**{player_name}** successfully escaped from combat!",
                color=0x00ff00
            )
            embed.add_field(
                name="Skill Check", 
                value=f"{'Navigation' if combat_type == 'ground' else 'Engineering'}: {flee_skill}\nRoll: {flee_roll:.2f} vs {flee_chance:.2f}",
                inline=False
            )
        else:
            # Failed escape - combat continues
            embed = discord.Embed(
                title="❌ Escape Failed!",
                description=f"**{player_name}** failed to escape! The fight continues...",
                color=0xff0000
            )
            embed.add_field(
                name="Skill Check", 
                value=f"{'Navigation' if combat_type == 'ground' else 'Engineering'}: {flee_skill}\nRoll: {flee_roll:.2f} vs {flee_chance:.2f}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_pvp_flee(self, interaction, combat_data):
        """Handle fleeing from PvP combat"""
        combat_id, attacker_id, defender_id, location_id, combat_type = combat_data
        
        # Determine opponent
        opponent_id = defender_id if interaction.user.id == attacker_id else attacker_id
        
        # Get player names
        player_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        opponent_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (opponent_id,),
            fetch='one'
        )
        
        if not player_data or not opponent_data:
            await interaction.response.send_message("Error retrieving character data!", ephemeral=True)
            return
        
        player_name = player_data[0]
        opponent_name = opponent_data[0]
        
        # Calculate flee cost (10% of current money, minimum 50 credits)
        player_money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        flee_cost = max(50, int(player_money * 0.1))
        flee_cost = min(flee_cost, player_money)  # Can't pay more than they have
        
        # End combat
        self.db.execute_query(
            "DELETE FROM pvp_combat_states WHERE combat_id = ?",
            (combat_id,)
        )
        
        # Restore location status for both players
        current_status = "docked" if combat_type == "ground" else "space"
        self.db.execute_query(
            "UPDATE characters SET location_status = ? WHERE user_id IN (?, ?)",
            (current_status, interaction.user.id, opponent_id)
        )
        
        # Deduct flee cost
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (flee_cost, interaction.user.id)
        )
        
        # Add flee cooldown (15 minutes)
        expire_time = datetime.utcnow() + timedelta(minutes=15)
        self.db.execute_query(
            """INSERT OR REPLACE INTO pvp_cooldowns 
               (player1_id, player2_id, cooldown_type, expires_at)
               VALUES (?, ?, 'flee', ?)""",
            (interaction.user.id, opponent_id, expire_time.isoformat())
        )
        
        # Success message
        embed = discord.Embed(
            title="🏃 PvP Escape Successful!",
            description=f"**{player_name}** has fled from combat with **{opponent_name}**!",
            color=0x00ff00
        )
        embed.add_field(name="Escape Cost", value=f"{flee_cost} credits", inline=True)
        embed.add_field(name="Cooldown", value="15 minutes until you can attack each other again", inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        # Notify opponent
        try:
            opponent_user = interaction.guild.get_member(opponent_id)
            if opponent_user:
                opponent_embed = discord.Embed(
                    title="🏃 Opponent Fled!",
                    description=f"**{player_name}** has fled from combat with you!",
                    color=0xffa500
                )
                await opponent_user.send(embed=opponent_embed)
        except discord.Forbidden:
            pass
    @app_commands.command(name="pvp_opt", description="Manage your PvP opt-out status")
    @app_commands.describe(action="Choose to opt in or out of PvP")
    @app_commands.choices(action=[
        app_commands.Choice(name="Opt Out", value="out"),
        app_commands.Choice(name="Opt In", value="in"),
        app_commands.Choice(name="Check Status", value="status")
    ])
    async def pvp_opt(self, interaction: discord.Interaction, action: str):
        """Manage PvP opt-out status"""
        # Check if user has character
        char_data = self.db.execute_query(
            "SELECT alignment FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You need a character first! Use `/character create`.", 
                ephemeral=True
            )
            return
        
        alignment = char_data[0]
        
        if action == "status":
            # Check current status
            opt_out_data = self.db.execute_query(
                "SELECT opted_out FROM pvp_opt_outs WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            opted_out = opt_out_data[0] if opt_out_data else False
            
            embed = discord.Embed(
                title="🛡️ PvP Status",
                color=0x00ff00 if not opted_out else 0xff4444
            )
            embed.add_field(
                name="Current Status", 
                value="Opted In" if not opted_out else "Opted Out", 
                inline=True
            )
            embed.add_field(name="Alignment", value=alignment.title(), inline=True)
            embed.add_field(
                name="Note", 
                value="Opposite alignments can always attack each other regardless of opt-out status", 
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif action == "out":
            # Opt out of PvP
            self.db.execute_query(
                """INSERT OR REPLACE INTO pvp_opt_outs (user_id, opted_out, updated_at)
                   VALUES (?, 1, datetime('now'))""",
                (interaction.user.id,)
            )
            
            embed = discord.Embed(
                title="🛡️ PvP Opt-Out",
                description="You have opted out of PvP combat!",
                color=0x00ff00
            )
            embed.add_field(
                name="Protection", 
                value="You cannot attack or be attacked by players of the same or neutral alignment", 
                inline=False
            )
            embed.add_field(
                name="Exception", 
                value="Opposite alignments (Loyal vs Bandit) can still attack each other", 
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif action == "in":
            # Opt into PvP
            self.db.execute_query(
                """INSERT OR REPLACE INTO pvp_opt_outs (user_id, opted_out, updated_at)
                   VALUES (?, 0, datetime('now'))""",
                (interaction.user.id,)
            )
            
            embed = discord.Embed(
                title="⚔️ PvP Opt-In",
                description="You have opted into PvP combat!",
                color=0xff4444
            )
            embed.add_field(
                name="Risk", 
                value="You can now attack and be attacked by any player at the same location", 
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @rob_group.command(name="npc", description="Attempt to rob an NPC")
    async def rob_npc(self, interaction: discord.Interaction):
        # Check if user has character
        char_data = self.db.execute_query(
            "SELECT current_location, location_status, hp, combat FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You need a character to rob! Use `/character create` first.", 
                ephemeral=True
            )
            return

        current_location, location_status, player_hp, player_combat = char_data

        if not current_location:
            await interaction.response.send_message(
                "You're in deep space and cannot rob anyone here!", 
                ephemeral=True
            )
            return

        if player_hp <= 0:
            await interaction.response.send_message(
                "You're too injured to attempt robbery! Heal yourself first.", 
                ephemeral=True
            )
            return

        # Check if already in combat
        existing_combat = self.db.execute_query(
            "SELECT combat_id FROM combat_states WHERE player_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if existing_combat:
            await interaction.response.send_message(
                "You can't rob while in combat!", 
                ephemeral=True
            )
            return

        # Get available NPCs
        is_docked = location_status == "docked"

        if is_docked:
            npcs = self.db.execute_query(
                """SELECT npc_id, name, occupation, alignment, credits 
                   FROM static_npcs 
                   WHERE location_id = ? AND is_alive = 1""",
                (current_location,),
                fetch='all'
            )
        else:
            npcs = self.db.execute_query(
                """SELECT npc_id, name, ship_name, alignment, credits 
                   FROM dynamic_npcs 
                   WHERE current_location = ? AND is_alive = 1""",
                (current_location,),
                fetch='all'
            )

        if not npcs:
            await interaction.response.send_message(
                "No NPCs available to rob at this location!", 
                ephemeral=True
            )
            return

        # Create dropdown with NPCs
        view = NPCRobSelectView(
            self.bot, interaction.user.id, current_location, npcs, is_docked
        )
        
        await interaction.response.send_message(
            f"💰 **{'Ground' if is_docked else 'Space'} Robbery Available**\nChoose an NPC to rob:",
            view=view,
            ephemeral=True
        )

    async def _execute_combat_round(self, interaction, combat_id, target_npc_id, target_npc_type, 
                                    combat_type, location_id, player_name, player_combat):
        """Execute a single round of combat"""
        effect_checker = ItemEffectChecker(self.bot)
        combat_boost = effect_checker.get_combat_boost(interaction.user.id)
        effective_combat = player_combat + combat_boost
        # Get NPC data
        if target_npc_type == "static":
            npc_data = self.db.execute_query(
                "SELECT name, hp, max_hp, combat_rating, alignment FROM static_npcs WHERE npc_id = ?",
                (target_npc_id,),
                fetch='one'
            )
        else:
            if combat_type == "space":
                npc_data = self.db.execute_query(
                    "SELECT name, ship_hull as hp, max_ship_hull as max_hp, combat_rating, alignment FROM dynamic_npcs WHERE npc_id = ?",
                    (target_npc_id,),
                    fetch='one'
                )
            else:
                npc_data = self.db.execute_query(
                    "SELECT name, hp, max_hp, combat_rating, alignment FROM dynamic_npcs WHERE npc_id = ?",
                    (target_npc_id,),
                    fetch='one'
                )

        if not npc_data:
            await interaction.response.send_message("Target NPC not found!", ephemeral=True)
            return

        npc_name, npc_hp, npc_max_hp, npc_combat, npc_alignment = npc_data

        # Player attack roll
        player_roll = random.randint(1, 20) + effective_combat  # Changed from player_combat
        npc_defense = random.randint(1, 20) + npc_combat

        damage_dealt = 0
        if player_roll > npc_defense:
            base_damage = random.randint(5, 15)
            skill_bonus = effective_combat // 2  # Changed from player_combat // 2
            damage_dealt = base_damage + skill_bonus
            new_npc_hp = max(0, npc_hp - damage_dealt)

            # Update NPC HP
            if target_npc_type == "static":
                self.db.execute_query(
                    "UPDATE static_npcs SET hp = ? WHERE npc_id = ?",
                    (new_npc_hp, target_npc_id)
                )
            else:
                if combat_type == "space":
                    self.db.execute_query(
                        "UPDATE dynamic_npcs SET ship_hull = ? WHERE npc_id = ?",
                        (new_npc_hp, target_npc_id)
                    )
                else:
                    self.db.execute_query(
                        "UPDATE dynamic_npcs SET hp = ? WHERE npc_id = ?",
                        (new_npc_hp, target_npc_id)
                    )

        # Check if NPC died
        if npc_hp - damage_dealt <= 0:
            await self._handle_npc_death(
                interaction, combat_id, target_npc_id, target_npc_type, 
                npc_name, npc_alignment, location_id
            )
            return

        # Set player cooldown
        next_action_time = datetime.utcnow() + timedelta(seconds=10)
        self.db.execute_query(
            "UPDATE combat_states SET player_can_act_time = ?, last_action_time = ? WHERE combat_id = ?",
            (next_action_time.isoformat(), datetime.utcnow().isoformat(), combat_id)
        )

        # Create combat result embed
        embed = discord.Embed(
            title="⚔️ Combat Round",
            color=0xff4444 if damage_dealt == 0 else 0x00ff00
        )

        if damage_dealt > 0:
            embed.add_field(
                name="💥 Hit!",
                value=f"**{player_name}** deals {damage_dealt} damage to **{npc_name}**",
                inline=False
            )
        else:
            embed.add_field(
                name="❌ Miss!",
                value=f"**{player_name}**'s attack missed!",
                inline=False
            )

        embed.add_field(
            name="🎲 Rolls",
            value=f"Your attack: {player_roll} vs NPC defense: {npc_defense}",
            inline=False
        )

        embed.add_field(
            name="❤️ NPC Health",
            value=f"**{npc_name}**: {max(0, npc_hp - damage_dealt)}/{npc_max_hp}",
            inline=False
        )

        embed.add_field(
            name="⏰ Next Action",
            value="You can attack again in 10 seconds",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_npc_death(self, interaction, combat_id, npc_id, npc_type, 
                                npc_name, npc_alignment, location_id):
        """Handle NPC death and reputation changes"""
        
        # End combat
        self.db.execute_query(
            "DELETE FROM combat_states WHERE combat_id = ?",
            (combat_id,)
        )

        # Mark NPC as dead
        if npc_type == "static":
            self.db.execute_query(
                "UPDATE static_npcs SET is_alive = 0 WHERE npc_id = ?",
                (npc_id,)
            )
            # Schedule respawn for static NPCs
            respawn_time = datetime.utcnow() + timedelta(hours=random.randint(2, 6))
            npc_backup = self.db.execute_query(
                "SELECT * FROM static_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if npc_backup:
                self.db.execute_query(
                    """INSERT INTO npc_respawn_queue 
                       (original_npc_id, location_id, scheduled_respawn_time, npc_data)
                       VALUES (?, ?, ?, ?)""",
                    (npc_id, location_id, respawn_time.isoformat(), str(npc_backup))
                )
        else:
            self.db.execute_query(
                "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                (npc_id,)
            )

        # Calculate reputation changes
        rep_change = self._calculate_reputation_change(npc_alignment, "kill")

        # Apply reputation changes
        reputation_cog = self.bot.get_cog('ReputationCog')
        if reputation_cog:
            await reputation_cog.update_reputation(
                interaction.user.id, location_id, rep_change
            )
        await self._send_kill_reputation_feedback(
            interaction, location_id, rep_change, npc_alignment
        )
        # Create death embed
        embed = discord.Embed(
            title="💀 Combat Victory!",
            description=f"**{npc_name}** has been defeated!",
            color=0x8b0000
        )

        rep_text = f"{'Gained' if rep_change > 0 else 'Lost'} {abs(rep_change)} reputation"
        embed.add_field(name="Reputation Change", value=rep_text, inline=False)

        if npc_type == "static":
            embed.add_field(
                name="📅 Respawn", 
                value="This NPC will respawn in 2-6 hours",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _calculate_reputation_change(self, npc_alignment: str, action: str) -> int:
        """Calculate reputation change based on NPC alignment and action"""
        base_values = {
            "attack": {"loyal": -10, "neutral": -7, "bandit": 7},
            "kill": {"loyal": -15, "neutral": -10, "bandit": 10},
            "rob_success": {"loyal": -8, "neutral": -4, "bandit": 5},
            "rob_fail": {"loyal": -9, "neutral": -5, "bandit": 3}
        }
        
        return base_values.get(action, {}).get(npc_alignment, 0)

    @tasks.loop(seconds=45)
    async def npc_counterattack_loop(self):
        """Background task for NPC counterattacks"""
        try:
            # Get all active combats where NPC should counterattack
            active_combats = self.db.execute_query(
                """SELECT combat_id, player_id, target_npc_id, target_npc_type, 
                          combat_type, location_id, next_npc_action_time
                   FROM combat_states 
                   WHERE next_npc_action_time IS NULL 
                   OR datetime(next_npc_action_time) <= datetime('now')""",
                fetch='all'
            )

            for combat_data in active_combats:
                await self._execute_npc_counterattack(combat_data)

        except Exception as e:
            print(f"Error in NPC counterattack loop: {e}")

    async def _execute_npc_counterattack(self, combat_data):
        """Execute an NPC counterattack"""
        combat_id, player_id, npc_id, npc_type, combat_type, location_id, _ = combat_data

        # Get player data
        player_data = self.db.execute_query(
            "SELECT hp, combat, name FROM characters WHERE user_id = ?",
            (player_id,),
            fetch='one'
        )
        
        if not player_data or player_data[0] <= 0:
            # Player is dead or gone, end combat
            self.db.execute_query(
                "DELETE FROM combat_states WHERE combat_id = ?",
                (combat_id,)
            )
            return

        player_hp, player_combat, player_name = player_data
        effect_checker = ItemEffectChecker(self.bot)
        combat_boost = effect_checker.get_combat_boost(player_id)
        effective_player_combat = player_combat + combat_boost
        # Get NPC data
        if npc_type == "static":
            npc_data = self.db.execute_query(
                "SELECT name, combat_rating FROM static_npcs WHERE npc_id = ? AND is_alive = 1",
                (npc_id,),
                fetch='one'
            )
        else:
            npc_data = self.db.execute_query(
                "SELECT name, combat_rating FROM dynamic_npcs WHERE npc_id = ? AND is_alive = 1",
                (npc_id,),
                fetch='one'
            )

        if not npc_data:
            # NPC is dead or gone, end combat
            self.db.execute_query(
                "DELETE FROM combat_states WHERE combat_id = ?",
                (combat_id,)
            )
            return

        npc_name, npc_combat = npc_data

        # NPC attack roll
        npc_roll = random.randint(1, 20) + npc_combat
        player_defense = random.randint(1, 20) + effective_player_combat

        damage_dealt = 0
        if npc_roll > player_defense:
            base_damage = random.randint(3, 12)
            skill_bonus = npc_combat // 3
            damage_dealt = base_damage + skill_bonus
            new_player_hp = max(0, player_hp - damage_dealt)

            # Update player HP
            self.db.execute_query(
                "UPDATE characters SET hp = ? WHERE user_id = ?",
                (new_player_hp, player_id)
            )

            # Check if player died
            if new_player_hp <= 0:
                # End combat and handle player death
                self.db.execute_query(
                    "DELETE FROM combat_states WHERE combat_id = ?",
                    (combat_id,)
                )
                # Let the character system handle death
                char_cog = self.bot.get_cog('CharacterCog')
                if char_cog:
                    user = self.bot.get_user(player_id)
                    if user and user.mutual_guilds:
                        await char_cog.update_character_hp(
                            player_id, 0, user.mutual_guilds[0], f"Killed by {npc_name} in combat"
                        )
                return

        # Schedule next NPC action
        next_npc_time = datetime.utcnow() + timedelta(seconds=random.randint(30, 45))
        self.db.execute_query(
            "UPDATE combat_states SET next_npc_action_time = ? WHERE combat_id = ?",
            (next_npc_time.isoformat(), combat_id)
        )

        # Send notification to location channel instead of DM
        if damage_dealt > 0 or random.random() < 0.3:  # Always send hits, 30% chance for misses
            # Get location channel
            channel_id = self.db.execute_query(
                "SELECT channel_id FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )
            
            if channel_id and channel_id[0]:
                for guild in self.bot.guilds:
                    channel = guild.get_channel(channel_id[0])
                    if channel:
                        embed = discord.Embed(
                            title="⚔️ NPC Counterattack!",
                            color=0xff0000 if damage_dealt > 0 else 0xffff00
                        )

                        if damage_dealt > 0:
                            embed.add_field(
                                name="💥 Hit!",
                                value=f"**{npc_name}** deals {damage_dealt} damage to **{player_name}**!",
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name="❌ Miss!",
                                value=f"**{npc_name}**'s attack missed **{player_name}**!",
                                inline=False
                            )

                        embed.add_field(
                            name="❤️ Player Health",
                            value=f"**{player_name}**: {max(0, player_hp - damage_dealt)} HP",
                            inline=False
                        )

                        try:
                            await channel.send(embed=embed)
                        except Exception:
                            pass  # Channel not accessible

    @tasks.loop(minutes=30)
    async def npc_respawn_loop(self):
        """Background task for NPC respawning"""
        try:
            # Check for NPCs ready to respawn
            ready_respawns = self.db.execute_query(
                """SELECT respawn_id, original_npc_id, location_id, npc_data
                   FROM npc_respawn_queue 
                   WHERE datetime(scheduled_respawn_time) <= datetime('now')""",
                fetch='all'
            )

            for respawn_data in ready_respawns:
                respawn_id, original_npc_id, location_id, npc_data_str = respawn_data
                
                # Restore the NPC
                self.db.execute_query(
                    """UPDATE static_npcs 
                       SET is_alive = 1, hp = max_hp 
                       WHERE npc_id = ?""",
                    (original_npc_id,)
                )

                # Remove from respawn queue
                self.db.execute_query(
                    "DELETE FROM npc_respawn_queue WHERE respawn_id = ?",
                    (respawn_id,)
                )

        except Exception as e:
            print(f"Error in NPC respawn loop: {e}")

    @npc_counterattack_loop.before_loop
    async def before_npc_counterattack_loop(self):
        await self.bot.wait_until_ready()

    @npc_respawn_loop.before_loop
    async def before_npc_respawn_loop(self):
        await self.bot.wait_until_ready()
    async def _send_kill_reputation_feedback(self, interaction, location_id, rep_change, npc_alignment):
        """Send reputation change feedback to location channel for kills"""
        if rep_change == 0:
            return
            
        # Get location channel
        channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not channel_id or not channel_id[0]:
            return
        
        # Get player name
        player_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not player_name:
            return
            
        player_name = player_name[0]
        
        # Send feedback to location channel
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id[0])
            if channel:
                # Determine reputation change description
                if rep_change > 0:
                    change_text = f"gained {rep_change}"
                    color = 0x00ff00
                    emoji = "📈"
                else:
                    change_text = f"lost {abs(rep_change)}"
                    color = 0xff0000
                    emoji = "📉"
                
                embed = discord.Embed(
                    title=f"{emoji} Reputation Change",
                    description=f"**{player_name}** has {change_text} reputation for killing a {npc_alignment} individual.",
                    color=color
                )
                embed.add_field(
                    name="Impact",
                    value="Reputation changes affect how NPCs and factions view you.",
                    inline=False
                )
                
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass  # Channel not accessible
    @rob_group.command(name="player", description="Attempt to rob another player")
    @app_commands.describe(target="The player you want to rob")
    async def player(self, interaction: discord.Interaction, target: discord.Member):
        # Basic validation
        if target.id == interaction.user.id:
            await interaction.response.send_message("You cannot rob yourself!", ephemeral=True)
            return

        # Check if robber has character
        robber_data = self.db.execute_query(
            "SELECT current_location, location_status, hp, combat, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not robber_data:
            await interaction.response.send_message(
                "You need a character to rob! Use `/character create` first.", 
                ephemeral=True
            )
            return

        # Check if target has character
        victim_data = self.db.execute_query(
            "SELECT current_location, location_status, hp, combat, name, money FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not victim_data:
            await interaction.response.send_message(
                f"{target.display_name} doesn't have a character!", 
                ephemeral=True
            )
            return

        robber_location, robber_status, robber_hp, robber_combat, robber_name = robber_data
        victim_location, victim_status, victim_hp, victim_combat, victim_name, victim_money = victim_data

        # Location and status checks
        if not robber_location or not victim_location:
            await interaction.response.send_message(
                "Both players must be at a location to attempt robbery!", 
                ephemeral=True
            )
            return

        if robber_location != victim_location:
            await interaction.response.send_message(
                "You must be at the same location as your target!", 
                ephemeral=True
            )
            return

        if robber_status != victim_status:
            await interaction.response.send_message(
                "Both players must have the same docked/undocked status!", 
                ephemeral=True
            )
            return

        # Health checks
        if robber_hp <= 0:
            await interaction.response.send_message(
                "You're too injured to attempt robbery! Heal yourself first.", 
                ephemeral=True
            )
            return

        if victim_hp <= 0:
            await interaction.response.send_message(
                f"{victim_name} is too injured to be robbed!", 
                ephemeral=True
            )
            return

        # Check if either player is in combat
        if self.check_any_combat_status(interaction.user.id) or self.check_any_combat_status(target.id):
            await interaction.response.send_message(
                "Cannot rob while in combat!", 
                ephemeral=True
            )
            return

        # Check robbery cooldown
        robbery_cooldown = self.db.execute_query(
            """SELECT expires_at FROM pvp_cooldowns 
               WHERE ((player1_id = ? AND player2_id = ?) OR (player1_id = ? AND player2_id = ?))
               AND cooldown_type = 'robbery' AND expires_at > datetime('now')""",
            (interaction.user.id, target.id, target.id, interaction.user.id),
            fetch='one'
        )

        if robbery_cooldown:
            await interaction.response.send_message(
                f"You cannot rob {victim_name} for another few minutes due to robbery cooldown!", 
                ephemeral=True
            )
            return

        # Check if victim has money
        if victim_money <= 0:
            await interaction.response.send_message(
                f"{victim_name} has no credits to steal!", 
                ephemeral=True
            )
            return

        # Get location channel
        location_channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (robber_location,),
            fetch='one'
        )

        if not location_channel_id or not location_channel_id[0]:
            await interaction.response.send_message(
                "This location doesn't have a proper channel for robberies!", 
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(location_channel_id[0])
        if not channel:
            await interaction.response.send_message(
                "Location channel not found!", 
                ephemeral=True
            )
            return

        # Create robbery timeout (2 minutes default, configurable)
        timeout_minutes = 2  # You can make this configurable
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        # Create robbery embed and view
        robbery_view = PlayerRobberyView(
            self.bot, interaction.user.id, target.id, robber_location, 
            robber_name, victim_name, expires_at, timeout_minutes
        )

        embed = discord.Embed(
            title="🔫 ROBBERY IN PROGRESS",
            description=f"**{robber_name}** is attempting to rob **{victim_name}**!",
            color=0xff4444
        )
        embed.add_field(
            name="Location", 
            value=f"This is happening here at this location", 
            inline=False
        )
        embed.add_field(
            name="Victim's Choice", 
            value=f"{victim_name} must choose to **Surrender** or **Fight Back**", 
            inline=False
        )
        embed.add_field(
            name="Time Limit", 
            value=f"{timeout_minutes} minutes to respond or automatic surrender", 
            inline=False
        )

        # Send to location channel
        robbery_message = await channel.send(
            content=f"{target.mention}", 
            embed=embed, 
            view=robbery_view
        )

        # Store pending robbery
        self.db.execute_query(
            """INSERT INTO pending_robberies 
               (robber_id, victim_id, location_id, message_id, channel_id, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (interaction.user.id, target.id, robber_location, robbery_message.id, channel.id, expires_at.isoformat())
        )

        # Update view with message ID
        robbery_view.message_id = robbery_message.id

        await interaction.response.send_message(
            f"Robbery attempt sent to location channel! {victim_name} has {timeout_minutes} minutes to respond.", 
            ephemeral=True
        )

# Add this View class to handle robbery interactions
class PlayerRobberyView(discord.ui.View):
    def __init__(self, bot, robber_id: int, victim_id: int, location_id: int, 
                 robber_name: str, victim_name: str, expires_at: datetime, timeout_minutes: int):
        super().__init__(timeout=timeout_minutes * 60)  # Convert to seconds
        self.bot = bot
        self.robber_id = robber_id
        self.victim_id = victim_id
        self.location_id = location_id
        self.robber_name = robber_name
        self.victim_name = victim_name
        self.expires_at = expires_at
        self.message_id = None
        self.resolved = False

    async def on_timeout(self):
        """Handle timeout - automatic surrender"""
        if self.resolved:
            return
            
        self.resolved = True
        
        # Process automatic surrender
        await self._process_surrender(None, automatic=True)

    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.danger, emoji="🏳️")
    async def surrender_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.victim_id:
            await interaction.response.send_message("You're not the victim of this robbery!", ephemeral=True)
            return
            
        if self.resolved:
            await interaction.response.send_message("This robbery has already been resolved!", ephemeral=True)
            return
            
        self.resolved = True
        await self._process_surrender(interaction, automatic=False)

    @discord.ui.button(label="Fight Back", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def fight_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.victim_id:
            await interaction.response.send_message("You're not the victim of this robbery!", ephemeral=True)
            return
            
        if self.resolved:
            await interaction.response.send_message("This robbery has already been resolved!", ephemeral=True)
            return
            
        self.resolved = True
        await self._process_fight_back(interaction)

    async def _process_surrender(self, interaction, automatic: bool = False):
        """Process victim surrender"""
        # Get current data
        victim_data = self.bot.db.execute_query(
            "SELECT money, hp FROM characters WHERE user_id = ?",
            (self.victim_id,),
            fetch='one'
        )
        
        if not victim_data:
            return

        victim_money, victim_hp = victim_data
        
        # Calculate stolen amount (random 20-50% of credits)
        steal_percentage = random.uniform(0.2, 0.5)
        stolen_credits = int(victim_money * steal_percentage)
        stolen_credits = max(stolen_credits, min(100, victim_money))  # Minimum 100 or all they have
        
        # Get victim's items for potential theft
        victim_items = self.bot.db.execute_query(
            "SELECT item_name, quantity FROM character_inventory WHERE user_id = ?",
            (self.victim_id,),
            fetch='all'
        )
        
        stolen_items = []
        if victim_items:
            # Steal 1-3 random items
            num_items_to_steal = min(random.randint(1, 3), len(victim_items))
            items_to_steal = random.sample(victim_items, num_items_to_steal)
            
            for item_name, quantity in items_to_steal:
                stolen_quantity = min(random.randint(1, max(1, quantity // 2)), quantity)
                stolen_items.append((item_name, stolen_quantity))
        
        # Small chance of HP damage (10%)
        hp_damage = 0
        if random.random() < 0.1:
            hp_damage = random.randint(5, 15)
        
        # Transfer credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (stolen_credits, self.victim_id)
        )
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (stolen_credits, self.robber_id)
        )
        
        # Transfer items
        for item_name, stolen_quantity in stolen_items:
            # Remove from victim
            self.bot.db.execute_query(
                "UPDATE character_inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                (stolen_quantity, self.victim_id, item_name)
            )
            # Add to robber
            self.bot.db.execute_query(
                """INSERT OR REPLACE INTO character_inventory (user_id, item_name, quantity)
                   VALUES (?, ?, COALESCE((SELECT quantity FROM character_inventory WHERE user_id = ? AND item_name = ?), 0) + ?)""",
                (self.robber_id, item_name, self.robber_id, item_name, stolen_quantity)
            )
            # Clean up zero quantities
            self.bot.db.execute_query(
                "DELETE FROM character_inventory WHERE quantity <= 0",
            )
        
        # Apply HP damage if any
        if hp_damage > 0:
            self.bot.db.execute_query(
                "UPDATE characters SET hp = max(0, hp - ?) WHERE user_id = ?",
                (hp_damage, self.victim_id)
            )
        
        # Add robbery cooldown
        expire_time = datetime.utcnow() + timedelta(minutes=15)
        self.bot.db.execute_query(
            """INSERT OR REPLACE INTO pvp_cooldowns 
               (player1_id, player2_id, cooldown_type, expires_at)
               VALUES (?, ?, 'robbery', ?)""",
            (self.robber_id, self.victim_id, expire_time.isoformat())
        )
        
        # Clean up pending robbery
        self.bot.db.execute_query(
            "DELETE FROM pending_robberies WHERE robber_id = ? AND victim_id = ?",
            (self.robber_id, self.victim_id)
        )
        
        # Create result embed
        if automatic:
            title = "🏳️ AUTOMATIC SURRENDER"
            description = f"**{self.victim_name}** froze in fear, allowing **{self.robber_name}** to take everything!"
            color = 0x888888
        else:
            title = "🏳️ SURRENDER"
            description = f"**{self.victim_name}** chose to surrender to **{self.robber_name}**!"
            color = 0xffa500
            
        embed = discord.Embed(title=title, description=description, color=color)
        embed.add_field(name="Stolen Credits", value=f"{stolen_credits}", inline=True)
        
        if stolen_items:
            items_text = ", ".join([f"{qty}x {item}" for item, qty in stolen_items])
            embed.add_field(name="Stolen Items", value=items_text, inline=True)
        
        if hp_damage > 0:
            embed.add_field(name="Damage Taken", value=f"{hp_damage} HP", inline=True)
            
        embed.add_field(name="Cooldown", value="15 minutes until next robbery attempt", inline=False)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # Timeout case - edit the message directly
            channel = self.bot.get_channel(self.bot.db.execute_query(
                "SELECT channel_id FROM pending_robberies WHERE message_id = ?",
                (self.message_id,),
                fetch='one'
            )[0])
            if channel:
                try:
                    message = await channel.fetch_message(self.message_id)
                    await message.edit(embed=embed, view=self)
                except discord.NotFound:
                    pass

    async def _process_fight_back(self, interaction):
        """Process victim fighting back"""
        # Get combat stats
        effect_checker = ItemEffectChecker(self.bot)
        # Get combat boosts
        robber_boost = effect_checker.get_combat_boost(self.robber_id)
        victim_boost = effect_checker.get_combat_boost(self.victim_id)
        
        robber_combat, robber_hp, robber_name = robber_data
        victim_combat, victim_hp, victim_name, victim_money = victim_data
        
        # Apply boosts
        effective_robber_combat = robber_combat + robber_boost
        effective_victim_combat = victim_combat + victim_boost    
        robber_data = self.bot.db.execute_query(
            "SELECT combat, hp, name FROM characters WHERE user_id = ?",
            (self.robber_id,),
            fetch='one'
        )
        
        victim_data = self.bot.db.execute_query(
            "SELECT combat, hp, name, money FROM characters WHERE user_id = ?",
            (self.victim_id,),
            fetch='one'
        )
        
        if not robber_data or not victim_data:
            await interaction.response.send_message("Error retrieving character data!", ephemeral=True)
            return

        robber_combat, robber_hp, robber_name = robber_data
        victim_combat, victim_hp, victim_name, victim_money = victim_data
        
        # Combat rolls
        robber_roll = random.randint(1, 20) + effective_robber_combat
        victim_roll = random.randint(1, 20) + effective_victim_combat
        
        # Determine winner
        if victim_roll >= robber_roll:
            # Victim wins
            await self._victim_wins_fight(interaction, robber_roll, victim_roll, robber_combat, victim_combat)
        else:
            # Robber wins
            await self._robber_wins_fight(interaction, robber_roll, victim_roll, robber_combat, victim_combat, victim_money)

    async def _victim_wins_fight(self, interaction, robber_roll, victim_roll, robber_combat, victim_combat):
        """Handle victim winning the fight"""
        # Determine damage to robber
        damage_to_robber = random.randint(10, 20) + (effective_victim_combat // 2)
        effect_checker = ItemEffectChecker(self.bot)
        robber_boost = effect_checker.get_combat_boost(self.robber_id)
        victim_boost = effect_checker.get_combat_boost(self.victim_id)
        effective_robber_combat = robber_combat + robber_boost
        effective_victim_combat = victim_combat + victim_boost    
        # Small chance victim takes damage too
        damage_to_victim = 0
        if random.random() < 0.3:  # 30% chance
            damage_to_victim = random.randint(5, 10)
        
        # Get location status to determine HP vs Hull damage
        location_status = self.bot.db.execute_query(
            "SELECT location_status FROM characters WHERE user_id = ?",
            (self.robber_id,),
            fetch='one'
        )[0]
        
        if location_status == "docked":
            # Ground combat - HP damage
            self.bot.db.execute_query(
                "UPDATE characters SET hp = max(0, hp - ?) WHERE user_id = ?",
                (damage_to_robber, self.robber_id)
            )
            if damage_to_victim > 0:
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = max(0, hp - ?) WHERE user_id = ?",
                    (damage_to_victim, self.victim_id)
                )
            damage_type = "HP"
        else:
            # Space combat - Hull damage
            # Apply damage to ship hull instead
            damage_type = "Hull"
            # Note: You'll need to implement ship hull damage logic here
        
        # Add robbery cooldown
        expire_time = datetime.utcnow() + timedelta(minutes=15)
        self.bot.db.execute_query(
            """INSERT OR REPLACE INTO pvp_cooldowns 
               (player1_id, player2_id, cooldown_type, expires_at)
               VALUES (?, ?, 'robbery', ?)""",
            (self.robber_id, self.victim_id, expire_time.isoformat())
        )
        
        # Clean up pending robbery
        self.bot.db.execute_query(
            "DELETE FROM pending_robberies WHERE robber_id = ? AND victim_id = ?",
            (self.robber_id, self.victim_id)
        )
        
        # Create result embed
        embed = discord.Embed(
            title="⚔️ VICTIM FIGHTS BACK - VICTIM WINS!",
            description=f"**{self.victim_name}** successfully fought off **{self.robber_name}**!",
            color=0x00ff00
        )
        embed.add_field(
            name="Combat Rolls",
            value=f"{self.robber_name}: {robber_roll}\n{self.victim_name}: {victim_roll}",
            inline=True
        )
        embed.add_field(
            name="Damage Dealt",
            value=f"{self.robber_name}: -{damage_to_robber} {damage_type}" + 
                  (f"\n{self.victim_name}: -{damage_to_victim} {damage_type}" if damage_to_victim > 0 else ""),
            inline=True
        )
        embed.add_field(name="Result", value="No credits or items stolen!", inline=False)
        embed.add_field(name="Cooldown", value="15 minutes until next robbery attempt", inline=False)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def _robber_wins_fight(self, interaction, robber_roll, victim_roll, robber_combat, victim_combat, victim_money):
        """Handle robber winning the fight"""
        effect_checker = ItemEffectChecker(self.bot)
        robber_boost = effect_checker.get_combat_boost(self.robber_id)
        victim_boost = effect_checker.get_combat_boost(self.victim_id)
        effective_robber_combat = robber_combat + robber_boost
        effective_victim_combat = victim_combat + victim_boost        
        # Similar damage calculation but robber wins
        damage_to_victim = random.randint(10, 20) + (effective_robber_combat // 2)
        damage_to_robber = 0
        if random.random() < 0.3:  # 30% chance robber takes some damage
            damage_to_robber = random.randint(5, 10)
        
        # Apply damage (similar logic to victim wins)
        location_status = self.bot.db.execute_query(
            "SELECT location_status FROM characters WHERE user_id = ?",
            (self.robber_id,),
            fetch='one'
        )[0]
        
        if location_status == "docked":
            self.bot.db.execute_query(
                "UPDATE characters SET hp = max(0, hp - ?) WHERE user_id = ?",
                (damage_to_victim, self.victim_id)
            )
            if damage_to_robber > 0:
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = max(0, hp - ?) WHERE user_id = ?",
                    (damage_to_robber, self.robber_id)
                )
            damage_type = "HP"
        else:
            damage_type = "Hull"
            # Ship hull damage logic here
        
        # Robber takes 90% of victim's money and items
        stolen_credits = int(victim_money * 0.9)
        
        # Transfer credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (stolen_credits, self.victim_id)
        )
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (stolen_credits, self.robber_id)
        )
        
        # Get and transfer 90% of items
        victim_items = self.bot.db.execute_query(
            "SELECT item_name, quantity FROM character_inventory WHERE user_id = ?",
            (self.victim_id,),
            fetch='all'
        )
        
        stolen_items = []
        for item_name, quantity in victim_items:
            stolen_quantity = int(quantity * 0.9)
            if stolen_quantity > 0:
                stolen_items.append((item_name, stolen_quantity))
                # Transfer items
                self.bot.db.execute_query(
                    "UPDATE character_inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                    (stolen_quantity, self.victim_id, item_name)
                )
                self.bot.db.execute_query(
                    """INSERT OR REPLACE INTO character_inventory (user_id, item_name, quantity)
                       VALUES (?, ?, COALESCE((SELECT quantity FROM character_inventory WHERE user_id = ? AND item_name = ?), 0) + ?)""",
                    (self.robber_id, item_name, self.robber_id, item_name, stolen_quantity)
                )
        
        # Clean up zero quantities
        self.bot.db.execute_query("DELETE FROM character_inventory WHERE quantity <= 0")
        
        # Add robbery cooldown
        expire_time = datetime.utcnow() + timedelta(minutes=15)
        self.bot.db.execute_query(
            """INSERT OR REPLACE INTO pvp_cooldowns 
               (player1_id, player2_id, cooldown_type, expires_at)
               VALUES (?, ?, 'robbery', ?)""",
            (self.robber_id, self.victim_id, expire_time.isoformat())
        )
        
        # Clean up pending robbery
        self.bot.db.execute_query(
            "DELETE FROM pending_robberies WHERE robber_id = ? AND victim_id = ?",
            (self.robber_id, self.victim_id)
        )
        
        # Create result embed
        embed = discord.Embed(
            title="⚔️ VICTIM FIGHTS BACK - ROBBER WINS!",
            description=f"**{self.robber_name}** overpowered **{self.victim_name}**!",
            color=0xff4444
        )
        embed.add_field(
            name="Combat Rolls",
            value=f"{self.robber_name}: {robber_roll}\n{self.victim_name}: {victim_roll}",
            inline=True
        )
        embed.add_field(
            name="Damage Dealt",
            value=f"{self.victim_name}: -{damage_to_victim} {damage_type}" + 
                  (f"\n{self.robber_name}: -{damage_to_robber} {damage_type}" if damage_to_robber > 0 else ""),
            inline=True
        )
        embed.add_field(name="Stolen Credits", value=f"{stolen_credits} (90%)", inline=True)
        
        if stolen_items:
            items_text = ", ".join([f"{qty}x {item}" for item, qty in stolen_items])
            embed.add_field(name="Stolen Items", value=f"{items_text} (90%)", inline=True)
        
        embed.add_field(name="Cooldown", value="15 minutes until next robbery attempt", inline=False)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
class NPCAttackSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, npcs: list, combat_type: str, is_docked: bool):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.combat_type = combat_type
        self.is_docked = is_docked
        
        # Create select menu for NPCs
        options = []
        
        for npc_data in npcs[:25]:  # Discord limit
            if is_docked:
                npc_id, name, occupation, alignment, hp, max_hp = npc_data
                description = f"{occupation} | {alignment} | HP: {hp}/{max_hp}"
            else:
                npc_id, name, ship_name, alignment, hp, max_hp = npc_data
                description = f"{ship_name} | {alignment} | HP: {hp}/{max_hp}"
            
            # Alignment emoji
            align_emoji = {"loyal": "🟦", "neutral": "👤", "bandit": "🟥"}.get(alignment, "👤")
            
            options.append(
                discord.SelectOption(
                    label=f"{name}",
                    description=description[:100],
                    value=str(npc_id),
                    emoji=align_emoji
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an NPC to attack...",
                options=options
            )
            select.callback = self.npc_selected
            self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_id = int(interaction.data['values'][0])
        
        # Start combat first
        next_npc_time = datetime.utcnow() + timedelta(seconds=random.randint(30, 45))
        
        combat_result = self.bot.db.execute_query(
            """INSERT INTO combat_states 
               (player_id, target_npc_id, target_npc_type, combat_type, location_id, next_npc_action_time, player_can_act_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self.user_id, npc_id, "static" if self.is_docked else "dynamic", 
             self.combat_type, self.location_id, next_npc_time.isoformat(), None)  # Set player_can_act_time to None initially
        )

        # Get combat_id for the just-created combat
        combat_id = self.bot.db.execute_query(
            "SELECT combat_id FROM combat_states WHERE player_id = ? ORDER BY combat_id DESC LIMIT 1",
            (self.user_id,),
            fetch='one'
        )[0]

        # Prevent travel during combat
        self.bot.db.execute_query(
            "UPDATE characters SET location_status = ? WHERE user_id = ?",
            ("combat", self.user_id)
        )
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog:
            # Get NPC alignment
            if self.is_docked:
                npc_alignment = self.bot.db.execute_query(
                    "SELECT alignment FROM static_npcs WHERE npc_id = ?",
                    (npc_id,),
                    fetch='one'
                )
            else:
                npc_alignment = self.bot.db.execute_query(
                    "SELECT alignment FROM dynamic_npcs WHERE npc_id = ?",
                    (npc_id,),
                    fetch='one'
                )
            
            if npc_alignment:
                alignment = npc_alignment[0]
                rep_change = combat_cog._calculate_reputation_change(alignment, "attack")
                
                # Apply reputation change
                reputation_cog = self.bot.get_cog('ReputationCog')
                if reputation_cog:
                    await reputation_cog.update_reputation(
                        self.user_id, self.location_id, rep_change
                    )
                    
                    # Send location feedback
                    await self._send_reputation_feedback(
                        interaction, self.location_id, rep_change, "attacking", alignment
                    )
        # Get player stats for immediate first attack
        player_data = self.bot.db.execute_query(
            "SELECT hp, combat, name FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        player_hp, player_combat, player_name = player_data

        # Execute the first combat round immediately
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog:
            await combat_cog._execute_combat_round(
                interaction, combat_id, npc_id, "static" if self.is_docked else "dynamic", 
                self.combat_type, self.location_id, player_name, player_combat
            )
        else:
            # Fallback if combat cog not found
            embed = discord.Embed(
                title="⚔️ Combat Initiated!",
                description=f"Combat started! Use `/attack fight` to continue fighting.",
                color=0xff4444
            )
            if combat_boost > 0:
                embed.add_field(
                    name="💉 Combat Stims Active",
                    value=f"+{combat_boost} combat effectiveness",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _send_reputation_feedback(self, interaction, location_id, rep_change, action, npc_alignment):
        """Send reputation change feedback to location channel"""
        if rep_change == 0:
            return
            
        # Get location channel
        channel_id = self.bot.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not channel_id or not channel_id[0]:
            return
        
        # Get player name
        player_name = self.bot.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if not player_name:
            return
            
        player_name = player_name[0]
        
        # Send feedback to location channel
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id[0])
            if channel:
                # Determine reputation change description
                if rep_change > 0:
                    change_text = f"gained {rep_change}"
                    color = 0x00ff00
                    emoji = "📈"
                else:
                    change_text = f"lost {abs(rep_change)}"
                    color = 0xff0000
                    emoji = "📉"
                
                # Determine action description
                action_descriptions = {
                    "attacking": f"attacking a {npc_alignment} individual",
                    "robbing": f"robbing a {npc_alignment} individual", 
                    "killing": f"killing a {npc_alignment} individual"
                }
                
                action_desc = action_descriptions.get(action, action)
                
                embed = discord.Embed(
                    title=f"{emoji} Reputation Change",
                    description=f"**{player_name}** has {change_text} reputation for {action_desc}.",
                    color=color
                )
                embed.add_field(
                    name="Impact",
                    value="Reputation changes affect how NPCs and factions view you.",
                    inline=False
                )
                
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass  # Channel not accessible

class NPCRobSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, npcs: list, is_docked: bool):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.is_docked = is_docked
        
        # Create select menu for NPCs
        options = []
        
        for npc_data in npcs[:25]:  # Discord limit
            if is_docked:
                npc_id, name, occupation, alignment, credits = npc_data
                description = f"{occupation} | {alignment} | Credits: {credits}"
            else:
                npc_id, name, ship_name, alignment, credits = npc_data
                description = f"{ship_name} | {alignment} | Credits: {credits}"
            
            # Alignment emoji
            align_emoji = {"loyal": "🟦", "neutral": "⚪", "bandit": "🟥"}.get(alignment, "⚪")
            
            options.append(
                discord.SelectOption(
                    label=f"{name}",
                    description=description[:100],
                    value=str(npc_id),
                    emoji=align_emoji
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an NPC to rob...",
                options=options
            )
            select.callback = self.npc_selected
            self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_id = int(interaction.data['values'][0])
        
        # Get player stats
        player_data = self.bot.db.execute_query(
            "SELECT combat, name FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        player_combat, player_name = player_data

        # Get NPC data
        if self.is_docked:
            npc_data = self.bot.db.execute_query(
                "SELECT name, alignment, credits FROM static_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
        else:
            npc_data = self.bot.db.execute_query(
                "SELECT name, alignment, credits FROM dynamic_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )

        npc_name, npc_alignment, npc_credits = npc_data

        # Robbery attempt roll
        base_chance = 0.3  # 30% base chance
        skill_bonus = player_combat * 0.05  # 5% per combat skill
        total_chance = min(base_chance + skill_bonus, 0.8)  # Cap at 80%

        rob_roll = random.random()
        
        if rob_roll < total_chance:
            # Successful robbery
            stolen_amount = random.randint(max(1, npc_credits // 10), max(1, npc_credits // 3))
            stolen_amount = min(stolen_amount, npc_credits)

            # Update credits
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (stolen_amount, self.user_id)
            )

            if self.is_docked:
                self.bot.db.execute_query(
                    "UPDATE static_npcs SET credits = credits - ? WHERE npc_id = ?",
                    (stolen_amount, npc_id)
                )
            else:
                self.bot.db.execute_query(
                    "UPDATE dynamic_npcs SET credits = credits - ? WHERE npc_id = ?",
                    (stolen_amount, npc_id)
                )

            # Reputation change
            combat_cog = self.bot.get_cog('CombatCog')
            rep_change = combat_cog._calculate_reputation_change(npc_alignment, "rob_success")

            reputation_cog = self.bot.get_cog('ReputationCog')
            if reputation_cog:
                await reputation_cog.update_reputation(self.user_id, self.location_id, rep_change)
            await self._send_reputation_feedback(interaction, self.location_id, rep_change, "robbing", npc_alignment)
            embed = discord.Embed(
                title="💰 Robbery Successful!",
                description=f"**{player_name}** successfully robbed **{npc_name}**!",
                color=0x00ff00
            )
            embed.add_field(name="Stolen", value=f"{stolen_amount} credits", inline=True)
            embed.add_field(name="Reputation", value=f"{'Gained' if rep_change > 0 else 'Lost'} {abs(rep_change)}", inline=True)

        else:
            # Failed robbery - start combat
            combat_cog = self.bot.get_cog('CombatCog')
            rep_change = combat_cog._calculate_reputation_change(npc_alignment, "rob_fail")
            
            reputation_cog = self.bot.get_cog('ReputationCog')
            if reputation_cog:
                await reputation_cog.update_reputation(self.user_id, self.location_id, rep_change)
            await self._send_reputation_feedback(interaction, self.location_id, rep_change, "robbing", npc_alignment)
            # Start combat
            next_npc_time = datetime.utcnow() + timedelta(seconds=random.randint(30, 45))
            
            self.bot.db.execute_query(
                """INSERT INTO combat_states 
                   (player_id, target_npc_id, target_npc_type, combat_type, location_id, next_npc_action_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (self.user_id, npc_id, "static" if self.is_docked else "dynamic", 
                 "ground" if self.is_docked else "space", self.location_id, next_npc_time.isoformat())
            )

            # Prevent travel during combat
            self.bot.db.execute_query(
                "UPDATE characters SET location_status = ? WHERE user_id = ?",
                ("combat", self.user_id)
            )

            embed = discord.Embed(
                title="❌ Robbery Failed!",
                description=f"**{npc_name}** caught you trying to rob them! Combat has begun!",
                color=0xff0000
            )
            embed.add_field(name="Reputation", value=f"Lost {abs(rep_change)}", inline=True)
            embed.add_field(name="Status", value="Combat initiated - you cannot travel!", inline=False)

        embed.add_field(
            name="🎲 Roll",
            value=f"Success chance: {total_chance:.1%}\nRoll: {rob_roll:.2f}",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _send_reputation_feedback(self, interaction, location_id, rep_change, action, npc_alignment):
        """Send reputation change feedback to location channel"""
        if rep_change == 0:
            return
            
        # Get location channel
        channel_id = self.bot.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not channel_id or not channel_id[0]:
            return
        
        # Get player name
        player_name = self.bot.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if not player_name:
            return
            
        player_name = player_name[0]
        
        # Send feedback to location channel
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id[0])
            if channel:
                # Determine reputation change description
                if rep_change > 0:
                    change_text = f"gained {rep_change}"
                    color = 0x00ff00
                    emoji = "📈"
                else:
                    change_text = f"lost {abs(rep_change)}"
                    color = 0xff0000
                    emoji = "📉"
                
                # Determine action description
                action_descriptions = {
                    "attacking": f"attacking a {npc_alignment} individual",
                    "robbing": f"robbing a {npc_alignment} individual", 
                    "killing": f"killing a {npc_alignment} individual"
                }
                
                action_desc = action_descriptions.get(action, action)
                
                embed = discord.Embed(
                    title=f"{emoji} Reputation Change",
                    description=f"**{player_name}** has {change_text} reputation for {action_desc}.",
                    color=color
                )
                embed.add_field(
                    name="Impact",
                    value="Reputation changes affect how NPCs and factions view you.",
                    inline=False
                )
                
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass  # Channel not accessible

async def setup(bot):
    await bot.add_cog(CombatCog(bot))