# cogs/ambient_events.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import AMBIENT_EVENTS_CONFIG
from utils.datetime_utils import safe_datetime_parse

class AmbientEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.config = AMBIENT_EVENTS_CONFIG
        self.logger = logging.getLogger('ambient_events')
        self.enabled = self.config.get('enabled', True)
        # Don't start tasks in __init__ - use cog_load instead
        
    # =========================
    # AMBIENT MESSAGE POOLS
    # =========================
    
    # Colony Messages - Industrial/civilian activity, no weather
    COLONY_MESSAGES = [
        "The morning shift workers stream through the main transit hub, their voices creating a low hum of conversation.",
        "A transport lift rolls down the main thoroughfare, its cargo bay filled with fresh produce from the hydroponic farms.",
        "The atmospheric processors hum steadily in the distance, maintaining the colony's breathable environment.",
        "Children can be heard playing in the residential sector's recreation area, their laughter echoing through the corridors.",
        "The colony's public address system crackles to life briefly before returning to its usual background static.",
        "A maintenance crew works on replacing air filtration units in the industrial sector, their tools clanking softly.",
        "The smell of freshly baked protein bread wafts from the community kitchens in the civilian quarter.",
        "A group of stout, off-duty, bearded miners gathers near the main hub sharing stories from their latest deep-rock expedition.",
        "The evening shift supervisor makes their rounds, checking security protocols at each checkpoint.",
        "Automated cargo lifts move supplies between the storage levels, their mechanical whirring barely audible.",
        "The colony's main generator cycles through its routine diagnostic, causing lights to flicker momentarily.",
        "A medical transport rushes past toward the clinic, its emergency beacon flashing silently.",
        "Workers in environmental suits inspect the external seals from inside the maintenance airlocks.",
        "The hydroponic gardens' grow lights create shifting patterns of green and blue across the agricultural zone.",
        "A announcement echoes through the halls: 'All residents please remember to conserve water during the evening cycle.'",
        "The soft chiming of the colony's time beacon marks the transition to the next work shift.",
        "Heavy machinery operates in the mining sector, its vibrations felt faintly through the colony's superstructure.",
        "A child drops their toy in the corridor, and {character_name} watches as they quickly retrieve it and run after their guardian.",
        "The local security patrol makes their routine sweep through the market district, nodding to familiar faces.",
        "Steam vents from the thermal processing plant, creating momentary clouds in the recycled atmosphere."
    ]
    
    # Space Station Messages - Docking, systems, announcements
    SPACE_STATION_MESSAGES = [
        "The docking bay's approach lights guide an incoming cargo freighter to berth seven.",
        "A maintenance drone glides past, its welding implement folded neatly underneath it heads to the maintenance bay.",
        "The station's artificial gravity fluctuates slightly as the graviton generators recalibrate.",
        "Passengers queue at the checkpoint, their travel documents ready for inspection.",
        "The main promenade bustles with traders hawking goods from across the galaxy.",
        "A automated announcement plays: 'Attention: Docking bay twelve is temporarily closed for decontamination.'",
        "The observation deck offers a stunning view of the nearby planet's aurora as solar particles hit its magnetosphere.",
        "A diplomatic shuttle requests priority docking clearance from the station's traffic control.",
        "The hydroponics bay's misting system activates, maintaining optimal humidity for the food production cycles.",
        "A security alert briefly activates before being cleared. Just a false alarm from a malfunctioning sensor.",
        "The station's central computer hums with activity as it processes thousands of data transactions.",
        "A medical emergency team rushes past, responding to an incident in the civilian quarters.",
        "The refueling depot's mechanical arms extend to service a patrol vessel that just docked.",
        "Brightly lit advertisements flicker and change in the commercial district, advertising various services.",
        "A group of spacers shares drinks at the cantina, discussing the latest corridor route discoveries.",
        "The waste recycling systems cycle through their daily processing routine with mechanical precision.",
        "A priority communication comes through the station's comm array, causing a brief spike in activity.",
        "{character_name} notices a maintenance hatch briefly open as a technician emerges to check the corridor sensors.",
        "The magnetic containment fields around the fusion reactors shimmer with contained energy.",
        "A customs inspection team boards a recently arrived merchant vessel for routine cargo verification."
    ]
    
    # Outpost Messages - Maintenance, patrol activity, isolation effects
    OUTPOST_MESSAGES = [
        "The perimeter sensors complete their automated sweep, detecting nothing but empty space and distant debris.",
        "A lone maintenance technician checks the solar collection arrays, their work suit glinting in the starlight.",
        "The communications array rotates slowly, maintaining contact with distant stations.",
        "The outpost's small crew gathers for their daily briefing in the cramped command center.",
        "A supply drone approaches the landing pad, carrying essential supplies from the nearest depot.",
        "The life support systems run their diagnostic cycle, their gentle humming the only sound in the quiet corridors.",
        "A patrol craft returns from its sector sweep, docking with practiced efficiency in the small hangar.",
        "The outpost commander reviews duty rosters while monitoring the long-range scanner displays.",
        "The hydroponics bay's single growing unit provides fresh vegetables for the small crew.",
        "An automated distress beacon test broadcasts briefly before shutting down. All systems nominal.",
        "The reactor's cooling system cycles quietly, maintaining optimal temperature in the isolated facility.",
        "A crew member performs routine maintenance on the emergency escape pods, testing each system methodically.",
        "The outpost's small recreation area shows signs of recent use; a half-finished puzzle on the table.",
        "The external sensors detect a small asteroid passing harmlessly by, logging it in the navigation database.",
        "A maintenance alert chimes softly - the water recycling system needs a filter replacement.",
        "The skeleton crew's voices can be heard from the mess hall during their shared meal time.",
        "A patrol schedule updates on the duty board, showing the next external inspection rounds.",
        "{character_name} overhears two crew members discussing how long it's been since they've seen a commercial vessel.",
        "The backup generator briefly kicks in during the primary power system's routine maintenance cycle.",
        "A long-range communication comes through, bringing news from the outside galaxy to the isolated crew."
    ]
    
    # Gate Messages - Quantum effects, corridor monitoring, energy readings
    GATE_MESSAGES = [
        "The gate's primary ring rotates slowly, atomically charged particles dancing along its circumference.",
        "Fluctuations from the gate's fission core create brief shimmer effects in the nearby space.",
        "A deep-space survey vessel emerges from the corridor, its hull still glowing faintly with residual radiation.",
        "The gate's navigation beacons pulse in synchronized sequence, marking safe passage coordinates.",
        "Massive gravitational sensors monitor the corridor distortions around the gate's activation zone.",
        "A automated voice announces: 'Corridor stable. Transit window open for the next forty-seven minutes.'",
        "The gate's control station tracks multiple vessels approaching from various sectors of local space.",
        "Energy collector drones harvest dense radiation particles from the vacuum around the gate's opening.",
        "A cargo convoy begins its transit sequence, each ship's drive synchronizing with the gate's field.",
        "The gate's magnetic containment fields flicker as they adjust to varying cosmic radiation levels.",
        "A patrol squadron maintains its watch position, scanning for any unauthorized approach vectors.",
        "The Corridor stabilizers adjust their output, maintaining the delicate balance needed for safe passage.",
        "A research vessel requests permission to conduct passive scans of the corridor's atomic signature.",
        "The gate's massive superstructure groans softly as tidal forces from nearby gravitational bodies affect its framework.",
        "Navigation computers update their databases with the latest corridor drift calculations and safety parameters.",
        "A priority transit authorization comes through for a diplomatic vessel requiring immediate passage.",
        "The Corridor monitoring station detects minor atomic distortions; Well within acceptable parameters.",
        "{character_name} watches as the gate's energy readings spike briefly during a routine calibration sequence.",
        "A emergency shutdown test activates the gate's failsafe systems, proving their readiness for any crisis.",
        "A terminal beeps as data is recieved from a distant connected gate."
    ]
    
    # Generic Messages - Work anywhere
    GENERIC_MESSAGES = [
        "The ambient lighting adjusts automatically as the facility transitions between shift schedules.",
        "A service worker quietly cleans the corridors, letting out a deep sigh.",
        "The air recycling system's gentle hum provides a constant background symphony of life support.",
        "A group of off-duty personnel shares a meal in the communal dining area, their conversation a low murmur.",
        "The facility's central computer processes routine data, its cores flickering with activity.",
        "A maintenance request appears on the duty board; someone needs to calibrate the artificial gravity in section C.",
        "The emergency lighting system conducts its weekly test, bathing the corridors in brief amber light.",
        "A cargo transport moves through the service tunnels, its automated navigation system guiding it precisely.",
        "The facility's communication array receives routine updates from distant administrative centers.",
        "A medical scanner hums to life in the clinic as someone receives their routine health evaluation.",
        "The thermal regulation system adjusts to maintain optimal comfort levels throughout the inhabited areas.",
        "A security checkpoint briefly activates as someone with proper clearance passes through its scanners.",
        "The facility's backup power systems run their diagnostic cycle, ensuring readiness for any emergency.",
        "An educational video flickers to life in the learning center, beginning an automated lesson sequence.",
        "The waste processing systems efficiently break down and recycle materials with minimal environmental impact.",
        "{character_name} notices the subtle vibration as the facility's structural integrity systems perform their regular check.",
        "An automated announcement reminds everyone to update their personal emergency contact information.",
        "The facility's environmental sensors continuously monitor air quality, radiation levels, and atmospheric composition.",
        "A routine supply delivery is processed through the logistics center, updating inventory databases automatically.",
        "The gentle pulse of the facility's power distribution grid creates barely perceptible patterns in the lighting."
    ]
    
    # Time-based message variations
    TIME_BASED_MESSAGES = {
        'morning': [
            "The morning shift begins their duties as the facility transitions from night cycle lighting.",
            "First shift workers arrive for duty, their footsteps echoing through the awakening corridors.",
            "The day cycle lighting gradually brightens, simulating a natural sunrise for psychological comfort.",
            "Morning briefings commence in various departments as the new day's activities begin.",
            "The facility's activity levels increase as personnel transition from rest period to active duty."
        ],
        'day': [
            "Peak activity hours see the facility operating at maximum efficiency with all departments active.",
            "The corridors buzz with activity as personnel move between departments during the busy day cycle.",
            "Shift supervisors conduct their rounds, ensuring all systems operate within normal parameters.",
            "The facility hums with productive energy as the day shift maintains full operational status.",
            "Various departments coordinate their activities during the peak efficiency hours of the day cycle."
        ],
        'evening': [
            "The evening shift takes over as day personnel prepare to transition to rest periods.",
            "Activity levels begin to decrease as non-essential systems switch to night cycle operations.",
            "The facility's lighting gradually dims to evening levels, preparing for the rest cycle.",
            "Personnel complete their final tasks before the shift change to evening operations.",
            "Evening briefings update the incoming shift on the day's activities and any ongoing concerns."
        ],
        'night': [
            "Night shift personnel maintain vigilant watch during the facility's quiet hours.",
            "Essential systems continue their operations while most personnel rest during the night cycle.",
            "The facility operates with minimal lighting during the sleep period, conserving energy.",
            "Night shift supervisors conduct quiet patrols through the dimly lit corridors.",
            "Only critical personnel remain active during the rest cycle, maintaining essential functions."
        ]
    }
        
    async def cog_load(self):
        """Start background tasks after cog is loaded"""
        print("🌌 Ambient Events cog loaded, scheduling background tasks...")
        
        # Wait a bit before starting tasks to ensure everything is ready
        await asyncio.sleep(3)
        
        try:
            print("🌌 Starting ambient event generation...")
            # Update task interval from config
            self.ambient_event_generation.change_interval(minutes=self.config.get('check_interval_minutes', 15))
            self.ambient_event_generation.start()
            
            print("✅ Ambient event tasks started successfully")
            
        except Exception as e:
            print(f"❌ Error starting ambient event tasks: {e}")
            import traceback
            traceback.print_exc()
    
    def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        print("🌌 Stopping ambient event background tasks...")
        try:
            self.ambient_event_generation.cancel()
        except:
            pass

    @tasks.loop(minutes=AMBIENT_EVENTS_CONFIG.get('check_interval_minutes', 15))
    async def ambient_event_generation(self):
        """Generate ambient events at locations with players"""
        # Check if system is enabled
        if not self.enabled:
            return
            
        try:
            # Get locations with active players
            active_locations = self.db.execute_query(
                '''SELECT c.current_location, l.name, l.location_type, 
                          l.wealth_level, l.population, COUNT(*) as player_count
                   FROM characters c 
                   JOIN locations l ON c.current_location = l.location_id
                   WHERE c.current_location IS NOT NULL 
                     AND c.is_logged_in = true
                   GROUP BY c.current_location, l.name, l.location_type, l.wealth_level, l.population''',
                fetch='all'
            )
            
            if not active_locations:
                if self.config.get('advanced_settings', {}).get('debug_logging', False):
                    self.logger.debug("No active locations found for ambient event generation")
                return
            
            events_generated = 0
            current_time = datetime.utcnow()
            
            for location_data in active_locations:
                # Handle both tuple (SQLite) and dict-like (PostgreSQL) results
                if isinstance(location_data, dict):
                    location_id = int(location_data['current_location'])
                    location_name = location_data['name']
                    location_type = location_data['location_type']
                    wealth = location_data['wealth_level']
                    population = location_data['population']
                    player_count = location_data['player_count']
                else:
                    location_id, location_name, location_type, wealth, population, player_count = location_data
                    location_id = int(location_id) if location_id is not None else 0
                
                # Check if enough time has passed since last ambient event at this location
                if not self._can_generate_ambient_event(location_id, current_time):
                    continue
                
                # Calculate chance for ambient events based on location activity
                event_chance = self._calculate_event_chance(location_type, wealth, population, player_count)
                
                # Apply configuration modifiers
                base_chance = self.config.get('base_event_chance', 0.25)
                event_chance = min(event_chance * base_chance, 0.25)  # Cap at 25%
                
                if random.random() < event_chance:
                    if self.config.get('advanced_settings', {}).get('debug_logging', False):
                        self.logger.debug(f"Generating ambient event for {location_name} (chance: {event_chance:.3f})")
                    await self._generate_ambient_event(location_id, location_name, location_type, wealth, population)
                    self._update_last_event_time(location_id, current_time)
                    events_generated += 1
                elif self.config.get('advanced_settings', {}).get('debug_logging', False):
                    self.logger.debug(f"Skipped event generation for {location_name} (chance: {event_chance:.3f}, roll failed)")
            
            if events_generated > 0:
                print(f"🌌 Generated {events_generated} ambient events")
                if self.config.get('advanced_settings', {}).get('debug_logging', False):
                    self.logger.info(f"Generated {events_generated} ambient events across {len(active_locations)} active locations")
                
        except Exception as e:
            error_msg = f"❌ Error in ambient event generation: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            import traceback
            traceback.print_exc()

    @ambient_event_generation.before_loop
    async def before_ambient_event_generation(self):
        """Wait until the bot is ready before starting the task"""
        await self.bot.wait_until_ready()

    def _calculate_event_chance(self, location_type: str, wealth: int, population: int, player_count: int) -> float:
        """Calculate the chance of an ambient event occurring at a location"""
        # Base chance varies by location type - using 15-25% range from requirements
        base_chances = {
            'colony': 0.18,      # 18% base chance
            'space_station': 0.20, # 20% base chance  
            'outpost': 0.15,     # 15% base chance
            'gate': 0.16         # 16% base chance
        }
        
        base_chance = base_chances.get(location_type, 0.17)
        
        # Modify based on factors
        # More players = slightly higher chance of events
        player_modifier = 1.0 + (player_count * 0.03)
        
        # Higher wealth = more activity = more events
        wealth_modifier = 1.0 + (wealth * 0.02)
        
        # Higher population = more ambient activity
        population_modifier = 1.0 + (population / 10000000 * 0.05)  # Scale based on millions
        
        final_chance = base_chance * player_modifier * wealth_modifier * population_modifier
        
        # Cap at reasonable maximum (25% from requirements)
        return min(final_chance, 0.25)
    
    def _get_current_time_period(self) -> str:
        """Determine current time period based on UTC hour"""
        hour = datetime.utcnow().hour
        
        if 6 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 18:
            return 'day'
        elif 18 <= hour < 22:
            return 'evening'
        else:
            return 'night'
    
    def _get_messages_for_location(self, location_type: str) -> List[str]:
        """Get appropriate message pool for location type"""
        message_pools = {
            'colony': self.COLONY_MESSAGES,
            'space_station': self.SPACE_STATION_MESSAGES,
            'outpost': self.OUTPOST_MESSAGES,
            'gate': self.GATE_MESSAGES
        }
        
        return message_pools.get(location_type, self.GENERIC_MESSAGES)
    
    def _format_message(self, message: str, character_name: str = None) -> str:
        """Format message with character name if placeholder exists"""
        if '{character_name}' in message and character_name:
            return message.format(character_name=character_name)
        elif '{character_name}' in message:
            # Remove messages that require character names if none available
            return None
        return message
    
    def _select_random_character(self, location_id: int) -> Optional[str]:
        """Select a random character name from players at this location"""
        characters = self.db.execute_query(
            '''SELECT c.name 
               FROM characters c 
               WHERE c.current_location = %s 
                 AND c.is_logged_in = true
                 AND c.name IS NOT NULL
               LIMIT 5''',
            (location_id,),
            fetch='all'
        )
        
        if characters:
            return random.choice(characters)[0]
        return None
    
    def _can_generate_ambient_event(self, location_id: int, current_time: datetime) -> bool:
        """Check if enough time has passed since last ambient event at this location"""
        try:
            # Get the minimum event spacing from config
            min_spacing_minutes = self.config.get('frequency_settings', {}).get('min_event_spacing_minutes', 30)
            
            # Check last event time for this location
            last_event = self.db.execute_query(
                '''SELECT last_ambient_event 
                   FROM ambient_event_tracking 
                   WHERE location_id = %s''',
                (location_id,),
                fetch='one'
            )
            
            if not last_event or not last_event[0]:
                return True  # No previous events, can generate
            
            # Parse the last event time
            try:
                last_event_str = str(last_event[0])
                last_event_time = safe_datetime_parse(last_event_str.replace('Z', '+00:00'))
                time_diff = current_time - last_event_time
                
                # Check if enough time has passed
                return time_diff.total_seconds() >= (min_spacing_minutes * 60)
            except (ValueError, TypeError) as parse_error:
                print(f"Error parsing datetime for location {location_id}: {last_event[0]} -> {parse_error}")
                return True  # Allow event if parsing fails
            
        except Exception as e:
            error_msg = f"⚠️ Error checking event timing for location {location_id}: {e}"
            print(error_msg)
            self.logger.warning(error_msg)
            return True  # Default to allowing events if check fails
    
    def _update_last_event_time(self, location_id: int, event_time: datetime):
        """Update the last ambient event time for a location"""
        try:
            # Insert or update the tracking record
            self.db.execute_query(
                '''INSERT INTO ambient_event_tracking 
                   (location_id, last_ambient_event, total_events_generated)
                   VALUES (%s, %s, 1)
                   ON CONFLICT (location_id) DO UPDATE SET 
                   last_ambient_event = EXCLUDED.last_ambient_event,
                   total_events_generated = ambient_event_tracking.total_events_generated + 1''',
                (location_id, event_time.isoformat())
            )
        except Exception as e:
            error_msg = f"⚠️ Error updating event tracking for location {location_id}: {e}"
            print(error_msg)
            self.logger.warning(error_msg)

    async def _generate_ambient_event(self, location_id: int, location_name: str, 
                                    location_type: str, wealth: int, population: int):
        """Generate and post an ambient event for a location"""
        try:
            # Get current time period
            time_period = self._get_current_time_period()
            
            # Decide between location-specific or time-based message (80% location, 20% time)
            use_time_based = random.random() < 0.2
            
            if use_time_based:
                message_pool = self.TIME_BASED_MESSAGES[time_period]
                message = random.choice(message_pool)
                formatted_message = message
            else:
                # Get location-specific messages
                message_pool = self._get_messages_for_location(location_type)
                message = random.choice(message_pool)
                
                # Get a random character for personalized messages
                character_name = self._select_random_character(location_id)
                formatted_message = self._format_message(message, character_name)
                
                # If message formatting failed (needed character name but none available), try again
                if formatted_message is None:
                    # Try again with a message that doesn't need character names
                    attempts = 0
                    while formatted_message is None and attempts < 5:
                        message = random.choice(message_pool)
                        formatted_message = self._format_message(message)
                        attempts += 1
                    
                    # Fallback to generic message if still None
                    if formatted_message is None:
                        formatted_message = random.choice(self.GENERIC_MESSAGES)
            
            # Post the event
            await self._post_ambient_event(location_id, {
                'message': formatted_message,
                'location_name': location_name,
                'location_type': location_type,
                'time_period': time_period
            })
            
        except Exception as e:
            error_msg = f"❌ Error generating ambient event for {location_name}: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            import traceback
            traceback.print_exc()

    async def _post_ambient_event(self, location_id: int, event_data: Dict):
        """Post an ambient event to the location's channel"""
        try:
            # Get the location's Discord channel
            channel = await self._get_location_channel(location_id)
            
            if not channel:
                print(f"⚠️ No channel found for location {event_data['location_name']} (ID: {location_id})")
                return
            
            # Check if bot has permission to send messages in the channel
            if not channel.permissions_for(channel.guild.me).send_messages:
                print(f"⚠️ No permission to send messages in {event_data['location_name']} channel")
                return
            
            # Create an atmospheric embed for the ambient event
            embed = discord.Embed(
                description=f"*{event_data['message']}*",
                color=0x2f3136  # Dark gray for subtle ambient messages
            )
            
            # Add location context to embed footer
            location_type_emoji = {
                'colony': '🏙️',
                'space_station': '🛰️', 
                'outpost': '🔭',
                'gate': '🌌'
            }
            
            emoji = location_type_emoji.get(event_data['location_type'], '📍')
            embed.set_footer(text=f"{emoji} {event_data['location_name']}")
            
            # Post the ambient event
            await channel.send(embed=embed)
            
        except discord.Forbidden as e:
            print(f"⚠️ Permission denied posting to {event_data.get('location_name', 'unknown')}: {e}")
        except discord.NotFound as e:
            print(f"⚠️ Channel not found for {event_data.get('location_name', 'unknown')}: {e}")
        except discord.HTTPException as e:
            print(f"❌ Discord HTTP error posting ambient event to {event_data.get('location_name', 'unknown')}: {e}")
        except Exception as e:
            print(f"❌ Unexpected error posting ambient event to {event_data.get('location_name', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()

    async def _get_location_channel(self, location_id: int) -> Optional[discord.TextChannel]:
        """Get the Discord channel for a location - returns first available channel for backwards compatibility"""
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        cross_guild_channels = await channel_manager.get_cross_guild_location_channels(location_id)
        
        if cross_guild_channels:
            # Return the first available channel for backwards compatibility
            return cross_guild_channels[0][1]
        return None

    # Admin commands for testing and management
    ambient_admin_group = app_commands.Group(name="ambient_admin", description="Ambient events administration")

    @ambient_admin_group.command(name="trigger", description="Manually trigger ambient event generation")
    async def trigger_ambient_events(self, interaction: discord.Interaction):
        """Manually trigger ambient event generation for testing"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.send_message("🌌 Triggering ambient event generation...", ephemeral=True)
        await self.ambient_event_generation()
        await interaction.followup.send("✅ Ambient event generation completed.", ephemeral=True)

    @ambient_admin_group.command(name="status", description="Show ambient events system status")
    async def ambient_status(self, interaction: discord.Interaction):
        """Show comprehensive status of the ambient events system"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Get comprehensive system statistics
        active_locations = self.db.execute_query(
            '''SELECT COUNT(DISTINCT c.current_location) 
               FROM characters c 
               WHERE c.current_location IS NOT NULL 
                 AND c.is_logged_in = true''',
            fetch='one'
        )[0]
        
        total_players = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE is_logged_in = true",
            fetch='one'
        )[0]
        
        # Get active locations with details
        active_location_details = self.db.execute_query(
            '''SELECT l.name, l.location_type, COUNT(*) as players,
                      COALESCE(aet.total_events_generated, 0) as events
               FROM characters c 
               JOIN locations l ON c.current_location = l.location_id
               LEFT JOIN ambient_event_tracking aet ON l.location_id = aet.location_id
               WHERE c.current_location IS NOT NULL 
                 AND c.is_logged_in = true
               GROUP BY c.current_location, l.name, l.location_type, aet.total_events_generated
               ORDER BY players DESC
               LIMIT 10''',
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🌌 Ambient Events System Status",
            description="Comprehensive system state and statistics",
            color=0x4b0082
        )
        
        # System state
        system_status = "✅ Enabled" if self.enabled else "❌ Disabled"
        task_status = "✅ Running" if self.ambient_event_generation.is_running() else "❌ Stopped"
        
        embed.add_field(name="🔧 System Status", value=system_status, inline=True)
        embed.add_field(name="🔧 Task Status", value=task_status, inline=True)
        embed.add_field(name="🏢 Active Locations", value=str(active_locations), inline=True)
        embed.add_field(name="👥 Online Players", value=str(total_players), inline=True)
        
        # Configuration info
        check_interval = self.config.get('check_interval_minutes', 15)
        min_spacing = self.config.get('frequency_settings', {}).get('min_event_spacing_minutes', 30)
        base_chance = self.config.get('base_event_chance', 0.25)
        
        embed.add_field(
            name="⏰ Configuration",
            value=f"Check Interval: {check_interval} min\nMin Spacing: {min_spacing} min\nBase Chance: {base_chance*100:.1f}%",
            inline=True
        )
        
        # Total events generated
        total_events = self.db.execute_query(
            "SELECT SUM(total_events_generated) FROM ambient_event_tracking",
            fetch='one'
        )
        total_events_count = total_events[0] if total_events and total_events[0] else 0
        embed.add_field(name="📊 Total Events Generated", value=str(total_events_count), inline=True)
        
        # Recent events (last 24 hours)
        recent_events = self.db.execute_query(
            '''SELECT COUNT(*) FROM ambient_event_tracking 
               WHERE last_ambient_event > NOW() - INTERVAL '24 hours' ''',
            fetch='one'
        )[0]
        embed.add_field(name="📅 Events (24h)", value=str(recent_events), inline=True)
        
        # Most active locations
        if active_location_details:
            location_list = "\n".join([
                f"**{name}** ({loc_type}): {players} players, {events} events"
                for name, loc_type, players, events in active_location_details[:5]
            ])
            embed.add_field(name="🌟 Most Active Locations", value=location_list, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ambient_admin_group.command(name="test_event", description="Generate a test ambient event at current location")
    async def test_ambient_event(self, interaction: discord.Interaction):
        """Generate a test ambient event at the user's current location"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Get user's current location
        char_location = self.db.execute_query(
            '''SELECT c.current_location, l.name, l.location_type, l.wealth_level, l.population
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message(
                "You must be at a location to test ambient events.", 
                ephemeral=True
            )
            return
        
        location_id, location_name, location_type, wealth, population = char_location
        
        await interaction.response.send_message(
            f"🌌 Generating test ambient event at {location_name}...", 
            ephemeral=True
        )
        
        await self._generate_ambient_event(location_id, location_name, location_type, wealth, population)
        
        await interaction.followup.send(
            f"✅ Test ambient event generated for {location_name}.", 
            ephemeral=True
        )

    @ambient_admin_group.command(name="enable", description="Enable or disable the ambient events system")
    async def toggle_ambient_system(self, interaction: discord.Interaction, enabled: bool):
        """Enable or disable the entire ambient events system"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        old_status = self.enabled
        self.enabled = enabled
        
        if enabled and not old_status:
            # System was disabled, now enabling
            if not self.ambient_event_generation.is_running():
                self.ambient_event_generation.start()
            status_msg = "✅ Ambient events system **ENABLED**"
            color = 0x00ff00
        elif not enabled and old_status:
            # System was enabled, now disabling
            status_msg = "❌ Ambient events system **DISABLED**"
            color = 0xff0000
        else:
            # No change
            status_msg = f"Ambient events system is already {'enabled' if enabled else 'disabled'}"
            color = 0x999999
        
        embed = discord.Embed(
            title="🌌 Ambient Events System Toggle",
            description=status_msg,
            color=color
        )
        
        if self.config.get('advanced_settings', {}).get('debug_logging', False):
            self.logger.info(f"Ambient events system {'enabled' if enabled else 'disabled'} by {interaction.user}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ambient_admin_group.command(name="statistics", description="Show detailed ambient events statistics")
    async def ambient_statistics(self, interaction: discord.Interaction):
        """Show detailed statistics about ambient event generation"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Get comprehensive statistics
        stats_queries = [
            ("SELECT COUNT(*) FROM ambient_event_tracking", [], 'one'),
            ("SELECT SUM(total_events_generated) FROM ambient_event_tracking", [], 'one'),
            ("SELECT AVG(total_events_generated) FROM ambient_event_tracking WHERE total_events_generated > 0", [], 'one'),
            ('''SELECT l.location_type, COUNT(*) as locations, SUM(COALESCE(aet.total_events_generated, 0)) as events
               FROM locations l
               LEFT JOIN ambient_event_tracking aet ON l.location_id = aet.location_id
               GROUP BY l.location_type
               ORDER BY events DESC''', [], 'all'),
            ('''SELECT l.name, l.location_type, aet.total_events_generated, aet.last_ambient_event
               FROM ambient_event_tracking aet
               JOIN locations l ON aet.location_id = l.location_id
               ORDER BY aet.total_events_generated DESC
               LIMIT 10''', [], 'all')
        ]
        
        results = self.db.execute_bulk_read_queries(stats_queries)
        
        locations_with_events = results[0][0] if results[0] else 0
        total_events = results[1][0] if results[1] and results[1][0] else 0
        avg_events = results[2][0] if results[2] and results[2][0] else 0
        type_stats = results[3] if results[3] else []
        top_locations = results[4] if results[4] else []
        
        embed = discord.Embed(
            title="📊 Ambient Events Statistics",
            description="Detailed event generation statistics",
            color=0x00aaff
        )
        
        # Overall statistics
        embed.add_field(
            name="🎯 Overall Stats",
            value=f"**Locations with Events:** {locations_with_events}\n**Total Events Generated:** {total_events:,}\n**Average Events per Location:** {avg_events:.1f}",
            inline=True
        )
        
        # Events by location type
        if type_stats:
            type_breakdown = "\n".join([
                f"**{loc_type.title()}:** {locations} locations, {events} events"
                for loc_type, locations, events in type_stats
            ])
            embed.add_field(
                name="🌍 By Location Type",
                value=type_breakdown,
                inline=True
            )
        
        # Configuration details
        config_info = (
            f"**Check Interval:** {self.config.get('check_interval_minutes', 15)} minutes\n"
            f"**Min Event Spacing:** {self.config.get('frequency_settings', {}).get('min_event_spacing_minutes', 30)} minutes\n"
            f"**Base Event Chance:** {self.config.get('base_event_chance', 0.25)*100:.1f}%\n"
            f"**System Enabled:** {'Yes' if self.enabled else 'No'}"
        )
        embed.add_field(
            name="⚙️ Configuration",
            value=config_info,
            inline=True
        )
        
        # Top event-generating locations
        if top_locations:
            top_list = "\n".join([
                f"**{name[:20]}** ({loc_type}): {events} events"
                for name, loc_type, events, last_event in top_locations[:8]
            ])
            embed.add_field(
                name="🏆 Most Active Locations",
                value=top_list,
                inline=False
            )
        
        # Recent activity (last hour)
        recent_activity = self.db.execute_query(
            '''SELECT COUNT(*) FROM ambient_event_tracking 
               WHERE last_ambient_event > NOW() - INTERVAL '1 hours' ''',
            fetch='one'
        )[0]
        
        embed.add_field(
            name="🗓️ Recent Activity",
            value=f"Events in last hour: **{recent_activity}**",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ambient_admin_group.command(name="trigger_location", description="Manually trigger ambient events for a specific location type")
    async def trigger_location_type(self, interaction: discord.Interaction, location_type: str):
        """Manually trigger ambient event generation for all locations of a specific type"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        valid_types = ['colony', 'space_station', 'outpost', 'gate']
        if location_type.lower() not in valid_types:
            await interaction.response.send_message(
                f"Invalid location type. Valid types: {', '.join(valid_types)}",
                ephemeral=True
            )
            return
        
        # Get all locations of specified type with active players
        locations = self.db.execute_query(
            '''SELECT l.location_id, l.name, l.location_type, l.wealth_level, l.population, COUNT(*) as player_count
               FROM characters c 
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.current_location IS NOT NULL 
                 AND c.is_logged_in = true
                 AND l.location_type = %s
               GROUP BY c.current_location''',
            (location_type,),
            fetch='all'
        )
        
        if not locations:
            await interaction.response.send_message(
                f"No active {location_type} locations found with players.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            f"🌌 Triggering ambient events for {len(locations)} {location_type} location(s)...",
            ephemeral=True
        )
        
        events_generated = 0
        for location_id, location_name, loc_type, wealth, population, player_count in locations:
            try:
                await self._generate_ambient_event(location_id, location_name, loc_type, wealth, population)
                self._update_last_event_time(location_id, datetime.utcnow())
                events_generated += 1
            except Exception as e:
                print(f"❌ Error generating event for {location_name}: {e}")
        
        await interaction.followup.send(
            f"✅ Generated {events_generated} ambient events for {location_type} locations.",
            ephemeral=True
        )

    @ambient_admin_group.command(name="cleanup", description="Clean up old ambient event data")
    async def cleanup_ambient_data(self, interaction: discord.Interaction):
        """Clean up old ambient event tracking data"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get retention hours from config
            retention_hours = self.config.get('advanced_settings', {}).get('event_history_retention_hours', 24)
            
            # Clean up old event tracking data
            cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)
            
            # Reset tracking for locations that haven't had events recently
            old_events = self.db.execute_query(
                '''SELECT COUNT(*) FROM ambient_event_tracking 
                   WHERE last_ambient_event < %s''',
                (cutoff_time.isoformat(),),
                fetch='one'
            )[0]
            
            if old_events > 0:
                self.db.execute_query(
                    '''UPDATE ambient_event_tracking 
                       SET last_ambient_event = NULL 
                       WHERE last_ambient_event < %s''',
                    (cutoff_time.isoformat(),)
                )
            
            # Get current stats
            total_tracked = self.db.execute_query(
                "SELECT COUNT(*) FROM ambient_event_tracking",
                fetch='one'
            )[0]
            
            embed = discord.Embed(
                title="🧹 Ambient Events Cleanup",
                description="Cleaned up old ambient event data",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📊 Cleanup Results",
                value=f"**Old Records Reset:** {old_events}\n**Total Locations Tracked:** {total_tracked}\n**Retention Period:** {retention_hours} hours",
                inline=False
            )
            
            if self.config.get('advanced_settings', {}).get('debug_logging', False):
                self.logger.info(f"Cleaned up {old_events} old ambient event records (retention: {retention_hours}h)")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Cleanup Error",
                description=f"Failed to clean up ambient event data: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            self.logger.error(f"Ambient events cleanup failed: {e}")

    @ambient_admin_group.command(name="debug_toggle", description="Toggle debug logging for ambient events")
    async def toggle_debug_logging(self, interaction: discord.Interaction):
        """Toggle debug logging for the ambient events system"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Toggle debug logging (note: this changes the config temporarily)
        current_debug = self.config.get('advanced_settings', {}).get('debug_logging', False)
        new_debug = not current_debug
        
        # Update config (this is temporary - would need persistent storage for permanent changes)
        if 'advanced_settings' not in self.config:
            self.config['advanced_settings'] = {}
        self.config['advanced_settings']['debug_logging'] = new_debug
        
        # Configure logger level
        if new_debug:
            self.logger.setLevel(logging.DEBUG)
            status_msg = "✅ Debug logging **ENABLED** for ambient events"
            color = 0x00ff00
        else:
            self.logger.setLevel(logging.INFO)
            status_msg = "❌ Debug logging **DISABLED** for ambient events"
            color = 0xff9900
        
        embed = discord.Embed(
            title="🔍 Debug Logging Toggle",
            description=status_msg,
            color=color
        )
        
        embed.add_field(
            name="ℹ️ Note",
            value="Debug setting is temporary and will reset on bot restart",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ambient_admin_group.command(name="health", description="Perform system health check")
    async def health_check(self, interaction: discord.Interaction):
        """Perform a comprehensive health check of the ambient events system"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            health = self._get_system_health()
            
            if 'error' in health:
                embed = discord.Embed(
                    title="❌ System Health Check Failed",
                    description=f"Error: {health['error']}",
                    color=0xff0000
                )
            else:
                # Determine overall health status
                issues = []
                if not health['enabled']:
                    issues.append("System is disabled")
                if not health['task_running']:
                    issues.append("Background task not running")
                if not health['config_valid']:
                    issues.append("Configuration validation failed")
                
                if not issues:
                    title = "✅ System Health: Excellent"
                    color = 0x00ff00
                    status = "All systems operational"
                elif len(issues) == 1:
                    title = "⚠️ System Health: Warning"
                    color = 0xff9900
                    status = f"Issue detected: {issues[0]}"
                else:
                    title = "❌ System Health: Critical"
                    color = 0xff0000
                    status = f"Multiple issues: {', '.join(issues)}"
                
                embed = discord.Embed(
                    title=title,
                    description=status,
                    color=color
                )
                
                # System status details
                embed.add_field(
                    name="🔧 System Status",
                    value=(
                        f"**Enabled:** {'Yes' if health['enabled'] else 'No'}\n"
                        f"**Task Running:** {'Yes' if health['task_running'] else 'No'}\n"
                        f"**Config Valid:** {'Yes' if health['config_valid'] else 'No'}"
                    ),
                    inline=True
                )
                
                # Database metrics
                embed.add_field(
                    name="📊 Database Metrics",
                    value=(
                        f"**Locations Tracked:** {health['total_locations_tracked']:,}\n"
                        f"**Events Generated:** {health['total_events_generated']:,}\n"
                        f"**Last Check:** {health['last_check'][:19]}"
                    ),
                    inline=True
                )
                
                # Configuration summary
                config_info = (
                    f"**Check Interval:** {self.config.get('check_interval_minutes', 15)} min\n"
                    f"**Base Event Chance:** {self.config.get('base_event_chance', 0.25)*100:.1f}%\n"
                    f"**Debug Logging:** {'On' if self.config.get('advanced_settings', {}).get('debug_logging', False) else 'Off'}"
                )
                embed.add_field(
                    name="⚙️ Configuration",
                    value=config_info,
                    inline=True
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Health Check Error",
                description=f"Failed to perform health check: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            self.logger.error(f"Health check failed: {e}")
    
    # =========================
    # HELPER METHODS
    # =========================
    
    def _validate_config(self) -> bool:
        """Validate the ambient events configuration"""
        try:
            required_keys = ['enabled', 'check_interval_minutes', 'base_event_chance']
            for key in required_keys:
                if key not in self.config:
                    self.logger.error(f"Missing required config key: {key}")
                    return False
            
            # Validate ranges
            if not (1 <= self.config.get('check_interval_minutes', 15) <= 60):
                self.logger.error("check_interval_minutes must be between 1 and 60")
                return False
            
            if not (0.0 <= self.config.get('base_event_chance', 0.25) <= 1.0):
                self.logger.error("base_event_chance must be between 0.0 and 1.0")
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Config validation failed: {e}")
            return False
    
    def _get_system_health(self) -> Dict[str, any]:
        """Get system health metrics"""
        try:
            health = {
                'enabled': self.enabled,
                'task_running': self.ambient_event_generation.is_running(),
                'config_valid': self._validate_config(),
                'last_check': datetime.utcnow().isoformat(),
                'total_locations_tracked': 0,
                'total_events_generated': 0
            }
            
            # Get database metrics
            try:
                health['total_locations_tracked'] = self.db.execute_query(
                    "SELECT COUNT(*) FROM ambient_event_tracking",
                    fetch='one'
                )[0]
                
                total_events = self.db.execute_query(
                    "SELECT SUM(total_events_generated) FROM ambient_event_tracking",
                    fetch='one'
                )[0]
                health['total_events_generated'] = total_events if total_events else 0
            except Exception as e:
                self.logger.warning(f"Could not get database health metrics: {e}")
            
            return health
        except Exception as e:
            self.logger.error(f"Failed to get system health: {e}")
            return {'error': str(e)}
    
    def _get_location_activity_score(self, location_type: str, wealth: int, population: int, player_count: int) -> float:
        """Calculate a comprehensive activity score for a location"""
        try:
            # Base score from location type
            type_multipliers = self.config.get('location_multipliers', {
                'colony': 1.2,
                'space_station': 1.2,
                'outpost': 0.9,
                'gate': 0.8
            })
            
            base_score = type_multipliers.get(location_type, 1.0)
            
            # Player activity bonus
            player_bonus = 1.0 + (player_count * 0.1)  # 10% bonus per player
            
            # Wealth modifier
            wealth_bonus = 1.0 + ((wealth - 5) * 0.05)  # +/-5% per wealth level from average
            
            # Population density
            population_bonus = 1.0 + (population / 10000000 * 0.1)  # Scale with population
            
            final_score = base_score * player_bonus * wealth_bonus * population_bonus
            
            if self.config.get('advanced_settings', {}).get('debug_logging', False):
                self.logger.debug(
                    f"Activity score for {location_type}: base={base_score:.2f}, "
                    f"players={player_bonus:.2f}, wealth={wealth_bonus:.2f}, "
                    f"population={population_bonus:.2f}, final={final_score:.2f}"
                )
            
            return final_score
        except Exception as e:
            self.logger.warning(f"Error calculating activity score: {e}")
            return 1.0  # Default neutral score
    
    async def _perform_maintenance(self) -> Dict[str, any]:
        """Perform system maintenance tasks"""
        maintenance_results = {
            'cleaned_old_records': 0,
            'validated_config': False,
            'health_check': False,
            'errors': []
        }
        
        try:
            # Validate configuration
            maintenance_results['validated_config'] = self._validate_config()
            
            # Health check
            health = self._get_system_health()
            maintenance_results['health_check'] = 'error' not in health
            
            # Clean up old records if configured
            retention_hours = self.config.get('advanced_settings', {}).get('event_history_retention_hours', 24)
            if retention_hours > 0:
                cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)
                
                cleaned = self.db.execute_query(
                    '''UPDATE ambient_event_tracking 
                       SET last_ambient_event = NULL 
                       WHERE last_ambient_event < %s
                       RETURNING 1''',
                    (cutoff_time.isoformat(),),
                    fetch='all'
                )
                maintenance_results['cleaned_old_records'] = len(cleaned) if cleaned else 0
            
            if self.config.get('advanced_settings', {}).get('debug_logging', False):
                self.logger.info(f"Maintenance completed: {maintenance_results}")
            
        except Exception as e:
            error_msg = f"Maintenance task failed: {e}"
            maintenance_results['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return maintenance_results

async def setup(bot):
    await bot.add_cog(AmbientEventsCog(bot))