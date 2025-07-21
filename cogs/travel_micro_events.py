import discord
from discord.ext import commands, tasks
from discord import ui
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class MicroEventView(ui.View):
    def __init__(self, event_data: dict, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.event_data = event_data
        self.responded = False
        
    @ui.button(label="Respond", style=discord.ButtonStyle.success, emoji="⚡")
    async def respond_button(self, interaction: discord.Interaction, button: ui.Button):
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
    async def ignore_button(self, interaction: discord.Interaction, button: ui.Button):
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
                    from bot import bot  # Import bot instance
                    cog = bot.get_cog('TravelMicroEventsCog')
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
        
    @tasks.loop(minutes=2)  # Check for micro-events every 2 minutes
    async def micro_event_scheduler(self):
        """Check for active travel sessions and potentially trigger micro-events"""
        try:
            # Get all active travel sessions with transit channels
            active_sessions = self.db.execute_query(
                """SELECT ts.session_id, ts.user_id, ts.temp_channel_id, ts.corridor_id, 
                          ts.start_time, ts.end_time, c.danger_level, c.name as corridor_name,
                          l.name as dest_name
                   FROM travel_sessions ts
                   JOIN corridors c ON ts.corridor_id = c.corridor_id  
                   JOIN locations l ON ts.destination_location = l.location_id
                   WHERE ts.status = 'traveling' 
                   AND ts.temp_channel_id IS NOT NULL
                   AND ts.end_time > datetime('now')""",
                fetch='all'
            )
            
            if not active_sessions:
                return
                
            for session in active_sessions:
                session_id, user_id, channel_id, corridor_id, start_time, end_time, danger_level, corridor_name, dest_name = session
                
                # Skip if channel has an active event
                if channel_id in self.active_events:
                    continue
                
                # Calculate travel progress
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
                now = datetime.utcnow()
                
                total_duration = (end_dt - start_dt).total_seconds()
                elapsed = (now - start_dt).total_seconds()
                remaining = (end_dt - now).total_seconds()
                
                # Don't trigger events in the first 30 seconds or last 45 seconds
                if elapsed < 30 or remaining < 45:
                    continue
                    
                # Calculate event probability based on danger level and time
                base_chance = 0.15  # 15% base chance per check
                danger_multiplier = danger_level * 0.05  # +5% per danger level
                time_multiplier = min(1.5, elapsed / 300)  # Increase chance over time, cap at 1.5x
                
                event_chance = base_chance * (1 + danger_multiplier) * time_multiplier
                
                if random.random() < event_chance:
                    await self.trigger_micro_event(user_id, channel_id, danger_level, corridor_name)
                    
        except Exception as e:
            print(f"Error in micro-event scheduler: {e}")
            
    @micro_event_scheduler.before_loop
    async def before_micro_event_scheduler(self):
        await self.bot.wait_until_ready()
        
    async def trigger_micro_event(self, user_id: int, channel_id: int, danger_level: int, corridor_name: str):
        """Trigger a micro-event for a traveling user"""
        try:
            # Get the transit channel
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
                
            # Mark this channel as having an active event
            self.active_events[channel_id] = True
            
            # Generate the event
            event_data = self.generate_event(user_id, danger_level, corridor_name)
            
            # Create the embed
            embed = discord.Embed(
                title=f"⚠️ {event_data['title']}",
                description=event_data['description'],
                color=event_data['color']
            )
            
            embed.add_field(
                name="🎯 Challenge", 
                value=f"**{event_data['skill'].title()}** check (Difficulty: {event_data['difficulty']})", 
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
            view = MicroEventView(event_data, timeout=30)
            
            # Get travel session info for logging
            session_info = self.db.execute_query(
                "SELECT session_id FROM travel_sessions WHERE user_id = ? AND temp_channel_id = ? AND status = 'traveling'",
                (user_id, channel_id),
                fetch='one'
            )
            
            session_id = session_info[0] if session_info else None
            
            # Log the event to database
            event_log_id = self.db.execute_query(
                """INSERT INTO travel_micro_events 
                   (travel_session_id, transit_channel_id, user_id, event_type, 
                    triggered_at, skill_used, difficulty)
                   VALUES (?, ?, ?, ?, datetime('now'), ?, ?)""",
                (session_id, channel_id, user_id, event_data['title'], event_data['skill'], event_data['difficulty']),
                fetch='lastrowid'
            )
            
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
            "SELECT engineering, navigation, combat, medical FROM characters WHERE user_id = ?",
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
        
        # Scale difficulty based on user's skill and danger level
        base_difficulty = 10 + (danger_level * 2)
        difficulty = max(8, base_difficulty - (user_skill_level - 5))  # Easier for skilled players
        
        # Scale rewards and consequences
        xp_reward = max(1, 3 + danger_level)
        damage = random.randint(1 + danger_level, 5 + (danger_level * 2))
        
        return {
            'user_id': user_id,
            'title': event_template['title'],
            'description': event_template['description'].format(corridor=corridor_name),
            'skill': skill_name,
            'difficulty': difficulty,
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
        difficulty = event_data['difficulty']
        
        # Get user's skill level
        user_skills = self.db.execute_query(
            f"SELECT {skill_name} FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not user_skills:
            skill_level = 5  # Default
        else:
            skill_level = user_skills[0]
            
        # Roll skill check
        roll = random.randint(1, 20) + skill_level
        success = roll >= difficulty
        
        # Update the event log with response results
        if 'event_log_id' in event_data:
            self.db.execute_query(
                """UPDATE travel_micro_events 
                   SET responded = 1, roll_result = ?, success = ?, 
                       xp_awarded = ?, damage_taken = ?
                   WHERE event_id = ?""",
                (roll, success, event_data['xp_reward'] if success else 0, 
                 0 if success else event_data['damage'], event_data['event_log_id'])
            )
        
        if success:
            # Success - award XP
            self.db.execute_query(
                "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                (event_data['xp_reward'], user_id)
            )
            
            embed = discord.Embed(
                title="✅ Success!",
                description=f"Your {skill_name} skills proved adequate for the challenge.",
                color=0x00ff00
            )
            embed.add_field(
                name="Roll Result", 
                value=f"🎲 {roll} vs {difficulty} (Success!)",
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
            await self.apply_damage(interaction, event_data, roll, difficulty)
            
    async def apply_failure(self, interaction: discord.Interaction, event_data: dict, timeout: bool = False):
        """Apply failure consequences for ignoring or timing out"""
        damage = event_data['damage']
        damage_type = event_data.get('damage_type', 'hp')
        
        # Update the event log
        if 'event_log_id' in event_data:
            self.db.execute_query(
                """UPDATE travel_micro_events 
                   SET responded = 0, success = 0, damage_taken = ?, damage_type = ?
                   WHERE event_id = ?""",
                (damage, damage_type, event_data['event_log_id'])
            )
        
        # Apply damage based on type
        if damage_type == 'hp':
            self.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (damage, event_data['user_id'])
            )
        elif damage_type == 'hull':
            self.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (damage, event_data['user_id'])
            )
        elif damage_type == 'fuel':
            self.db.execute_query(
                "UPDATE ships SET current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
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
            
    async def apply_damage(self, interaction: discord.Interaction, event_data: dict, roll: int, difficulty: int):
        """Apply damage for failed skill check"""
        damage = event_data['damage']  
        damage_type = event_data.get('damage_type', 'hp')
        
        # Apply damage based on type
        if damage_type == 'hp':
            self.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (damage, event_data['user_id'])
            )
        elif damage_type == 'hull':
            self.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (damage, event_data['user_id'])
            )
        elif damage_type == 'fuel':
            self.db.execute_query(
                "UPDATE ships SET current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
                (damage, event_data['user_id'])
            )
            
        embed = discord.Embed(
            title="❌ Failure",
            description=f"Your {event_data['skill']} check wasn't enough.",
            color=0xff4444
        )
        embed.add_field(
            name="Roll Result",
            value=f"🎲 {roll} vs {difficulty} (Failed)",
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
                   SET responded = 0, success = 0, damage_taken = ?, damage_type = ?
                   WHERE event_id = ?""",
                (damage, damage_type, event_data['event_log_id'])
            )
        
        # Apply damage based on type
        if damage_type == 'hp':
            self.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (damage, user_id)
            )
        elif damage_type == 'hull':
            self.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (damage, user_id)
            )
        elif damage_type == 'fuel':
            self.db.execute_query(
                "UPDATE ships SET current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
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
            }
        ]

async def setup(bot):
    await bot.add_cog(TravelMicroEventsCog(bot))