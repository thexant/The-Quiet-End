# cogs/npcs.py
import discord
from discord.ext import commands, tasks
import random
from views.jobview import JobView
from cogs.jobs import StationaryJob, TransportJob
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import string
from utils.npc_data import (
    generate_npc_name, generate_ship_name, get_random_radio_message, 
    get_location_action, get_occupation, PERSONALITIES, TRADE_SPECIALTIES, SHIP_TYPES
)

class NPCCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.dynamic_npc_tasks = {}  # Track active NPC tasks
        # Start initial tasks
        self.bot.loop.create_task(self._start_variable_tasks())

    async def _start_variable_tasks(self):
        """Start all variable-interval tasks"""
        await self.bot.wait_until_ready()
        # Start each task with initial random delays
        self.bot.loop.create_task(self._radio_message_loop())
        self.bot.loop.create_task(self._dynamic_npc_movement_loop())
        self.bot.loop.create_task(self._dynamic_npc_actions_loop())

    async def _radio_message_loop(self):
        """Variable interval radio message task with chance component"""
        while True:
            try:
                # Get all alive dynamic NPCs
                npcs = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.callsign, n.ship_name, n.current_location,
                              l.name as location_name, l.system_name, l.x_coord, l.y_coord,
                              n.last_radio_message
                       FROM dynamic_npcs n
                       LEFT JOIN locations l ON n.current_location = l.location_id
                       WHERE n.is_alive = 1 AND n.current_location IS NOT NULL""",
                    fetch='all'
                )

                if npcs:
                    # Each NPC has a chance to send a message (not all at once)
                    for npc_data in npcs:
                        npc_id, name, callsign, ship_name, location_id, location_name, system_name, x_coord, y_coord, last_message = npc_data

                        # 3% chance each cycle for any given NPC to send a message
                        if random.random() < 0.03:
                            # Check cooldown (don't spam messages from same NPC)
                            if last_message:
                                try:
                                    last_time = datetime.fromisoformat(last_message)
                                    if datetime.now() - last_time < timedelta(hours=2):
                                        continue
                                except (ValueError, TypeError):
                                    # Handle cases where last_message is not a valid ISO format string
                                    pass


                            # Get random message template and format it
                            message_template = get_random_radio_message()
                            message = message_template.format(
                                name=name.split()[0],  # First name only
                                callsign=callsign,
                                ship=ship_name,
                                location=location_name or "Unknown",
                                system=system_name or "Unknown"
                            )

                            # Send the message
                            await self._send_npc_radio_message(name, callsign, location_name or "Deep Space", system_name or "Unknown", message)

                            # Update last radio message time
                            self.db.execute_query(
                                "UPDATE dynamic_npcs SET last_radio_message = ? WHERE npc_id = ?",
                                (datetime.now().isoformat(), npc_id)
                            )

                            # Small delay between messages if multiple NPCs are sending
                            await asyncio.sleep(random.uniform(300, 1200))

            except Exception as e:
                print(f"❌ Error in NPC radio message loop: {e}")

            # Wait random time before next cycle (30-90 minutes)
            next_delay = random.uniform(30 * 60, 90 * 60)  # Convert to seconds
            await asyncio.sleep(next_delay)

    async def _dynamic_npc_movement_loop(self):
        """Variable interval movement task"""
        while True:
            try:
                # Get NPCs that aren't currently traveling
                idle_npcs = self.db.execute_query(
                    """SELECT npc_id, name, current_location FROM dynamic_npcs 
                       WHERE is_alive = 1 AND travel_start_time IS NULL AND current_location IS NOT NULL""",
                    fetch='all'
                )
                
                for npc_id, name, location_id in idle_npcs:
                    # 20% chance each cycle for an NPC to decide to travel
                    if random.random() < 0.2:
                        await self._start_npc_travel(npc_id, name, location_id)
                        # Small delay between travel starts
                        await asyncio.sleep(random.uniform(10, 60))
                
            except Exception as e:
                print(f"❌ Error in NPC movement loop: {e}")
            
            # Wait random time before next cycle (30-90 minutes)
            next_delay = random.uniform(30 * 60, 90 * 60)  # Convert to seconds
            await asyncio.sleep(next_delay)

    async def _dynamic_npc_actions_loop(self):
        """Variable interval actions task"""
        while True:
            try:
                # Get NPCs that are currently at locations (not traveling)
                npcs_at_locations = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.ship_name, n.current_location, l.location_type, l.name as location_name
                       FROM dynamic_npcs n
                       JOIN locations l ON n.current_location = l.location_id
                       WHERE n.is_alive = 1 AND n.travel_start_time IS NULL""",
                    fetch='all'
                )
                
                for npc_id, name, ship_name, location_id, location_type, location_name in npcs_at_locations:
                    # 30% chance for each NPC to perform an action
                    if random.random() < 0.3:
                        await self._perform_npc_action(npc_id, name, ship_name, location_id, location_type, location_name)
                        # Small delay between actions
                        await asyncio.sleep(random.uniform(5, 20))
                
            except Exception as e:
                print(f"❌ Error in NPC actions loop: {e}")
            
            # Wait random time before next cycle (45-120 minutes)
            next_delay = random.uniform(45 * 60, 120 * 60)  # Convert to seconds
            await asyncio.sleep(next_delay)
        
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        for task in self.dynamic_npc_tasks.values():
            task.cancel()

    async def create_static_npcs_for_location(self, location_id: int, population: int):
        """Create static NPCs for a location based on population"""
        
        # Get location info first
        location_info = self.db.execute_query(
            "SELECT location_type, wealth_level FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return 0
        
        location_type, wealth_level = location_info
        
        # Special handling for gates - they always have maintenance staff regardless of population
        if location_type == 'gate':
            npc_count = random.randint(2, 4)  # Gates always have 2-4 maintenance staff
        elif population == 0:
            return 0  # Other locations with 0 population get no NPCs
        elif population < 5:
            npc_count = 1
        elif population <= 20:
            npc_count = random.randint(1, 3)
        else:
            npc_count = random.randint(3, 5)
        
        # Get current galaxy year for age calculation
        galaxy_info = self.db.execute_query(
            "SELECT start_date FROM galaxy_info WHERE galaxy_id = 1",
            fetch='one'
        )
        
        current_year = 2751  # Default year
        if galaxy_info:
            start_date = galaxy_info[0]
            current_year = int(start_date.split('-')[0])
        
        npcs_created = 0
        for _ in range(npc_count):
            first_name, last_name = generate_npc_name()
            name = f"{first_name} {last_name}"
            age = random.randint(18, 80)
            occupation = get_occupation(location_type, wealth_level)
            personality = random.choice(PERSONALITIES)
            trade_specialty = random.choice(TRADE_SPECIALTIES) if random.random() < 0.3 else None
            
            self.db.execute_query(
                """INSERT INTO static_npcs 
                   (location_id, name, age, occupation, personality, trade_specialty)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (location_id, name, age, occupation, personality, trade_specialty)
            )
            npcs_created += 1
            
            if location_type == 'gate':
                print(f"🔧 Created gate maintenance NPC: {name} ({occupation}) at gate {location_id}")
        
        return npcs_created

    async def create_dynamic_npc(self) -> int:
        """Create a new dynamic NPC"""
        # Get a random location for spawning
        spawn_location = self.db.execute_query(
            "SELECT location_id FROM locations WHERE location_type != 'gate' ORDER BY RANDOM() LIMIT 1",
            fetch='one'
        )
        
        if not spawn_location:
            return 0
        
        location_id = spawn_location[0]
        
        first_name, last_name = generate_npc_name()
        name = f"{first_name} {last_name}"
        callsign = self._generate_unique_callsign()
        age = random.randint(18, 80)
        ship_name = generate_ship_name()
        ship_type = random.choice(SHIP_TYPES)
        credits = random.randint(5000, 50000)
        
        # Insert the NPC
        self.db.execute_query(
            """INSERT INTO dynamic_npcs 
               (name, callsign, age, ship_name, ship_type, current_location, credits)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, callsign, age, ship_name, ship_type, location_id, credits)
        )
        
        npc_id = self.db.execute_query("SELECT last_insert_rowid()", fetch='one')[0]
        
        print(f"🤖 Created dynamic NPC: {name} ({callsign}) aboard {ship_name} at location {location_id}")
        return npc_id

    def _generate_unique_callsign(self) -> str:
        """Generate a unique callsign for dynamic NPCs"""
        while True:
            letters = ''.join(random.choices(string.ascii_uppercase, k=4))
            numbers = ''.join(random.choices(string.digits, k=4))
            callsign = f"{letters}-{numbers}"
            
            # Check if callsign is unique among both players and NPCs
            existing = self.db.execute_query(
                "SELECT 1 FROM characters WHERE callsign = ? UNION SELECT 1 FROM dynamic_npcs WHERE callsign = ?",
                (callsign, callsign),
                fetch='one'
            )
            
            if not existing:
                return callsign

    async def spawn_initial_dynamic_npcs(self):
        """Spawn initial population of dynamic NPCs"""
        # Count major locations (excluding gates)
        major_location_count = self.db.execute_query(
            "SELECT COUNT(*) FROM locations WHERE location_type != 'gate'",
            fetch='one'
        )[0]
        
        # Target about (major_locations ÷ 5) NPCs
        target_count = max(5, major_location_count // 5)
        
        # Add some randomness (±30%)
        variation = int(target_count * 0.3)
        target_count = random.randint(target_count - variation, target_count + variation)
        
        print(f"🤖 Spawning {target_count} initial dynamic NPCs...")
        
        for _ in range(target_count):
            await self.create_dynamic_npc()
            await asyncio.sleep(0.1)  # Small delay to prevent overwhelming


    async def _send_npc_radio_message(self, npc_name: str, callsign: str, location_name: str, system_name: str, message: str):
        """Send radio message using exact same logic and format as player messages"""
        radio_cog = self.bot.get_cog('RadioCog')
        if not radio_cog:
            return

        # Get NPC's current location for signal calculation
        npc_location_data = self.db.execute_query(
            """SELECT l.x_coord, l.y_coord, l.system_name
               FROM dynamic_npcs n
               JOIN locations l ON n.current_location = l.location_id
               WHERE n.callsign = ?""",
            (callsign,),
            fetch='one'
        )

        if not npc_location_data:
            return

        npc_x, npc_y, npc_system = npc_location_data
        
        # Radio propagation is global, so we calculate all potential recipients once.
        # The _calculate_radio_propagation function expects a guild_id but does not use it in its query,
        # so we can safely pass the ID of the first guild the bot is in.
        if not self.bot.guilds:
            return # No guilds to send to

        recipients = await radio_cog._calculate_radio_propagation(
            npc_x, npc_y, npc_system, message, self.bot.guilds[0].id
        )

        if not recipients:
            return # No one is in range to receive the message

        # Iterate through each guild the bot is in and broadcast the message
        # to the relevant location channels where players are present.
        for guild in self.bot.guilds:
            await radio_cog._broadcast_to_location_channels(
                guild, npc_name, callsign, location_name, system_name, message, recipients
            )

    async def _start_npc_travel(self, npc_id: int, npc_name: str, current_location: int):
        """Start travel for a dynamic NPC"""
        # Get available corridors from current location
        corridors = self.db.execute_query(
            """SELECT corridor_id, destination_location, travel_time, c.name as corridor_name, 
                      dl.name as dest_name, dl.system_name as dest_system
               FROM corridors c
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.origin_location = ? AND c.is_active = 1""",
            (current_location,),
            fetch='all'
        )
        
        if not corridors:
            return
        
        # Select random destination
        corridor_id, dest_location, travel_time, corridor_name, dest_name, dest_system = random.choice(corridors)
        
        # Start travel
        start_time = datetime.now()
        self.db.execute_query(
            """UPDATE dynamic_npcs 
               SET destination_location = ?, travel_start_time = ?, travel_duration = ?
               WHERE npc_id = ?""",
            (dest_location, start_time.isoformat(), travel_time, npc_id)
        )
        
        # Announce departure if players are present
        await self._announce_npc_departure(current_location, npc_name, dest_name, travel_time)
        
        # Schedule arrival
        arrival_time = start_time + timedelta(seconds=travel_time)
        delay = (arrival_time - datetime.now()).total_seconds()
        
        if delay > 0:
            task = asyncio.create_task(self._handle_npc_arrival_delayed(npc_id, npc_name, dest_location, dest_name, delay))
            self.dynamic_npc_tasks[npc_id] = task

    async def _handle_npc_arrival_delayed(self, npc_id: int, npc_name: str, dest_location: int, dest_name: str, delay: float):
        """Handle NPC arrival after travel delay"""
        await asyncio.sleep(delay)
        
        # Check if NPC is still alive (might have died in corridor collapse)
        npc_status = self.db.execute_query(
            "SELECT is_alive FROM dynamic_npcs WHERE npc_id = ?",
            (npc_id,),
            fetch='one'
        )
        
        if not npc_status or not npc_status[0]:
            return  # NPC died during travel
        
        # Complete the travel
        self.db.execute_query(
            """UPDATE dynamic_npcs 
               SET current_location = ?, destination_location = NULL, 
                   travel_start_time = NULL, travel_duration = NULL
               WHERE npc_id = ?""",
            (dest_location, npc_id)
        )
        
        # Announce arrival if players are present
        await self._announce_npc_arrival(dest_location, npc_name)
        
        # Clean up task
        if npc_id in self.dynamic_npc_tasks:
            del self.dynamic_npc_tasks[npc_id]

    async def _announce_npc_departure(self, location_id: int, npc_name: str, destination: str, travel_time: int):
        """Announce NPC departure if players are present"""
        # Check if any players are at this location
        players_present = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
            (location_id,),
            fetch='all'
        )
        
        if not players_present:
            return
        
        # Get location channel
        channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not channel_id or not channel_id[0]:
            return
        
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id[0])
            if channel:
                travel_hours = travel_time // 3600
                travel_minutes = (travel_time % 3600) // 60
                
                if travel_hours > 0:
                    duration_text = f"{travel_hours}h {travel_minutes}m"
                else:
                    duration_text = f"{travel_minutes}m"
                
                embed = discord.Embed(
                    title="🚀 Departure",
                    description=f"**{npc_name}** is departing for **{destination}**",
                    color=0xff6600
                )
                embed.add_field(
                    name="⏱️ Estimated Travel Time",
                    value=duration_text,
                    inline=True
                )
                # Removed the "NPC Activity" field
                
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    async def _announce_npc_arrival(self, location_id: int, npc_name: str):
        """Announce NPC arrival if players are present"""
        # Check if any players are at this location
        players_present = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
            (location_id,),
            fetch='all'
        )
        
        if not players_present:
            return
        
        # Get location channel
        channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not channel_id or not channel_id[0]:
            return
        
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id[0])
            if channel:
                embed = discord.Embed(
                    title="🛬 Arrival",
                    description=f"**{npc_name}** has arrived at this location",
                    color=0x00ff00
                )
                embed.add_field(
                    name="💼 Status",
                    value="Available for trade and interaction",
                    inline=True
                )
                # Removed the "NPC Activity" field
                
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass


    async def _perform_npc_action(self, npc_id: int, name: str, ship_name: str, location_id: int, location_type: str, location_name: str):
        """Perform a location-specific action for an NPC"""
        # Check if players are present to send the message
        players_present = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
            (location_id,),
            fetch='all'
        )
        
        if not players_present:
            return
        
        # Get location channel
        channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not channel_id or not channel_id[0]:
            return
        
        # Get action message
        action_template = get_location_action(location_type)
        action_message = action_template.format(name=name.split()[0], ship=ship_name)
        
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id[0])
            if channel:
                embed = discord.Embed(
                    description=f"👤 {action_message}",
                    color=0x6c5ce7
                )
                
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
        
        # Update last action time
        self.db.execute_query(
            "UPDATE dynamic_npcs SET last_location_action = ? WHERE npc_id = ?",
            (datetime.now().isoformat(), npc_id)
        )


    async def handle_corridor_collapse(self, corridor_id: int):
        """Handle dynamic NPC deaths in corridor collapses"""
        # Find NPCs traveling through the collapsed corridor
        traveling_npcs = self.db.execute_query(
            """SELECT n.npc_id, n.name, n.callsign, c.origin_location, c.destination_location
               FROM dynamic_npcs n
               JOIN corridors c ON (
                   (n.current_location = c.origin_location AND n.destination_location = c.destination_location) OR
                   (n.current_location = c.destination_location AND n.destination_location = c.origin_location)
               )
               WHERE c.corridor_id = ? AND n.travel_start_time IS NOT NULL AND n.is_alive = 1""",
            (corridor_id,),
            fetch='all'
        )
        
        for npc_id, npc_name, callsign, origin_loc, dest_loc in traveling_npcs:
            # Kill the NPC
            self.db.execute_query(
                "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                (npc_id,)
            )
            
            # Cancel any pending arrival tasks
            if npc_id in self.dynamic_npc_tasks:
                self.dynamic_npc_tasks[npc_id].cancel()
                del self.dynamic_npc_tasks[npc_id]
            
            # Post obituary using GalacticNewsCog
            galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
            if galactic_news_cog:
                await galactic_news_cog.post_character_obituary(
                    npc_name, origin_loc, "corridor collapse"
                )
            
            print(f"💀 Dynamic NPC {npc_name} ({callsign}) died in corridor collapse")
        
        # Schedule replacement NPCs (with delay)
        if traveling_npcs:
            replacements_needed = len(traveling_npcs)
            asyncio.create_task(self._spawn_replacement_npcs(replacements_needed))

    async def _spawn_replacement_npcs(self, count: int):
        """Spawn replacement NPCs after a delay"""
        # Wait random time between 1-6 hours
        delay_hours = random.uniform(1.0, 6.0)
        await asyncio.sleep(delay_hours * 3600)
        
        for _ in range(count):
            await self.create_dynamic_npc()
            await asyncio.sleep(random.uniform(60, 300))  # 1-5 minute spacing

    def get_static_npcs_for_location(self, location_id: int) -> List[Tuple[str, int]]:
        """Get static NPCs for a location (for welcome embed)"""
        npcs = self.db.execute_query(
            "SELECT name, age FROM static_npcs WHERE location_id = ? ORDER BY name",
            (location_id,),
            fetch='all'
        )
        return npcs

async def setup(bot):
    await bot.add_cog(NPCCog(bot))