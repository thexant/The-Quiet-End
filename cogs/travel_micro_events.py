import discord
from discord.ext import commands, tasks
from discord import ui
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from utils.datetime_utils import safe_datetime_parse

class MicroEventView(ui.View):
    def __init__(self, event_data: dict, bot, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.event_data = event_data
        self.bot = bot
        self.responded = False
        
    @ui.button(label="Respond", style=discord.ButtonStyle.success, emoji="⚡")
    async def respond_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.event_data['user_id']:
            await interaction.response.send_message("This isn't your event to handle!", ephemeral=True)
            return
            
        if self.responded:
            await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
            return
            
        self.responded = True
        await interaction.response.defer()
        
        # Get the micro events cog to handle the response
        cog = interaction.client.get_cog('TravelMicroEventsCog')
        if cog:
            await cog.handle_response(interaction, self.event_data, responded=True)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        
    @ui.button(label="Ignore", style=discord.ButtonStyle.secondary, emoji="👎")
    async def ignore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.event_data['user_id']:
            await interaction.response.send_message("This isn't your event to handle!", ephemeral=True)
            return
            
        if self.responded:
            await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
            return
            
        self.responded = True
        await interaction.response.defer()
        
        # Get the micro events cog to handle the ignore
        cog = interaction.client.get_cog('TravelMicroEventsCog')
        if cog:
            await cog.handle_response(interaction, self.event_data, responded=False)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        
    async def on_timeout(self):
        """Handle timeout - treat as ignored"""
        if not self.responded:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Get the channel and handle timeout
            if hasattr(self, '_message') and self._message:
                try:
                    # Get the micro events cog to handle the timeout
                    cog = self.bot.get_cog('TravelMicroEventsCog')
                    if cog:
                        # Apply timeout failure directly
                        await cog.apply_timeout_failure(self._message.channel, self.event_data)
                        
                    await self._message.edit(view=self)
                except Exception as e:
                    print(f"Error handling micro-event timeout: {e}")

class TravelMicroEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_events = {}  # Track active events by channel_id
        
    async def cog_load(self):
        """Start the micro-events task when cog loads"""
        await asyncio.sleep(5)  # Wait for other systems to initialize
        self.micro_event_scheduler.start()
        print("🔧 Travel micro-events system started")
        
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.micro_event_scheduler.cancel()
        
    @tasks.loop(minutes=1)  # Check for micro-events every 1 minute
    async def micro_event_scheduler(self):
        """Check for active travel sessions and potentially trigger micro-events"""
        try:
            # Get all active travel sessions with transit channels
            active_sessions = self.db.execute_query(
                """SELECT ts.session_id, ts.user_id, ts.temp_channel_id, ts.corridor_id, 
                          ts.start_time, ts.end_time, ts.last_event_time, c.danger_level, 
                          c.name as corridor_name, l.name as dest_name
                   FROM travel_sessions ts
                   JOIN corridors c ON ts.corridor_id = c.corridor_id  
                   JOIN locations l ON ts.destination_location = l.location_id
                   WHERE ts.status = 'traveling' 
                   AND ts.temp_channel_id IS NOT NULL
                   AND ts.end_time > NOW()""",
                fetch='all'
            )
            
            if not active_sessions:
                return
                
            for session in active_sessions:
                session_id, user_id, channel_id, corridor_id, start_time, end_time, last_event_time, danger_level, corridor_name, dest_name = session
                
                # Skip if channel has an active event
                if channel_id in self.active_events:
                    continue
                
                # Calculate travel progress
                start_dt = safe_datetime_parse(start_time)
                end_dt = safe_datetime_parse(end_time)
                now = datetime.utcnow()
                
                total_duration = (end_dt - start_dt).total_seconds()
                elapsed = (now - start_dt).total_seconds()
                remaining = (end_dt - now).total_seconds()
                
                # Don't trigger events in the first 30 seconds or last 45 seconds
                if elapsed < 30 or remaining < 45:
                    continue
                
                # Calculate time since last event
                time_since_last_event = elapsed
                if last_event_time:
                    try:
                        last_event_dt = safe_datetime_parse(last_event_time)
                        time_since_last_event = (now - last_event_dt).total_seconds()
                    except (ValueError, TypeError):
                        # If there's an issue parsing, fall back to elapsed time
                        time_since_last_event = elapsed
                    
                # Calculate event probability with improved scaling
                base_chance = 0.18  # Increased from 15% to 18% base chance per check
                danger_multiplier = danger_level * 0.05  # +5% per danger level
                time_multiplier = min(1.5, elapsed / 300)  # Increase chance over time, cap at 1.5x
                
                # Anti-drought multiplier - significantly increases chance if no events for a while
                drought_multiplier = 1.0
                if time_since_last_event > 150:  # 2.5 minutes
                    drought_multiplier = 1.25
                if time_since_last_event > 210:  # 3.5 minutes
                    drought_multiplier = 1.5
                if time_since_last_event > 240:  # 4+ minutes
                    drought_multiplier = 2.0
                
                event_chance = base_chance * (1 + danger_multiplier) * time_multiplier * drought_multiplier
                
                if random.random() < event_chance:
                    await self.trigger_micro_event(user_id, channel_id, danger_level, corridor_name, session_id)
                    
        except Exception as e:
            print(f"Error in micro-event scheduler: {e}")
            
    @micro_event_scheduler.before_loop
    async def before_micro_event_scheduler(self):
        await self.bot.wait_until_ready()
        
    async def trigger_micro_event(self, user_id: int, channel_id: int, danger_level: int, corridor_name: str, session_id: int = None):
        """Trigger a micro-event for a traveling user"""
        try:
            # Get the transit channel
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
                
            # Mark this channel as having an active event
            self.active_events[channel_id] = True
            
            # Update last event time for this session
            if session_id:
                self.db.execute_query(
                    "UPDATE travel_sessions SET last_event_time = NOW() WHERE session_id = %s",
                    (session_id,)
                )
            
            # Generate the event
            event_data = self.generate_event(user_id, danger_level, corridor_name)
            
            # Calculate success percentage for display
            user_skills = self.db.execute_query(
                f"SELECT {event_data['skill']} FROM characters WHERE user_id = %s",
                (user_id,),
                fetch='one'
            )
            
            if not user_skills:
                skill_level = 5  # Default
            else:
                skill_level = user_skills[0]
                
            # Calculate success percentage (same logic as make_skill_check)
            base_success_rate = 65
            skill_difference = skill_level - event_data['expected_skill']
            success_rate = base_success_rate + (skill_difference * 4)
            success_rate = max(15, min(85, success_rate))
            
            # Create the embed
            embed = discord.Embed(
                title=f"⚠️ {event_data['title']}",
                description=event_data['description'],
                color=event_data['color']
            )
            
            embed.add_field(
                name="🎯 Challenge", 
                value=f"**{event_data['skill'].title()}** check ({success_rate}% success chance)", 
                inline=True
            )
            
            embed.add_field(
                name="⏰ Decision Time", 
                value="30 seconds to respond", 
                inline=True
            )
            
            # Add consequence preview
            embed.add_field(
                name="⚖️ Consequences",
                value=f"**Success:** Gain {event_data['xp_reward']} XP\n**Failure:** Take {event_data['damage']} damage",
                inline=False
            )
            
            # Create view with buttons
            view = MicroEventView(event_data, self.bot, timeout=30)
            
            # Get travel session info for logging (if not already provided)
            if not session_id:
                session_info = self.db.execute_query(
                    "SELECT session_id FROM travel_sessions WHERE user_id = %s AND temp_channel_id = %s AND status = 'traveling'",
                    (user_id, channel_id),
                    fetch='one'
                )
                session_id = session_info[0] if session_info else None
            
            # Log the event to database
            result = self.db.execute_query(
                """INSERT INTO travel_micro_events 
                   (travel_session_id, transit_channel_id, user_id, event_type, 
                    triggered_at, skill_used, difficulty)
                   VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                   RETURNING event_id""",
                (session_id, channel_id, user_id, event_data['title'], event_data['skill'], event_data['expected_skill']),
                fetch='one'
            )
            
            # Extract the event ID from the result tuple
            event_log_id = result[0] if result else None
            
            # Store event log ID for later updates
            event_data['event_log_id'] = event_log_id
            
            # Send the event
            message = await channel.send(
                content=f"<@{user_id}>", 
                embed=embed, 
                view=view
            )
            
            # Store reference for timeout handling
            view._message = message
            
            # Clean up the active event marker after timeout
            await asyncio.sleep(35)  # 5 seconds after timeout
            self.active_events.pop(channel_id, None)
            
        except Exception as e:
            print(f"Error triggering micro-event: {e}")
            self.active_events.pop(channel_id, None)
            
    def generate_event(self, user_id: int, danger_level: int, corridor_name: str) -> dict:
        """Generate a random micro-event based on danger level"""
        
        # Get user's skills for appropriate challenge scaling
        user_skills = self.db.execute_query(
            "SELECT engineering, navigation, combat, medical FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not user_skills:
            user_skills = (5, 5, 5, 5)  # Default values
            
        engineering, navigation, combat, medical = user_skills
        
        # Event categories based on danger level
        if danger_level <= 2:
            events = self.get_low_danger_events()
        elif danger_level <= 4:
            events = self.get_medium_danger_events()  
        else:
            events = self.get_high_danger_events()
            
        # Select random event
        event_template = random.choice(events)
        
        # Determine which skill to use
        skill_name = event_template['skill']
        skill_values = {
            'engineering': engineering,
            'navigation': navigation, 
            'combat': combat,
            'medical': medical
        }
        
        user_skill_level = skill_values[skill_name]
        
        # Determine expected skill level based on danger level
        if danger_level <= 2:
            expected_skill = 8 + random.randint(0, 2)  # 8-10 expected
        elif danger_level <= 4:
            expected_skill = 12 + random.randint(0, 3)  # 12-15 expected
        else:
            expected_skill = 18 + random.randint(0, 2)  # 18-20 expected
        
        # Scale rewards and consequences
        xp_reward = max(1, 3 + danger_level)
        damage = random.randint(1 + danger_level, 5 + (danger_level * 2))
        
        return {
            'user_id': user_id,
            'title': event_template['title'],
            'description': event_template['description'].format(corridor=corridor_name),
            'skill': skill_name,
            'expected_skill': expected_skill,
            'color': event_template['color'],
            'xp_reward': xp_reward,
            'damage': damage,
            'damage_type': event_template.get('damage_type', 'hp')
        }
        
    async def handle_response(self, interaction: discord.Interaction, event_data: dict, responded: bool, timeout: bool = False):
        """Handle the user's response to a micro-event"""
        try:
            user_id = event_data['user_id']
            
            if responded and not timeout:
                # User chose to respond - make skill check
                await self.make_skill_check(interaction, event_data)
            else:
                # User ignored or timed out - apply failure consequences
                await self.apply_failure(interaction, event_data, timeout)
                
        except Exception as e:
            print(f"Error handling micro-event response: {e}")
            if not timeout:
                await interaction.followup.send("❌ Error processing event response.", ephemeral=True)
                
    async def make_skill_check(self, interaction: discord.Interaction, event_data: dict):
        """Perform the skill check and apply results"""
        user_id = event_data['user_id']
        skill_name = event_data['skill']
        expected_skill = event_data['expected_skill']
        
        # Get user's skill level
        user_skills = self.db.execute_query(
            f"SELECT {skill_name} FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not user_skills:
            skill_level = 5  # Default
        else:
            skill_level = user_skills[0]
            
        # Calculate success percentage based on skill vs expected level
        base_success_rate = 65  # Base 65% success rate
        skill_difference = skill_level - expected_skill
        success_rate = base_success_rate + (skill_difference * 4)  # +/- 4% per skill point difference
        
        # Cap the success rate between 15% and 85%
        success_rate = max(15, min(85, success_rate))
        
        # Roll for success
        roll = random.randint(1, 100)
        success = roll <= success_rate
        
        # Update the event log with response results
        if 'event_log_id' in event_data:
            self.db.execute_query(
                """UPDATE travel_micro_events 
                   SET responded = true, roll_result = %s, success = %s, 
                       xp_awarded = %s, damage_taken = %s
                   WHERE event_id = %s""",
                (success_rate, success, event_data['xp_reward'] if success else 0, 
                 0 if success else event_data['damage'], event_data['event_log_id'])
            )
        
        if success:
            # Success - award XP
            self.db.execute_query(
                "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                (event_data['xp_reward'], user_id)
            )
            
            embed = discord.Embed(
                title="✅ Success!",
                description=f"Your {skill_name} skills proved adequate for the challenge.",
                color=0x00ff00
            )
            embed.add_field(
                name="Success Check", 
                value=f"🎯 {success_rate}% chance (Rolled {roll})",
                inline=True
            )
            embed.add_field(
                name="Reward",
                value=f"📈 +{event_data['xp_reward']} XP earned",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        else:
            # Failure - apply damage
            await self.apply_damage(interaction, event_data, success_rate, roll)
            
    async def apply_failure(self, interaction: discord.Interaction, event_data: dict, timeout: bool = False):
        """Apply failure consequences for ignoring or timing out"""
        damage = event_data['damage']
        damage_type = event_data.get('damage_type', 'hp')
        
        # Update the event log
        if 'event_log_id' in event_data:
            self.db.execute_query(
                """UPDATE travel_micro_events 
                   SET responded = false, success = false, damage_taken = %s, damage_type = %s
                   WHERE event_id = %s""",
                (damage, damage_type, event_data['event_log_id'])
            )
        
        # Apply damage based on type
        if damage_type == 'hp':
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_character_hp(event_data['user_id'], -damage, interaction.guild, "Travel micro event failure")
        elif damage_type == 'hull':
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_ship_hull(event_data['user_id'], -damage, interaction.guild)
        elif damage_type == 'fuel':
            self.db.execute_query(
                "UPDATE ships SET current_fuel = GREATEST(0::bigint, current_fuel - %s) WHERE owner_id = %s",
                (damage, event_data['user_id'])
            )
            
        action = "timed out" if timeout else "ignored the situation"
        
        embed = discord.Embed(
            title="❌ Failure",
            description=f"You {action} and suffered the consequences.",
            color=0xff4444
        )
        embed.add_field(
            name="Consequence",
            value=f"💔 -{damage} {damage_type.upper()}",
            inline=True
        )
        
        if timeout:
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except:
                # Fallback for timeout case
                channel = interaction.channel if hasattr(interaction, 'channel') else self.bot.get_channel(interaction.channel_id)
                if channel:
                    await channel.send(embed=embed)
        else:
            await interaction.followup.send(embed=embed)
            
    async def apply_damage(self, interaction: discord.Interaction, event_data: dict, success_rate: int, roll: int):
        """Apply damage for failed skill check"""
        damage = event_data['damage']  
        damage_type = event_data.get('damage_type', 'hp')
        
        # Apply damage based on type
        if damage_type == 'hp':
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_character_hp(event_data['user_id'], -damage, interaction.guild, "Travel micro event damage")
        elif damage_type == 'hull':
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_ship_hull(event_data['user_id'], -damage, interaction.guild)
        elif damage_type == 'fuel':
            self.db.execute_query(
                "UPDATE ships SET current_fuel = GREATEST(0::bigint, current_fuel - %s) WHERE owner_id = %s",
                (damage, event_data['user_id'])
            )
            
        embed = discord.Embed(
            title="❌ Failure",
            description=f"Your {event_data['skill']} check wasn't enough.",
            color=0xff4444
        )
        embed.add_field(
            name="Failure Check",
            value=f"🎯 {success_rate}% chance (Rolled {roll})",
            inline=True
        )
        embed.add_field(
            name="Consequence", 
            value=f"💔 -{damage} {damage_type.upper()}",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)
    
    async def apply_timeout_failure(self, channel: discord.TextChannel, event_data: dict):
        """Apply failure consequences when user times out (30 seconds)"""
        damage = event_data['damage']
        damage_type = event_data.get('damage_type', 'hp')
        user_id = event_data['user_id']
        
        # Update the event log
        if 'event_log_id' in event_data:
            self.db.execute_query(
                """UPDATE travel_micro_events 
                   SET responded = false, success = false, damage_taken = %s, damage_type = %s
                   WHERE event_id = %s""",
                (damage, damage_type, event_data['event_log_id'])
            )
        
        # Apply damage based on type
        if damage_type == 'hp':
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_character_hp(user_id, -damage, channel.guild, "Travel micro event timeout")
        elif damage_type == 'hull':
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.update_ship_hull(user_id, -damage, channel.guild)
        elif damage_type == 'fuel':
            self.db.execute_query(
                "UPDATE ships SET current_fuel = GREATEST(0::bigint, current_fuel - %s) WHERE owner_id = %s",
                (damage, user_id)
            )
        
        # Send clear timeout message
        embed = discord.Embed(
            title="⏰ Response Timeout",
            description=f"<@{user_id}> failed to respond within 30 seconds and suffered the consequences!",
            color=0xff6600
        )
        embed.add_field(
            name="Auto-Failure Consequence",
            value=f"💔 -{damage} {damage_type.upper()} (same as ignoring)",
            inline=True
        )
        embed.add_field(
            name="⚡ Quick Tip",
            value="Stay alert during travel - these events require fast responses!",
            inline=False
        )
        
        await channel.send(embed=embed)
        
    def get_low_danger_events(self) -> List[dict]:
        """Get low-danger micro-events (danger level 1-2)"""
        return [
            {
                'title': 'Minor System Fluctuation',
                'description': 'Your ship\'s systems show minor irregularities while traveling through {corridor}. A quick diagnostic might prevent issues.',
                'skill': 'engineering',
                'color': 0xffaa00,
                'damage_type': 'hull'
            },
            {
                'title': 'Navigation Drift',
                'description': 'Your course has drifted slightly in {corridor}. Quick course correction needed.',
                'skill': 'navigation', 
                'color': 0x4169e1,
                'damage_type': 'fuel'
            },
            {
                'title': 'Micro Debris Field',
                'description': 'Small debris particles detected ahead in {corridor}. Evasive maneuvers recommended.',
                'skill': 'navigation',
                'color': 0x808080,
                'damage_type': 'hull'
            },
            {
                'title': 'Minor Radiation Spike', 
                'description': 'Elevated radiation readings detected in {corridor}. Shield adjustment may help.',
                'skill': 'engineering',
                'color': 0xffa500,
                'damage_type': 'hp'
            },
            {
                'title': 'Comm Static Interference',
                'description': 'Communication systems are experiencing interference in {corridor}. Signal filtering needed.',
                'skill': 'engineering',
                'color': 0x9370db,
                'damage_type': 'hull'
            },
            {
                'title': 'Fuel Line Micro-Leak',
                'description': 'Sensors detect a tiny fuel leak in {corridor}. Quick seal required before it worsens.',
                'skill': 'engineering',
                'color': 0xffd700,
                'damage_type': 'fuel'
            },
            {
                'title': 'Solar Flare Echo',
                'description': 'Residual solar flare activity in {corridor} is affecting instruments. Recalibration needed.',
                'skill': 'navigation',
                'color': 0xff8c00,
                'damage_type': 'hull'
            },
            {
                'title': 'Asteroid Dust Coating',
                'description': 'Fine asteroid dust is coating sensors while passing through {corridor}. Cleaning protocols advised.',
                'skill': 'engineering', 
                'color': 0x696969,
                'damage_type': 'hull'
            },
            {
                'title': 'Routine System Hiccup',
                'description': 'Minor system glitch detected during routine checks in {corridor}. Simple reset should fix it.',
                'skill': 'engineering',
                'color': 0x87ceeb,
                'damage_type': 'hull'
            }
        ]
        
    def get_medium_danger_events(self) -> List[dict]:
        """Get medium-danger micro-events (danger level 3-4)"""
        return [
            {
                'title': 'Power Fluctuation',
                'description': 'Ship power systems are fluctuating while crossing {corridor}. Immediate stabilization required.',
                'skill': 'engineering',
                'color': 0xff6600,
                'damage_type': 'hull'
            },
            {
                'title': 'Gravity Well Distortion',
                'description': 'Unexpected gravity distortions in {corridor} are affecting your trajectory.',
                'skill': 'navigation',
                'color': 0x4b0082,
                'damage_type': 'fuel'
            },
            {
                'title': 'Sensor Ghost Contact',
                'description': 'Sensors detect an unidentified contact in {corridor}. Defensive posture advised.',
                'skill': 'combat',
                'color': 0xdc143c,
                'damage_type': 'hp'
            },
            {
                'title': 'Atmospheric Leak',
                'description': 'Minor atmospheric leak detected during transit through {corridor}. Emergency seal needed.',
                'skill': 'medical',
                'color': 0xff1493,
                'damage_type': 'hp'
            },
            {
                'title': 'Engine Stress Warning',
                'description': 'Engine stress indicators are elevated in the turbulence of {corridor}.',
                'skill': 'engineering', 
                'color': 0xff4500,
                'damage_type': 'hull'
            },
            {
                'title': 'Electromagnetic Anomaly',
                'description': 'EM anomaly in {corridor} is interfering with ship systems. Shielding adjustment required.',
                'skill': 'engineering',
                'color': 0x8a2be2,
                'damage_type': 'hull'
            },
            {
                'title': 'Pirate Scanning Probe',
                'description': 'Unknown probe detected scanning your ship in {corridor}. Evasive action recommended.',
                'skill': 'navigation',
                'color': 0xb22222,
                'damage_type': 'hp'
            },
            {
                'title': 'System Virus Alert',
                'description': 'Ship computer reports possible viral intrusion while in {corridor}. Immediate scan required.',
                'skill': 'engineering',
                'color': 0xff1493,
                'damage_type': 'hull'
            },
            {
                'title': 'Coolant Temperature Spike',
                'description': 'Engine coolant temperature rising beyond normal in {corridor}. System balance needed.',
                'skill': 'engineering',
                'color': 0xff6347,
                'damage_type': 'hull'
            },
            {
                'title': 'Thruster Misalignment',
                'description': 'Maneuvering thrusters showing slight misalignment in {corridor}. Calibration required.',
                'skill': 'navigation',
                'color': 0xdaa520,
                'damage_type': 'fuel'
            }
        ]
        
    def get_high_danger_events(self) -> List[dict]:
        """Get high-danger micro-events (danger level 5+)"""
        return [
            {
                'title': 'Critical System Alert',
                'description': 'Multiple ship systems are showing critical errors while in {corridor}. Emergency repairs needed!',
                'skill': 'engineering',
                'color': 0xff0000,
                'damage_type': 'hull'
            },
            {
                'title': 'Hostile Signature Detected',
                'description': 'Aggressive contacts detected in {corridor}. Combat readiness required!',
                'skill': 'combat', 
                'color': 0x8b0000,
                'damage_type': 'hp'
            },
            {
                'title': 'Severe Radiation Storm',
                'description': 'Dangerous radiation storm engulfs your ship in {corridor}. Immediate protection protocols needed!',
                'skill': 'medical',
                'color': 0xff0000,
                'damage_type': 'hp'
            },
            {
                'title': 'Corridor Instability',
                'description': 'Severe instability in {corridor} threatens to tear your ship apart. Emergency navigation required!',
                'skill': 'navigation',
                'color': 0x800000,
                'damage_type': 'hull'
            },
            {
                'title': 'Hull Breach Warning',
                'description': 'Micro-fractures detected in hull integrity while traversing {corridor}. Emergency containment needed!',
                'skill': 'engineering',
                'color': 0xdc143c,
                'damage_type': 'hull'
            },
            {
                'title': 'Life Support Strain',
                'description': 'Life support systems working harder than normal in the harsh environment of {corridor}. Efficiency check needed.',
                'skill': 'medical',
                'color': 0xff4500,
                'damage_type': 'hp'
            },
            {
                'title': 'Navigation Computer Lag',
                'description': 'Navigation computer responding slowly to input commands while in {corridor}. System refresh required.',
                'skill': 'navigation',
                'color': 0xff6600,
                'damage_type': 'fuel'
            },
            {
                'title': 'Weapons System Glitch',
                'description': 'Defensive systems showing intermittent errors while crossing {corridor}. Quick diagnostic advised.',
                'skill': 'combat',
                'color': 0xcd5c5c,
                'damage_type': 'hull'
            }
        ]

async def setup(bot):
    await bot.add_cog(TravelMicroEventsCog(bot))