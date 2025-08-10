# cogs/corridor_events.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from utils.datetime_utils import safe_datetime_parse

class CorridorEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_events = {}  # Track active events by channel_id
    
    async def trigger_corridor_event(self, transit_channel: discord.TextChannel, 
                                   travelers: List[int], danger_level: int):
        """Trigger a corridor event with dynamic timing based on remaining travel time"""
        
        # Check for active events
        if transit_channel.id in self.active_events:
            return
        
        # Get remaining travel time
        remaining_travel_time = await self._get_remaining_travel_time(transit_channel.id)
        
        # If less than 30 seconds remaining, don't trigger event
        if remaining_travel_time < 30:
            return
        
        # Determine event type based on danger level
        event_types = ["corridor_radiation", "static_fog", "vacuum_bloom", "hostile_raiders"]
        weights = [0.40, 0.35, 0.3, 0.25]
        
        if danger_level >= 4:
            weights = [0.45, 0.4, 0.35, 0.3]
        
        event_type = random.choices(event_types, weights=weights)[0]
        
        # Severity based on danger level
        severity = min(5, random.randint(max(1, danger_level - 1), danger_level + 1))
        
        # CRITICAL FIX: Calculate response time based on remaining travel time
        # Ensure event expires BEFORE travel completes
        max_response_time = min(
            180,  # Maximum 3 minutes
            int(remaining_travel_time * 0.7)  # 70% of remaining travel time
        )
        
        # Minimum 30 seconds, maximum based on calculation above
        response_time = max(30, min(max_response_time, 60 + (severity * 20)))
        
        # If response time would be too short, don't trigger event
        if response_time < 30:
            return
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=response_time)
        
        # Log event for debugging
        print(f"🚨 Triggering {event_type} event - Remaining travel: {remaining_travel_time}s, Response time: {response_time}s")
        
        # Store event in database
        affected_users_json = json.dumps(travelers)
        self.db.execute_query(
            '''INSERT INTO corridor_events 
               (transit_channel_id, event_type, severity, expires_at, affected_users)
               VALUES (%s, %s, %s, %s, %s)''',
            (transit_channel.id, event_type, severity, expires_at, affected_users_json)
        )
        
        event_id = self.db.execute_query(
            "SELECT event_id FROM corridor_events WHERE transit_channel_id = %s ORDER BY event_id DESC LIMIT 1",
            (transit_channel.id,),
            fetch='one'
        )[0]
        
        # Schedule event resolution
        timeout_task = asyncio.create_task(self._handle_event_timeout(transit_channel.id, event_id))
        
        # Track active event
        self.active_events[transit_channel.id] = {
            'event_id': event_id,
            'event_type': event_type,
            'severity': severity,
            'expires_at': expires_at,
            'travelers': travelers,
            'responses': {},
            'timeout_task': timeout_task,
            'response_time': response_time  # Store for reference
        }
        
        # Send event alert
        await self._send_event_alert(transit_channel, event_type, severity, expires_at, travelers)

    
    async def _get_remaining_travel_time(self, channel_id: int) -> int:
        """Get remaining travel time for a transit channel"""
        session_data = self.db.execute_query(
            """SELECT end_time FROM travel_sessions 
               WHERE temp_channel_id = %s AND status = %s
               ORDER BY session_id DESC LIMIT 1""",
            (channel_id, 'traveling'),
            fetch='one'
        )
        
        if session_data and session_data[0]:
            end_time = safe_datetime_parse(session_data[0])
            remaining = (end_time - datetime.utcnow()).total_seconds()
            return max(0, int(remaining))
        
        return 0
    
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
        elif event_type == "hostile_raiders":
            embed = self._create_hostile_raiders_alert(severity, expires_at)
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
            precaution_help = "**🚨 Emergency:** Maximum shielding protocols, high power draw\n**⚠️ Standard:** Balanced radiation countermeasures\n**🔧 Basic:** Conservative shielding approach"
        elif severity <= 4:
            danger_text = "DANGEROUS radiation levels"
            effects_text = "• Severe radiation poisoning risk\n• Critical system damage\n• Immediate health effects"
            precaution_help = "**🚨 Emergency:** Full radiation protocols, system strain\n**⚠️ Standard:** Standard protective measures\n**🔧 Basic:** Light countermeasures only"
        else:
            danger_text = "**LETHAL** radiation storm"
            effects_text = "• **FATAL** radiation exposure\n• Complete system shutdown\n• Immediate life threat"
            precaution_help = "**🚨 Emergency:** Maximum protection protocols\n**⚠️ Standard:** Heavy defensive measures\n**🔧 Basic:** Minimal resource commitment"
        
        embed.add_field(name="🎚️ Severity Level", value=f"Level {severity}/5 - {danger_text}", inline=False)
        embed.add_field(name="⚠️ Potential Effects", value=effects_text, inline=False)
        embed.add_field(name="🛡️ Response Options", value=precaution_help, inline=False)
        embed.add_field(name="⏰ Time to Respond", value=f"You have until <t:{int(expires_at.timestamp())}:R> to choose your response!", inline=False)
        embed.add_field(name="💡 Skill Used", value="**Engineering** - Higher skill = better outcomes", inline=False)
        
        return embed
    def _create_hostile_raiders_alert(self, severity: int, expires_at: datetime) -> discord.Embed:
        """Create hostile raiders event alert embed"""
        embed = discord.Embed(
            title="⚔️ HOSTILE RAIDERS DETECTED",
            description="⚠️ **COMBAT ALERT** ⚠️\nAggressive ships detected intercepting your route!",
            color=0xdc143c  # Crimson red
        )
        
        if severity <= 2:
            danger_text = "Small raider patrol"
            effects_text = "• Light weapons fire\n• Attempted boarding\n• Cargo theft risk"
            precaution_help = "**🚨 Emergency:** All weapons hot, aggressive stance\n**⚠️ Standard:** Defensive combat posture\n**🔧 Basic:** Evasive maneuvers only"
        elif severity <= 4:
            danger_text = "MAJOR raider fleet"
            effects_text = "• Heavy weapons barrage\n• Multiple boarding attempts\n• Ship capture risk"
            precaution_help = "**🚨 Emergency:** Full combat engagement\n**⚠️ Standard:** Tactical defensive stance\n**🔧 Basic:** Evasion and retreat"
        else:
            danger_text = "**OVERWHELMING** raider armada"
            effects_text = "• Devastating firepower\n• Coordinated assault\n• **TOTAL DESTRUCTION** risk"
            precaution_help = "**🚨 Emergency:** Maximum firepower deployment\n**⚠️ Standard:** Heavy defensive measures\n**🔧 Basic:** High-risk evasion attempt"
        
        embed.add_field(name="🎚️ Severity Level", value=f"Level {severity}/5 - {danger_text}", inline=False)
        embed.add_field(name="⚠️ Potential Effects", value=effects_text, inline=False)
        embed.add_field(name="🛡️ Response Options", value=precaution_help, inline=False)
        embed.add_field(name="⏰ Time to Respond", value=f"Engage or evade before <t:{int(expires_at.timestamp())}:R>!", inline=False)
        embed.add_field(name="💡 Skill Used", value="**Combat** - Higher skill = better outcomes", inline=False)
        
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
            precaution_help = "**🚨 Emergency:** Complete electromagnetic isolation\n**⚠️ Standard:** Selective system hardening\n**🔧 Basic:** Light interference filtering"
        elif severity <= 4:
            danger_text = "MAJOR electromagnetic storm"
            effects_text = "• Complete communication blackout\n• Navigation system failure\n• Life support interference"
            precaution_help = "**🚨 Emergency:** Full system isolation protocols\n**⚠️ Standard:** Enhanced electromagnetic shielding\n**🔧 Basic:** Standard interference countermeasures"
        else:
            danger_text = "**CATASTROPHIC** electromagnetic storm"
            effects_text = "• Total system shutdown risk\n• Hull integrity threats\n• Complete navigation loss"
            precaution_help = "**🚨 Emergency:** Complete electromagnetic lockdown\n**⚠️ Standard:** Heavy interference mitigation\n**🔧 Basic:** Minimal system protection"
        
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
            precaution_help = "**🚨 Emergency:** Complete quarantine lockdown\n**⚠️ Standard:** Controlled containment protocols\n**🔧 Basic:** Basic contamination prevention"
        elif severity <= 4:
            danger_text = "MAJOR contamination event"
            effects_text = "• Significant hull contamination\n• Air system compromise\n• Respiratory health risks"
            precaution_help = "**🚨 Emergency:** Full contamination protocols\n**⚠️ Standard:** Standard biological containment\n**🔧 Basic:** Light protective measures"
        else:
            danger_text = "**CRITICAL** contamination crisis"
            effects_text = "• Massive hull infestation\n• Life support failure risk\n• **LETHAL** spore exposure"
            precaution_help = "**🚨 Emergency:** Maximum containment measures\n**⚠️ Standard:** Heavy biological countermeasures\n**🔧 Basic:** Conservative response approach"
        
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
        now = datetime.now(timezone.utc)
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
            "UPDATE corridor_events SET is_active = %s WHERE event_id = %s",
            (False, event_id)
        )
    async def _apply_timeout_consequences(self, channel_id: int, unresponsive_travelers: List[int], event_data: Dict):
        """Apply consequences to travelers who didn't respond in time"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        event_type = event_data['event_type']
        severity = event_data['severity']
        
        # Calculate timeout damage (worse than basic response)
        base_hp_damage = severity * 10  # Higher than normal
        base_ship_damage = severity * 15
        
        for user_id in unresponsive_travelers:
            user = channel.guild.get_member(user_id)
            if not user:
                continue
            
            # Apply full damage and check for death
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                died_from_hp = await char_cog.update_character_hp(user_id, -base_hp_damage, channel.guild, f"died from exposure to a {event_type.replace('_', ' ')}")
                if not died_from_hp:
                     await char_cog.update_ship_hull(user_id, -base_ship_damage, channel.guild, f"ship critically damaged by a {event_type.replace('_', ' ')}")
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
            
            # Check for character death
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                if damage['hp_loss'] > 0:
                    died_from_hp = await char_cog.update_character_hp(user_id, -damage['hp_loss'], channel.guild)
                    if not died_from_hp and damage['ship_damage'] > 0:
                        await char_cog.update_ship_hull(user_id, -damage['ship_damage'], channel.guild)
                elif damage['ship_damage'] > 0:
                    await char_cog.update_ship_hull(user_id, -damage['ship_damage'], channel.guild)
            
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
        base_hp_damage = severity * 12
        base_ship_damage = severity * 15
        
        # Response effectiveness
        if response == 'emergency_protocols':
            damage_reduction = 0.6  # 80% reduction
        elif response == 'standard_protocols':
            damage_reduction = 0.4  # 50% reduction
        elif response == 'basic_response':
            damage_reduction = 0.2  # 30% reduction
        else:  # no_response
            damage_reduction = 0.0  # No reduction
        
        # Event-specific modifiers
        if event_type == "corridor_radiation":
            hp_modifier = 1.5  # More HP damage
            ship_modifier = 0.8
        elif event_type == "static_fog":
            hp_modifier = 0.8
            ship_modifier = 2.0  # More ship damage
        elif event_type == "vacuum_bloom":
            hp_modifier = 1.35
            ship_modifier = 1.5
        elif event_type == "hostile_raiders":
            hp_modifier = 2.0  # Heavy crew casualties
            ship_modifier = 1.8  # Significant ship damage from weapons fire
        else:
            hp_modifier = 1.1
            ship_modifier = 1.2
        
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
            "vacuum_bloom": "Emergency quarantine protocols. Risk: Life support strain, potential system shutdown.",
            "hostile_raiders": "All weapons engaged, full combat protocols. Risk: Massive ammunition expenditure, death or injury."
        }
        return descriptions.get(event_type, "Maximum protection with unknown consequences.")
    
    def _get_standard_risk_description(self, event_type: str) -> str:
        descriptions = {
            "corridor_radiation": "Standard shielding protocols. Balanced protection with moderate power consumption.",
            "static_fog": "Selective system hardening. Maintains basic functionality while filtering interference.",
            "vacuum_bloom": "Controlled containment procedures. Standard filtration with normal operation.",
            "hostile_raiders": "Defensive combat stance. Balanced engagement with moderate resource consumption."
        }
        return descriptions.get(event_type, "Standard protective measures activated.")
    
    def _get_basic_risk_description(self, event_type: str) -> str:
        descriptions = {
            "corridor_radiation": "Minimal shielding only. Low power cost but limited protection.",
            "static_fog": "Basic interference filtering. Minimal system impact but reduced effectiveness.",
            "vacuum_bloom": "Surface-level containment only. Quick response but minimal protection.",
            "hostile_raiders": "Evasive maneuvers only. Minimal engagement but limited protection."
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
                "UPDATE corridor_events SET is_active = %s WHERE event_id = %s",
                (False, event_data['event_id'])
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
                'vacuum_bloom': f"🚨 {user.mention} triggers emergency quarantine! All ship systems lock down...",
                'hostile_raiders': f"🚨 {user.mention} powers all weapon systems! The ship prepares for brutal combat..."
            },
            'standard_protocols': {
                'corridor_radiation': f"⚠️ {user.mention} raises standard radiation shields. Power levels stable, protection adequate...",
                'static_fog': f"⚠️ {user.mention} activates interference filters. Systems hardened against electromagnetic disruption...",
                'vacuum_bloom': f"⚠️ {user.mention} seals air filtration systems. Containment protocols engaged...",
                'hostile_raiders': f"⚠️ {user.mention} raises shields and arms defensive weapons. Ready for controlled engagement..."
            },
            'basic_response': {
                'corridor_radiation': f"🔧 {user.mention} makes basic adjustments to shielding. Minimal power consumption...",
                'static_fog': f"🔧 {user.mention} switches to backup communications. Basic countermeasures active...",
                'vacuum_bloom': f"🔧 {user.mention} closes external vents. Surface-level contamination prevention...",
                'hostile_raiders': f"🔧 {user.mention} diverts power to engines. Attempting evasive maneuvers..."
            },
            'no_response': {
                'corridor_radiation': f"⏸️ {user.mention} takes no action. Ship remains vulnerable to radiation exposure...",
                'static_fog': f"⏸️ {user.mention} maintains course without precautions. Systems exposed to interference...",
                'vacuum_bloom': f"⏸️ {user.mention} ignores the contamination warning. Ship systems remain unsealed...",
                'hostile_raiders': f"⏸️ {user.mention} freezes in panic. Ship drifts helplessly as raiders close in..."
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
            "SELECT engineering, navigation, combat, medical FROM characters WHERE user_id = %s",
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
        elif event_type == "hostile_raiders":
            skill_used = "combat"
            skill_value = combat
        else:
            skill_used = "engineering"
            skill_value = engineering
        
        # --- REBALANCED DIFFICULTY ---
        # Base difficulty is higher now
        base_difficulty = 65 + ((severity - 1) * 15) # Range: 60-120

        # Skill provides a direct bonus
        skill_bonus = skill_value * 1

        # Response type now acts as a multiplier on your skill bonus
        if response_type == 'emergency_protocols':
            # High risk, high reward: Full skill bonus but high failure penalty
            difficulty = base_difficulty - skill_bonus
            crit_fail_chance = 0.2  # 10% chance of critical failure
        elif response_type == 'standard_protocols':
            # Standard: Good bonus, low failure risk
            difficulty = base_difficulty - (skill_bonus * 0.75)
            crit_fail_chance = 0.15  # 5% chance
        elif response_type == 'basic_response':
            # Basic: Low bonus, very safe
            difficulty = base_difficulty - (skill_bonus * 0.4)
            crit_fail_chance = 0.10  # 2% chance
        else:  # no_response
            difficulty = 100
            crit_fail_chance = 0.75
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
        base_hp_damage = severity * 6
        base_ship_damage = severity * 8
        
        # Apply outcome modifiers
        if outcome.get('critical_failure', False):
            # Critical failure: Take extra damage and lose resources
            hp_damage = int(base_hp_damage * 1.5)
            ship_damage = int(base_ship_damage * 2.0)
            credit_loss = severity * 50
            
            # Apply damages
            self.bot.db.execute_query(
                "UPDATE characters SET money = GREATEST(0, money - %s) WHERE user_id = %s",
                (credit_loss, user.id)
            )
            # Create and send the damage result embed
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
            
            # Send the embed to show the damage
            await channel.send(embed=embed)
            
            # Check for character death after critical failure
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                died_from_hp = await char_cog.update_character_hp(user.id, -hp_damage, channel.guild, "Critical system failure")
                if not died_from_hp:
                    await char_cog.update_ship_hull(user.id, -ship_damage, channel.guild)
            
            return  # Exit early to prevent duplicate embeds
            
            
        elif outcome['success']:
            # Success: Minimal or no damage, possible benefits
            hp_damage = max(0, int(base_hp_damage * 0.1))
            ship_damage = max(0, int(base_ship_damage * 0.1))
            exp_gain = severity * 5
            
            self.bot.db.execute_query(
                "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                (exp_gain, user.id)
            )
            if hp_damage > 0:
                char_cog = self.bot.get_cog('CharacterCog')
                if char_cog:
                    await char_cog.update_character_hp(user.id, -hp_damage, channel.guild, "Minor crisis exposure")
            
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
            # FAILURE HANDLING - NEW LOGIC
            roll = outcome['roll']
            needed = outcome['needed']
            margin = needed - roll
            
            # Calculate how badly they failed
            # If they missed by 20 or less, it's a partial failure
            # If they missed by more than 20, it's a full failure
            if margin <= 20:
                # Partial failure: Some damage reduction for being close
                hp_damage = int(base_hp_damage * 0.6)
                ship_damage = int(base_ship_damage * 0.6)
                
                embed = discord.Embed(
                    title="⚠️ PARTIAL FAILURE",
                    description=f"{user.mention}'s response was insufficient but partially mitigated the hazard.",
                    color=0xff4444
                )
                embed.add_field(
                    name="Consequences",
                    value=f"• **-{hp_damage} HP** (partial exposure)\n• **-{ship_damage} Hull** (moderate damage)",
                    inline=False
                )
            else:
                # Full failure: Take full damage
                hp_damage = base_hp_damage
                ship_damage = base_ship_damage
                
                embed = discord.Embed(
                    title="❌ COMPLETE FAILURE",
                    description=f"{user.mention}'s response completely failed to protect against the hazard!",
                    color=0x8b0000
                )
                embed.add_field(
                    name="Severe Consequences",
                    value=f"• **-{hp_damage} HP** (full hazard exposure)\n• **-{ship_damage} Hull** (major system damage)",
                    inline=False
                )
            
        
        await channel.send(embed=embed)
        
        # Check for character death
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            if outcome.get('critical_failure', False) or not outcome['success']:
                died_from_hp = await char_cog.update_character_hp(user.id, -hp_damage, channel.guild, "Crisis damage")
                if not died_from_hp:
                    await char_cog.update_ship_hull(user.id, -ship_damage, channel.guild)
            else:
                await char_cog.update_character_hp(user.id, -hp_damage, channel.guild, "Crisis damage")
                await char_cog.update_ship_hull(user.id, -ship_damage, channel.guild)
        
async def setup(bot):
    await bot.add_cog(CorridorEventsCog(bot))