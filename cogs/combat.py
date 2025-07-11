# cogs/combat.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from datetime import datetime, timedelta
import json

class CombatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_combats = {}  # Track ongoing combat encounters
    
    combat_group = app_commands.Group(name="combat", description="Combat system commands")
    
    @combat_group.command(name="challenge", description="Challenge another player to combat")
    @app_commands.describe(
        target="Player to challenge",
        combat_type="Type of combat (ship or personal)"
    )
    @app_commands.choices(combat_type=[
        app_commands.Choice(name="Ship Combat", value="ship"),
        app_commands.Choice(name="Personal Combat", value="personal")
    ])
    async def challenge_player(self, interaction: discord.Interaction, target: discord.Member, combat_type: str):
        # Check if PvP is enabled
        pvp_enabled = self.db.execute_query(
            "SELECT pvp_enabled FROM server_config WHERE guild_id = ?",
            (interaction.guild.id,),
            fetch='one'
        )
        
        if not pvp_enabled or not pvp_enabled[0]:
            await interaction.response.send_message("PvP combat is disabled on this server.", ephemeral=True)
            return
        
        # Check if both players have characters
        challenger_char = self.db.execute_query(
            "SELECT name, current_location, location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        target_char = self.db.execute_query(
            "SELECT name, current_location, location_status FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not challenger_char:
            await interaction.response.send_message("You don't have a character!", ephemeral=True)
            return
        
        if not target_char:
            await interaction.response.send_message("Target player doesn't have a character!", ephemeral=True)
            return
        
        # Check if both players are in the same location
        if challenger_char[1] != target_char[1]:
            await interaction.response.send_message("You must be in the same location to initiate combat!", ephemeral=True)
            return
        
        # Check combat type compatibility
        if combat_type == "ship" and (challenger_char[2] == "docked" or target_char[2] == "docked"):
            await interaction.response.send_message("Ship combat requires both players to be in space near the location!", ephemeral=True)
            return
        
        if combat_type == "personal" and (challenger_char[2] == "in_space" or target_char[2] == "in_space"):
            await interaction.response.send_message("Personal combat requires both players to be docked at the location!", ephemeral=True)
            return
        
        # Create challenge
        challenge_embed = discord.Embed(
            title="⚔️ Combat Challenge",
            description=f"**{challenger_char[0]}** challenges **{target_char[0]}** to {combat_type} combat!",
            color=0xff0000
        )
        
        challenge_embed.add_field(
            name="Combat Type",
            value=combat_type.title() + " Combat",
            inline=True
        )
        
        challenge_embed.add_field(
            name="Location",
            value=f"Location ID: {challenger_char[1]}",
            inline=True
        )
        
        view = CombatChallengeView(self.bot, interaction.user.id, target.id, combat_type)
        
        await interaction.response.send_message(f"{target.mention}", embed=challenge_embed, view=view)
    
    async def start_pirate_combat(self, channel: discord.TextChannel, player_ids: list, pirate_ships: int):
        """Start PvE combat against pirates"""
        
        encounter_id = f"pirates_{channel.id}_{int(datetime.now().timestamp())}"
        
        # Create pirate enemies
        pirates = []
        for i in range(pirate_ships):
            pirate = {
                'name': f"Pirate Ship {i+1}",
                'hp': random.randint(80, 120),
                'max_hp': random.randint(80, 120),
                'attack': random.randint(15, 25),
                'defense': random.randint(5, 15),
                'type': 'npc_ship'
            }
            pirates.append(pirate)
        
        # Initialize combat
        participants = []
        
        # Add players
        for player_id in player_ids:
            player_data = self.db.execute_query(
                '''SELECT c.name, c.hp, c.max_hp, c.combat, c.location_status,
                          s.hull_integrity, s.max_hull, s.combat_rating
                   FROM characters c
                   LEFT JOIN ships s ON c.ship_id = s.ship_id
                   WHERE c.user_id = ?''',
                (player_id,),
                fetch='one'
            )
            
            if player_data:
                participants.append({
                    'id': player_id,
                    'name': player_data[0],
                    'hp': player_data[1],
                    'max_hp': player_data[2],
                    'combat_skill': player_data[3],
                    'location_status': player_data[4],
                    'ship_hull': player_data[5] or 0,
                    'ship_max_hull': player_data[6] or 0,
                    'ship_combat': player_data[7] or 0,
                    'type': 'player'
                })
        
        # Add pirates
        participants.extend(pirates)
        
        # Roll initiative
        for p in participants:
            p['initiative'] = random.randint(1, 20) + (p.get('combat_skill', 10) // 5)
        
        participants.sort(key=lambda x: x['initiative'], reverse=True)
        
        # Store combat state
        self.active_combats[encounter_id] = {
            'participants': participants,
            'current_turn': 0,
            'turn_order': [p.get('id', p['name']) for p in participants],
            'combat_type': 'ship',  # Pirates are always ship combat
            'channel_id': channel.id,
            'round': 1
        }
        
        # Send initial combat embed
        await self._send_combat_status(encounter_id, channel)
    
    async def start_player_combat(self, channel: discord.TextChannel, player1_id: int, player2_id: int, combat_type: str):
        """Start PvP combat between players"""
        
        encounter_id = f"pvp_{player1_id}_{player2_id}_{int(datetime.now().timestamp())}"
        
        participants = []
        
        for player_id in [player1_id, player2_id]:
            player_data = self.db.execute_query(
                '''SELECT c.name, c.hp, c.max_hp, c.combat, c.engineering, c.location_status,
                          s.hull_integrity, s.max_hull, s.combat_rating
                   FROM characters c
                   LEFT JOIN ships s ON c.ship_id = s.ship_id
                   WHERE c.user_id = ?''',
                (player_id,),
                fetch='one'
            )
            
            if player_data:
                participants.append({
                    'id': player_id,
                    'name': player_data[0],
                    'hp': player_data[1],
                    'max_hp': player_data[2],
                    'combat_skill': player_data[3],
                    'engineering': player_data[4],
                    'location_status': player_data[5],
                    'ship_hull': player_data[6] or 0,
                    'ship_max_hull': player_data[7] or 0,
                    'ship_combat': player_data[8] or 0,
                    'type': 'player'
                })
        
        # Roll initiative
        for p in participants:
            p['initiative'] = random.randint(1, 20) + (p['combat_skill'] // 5)
        
        participants.sort(key=lambda x: x['initiative'], reverse=True)
        
        # Store combat state
        self.active_combats[encounter_id] = {
            'participants': participants,
            'current_turn': 0,
            'turn_order': [p['id'] for p in participants],
            'combat_type': combat_type,
            'channel_id': channel.id,
            'round': 1
        }
        
        await self._send_combat_status(encounter_id, channel)
    
    async def _send_combat_status(self, encounter_id: str, channel: discord.TextChannel):
        """Send current combat status"""
        
        combat = self.active_combats[encounter_id]
        current_participant = combat['participants'][combat['current_turn']]
        
        embed = discord.Embed(
            title=f"⚔️ {'Ship' if combat['combat_type'] == 'ship' else 'Personal'} Combat - Round {combat['round']}",
            color=0xff4500
        )
        
        # Show all participants
        status_lines = []
        for p in combat['participants']:
            if p['type'] == 'player':
                member = channel.guild.get_member(p['id'])
                name = member.display_name if member else p['name']
                
                if combat['combat_type'] == 'ship':
                    hp_display = f"{p['ship_hull']}/{p['ship_max_hull']} hull"
                else:
                    hp_display = f"{p['hp']}/{p['max_hp']} HP"
            else:
                name = p['name']
                hp_display = f"{p['hp']}/{p['max_hp']} HP"
            
            status_indicator = "➤" if p == current_participant else "  "
            status_lines.append(f"{status_indicator} **{name}**: {hp_display}")
        
        embed.add_field(
            name="🎯 Combat Status",
            value="\n".join(status_lines),
            inline=False
        )
        
        # Current turn info
        if current_participant['type'] == 'player':
            member = channel.guild.get_member(current_participant['id'])
            embed.add_field(
                name="⏰ Current Turn",
                value=f"{member.mention if member else current_participant['name']}'s turn!",
                inline=True
            )
            
            # Show action buttons for current player
            view = CombatActionView(self.bot, encounter_id, current_participant['id'])
            await channel.send(embed=embed, view=view)
        else:
            # NPC turn - handle automatically
            embed.add_field(
                name="⏰ Current Turn",
                value=f"{current_participant['name']}'s turn!",
                inline=True
            )
            
            await channel.send(embed=embed)
            
            # Handle NPC action after short delay
            await asyncio.sleep(2)
            await self._handle_npc_action(encounter_id, channel)
    
    async def _handle_npc_action(self, encounter_id: str, channel: discord.TextChannel):
        """Handle NPC combat actions"""
        
        combat = self.active_combats[encounter_id]
        current_npc = combat['participants'][combat['current_turn']]
        
        # Simple AI: attack random player
        player_targets = [p for p in combat['participants'] if p['type'] == 'player' and p['hp'] > 0]
        
        if not player_targets:
            # All players defeated
            await self._end_combat(encounter_id, channel, "defeat")
            return
        
        target = random.choice(player_targets)
        
        # Calculate damage
        if combat['combat_type'] == 'ship':
            base_damage = current_npc.get('attack', 20)
            target_defense = target.get('ship_combat', 10)
        else:
            base_damage = current_npc.get('attack', 15)
            target_defense = target.get('combat_skill', 10)
        
        damage = max(1, base_damage - target_defense // 2 + random.randint(-5, 5))
        
        # Apply damage
        if combat['combat_type'] == 'ship':
            target['ship_hull'] = max(0, target['ship_hull'] - damage)
            damage_type = "hull"
        else:
            target['hp'] = max(0, target['hp'] - damage)
            damage_type = "HP"
        
        # Send action result
        member = channel.guild.get_member(target['id'])
        target_name = member.display_name if member else target['name']
        
        embed = discord.Embed(
            title="💥 Enemy Action",
            description=f"**{current_npc['name']}** attacks **{target_name}** for {damage} {damage_type} damage!",
            color=0xff0000
        )
        
        await channel.send(embed=embed)
        
        # Check if target is defeated
        if (combat['combat_type'] == 'ship' and target['ship_hull'] <= 0) or \
           (combat['combat_type'] == 'personal' and target['hp'] <= 0):
            
            defeat_embed = discord.Embed(
                title="💀 Combatant Defeated",
                description=f"**{target_name}** has been defeated!",
                color=0x8b0000
            )
            await channel.send(embed=defeat_embed)
        
        # Next turn
        await self._next_turn(encounter_id, channel)
    
    async def handle_player_action(self, encounter_id: str, player_id: int, action: str, channel: discord.TextChannel):
        """Handle player combat action"""
        
        combat = self.active_combats[encounter_id]
        current_participant = combat['participants'][combat['current_turn']]
        
        if current_participant['id'] != player_id:
            return False  # Not their turn
        
        if action == "attack":
            await self._handle_attack_action(encounter_id, player_id, channel)
        elif action == "defend":
            await self._handle_defend_action(encounter_id, player_id, channel)
        elif action == "special":
            await self._handle_special_action(encounter_id, player_id, channel)
        elif action == "flee":
            await self._handle_flee_action(encounter_id, player_id, channel)
        
        return True
    
    async def _handle_attack_action(self, encounter_id: str, player_id: int, channel: discord.TextChannel):
        """Handle attack action"""
        
        combat = self.active_combats[encounter_id]
        attacker = combat['participants'][combat['current_turn']]
        
        # Find valid targets
        if combat['combat_type'] == 'ship':
            targets = [p for p in combat['participants'] if p != attacker and 
                      (p['type'] != 'player' or p['ship_hull'] > 0)]
        else:
            targets = [p for p in combat['participants'] if p != attacker and p['hp'] > 0]
        
        if not targets:
            await self._next_turn(encounter_id, channel)
            return
        
        # For now, attack first available target (could be expanded to target selection)
        target = targets[0]
        
        # Calculate damage
        if combat['combat_type'] == 'ship':
            base_damage = attacker['ship_combat'] + random.randint(5, 15)
            target_defense = target.get('ship_combat', 10) if target['type'] == 'player' else target.get('defense', 5)
        else:
            base_damage = attacker['combat_skill'] + random.randint(3, 12)
            target_defense = target.get('combat_skill', 10) if target['type'] == 'player' else target.get('defense', 5)
        
        damage = max(1, base_damage - target_defense // 3 + random.randint(-3, 3))
        
        # Apply damage
        if combat['combat_type'] == 'ship' and target['type'] == 'player':
            target['ship_hull'] = max(0, target['ship_hull'] - damage)
            damage_type = "hull"
        else:
            target['hp'] = max(0, target['hp'] - damage)
            damage_type = "HP"
        
        # Send result
        attacker_member = channel.guild.get_member(attacker['id'])
        if target['type'] == 'player':
            target_member = channel.guild.get_member(target['id'])
            target_name = target_member.display_name if target_member else target['name']
        else:
            target_name = target['name']
        
        embed = discord.Embed(
            title="⚔️ Attack Action",
            description=f"**{attacker_member.display_name if attacker_member else attacker['name']}** attacks **{target_name}** for {damage} {damage_type} damage!",
            color=0xff4500
        )
        
        await channel.send(embed=embed)
        
        # Award experience for combat
        self.db.execute_query(
            "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
            (random.randint(2, 8), player_id)
        )
        
        await self._next_turn(encounter_id, channel)
    
    async def _handle_defend_action(self, encounter_id: str, player_id: int, channel: discord.TextChannel):
        """Handle defend action"""
        
        combat = self.active_combats[encounter_id]
        defender = combat['participants'][combat['current_turn']]
        
        # Apply temporary defense bonus for next incoming attack
        defender['defense_bonus'] = defender.get('combat_skill', 10) // 2
        
        member = channel.guild.get_member(player_id)
        embed = discord.Embed(
            title="🛡️ Defensive Stance",
            description=f"**{member.display_name if member else defender['name']}** takes a defensive stance, increasing protection against the next attack!",
            color=0x4169e1
        )
        
        await channel.send(embed=embed)
        await self._next_turn(encounter_id, channel)
    
    async def _handle_special_action(self, encounter_id: str, player_id: int, channel: discord.TextChannel):
        """Handle special action based on combat type"""
        
        combat = self.active_combats[encounter_id]
        actor = combat['participants'][combat['current_turn']]
        
        member = channel.guild.get_member(player_id)
        
        if combat['combat_type'] == 'ship':
            # Ship special: Emergency repairs
            if actor['ship_hull'] < actor['ship_max_hull']:
                repair_amount = actor.get('engineering', 10) + random.randint(5, 15)
                actor['ship_hull'] = min(actor['ship_max_hull'], actor['ship_hull'] + repair_amount)
                
                embed = discord.Embed(
                    title="🔧 Emergency Repairs",
                    description=f"**{member.display_name if member else actor['name']}** performs emergency repairs, restoring {repair_amount} hull integrity!",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="🔧 No Repairs Needed",
                    description=f"**{member.display_name if member else actor['name']}'s** ship is already at full hull integrity!",
                    color=0xffa500
                )
        else:
            # Personal special: First aid
            if actor['hp'] < actor['max_hp']:
                heal_amount = actor.get('medical', 10) + random.randint(3, 10)
                actor['hp'] = min(actor['max_hp'], actor['hp'] + heal_amount)
                
                embed = discord.Embed(
                    title="⚕️ First Aid",
                    description=f"**{member.display_name if member else actor['name']}** applies first aid, restoring {heal_amount} HP!",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="⚕️ No Treatment Needed",
                    description=f"**{member.display_name if member else actor['name']}** is already at full health!",
                    color=0xffa500
                )
        
        await channel.send(embed=embed)
        await self._next_turn(encounter_id, channel)
    
    async def _handle_flee_action(self, encounter_id: str, player_id: int, channel: discord.TextChannel):
        """Handle flee action"""
        
        combat = self.active_combats[encounter_id]
        fleer = combat['participants'][combat['current_turn']]
        
        # Flee chance based on navigation skill for ships, or base chance for personal
        if combat['combat_type'] == 'ship':
            flee_chance = 0.5 + (fleer.get('navigation', 10) * 0.02)  # Base 50% + nav skill
        else:
            flee_chance = 0.6  # Base 60% for personal combat
        
        member = channel.guild.get_member(player_id)
        
        if random.random() < flee_chance:
            # Successful flee
            embed = discord.Embed(
                title="🏃 Successful Escape",
                description=f"**{member.display_name if member else fleer['name']}** successfully flees from combat!",
                color=0x00ff00
            )
            
            # Remove from combat
            combat['participants'].remove(fleer)
            
            # Check if combat should end
            remaining_players = [p for p in combat['participants'] if p['type'] == 'player']
            if not remaining_players:
                await self._end_combat(encounter_id, channel, "flee")
                return
        else:
            # Failed flee
            embed = discord.Embed(
                title="🏃 Escape Failed",
                description=f"**{member.display_name if member else fleer['name']}** fails to escape and remains in combat!",
                color=0xff0000
            )
        
        await channel.send(embed=embed)
        await self._next_turn(encounter_id, channel)
    
    async def _next_turn(self, encounter_id: str, channel: discord.TextChannel):
        """Advance to next turn"""
        
        combat = self.active_combats[encounter_id]
        
        # Remove defeated participants
        combat['participants'] = [p for p in combat['participants'] if 
                                (p['type'] != 'player' and p['hp'] > 0) or 
                                (p['type'] == 'player' and ((combat['combat_type'] == 'ship' and p['ship_hull'] > 0) or 
                                                           (combat['combat_type'] == 'personal' and p['hp'] > 0)))]
        
        # Check win conditions
        players_alive = [p for p in combat['participants'] if p['type'] == 'player']
        npcs_alive = [p for p in combat['participants'] if p['type'] != 'player']
        
        if not players_alive:
            await self._end_combat(encounter_id, channel, "defeat")
            return
        elif not npcs_alive:
            await self._end_combat(encounter_id, channel, "victory")
            return
        
        # Next turn
        combat['current_turn'] = (combat['current_turn'] + 1) % len(combat['participants'])
        if combat['current_turn'] == 0:
            combat['round'] += 1
        
        await asyncio.sleep(1)  # Brief pause between turns
        await self._send_combat_status(encounter_id, channel)
    
    async def _end_combat(self, encounter_id: str, channel: discord.TextChannel, result: str):
        """End combat and apply results"""
        
        combat = self.active_combats[encounter_id]
        
        if result == "victory":
            embed = discord.Embed(
                title="🏆 Victory!",
                description="The enemies have been defeated!",
                color=0x00ff00
            )
            
            # Award experience and possible loot
            for p in combat['participants']:
                if p['type'] == 'player':
                    exp_reward = random.randint(25, 75)
                    credits_reward = random.randint(100, 300)
                    
                    self.db.execute_query(
                        "UPDATE characters SET experience = experience + ?, money = money + ? WHERE user_id = ?",
                        (exp_reward, credits_reward, p['id'])
                    )
                    
                    member = channel.guild.get_member(p['id'])
                    if member:
                        embed.add_field(
                            name=f"🎁 {member.display_name}",
                            value=f"+{exp_reward} EXP, +{credits_reward} credits",
                            inline=True
                        )
        
        elif result == "defeat":
            embed = discord.Embed(
                title="💀 Defeat",
                description="Your forces have been defeated...",
                color=0x8b0000
            )
            
            # Apply penalties (minor)
            for p in combat['participants']:
                if p['type'] == 'player':
                    # Small credit loss
                    credit_loss = random.randint(50, 150)
                    self.db.execute_query(
                        "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
                        (credit_loss, p['id'])
                    )
        
        else:  # flee
            embed = discord.Embed(
                title="🏃 Combat Abandoned",
                description="All participants have fled from combat.",
                color=0xffa500
            )
        
        await channel.send(embed=embed)
        
        # Update character HP/hull in database
        for p in combat['participants']:
            if p['type'] == 'player':
                if combat['combat_type'] == 'ship':
                    self.db.execute_query(
                        "UPDATE ships SET hull_integrity = ? WHERE owner_id = ?",
                        (p['ship_hull'], p['id'])
                    )
                else:
                    self.db.execute_query(
                        "UPDATE characters SET hp = ? WHERE user_id = ?",
                        (p['hp'], p['id'])
                    )
        
        # Clean up
        del self.active_combats[encounter_id]

class CombatChallengeView(discord.ui.View):
    def __init__(self, bot, challenger_id: int, target_id: int, combat_type: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.combat_type = combat_type
    
    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def accept_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚔️ Challenge Accepted!",
            description=f"Combat will begin momentarily...",
            color=0xff4500
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Start combat
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog:
            await combat_cog.start_player_combat(
                interaction.channel, 
                self.challenger_id, 
                self.target_id, 
                self.combat_type
            )
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary, emoji="❌")
    async def decline_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
            return
        
        await interaction.response.send_message("❌ Combat challenge declined.", ephemeral=True)

class CombatActionView(discord.ui.View):
    def __init__(self, bot, encounter_id: str, player_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.encounter_id = encounter_id
        self.player_id = player_id
    
    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_action(interaction, "attack")
    
    @discord.ui.button(label="Defend", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def defend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_action(interaction, "defend")
    
    @discord.ui.button(label="Special", style=discord.ButtonStyle.success, emoji="⚡")
    async def special(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_action(interaction, "special")
    
    @discord.ui.button(label="Flee", style=discord.ButtonStyle.secondary, emoji="🏃")
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_action(interaction, "flee")
    
    async def _handle_action(self, interaction: discord.Interaction, action: str):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog:
            success = await combat_cog.handle_player_action(
                self.encounter_id, 
                self.player_id, 
                action, 
                interaction.channel
            )
            
            if not success:
                await interaction.followup.send("Unable to perform that action.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CombatCog(bot))