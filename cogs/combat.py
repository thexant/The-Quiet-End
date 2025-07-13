# cogs/combat.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from utils.location_utils import get_character_location_status

class CombatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        # Start background task for NPC counterattacks
        self.npc_counterattack_loop.start()
        self.npc_respawn_loop.start()

    def cog_unload(self):
        self.npc_counterattack_loop.cancel()
        self.npc_respawn_loop.cancel()

    # Attack command group
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

    @attack_group.command(name="fight", description="Continue an ongoing fight")
    async def continue_fight(self, interaction: discord.Interaction):
        # Check if user is in combat
        combat_data = self.db.execute_query(
            """SELECT combat_id, target_npc_id, target_npc_type, combat_type, 
                      location_id, player_can_act_time
               FROM combat_states 
               WHERE player_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )

        if not combat_data:
            await interaction.response.send_message(
                "You're not in combat! Use `/attack npc` to start a fight.", 
                ephemeral=True
            )
            return

        combat_id, target_npc_id, target_npc_type, combat_type, location_id, can_act_time = combat_data

        # Check cooldown
        if can_act_time:
            try:
                can_act_datetime = datetime.fromisoformat(can_act_time)
                current_time = datetime.now()
                if current_time < can_act_datetime:
                    remaining = (can_act_datetime - current_time).total_seconds()
                    # Cap the maximum wait time to prevent absurd values
                    if remaining > 300:  # More than 5 minutes is likely an error
                        # Reset the cooldown
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
                # Handle invalid datetime format by clearing it
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
                "You're too injured to continue fighting!", 
                ephemeral=True
            )
            return

        player_hp, player_combat, player_name = player_data

        # Execute combat round
        await self._execute_combat_round(
            interaction, combat_id, target_npc_id, target_npc_type, 
            combat_type, location_id, player_name, player_combat
        )

    @attack_group.command(name="flee", description="Attempt to escape from combat")
    async def flee_combat(self, interaction: discord.Interaction):
        # Check if user is in combat
        combat_data = self.db.execute_query(
            """SELECT combat_id, target_npc_id, target_npc_type, combat_type
               FROM combat_states 
               WHERE player_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )

        if not combat_data:
            await interaction.response.send_message(
                "You're not in combat!", 
                ephemeral=True
            )
            return

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

    @app_commands.command(name="rob", description="Attempt to rob an NPC")
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
        player_roll = random.randint(1, 20) + player_combat
        npc_defense = random.randint(1, 20) + npc_combat

        damage_dealt = 0
        if player_roll > npc_defense:
            base_damage = random.randint(5, 15)
            skill_bonus = player_combat // 2
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
        next_action_time = datetime.now() + timedelta(seconds=30)
        self.db.execute_query(
            "UPDATE combat_states SET player_can_act_time = ?, last_action_time = ? WHERE combat_id = ?",
            (next_action_time.isoformat(), datetime.now().isoformat(), combat_id)
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
            value="You can attack again in 30 seconds",
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
            respawn_time = datetime.now() + timedelta(hours=random.randint(2, 6))
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
        player_defense = random.randint(1, 20) + player_combat

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
        next_npc_time = datetime.now() + timedelta(seconds=random.randint(30, 45))
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
        next_npc_time = datetime.now() + timedelta(seconds=random.randint(30, 45))
        
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
            rep_change = combat_cog._calculate_reputation_change(npc_alignment, "rob_fail")
            
            reputation_cog = self.bot.get_cog('ReputationCog')
            if reputation_cog:
                await reputation_cog.update_reputation(self.user_id, self.location_id, rep_change)
            await self._send_reputation_feedback(interaction, self.location_id, rep_change, "robbing", npc_alignment)
            # Start combat
            next_npc_time = datetime.now() + timedelta(seconds=random.randint(30, 45))
            
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