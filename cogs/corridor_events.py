# cogs/corridor_events.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List

class CorridorEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_events = {}  # Track active events by channel_id
    
    async def trigger_corridor_event(self, transit_channel: discord.TextChannel, 
                                   travelers: List[int], danger_level: int):
        """Trigger a corridor event based on danger level and random chance"""
        
        # Calculate event probability based on danger level
        base_chance = danger_level * 0.15  # 15% per danger level
        
        if random.random() > base_chance:
            return  # No event triggered
        
        # Select event type based on danger level
        event_types = [
            ("corridor_radiation", 1, 5),
            ("static_fog", 2, 4), 
            ("vacuum_bloom", 3, 5)
        ]
        
        # Filter events by danger level
        available_events = [e for e in event_types if e[1] <= danger_level]
        if not available_events:
            return
        
        event_type, min_danger, max_danger = random.choice(available_events)
        severity = min(danger_level, random.randint(min_danger, max_danger))
        
        # Create event record
        expires_at = datetime.now() + timedelta(minutes=random.randint(3, 8))
        affected_users_json = json.dumps(travelers)
        
        self.db.execute_query(
            '''INSERT INTO corridor_events 
               (transit_channel_id, event_type, severity, expires_at, affected_users)
               VALUES (?, ?, ?, ?, ?)''',
            (transit_channel.id, event_type, severity, expires_at, affected_users_json)
        )
        
        event_id = self.db.execute_query(
            "SELECT event_id FROM corridor_events WHERE transit_channel_id = ? ORDER BY event_id DESC LIMIT 1",
            (transit_channel.id,),
            fetch='one'
        )[0]
        
        # Schedule event resolution and store the task
        timeout_task = asyncio.create_task(self._handle_event_timeout(transit_channel.id, event_id))
        
        # Track active event
        self.active_events[transit_channel.id] = {
            'event_id': event_id,
            'event_type': event_type,
            'severity': severity,
            'expires_at': expires_at,
            'travelers': travelers,
            'responses': {},
            'timeout_task': timeout_task  # Store the task
        }
        
        # Send event alert
        await self._send_event_alert(transit_channel, event_type, severity, expires_at, travelers)
        
        # Schedule event resolution
        asyncio.create_task(self._handle_event_timeout(transit_channel.id, event_id))
    
    async def _send_event_alert(self, channel: discord.TextChannel, event_type: str, 
                              severity: int, expires_at: datetime, travelers: List[int]):
        """Send event alert to transit channel"""
        
        # Get traveler mentions
        mentions = []
        for user_id in travelers:
            user = channel.guild.get_member(user_id)
            if user:
                mentions.append(user.mention)
        
        mention_text = " ".join(mentions) if mentions else "@here"
        
        # Create event-specific embeds
        if event_type == "corridor_radiation":
            embed = self._create_radiation_alert(severity, expires_at)
        elif event_type == "static_fog":
            embed = self._create_static_fog_alert(severity, expires_at)
        elif event_type == "vacuum_bloom":
            embed = self._create_vacuum_bloom_alert(severity, expires_at)
        else:
            return
        
        view = CorridorEventView(self.bot, channel.id, event_type, severity)
        
        try:
            await channel.send(
                content=f"🚨 **CORRIDOR HAZARD DETECTED** 🚨\n{mention_text}",
                embed=embed,
                view=view
            )
        except Exception as e:
            print(f"❌ Failed to send corridor event alert: {e}")
    
    def _create_radiation_alert(self, severity: int, expires_at: datetime) -> discord.Embed:
        """Create radiation event alert embed"""
        colors = [0xffff00, 0xff8800, 0xff4400, 0xff0000, 0x8b0000]
        color = colors[min(severity - 1, 4)]
        
        embed = discord.Embed(
            title="☢️ CORRIDOR RADIATION SPIKE",
            description="⚠️ **IMMEDIATE ACTION REQUIRED** ⚠️\nDangerous radiation levels detected in corridor space!",
            color=color
        )
        
        if severity <= 2:
            danger_text = "Minor radiation exposure"
            effects_text = "• Mild radiation sickness risk\n• Electronic interference\n• Increased cancer risk"
            precaution_help = "**🚨 Emergency:** Max shielding, power strain risk\n**⚠️ Standard:** Balanced protection\n**🔧 Basic:** Minimal protection, safe"
        elif severity <= 4:
            danger_text = "DANGEROUS radiation levels"
            effects_text = "• Severe radiation poisoning risk\n• Critical system damage\n• Immediate health effects"
            precaution_help = "**🚨 Emergency:** Essential for survival, system risk\n**⚠️ Standard:** Moderate protection\n**🔧 Basic:** Insufficient protection"
        else:
            danger_text = "**LETHAL** radiation storm"
            effects_text = "• **FATAL** radiation exposure\n• Complete system shutdown\n• Immediate life threat"
            precaution_help = "**🚨 Emergency:** Only chance of survival\n**⚠️ Standard:** Still dangerous\n**🔧 Basic:** Nearly useless"
        
        embed.add_field(name="🎚️ Severity Level", value=f"Level {severity}/5 - {danger_text}", inline=False)
        embed.add_field(name="⚠️ Potential Effects", value=effects_text, inline=False)
        embed.add_field(name="🛡️ Response Options", value=precaution_help, inline=False)
        embed.add_field(name="⏰ Time to Respond", value=f"You have until <t:{int(expires_at.timestamp())}:R> to choose your response!", inline=False)
        embed.add_field(name="💡 Skill Used", value="**Engineering** - Higher skill = better outcomes", inline=False)
        
        return embed

    def _create_static_fog_alert(self, severity: int, expires_at: datetime) -> discord.Embed:
        """Create static fog event alert embed"""
        embed = discord.Embed(
            title="⚡ STATIC FOG ENCOUNTERED",
            description="⚠️ **NAVIGATION CRISIS** ⚠️\nElectromagnetic interference cloud detected!",
            color=0x8a2be2
        )
        
        if severity <= 2:
            danger_text = "Minor electromagnetic interference"
            effects_text = "• Communication disruption\n• Sensor degradation\n• Minor navigation errors"
            precaution_help = "**🚨 Emergency:** Full isolation, comms blackout\n**⚠️ Standard:** Filtered operation\n**🔧 Basic:** Minimal countermeasures"
        elif severity <= 4:
            danger_text = "MAJOR electromagnetic storm"
            effects_text = "• Complete communication blackout\n• Navigation system failure\n• Life support interference"
            precaution_help = "**🚨 Emergency:** Total shutdown, complete protection\n**⚠️ Standard:** Hardened systems\n**🔧 Basic:** Basic filtering only"
        else:
            danger_text = "**CATASTROPHIC** electromagnetic storm"
            effects_text = "• Total system shutdown risk\n• Hull integrity threats\n• Complete navigation loss"
            precaution_help = "**🚨 Emergency:** Faraday cage mode required\n**⚠️ Standard:** Still risky\n**🔧 Basic:** Completely inadequate"
        
        embed.add_field(name="🎚️ Severity Level", value=f"Level {severity}/5 - {danger_text}", inline=False)
        embed.add_field(name="⚠️ Potential Effects", value=effects_text, inline=False)
        embed.add_field(name="🛡️ Response Options", value=precaution_help, inline=False)
        embed.add_field(name="⏰ Time to Respond", value=f"Choose your response before <t:{int(expires_at.timestamp())}:R>!", inline=False)
        embed.add_field(name="💡 Skill Used", value="**Navigation** - Higher skill = better outcomes", inline=False)
        
        return embed

    def _create_vacuum_bloom_alert(self, severity: int, expires_at: datetime) -> discord.Embed:
        """Create vacuum bloom event alert embed"""
        embed = discord.Embed(
            title="🦠 VACUUM BLOOM DETECTED",
            description="⚠️ **BIOLOGICAL CONTAMINATION** ⚠️\nHostile organic matter detected in corridor space!",
            color=0x8b4513
        )
        
        if severity <= 2:
            danger_text = "Minor spore contamination"
            effects_text = "• Hull surface contamination\n• Air filtration stress\n• Minor respiratory irritation"
            precaution_help = "**🚨 Emergency:** Full quarantine, life support strain\n**⚠️ Standard:** Controlled containment\n**🔧 Basic:** Surface protection only"
        elif severity <= 4:
            danger_text = "MAJOR contamination event"
            effects_text = "• Significant hull contamination\n• Air system compromise\n• Respiratory health risks"
            precaution_help = "**🚨 Emergency:** Emergency protocols essential\n**⚠️ Standard:** Adequate containment\n**🔧 Basic:** Minimal protection"
        else:
            danger_text = "**CRITICAL** contamination crisis"
            effects_text = "• Massive hull infestation\n• Life support failure risk\n• **LETHAL** spore exposure"
            precaution_help = "**🚨 Emergency:** Life or death protocols\n**⚠️ Standard:** Still very dangerous\n**🔧 Basic:** Nearly suicidal"
        
        embed.add_field(name="🎚️ Severity Level", value=f"Level {severity}/5 - {danger_text}", inline=False)
        embed.add_field(name="⚠️ Potential Effects", value=effects_text, inline=False)
        embed.add_field(name="🛡️ Response Options", value=precaution_help, inline=False)
        embed.add_field(name="⏰ Time to Respond", value=f"Act before <t:{int(expires_at.timestamp())}:R> or face consequences!", inline=False)
        embed.add_field(name="💡 Skill Used", value="**Medical** - Higher skill = better outcomes", inline=False)
        
        return embed
    
    async def _handle_event_timeout(self, channel_id: int, event_id: int):
        """Handle event timeout - resolve immediately for users who haven't responded"""
        event_data = self.active_events.get(channel_id)
        if not event_data:
            return
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        # Wait until event expires
        now = datetime.now()
        if event_data['expires_at'] > now:
            wait_time = (event_data['expires_at'] - now).total_seconds()
            await asyncio.sleep(wait_time)
        
        # Check if event still exists and process remaining travelers
        if channel_id not in self.active_events:
            return
        
        event_data = self.active_events[channel_id]
        travelers = event_data['travelers']
        responses = event_data['responses']
        
        # Find travelers who didn't respond
        unresponsive_travelers = []
        for traveler_id in travelers:
            if traveler_id not in responses:
                unresponsive_travelers.append(traveler_id)
                # Mark them as non-responsive
                responses[traveler_id] = 'no_response'
        
        if unresponsive_travelers:
            # Show timeout message
            mentions = []
            for user_id in unresponsive_travelers:
                user = channel.guild.get_member(user_id)
                if user:
                    mentions.append(user.mention)
            
            if mentions:
                embed = discord.Embed(
                    title="⏰ RESPONSE WINDOW EXPIRED",
                    description=f"Time's up! {', '.join(mentions)} failed to respond to the crisis in time.",
                    color=0xff6600
                )
                embed.add_field(
                    name="Consequence",
                    value="Taking full damage from hazard exposure due to lack of preparation.",
                    inline=False
                )
                await channel.send(embed=embed)
                
                # Apply consequences to non-responsive travelers
                await asyncio.sleep(2)
                await self._apply_timeout_consequences(channel_id, unresponsive_travelers, event_data)
        
        # Clean up
        if channel_id in self.active_events:
            del self.active_events[channel_id]
        
        self.db.execute_query(
            "UPDATE corridor_events SET is_active = 0 WHERE event_id = ?",
            (event_id,)
        )
    async def _apply_timeout_consequences(self, channel_id: int, unresponsive_travelers: List[int], event_data: Dict):
        """Apply consequences to travelers who didn't respond in time"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        event_type = event_data['event_type']
        severity = event_data['severity']
        
        # Calculate timeout damage (worse than basic response)
        base_hp_damage = severity * 6  # Higher than normal
        base_ship_damage = severity * 10
        
        for user_id in unresponsive_travelers:
            user = channel.guild.get_member(user_id)
            if not user:
                continue
            
            # Apply full damage
            self.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (base_hp_damage, user_id)
            )
            self.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (base_ship_damage, user_id)
            )
            # Check for character death
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                died_from_hp = await char_cog.check_character_death(user_id, channel.guild, f"died from exposure to a {event_type.replace('_', ' ')}")
                if not died_from_hp:
                     await char_cog.check_ship_death(user_id, channel.guild, f"ship critically damaged by a {event_type.replace('_', ' ')}")
            # Show individual consequence
            embed = discord.Embed(
                title="💀 FAILURE TO RESPOND",
                description=f"{user.mention} was caught completely unprepared by the {event_type.replace('_', ' ')}!",
                color=0x8b0000
            )
            embed.add_field(
                name="Heavy Consequences",
                value=f"• **-{base_hp_damage} HP** (full hazard exposure)\n• **-{base_ship_damage} Hull** (unprotected systems)",
                inline=False
            )
            embed.add_field(
                name="Lesson Learned",
                value="Always be ready to respond quickly to corridor hazards!",
                inline=False
            )
            
            await channel.send(embed=embed)
            
            # Check for character death
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.check_character_death(user_id, channel.guild)
            
            await asyncio.sleep(1)  # Stagger the messages
    async def _apply_event_consequences(self, channel_id: int, event_data: Dict):
        """Apply consequences based on event type and responses"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        travelers = event_data['travelers']
        responses = event_data['responses']
        event_type = event_data['event_type']
        severity = event_data['severity']
        
        consequences = []
        
        for user_id in travelers:
            user_response = responses.get(user_id, 'no_response')
            damage = await self._calculate_event_damage(event_type, severity, user_response)
            
            if damage['hp_loss'] > 0:
                self.db.execute_query(
                    "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                    (damage['hp_loss'], user_id)
                )
            
            if damage['ship_damage'] > 0:
                self.db.execute_query(
                    "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                    (damage['ship_damage'], user_id)
                )
            
            # Check for character death
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog and damage['hp_loss'] > 0:
                await char_cog.check_character_death(user_id, channel.guild)
            
            # Record consequences
            user = channel.guild.get_member(user_id)
            if user:
                if user_response == 'no_response':
                    consequences.append(f"💀 {user.mention} failed to respond - took full damage!")
                elif damage['hp_loss'] > 0 or damage['ship_damage'] > 0:
                    consequences.append(f"⚠️ {user.mention} took {damage['hp_loss']} HP damage, {damage['ship_damage']} ship damage")
                else:
                    consequences.append(f"✅ {user.mention} successfully mitigated the hazard!")
        
        # Send consequences message
        embed = discord.Embed(
            title="📊 Event Resolution",
            description=f"**{event_type.replace('_', ' ').title()}** event has concluded.",
            color=0xff9900
        )
        
        if consequences:
            embed.add_field(
                name="💥 Consequences",
                value="\n".join(consequences),
                inline=False
            )
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    async def _calculate_event_damage(self, event_type: str, severity: int, response: str) -> Dict:
        """Calculate damage based on event type, severity, and player response"""
        base_hp_damage = severity * 10
        base_ship_damage = severity * 12
        
        # Response effectiveness
        if response == 'emergency_protocols':
            damage_reduction = 0.8  # 80% reduction
        elif response == 'standard_protocols':
            damage_reduction = 0.5  # 50% reduction
        elif response == 'basic_response':
            damage_reduction = 0.3  # 30% reduction
        else:  # no_response
            damage_reduction = 0.0  # No reduction
        
        # Event-specific modifiers
        if event_type == "corridor_radiation":
            hp_modifier = 1.5  # More HP damage
            ship_modifier = 0.8
        elif event_type == "static_fog":
            hp_modifier = 0.7
            ship_modifier = 2.0  # More ship damage
        elif event_type == "vacuum_bloom":
            hp_modifier = 1.35
            ship_modifier = 1.5
        else:
            hp_modifier = 1.0
            ship_modifier = 1.0
        
        final_hp_damage = int(base_hp_damage * hp_modifier * (1 - damage_reduction))
        final_ship_damage = int(base_ship_damage * ship_modifier * (1 - damage_reduction))
        
        return {
            'hp_loss': max(0, final_hp_damage),
            'ship_damage': max(0, final_ship_damage)
        }

class CorridorEventView(discord.ui.View):
    def __init__(self, bot, channel_id: int, event_type: str, severity: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_id = channel_id
        self.event_type = event_type
        self.severity = severity
    
    @discord.ui.button(label="Emergency Protocols", style=discord.ButtonStyle.danger, emoji="🚨")
    async def emergency_protocols(self, interaction: discord.Interaction, button: discord.ui.Button):
        risk_desc = self._get_emergency_risk_description(self.event_type)
        await self._handle_response(interaction, 'emergency_protocols', 
                                   f"⚡ **EMERGENCY PROTOCOLS ACTIVATED**\n{risk_desc}")
    
    @discord.ui.button(label="Standard Protocols", style=discord.ButtonStyle.primary, emoji="⚠️")
    async def standard_response(self, interaction: discord.Interaction, button: discord.ui.Button):
        risk_desc = self._get_standard_risk_description(self.event_type)
        await self._handle_response(interaction, 'standard_protocols',
                                   f"🛡️ **STANDARD PROTOCOLS ACTIVATED**\n{risk_desc}")
    
    @discord.ui.button(label="Basic Precautions", style=discord.ButtonStyle.secondary, emoji="🔧")
    async def basic_response(self, interaction: discord.Interaction, button: discord.ui.Button):
        risk_desc = self._get_basic_risk_description(self.event_type)
        await self._handle_response(interaction, 'basic_response',
                                   f"⚙️ **BASIC PRECAUTIONS TAKEN**\n{risk_desc}")
    
    @discord.ui.button(label="No Action", style=discord.ButtonStyle.gray, emoji="⏸️")
    async def no_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_response(interaction, 'no_response',
                                   "⏸️ **NO ACTION TAKEN**\nAccepting whatever happens...")
    
    def _get_emergency_risk_description(self, event_type: str) -> str:
        descriptions = {
            "corridor_radiation": "Maximum shielding engaged. Risk: Massive power drain, potential system overload.",
            "static_fog": "Full electromagnetic isolation activated. Risk: Complete communication blackout, navigation failure.",
            "vacuum_bloom": "Emergency quarantine protocols. Risk: Life support strain, potential system shutdown."
        }
        return descriptions.get(event_type, "Maximum protection with unknown consequences.")
    
    def _get_standard_risk_description(self, event_type: str) -> str:
        descriptions = {
            "corridor_radiation": "Standard shielding protocols. Balanced protection with moderate power consumption.",
            "static_fog": "Selective system hardening. Maintains basic functionality while filtering interference.",
            "vacuum_bloom": "Controlled containment procedures. Standard filtration with normal operation."
        }
        return descriptions.get(event_type, "Standard protective measures activated.")
    
    def _get_basic_risk_description(self, event_type: str) -> str:
        descriptions = {
            "corridor_radiation": "Minimal shielding only. Low power cost but limited protection.",
            "static_fog": "Basic interference filtering. Minimal system impact but reduced effectiveness.",
            "vacuum_bloom": "Surface-level containment only. Quick response but minimal protection."
        }
        return descriptions.get(event_type, "Minimal precautions with limited protection.")
    
    async def _handle_response(self, interaction: discord.Interaction, response_type: str, response_message: str):
        """Handle player response to corridor event, check for completion, and resolve immediately."""
        events_cog = self.bot.get_cog('CorridorEventsCog')
        if not events_cog or self.channel_id not in events_cog.active_events:
            await interaction.response.send_message("This event is no longer active.", ephemeral=True, delete_after=5)
            # Try to remove the view from the original message if possible
            try:
                await interaction.message.edit(view=None)
            except:
                pass
            return

        event_data = events_cog.active_events[self.channel_id]

        # Prevent a user from responding more than once
        if interaction.user.id in event_data['responses']:
            await interaction.response.send_message("You have already responded to this event.", ephemeral=True)
            return

        # Record the user's response and process their action immediately
        event_data['responses'][interaction.user.id] = response_type
        await interaction.response.send_message(response_message, ephemeral=True)
        asyncio.create_task(self._process_user_action(interaction.user, response_type, events_cog))

        # Check if all travelers have now responded
        if len(event_data['responses']) >= len(event_data['travelers']):
            # All players have responded, so we can resolve the event
            # First, disable the buttons on the original message
            self.stop()
            try:
                await interaction.message.edit(view=None)
            except discord.NotFound:
                pass # Message was already deleted, which is fine

            # Cancel the timeout task so it doesn't fire later
            if 'timeout_task' in event_data and not event_data['timeout_task'].done():
                event_data['timeout_task'].cancel()

            # Clean up the event from the active_events dictionary
            if self.channel_id in events_cog.active_events:
                del events_cog.active_events[self.channel_id]

            # Mark the event as inactive in the database
            self.bot.db.execute_query(
                "UPDATE corridor_events SET is_active = 0 WHERE event_id = ?",
                (event_data['event_id'],)
            )

            # Post a concluding message in the channel
            await interaction.channel.send(embed=discord.Embed(
                title="✅ Event Concluded",
                description="All travelers have responded to the hazard. The situation is resolved.",
                color=0x333333
            ))

    
    async def _process_user_action(self, user: discord.User, response_type: str, events_cog):
        """Process the user's action with immersive feedback and immediate resolution"""
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        
        event_data = events_cog.active_events[self.channel_id]
        
        # Show action feedback with skill check
        await self._show_action_feedback(channel, user, response_type, event_data)
        
        # Wait a moment for immersion
        await asyncio.sleep(2)
        
        # Perform skill check and calculate outcome
        outcome = await self._perform_skill_check(user, response_type, event_data)
        
        # Show skill check result
        await self._show_skill_check_result(channel, user, response_type, outcome)
        
        # Wait for dramatic effect
        await asyncio.sleep(3)
        
        # Apply consequences
        await self._apply_immediate_consequences(channel, user, outcome, event_data)
    
    async def _show_action_feedback(self, channel, user, response_type, event_data):
        """Show immediate feedback when user takes action"""
        event_type = event_data['event_type']
        severity = event_data['severity']
        
        feedback_messages = {
            'emergency_protocols': {
                'corridor_radiation': f"🚨 {user.mention} activates emergency radiation shielding! Systems strain under maximum power draw...",
                'static_fog': f"🚨 {user.mention} initiates full electromagnetic isolation! Ship goes dark to external sensors...",
                'vacuum_bloom': f"🚨 {user.mention} triggers emergency quarantine! All ship systems lock down..."
            },
            'standard_protocols': {
                'corridor_radiation': f"⚠️ {user.mention} raises standard radiation shields. Power levels stable, protection adequate...",
                'static_fog': f"⚠️ {user.mention} activates interference filters. Systems hardened against electromagnetic disruption...",
                'vacuum_bloom': f"⚠️ {user.mention} seals air filtration systems. Containment protocols engaged..."
            },
            'basic_response': {
                'corridor_radiation': f"🔧 {user.mention} makes basic adjustments to shielding. Minimal power consumption...",
                'static_fog': f"🔧 {user.mention} switches to backup communications. Basic countermeasures active...",
                'vacuum_bloom': f"🔧 {user.mention} closes external vents. Surface-level contamination prevention..."
            },
            'no_response': {
                'corridor_radiation': f"⏸️ {user.mention} takes no action. Ship remains vulnerable to radiation exposure...",
                'static_fog': f"⏸️ {user.mention} maintains course without precautions. Systems exposed to interference...",
                'vacuum_bloom': f"⏸️ {user.mention} ignores the contamination warning. Ship systems remain unsealed..."
            }
        }
        
        message = feedback_messages.get(response_type, {}).get(event_type, f"{user.mention} responds to the crisis...")
        
        embed = discord.Embed(
            title="⚡ Action Taken",
            description=message,
            color=0xff6600
        )
        
        await channel.send(embed=embed)
    
    async def _perform_skill_check(self, user, response_type, event_data):
        """Perform skill check based on response type and character skills"""
        # Get character skills
        char_data = self.bot.db.execute_query(
            "SELECT engineering, navigation, combat, medical FROM characters WHERE user_id = ?",
            (user.id,),
            fetch='one'
        )
        
        if not char_data:
            return {'success': False, 'skill_used': None, 'roll': 0, 'needed': 50}
        
        engineering, navigation, combat, medical = char_data
        event_type = event_data['event_type']
        severity = event_data['severity']
        
        # Determine relevant skill and difficulty
        if event_type == "corridor_radiation":
            skill_used = "engineering"
            skill_value = engineering
        elif event_type == "static_fog":
            skill_used = "navigation" 
            skill_value = navigation
        elif event_type == "vacuum_bloom":
            skill_used = "medical"
            skill_value = medical
        else:
            skill_used = "engineering"
            skill_value = engineering
        
        # --- REBALANCED DIFFICULTY ---
        # Base difficulty is higher now
        base_difficulty = 30 + (severity * 10) # Range: 40-80

        # Skill provides a direct bonus
        skill_bonus = skill_value * 2

        # Response type now acts as a multiplier on your skill bonus
        if response_type == 'emergency_protocols':
            # High risk, high reward: Full skill bonus but high failure penalty
            difficulty = base_difficulty - skill_bonus
            crit_fail_chance = 0.10  # 10% chance of critical failure
        elif response_type == 'standard_protocols':
            # Standard: Good bonus, low failure risk
            difficulty = base_difficulty - (skill_bonus * 0.75)
            crit_fail_chance = 0.05  # 5% chance
        elif response_type == 'basic_response':
            # Basic: Low bonus, very safe
            difficulty = base_difficulty - (skill_bonus * 0.4)
            crit_fail_chance = 0.02  # 2% chance
        else:  # no_response
            difficulty = 100
            crit_fail_chance = 0.3
            skill_bonus = 0
        
        # Roll d100
        roll = random.randint(1, 100)
        
        # Check for critical failure first
        crit_fail_roll = random.random()
        if crit_fail_roll < crit_fail_chance:
            return {
                'success': False,
                'critical_failure': True,
                'skill_used': skill_used,
                'skill_value': skill_value,
                'roll': roll,
                'needed': difficulty,
                'skill_bonus': skill_bonus
            }
        
        # Normal success check
        success = roll >= difficulty
        
        return {
            'success': success,
            'critical_failure': False,
            'skill_used': skill_used,
            'skill_value': skill_value,
            'roll': roll,
            'needed': max(5, difficulty),  # Minimum 5% chance of success
            'skill_bonus': skill_bonus
        }
    
    async def _show_skill_check_result(self, channel, user, response_type, outcome):
        """Show the result of the skill check"""
        skill_name = outcome['skill_used'].capitalize()
        roll = outcome['roll']
        needed = outcome['needed']
        skill_value = outcome['skill_value']
        
        if outcome.get('critical_failure', False):
            color = 0x8b0000  # Dark red
            title = "💥 CRITICAL SYSTEM FAILURE"
            description = f"{user.mention}'s {response_type.replace('_', ' ')} **critically failed**!"
            result_text = f"**{skill_name}** skill check: {roll}/100 (Skill: {skill_value})\n💀 **CRITICAL MALFUNCTION DETECTED**"
        elif outcome['success']:
            color = 0x00ff00  # Green
            title = "✅ SUCCESSFUL RESPONSE"
            description = f"{user.mention}'s {response_type.replace('_', ' ')} **succeeded**!"
            result_text = f"**{skill_name}** skill check: {roll}/100 (Needed: {needed}, Skill: {skill_value})\n🎯 **SUCCESS!**"
        else:
            color = 0xff4444  # Red
            title = "❌ RESPONSE FAILED"
            description = f"{user.mention}'s {response_type.replace('_', ' ')} **failed**!"
            result_text = f"**{skill_name}** skill check: {roll}/100 (Needed: {needed}, Skill: {skill_value})\n⚠️ **INSUFFICIENT SKILL**"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        embed.add_field(
            name="🎲 Skill Check Result",
            value=result_text,
            inline=False
        )
        
        await channel.send(embed=embed)
    
    async def _apply_immediate_consequences(self, channel, user, outcome, event_data):
        """Apply consequences based on skill check outcome"""
        event_type = event_data['event_type']
        severity = event_data['severity']
        
        # Calculate base damage
        base_hp_damage = severity * 5
        base_ship_damage = severity * 8
        
        # Apply outcome modifiers
        if outcome.get('critical_failure', False):
            # Critical failure: Take extra damage and lose resources
            hp_damage = int(base_hp_damage * 1.5)
            ship_damage = int(base_ship_damage * 2.0)
            credit_loss = severity * 50
            
            # Apply damages
            self.bot.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?), money = MAX(0, money - ?) WHERE user_id = ?",
                (hp_damage, credit_loss, user.id)
            )
            self.bot.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (ship_damage, user.id)
            )
            # Check for character death
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog and (outcome.get('critical_failure', False) or not outcome['success']):
                died_from_hp = await char_cog.check_character_death(user.id, channel.guild, f"died from a {event_type.replace('_', ' ')} after a {response_type.replace('_',' ')}")
                if not died_from_hp:
                    await char_cog.check_ship_death(user.id, channel.guild, f"ship destroyed by a {event_type.replace('_', ' ')} after a {response_type.replace('_',' ')}")
            embed = discord.Embed(
                title="💥 CATASTROPHIC CONSEQUENCES",
                description=f"{user.mention} suffers severe consequences from the critical failure!",
                color=0x8b0000
            )
            embed.add_field(
                name="Damages Sustained",
                value=f"• **-{hp_damage} HP** (system overload injuries)\n• **-{ship_damage} Hull** (critical system damage)\n• **-{credit_loss} Credits** (emergency repairs)",
                inline=False
            )
            
        elif outcome['success']:
            # Success: Minimal or no damage, possible benefits
            hp_damage = max(0, int(base_hp_damage * 0.1))
            ship_damage = max(0, int(base_ship_damage * 0.1))
            exp_gain = severity * 5
            
            if hp_damage > 0 or ship_damage > 0:
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = MAX(1, hp - ?), experience = experience + ? WHERE user_id = ?",
                    (hp_damage, exp_gain, user.id)
                )
                self.bot.db.execute_query(
                    "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                    (ship_damage, user.id)
                )
            else:
                self.bot.db.execute_query(
                    "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                    (exp_gain, user.id)
                )
            
            embed = discord.Embed(
                title="🛡️ SUCCESSFUL MITIGATION",
                description=f"{user.mention} successfully handles the crisis with skill and precision!",
                color=0x00ff00
            )
            
            if hp_damage > 0 or ship_damage > 0:
                embed.add_field(
                    name="Minor Consequences",
                    value=f"• **-{hp_damage} HP** (minor exposure)\n• **-{ship_damage} Hull** (minimal wear)\n• **+{exp_gain} EXP** (learning experience)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Perfect Execution",
                    value=f"• **No damage taken!**\n• **+{exp_gain} EXP** (masterful handling)",
                    inline=False
                )
        else:
            # Failure: Standard damage
            hp_damage = int(base_hp_damage * 0.6)
            ship_damage = int(base_ship_damage * 0.6)
            
            self.bot.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (hp_damage, user.id)
            )
            self.bot.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (ship_damage, user.id)
            )
            
            embed = discord.Embed(
                title="⚠️ PARTIAL FAILURE",
                description=f"{user.mention}'s response was insufficient to fully protect against the hazard.",
                color=0xff4444
            )
            embed.add_field(
                name="Consequences",
                value=f"• **-{hp_damage} HP** (hazard exposure)\n• **-{ship_damage} Hull** (system damage)",
                inline=False
            )
        
        await channel.send(embed=embed)
        
        # Check for character death
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog and (outcome.get('critical_failure', False) or not outcome['success']):
            await char_cog.check_character_death(user.id, channel.guild)

async def setup(bot):
    await bot.add_cog(CorridorEventsCog(bot))