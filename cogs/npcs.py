# cogs/npcs.py
import discord
from discord.ext import commands, tasks
import random
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
        self.endgame_active = False
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
        # NEW: Add enhanced background simulation tasks
        self.bot.loop.create_task(self._random_death_loop())
        self.bot.loop.create_task(self._background_job_simulation_loop())
        self.bot.loop.create_task(self._background_event_simulation_loop())

    async def _radio_message_loop(self):
        """Initialize individual NPC radio timers for truly random distribution"""
        await self._schedule_all_npc_timers()
        
        # Keep the loop running but just for error handling and periodic checks
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour for any issues
            except Exception as e:
                print(f"❌ Error in NPC radio message loop: {e}")
                await asyncio.sleep(60)

    async def _schedule_all_npc_timers(self):
        """Schedule individual timers for each NPC"""
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
                for npc_data in npcs:
                    npc_id = npc_data[0]
                    # Schedule this NPC with a random delay (2-12 hours to stagger startup)
                    initial_delay = random.uniform(7200, 43200)  # 2-12 hours
                    asyncio.create_task(self._individual_npc_timer(npc_data, initial_delay))
                    
                print(f"📡 Scheduled radio timers for {len(npcs)} NPCs with staggered starts")
                
        except Exception as e:
            print(f"❌ Error scheduling NPC timers: {e}")

    async def _individual_npc_timer(self, npc_data, initial_delay=0):
        """Individual timer for a single NPC's radio messages"""
        npc_id, name, callsign, ship_name, location_id, location_name, system_name, x_coord, y_coord, last_message = npc_data
        
        # Wait for initial staggered delay
        if initial_delay > 0:
            await asyncio.sleep(initial_delay)
        
        while True:
            try:
                # Check if NPC is still alive and has a location
                npc_check = self.db.execute_query(
                    """SELECT n.current_location, l.name as location_name, l.system_name
                       FROM dynamic_npcs n
                       LEFT JOIN locations l ON n.current_location = l.location_id
                       WHERE n.npc_id = ? AND n.is_alive = 1 AND n.current_location IS NOT NULL""",
                    (npc_id,),
                    fetch='one'
                )
                
                if not npc_check:
                    print(f"📡 NPC {name} ({callsign}) timer stopped - NPC deceased or relocated")
                    break
                
                # Update location data if it changed
                location_id, location_name, system_name = npc_check
                
                # Send radio message
                message_template = get_random_radio_message()
                message = message_template.format(
                    name=name.split()[0],  # First name only
                    callsign=callsign,
                    ship=ship_name,
                    location=location_name or "Unknown",
                    system=system_name or "Unknown"
                )

                await self._send_npc_radio_message(name, callsign, location_name or "Deep Space", system_name or "Unknown", message)

                # Update last radio message time
                self.db.execute_query(
                    "UPDATE dynamic_npcs SET last_radio_message = ? WHERE npc_id = ?",
                    (datetime.now().isoformat(), npc_id)
                )

                # Wait for next message (3-12 hours, truly random per NPC)
                next_delay = random.uniform(10800, 43200)  # 3-12 hours in seconds
                await asyncio.sleep(next_delay)
                
            except Exception as e:
                print(f"❌ Error in NPC {name} ({callsign}) radio timer: {e}")
                # Wait a bit before retrying to avoid spam
                await asyncio.sleep(300)  # 5 minutes

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
    def generate_npc_alignment(self, location_id: int) -> str:
        """Generate NPC alignment based on location reputation and special rules"""
        
        # Check if location has special alignment requirements
        location_data = self.db.execute_query(
            "SELECT has_black_market, wealth_level, location_type FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            return "neutral"
        
        has_black_market, wealth_level, location_type = location_data
        
        # Black market locations = only bandits
        if has_black_market:
            return "bandit"
        
        # High wealth federal locations = only loyalists
        if wealth_level >= 8:
            return "loyal"
        
        # Check average reputation at location to determine dominant faction
        avg_reputation = self.db.execute_query(
            """SELECT AVG(reputation) FROM character_reputation 
               WHERE location_id = ? AND ABS(reputation) > 10""",
            (location_id,),
            fetch='one'
        )
        
        if avg_reputation and avg_reputation[0]:
            avg_rep = avg_reputation[0]
            if avg_rep > 30:  # High positive rep = loyal area
                return "loyal"
            elif avg_rep < -30:  # High negative rep = bandit area
                return "bandit"
        
        # Default distribution: 15% loyal, 15% bandit, 70% neutral
        rand = random.random()
        if rand < 0.15:
            return "loyal"
        elif rand < 0.30:
            return "bandit"
        else:
            return "neutral"

    def generate_npc_alignment_from_data(self, location_type: str, wealth_level: int, has_black_market: bool = False) -> str:
        """
        Generate NPC alignment based on location data without database queries.
        Used during galaxy generation to avoid transaction conflicts.
        """
        # Black market locations = only bandits
        if has_black_market:
            return "bandit"
        
        # High wealth federal locations = only loyalists
        if wealth_level >= 8:
            return "loyal"
        
        # For new locations during galaxy generation, use wealth-based logic
        # since there's no reputation data yet
        if wealth_level <= 3:
            # Poor locations tend toward bandit
            return random.choices(["bandit", "neutral"], weights=[0.7, 0.3])[0]
        elif wealth_level >= 7:
            # Rich locations tend toward loyal
            return random.choices(["loyal", "neutral"], weights=[0.7, 0.3])[0]
        else:
            # Middle wealth locations are more mixed
            return random.choices(["loyal", "neutral", "bandit"], weights=[0.15, 0.70, 0.15])[0]
    def generate_npc_combat_stats(self, alignment: str) -> tuple:
        """Generate combat stats for an NPC based on alignment"""
        
        # Base stats ranges by alignment
        stat_ranges = {
            "loyal": (3, 8),      # Trained but not aggressive
            "neutral": (2, 6),    # Average civilians
            "bandit": (4, 9)      # More combat-focused
        }
        
        min_combat, max_combat = stat_ranges.get(alignment, (2, 6))
        combat_rating = random.randint(min_combat, max_combat)
        
        # HP based on combat rating
        base_hp = random.randint(60, 120)
        hp_bonus = combat_rating * 5
        max_hp = base_hp + hp_bonus
        
        # Credits based on alignment and combat skill
        credit_ranges = {
            "loyal": (100, 500),
            "neutral": (50, 300),
            "bandit": (20, 200)
        }
        
        min_credits, max_credits = credit_ranges.get(alignment, (50, 300))
        credits = random.randint(min_credits, max_credits) + (combat_rating * 10)
        
        return combat_rating, max_hp, credits
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
    async def _random_death_loop(self):
        """Background task for random NPC deaths to create dynamic universe feel"""
        while True:
            try:
                # Random time range between checks (1-4 hours)
                next_delay = random.uniform(60 * 60, 240 * 60)  # 1-4 hours in seconds
                await asyncio.sleep(next_delay)
                
                # 25% chance to proceed with death check
                if random.random() > 0.25:
                    continue
                    
                # Get all alive dynamic NPCs that are NOT in locations with players present
                npcs_not_with_players = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.callsign, n.current_location, l.name as location_name, l.system_name
                       FROM dynamic_npcs n
                       LEFT JOIN locations l ON n.current_location = l.location_id
                       WHERE n.is_alive = 1 
                       AND n.current_location NOT IN (
                           SELECT DISTINCT current_location 
                           FROM characters 
                           WHERE is_logged_in = 1 AND current_location IS NOT NULL
                       )""",
                    fetch='all'
                )
                
                if not npcs_not_with_players:
                    continue
                    
                # Select random NPC for potential death
                npc_data = random.choice(npcs_not_with_players)
                npc_id, npc_name, callsign, location_id, location_name, system_name = npc_data
                
                # Roll for death (10% chance)
                if random.random() < 0.10:
                    # Generate cause of death
                    cause_of_death = self._generate_cause_of_death()
                    
                    # Kill the NPC
                    self.db.execute_query(
                        "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                        (npc_id,)
                    )
                    
                    # Cancel any pending tasks for this NPC
                    if npc_id in self.dynamic_npc_tasks:
                        self.dynamic_npc_tasks[npc_id].cancel()
                        del self.dynamic_npc_tasks[npc_id]
                    
                    # Post obituary to galactic news
                    galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
                    if galactic_news_cog and location_id:
                        await galactic_news_cog.post_character_obituary(
                            npc_name, location_id, cause_of_death
                        )
                    
                    print(f"💀 Dynamic NPC {npc_name} ({callsign}) died from {cause_of_death}")
                    
                    # Schedule replacement NPC (1-6 hour delay)
                    asyncio.create_task(self._spawn_replacement_npcs(1))
                    
            except Exception as e:
                print(f"❌ Error in random death loop: {e}")
    def _generate_cause_of_death(self) -> str:
        """Generate a random but plausible cause of death for NPCs"""
        causes = [
            "system malfunction",
            "corridor instability",
            "reactor overload",
            "life support failure",
            "navigation error", 
            "power core breach",
            "hull breach",
            "unknown circumstances",
            "mechanical failure",
            "hypoxia incident",
            "radiation exposure",
            "debris impact",
            "equipment failure",
            "structural collapse",
            "communications blackout",
            "fuel system explosion",
            "gravity generator malfunction",
            "pressure seal failure",
            "electronic systems failure",
            "asteroid collision",
            "solar radiation storm",
            "magnetic field anomaly"
        ]
        return random.choice(causes)    

    async def _generate_jobs_for_npcs(self):
        """Generate jobs for static NPCs on a cycle"""
        try:
            # Clear old jobs first (keep only jobs from last 3 hours to prevent buildup)
            self.db.execute_query(
                "DELETE FROM npc_jobs WHERE created_at < datetime('now', '-3 hours')"
            )
            
            # Get all static NPCs with their locations and occupations
            static_npcs = self.db.execute_query(
                """SELECT npc_id, location_id, occupation
                   FROM static_npcs 
                   WHERE location_id IS NOT NULL""",
                fetch='all'
            )
            
            # Get the NPC interactions cog to use its job generation method
            npc_interactions_cog = self.bot.get_cog('NPCInteractionsCog')
            if not npc_interactions_cog:
                return
                
            for npc_data in static_npcs:
                npc_id, location_id, occupation = npc_data
                npc_type = 'static'  # Hardcoded since this is the static NPCs table
                
                # 30% chance for each NPC to generate jobs this cycle
                if random.random() < 0.30:
                    await npc_interactions_cog.generate_npc_jobs(npc_id, npc_type, location_id, occupation)
                    
                    # Small delay between job generations
                    await asyncio.sleep(random.uniform(1, 3))
                    
        except Exception as e:
            print(f"❌ Error generating NPC jobs: {e}")

    async def _background_job_simulation_loop(self):
        """Background simulation of NPCs taking and completing jobs, and generating new jobs"""
        while True:
            try:
                # Random interval between 45-90 minutes
                next_delay = random.uniform(45 * 60, 90 * 60)
                await asyncio.sleep(next_delay)
                
                # First, generate new jobs for static NPCs
                await self._generate_jobs_for_npcs()
                
                # Then simulate dynamic NPCs taking jobs
                # Get NPCs that could potentially take jobs (not traveling, alive)
                available_npcs = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.callsign, n.current_location, n.credits,
                              l.name as location_name, l.system_name, l.x_coord, l.y_coord
                       FROM dynamic_npcs n
                       JOIN locations l ON n.current_location = l.location_id
                       WHERE n.is_alive = 1 AND n.travel_start_time IS NULL""",
                    fetch='all'
                )
                
                for npc_data in available_npcs:
                    npc_id, name, callsign, location_id, credits, location_name, system_name, x_coord, y_coord = npc_data
                    
                    # 15% chance for each NPC to simulate taking a job
                    if random.random() < 0.15:
                        job_outcome = await self._simulate_npc_job(npc_id, name, callsign, location_id, location_name, system_name, x_coord, y_coord)
                        
                        # Small delay between job simulations
                        await asyncio.sleep(random.uniform(10, 30))
                        
            except Exception as e:
                print(f"❌ Error in background job simulation: {e}")
    async def _simulate_npc_job(self, npc_id: int, name: str, callsign: str, location_id: int, location_name: str, system_name: str, x_coord: int, y_coord: int):
        """Simulate an NPC taking and completing a job"""
        job_types = [
            ("cargo transport", "hauling goods to distant locations"),
            ("data courier", "delivering sensitive information"),
            ("maintenance work", "performing system repairs"),
            ("security patrol", "monitoring sector safety"),
            ("medical supply run", "transporting critical supplies"),
            ("scientific survey", "conducting research operations"),
            ("trade negotiation", "establishing business contacts"),
            ("passenger transport", "ferrying travelers safely")
        ]
        
        job_type, job_description = random.choice(job_types)
        
        # Determine outcome
        success_chance = random.randint(1, 100)
        
        if success_chance <= 70:  # 70% success rate
            # Successful job completion
            credits_earned = random.randint(500, 3000)
            self.db.execute_query(
                "UPDATE dynamic_npcs SET credits = credits + ? WHERE npc_id = ?",
                (credits_earned, npc_id)
            )
            
            # Send radio message about job completion
            radio_messages = [
                f"{callsign} to all stations, {job_type} contract completed successfully.",
                f"This is {name} reporting job completion. {job_description.capitalize()} finished without incident.",
                f"{callsign} confirming successful delivery. Contract fulfilled, returning to {location_name}.",
                f"Job well done! {name} here, {job_description} completed on schedule."
            ]
            
            message = random.choice(radio_messages)
            await self._send_npc_radio_message(name, callsign, location_name, system_name, message)
            
            print(f"💼 {name} ({callsign}) completed {job_type} job, earned {credits_earned} credits")
            
        elif success_chance <= 85:  # 15% chance of complications
            # Job complications but survived
            radio_messages = [
                f"{callsign} reporting job complications. Situation manageable but challenging.",
                f"This is {name}, encountered unexpected difficulties during {job_description}.",
                f"{callsign} to control, job proving more complex than anticipated.",
                f"Minor setbacks on current contract. {name} working to resolve issues."
            ]
            
            message = random.choice(radio_messages)
            await self._send_npc_radio_message(name, callsign, location_name, system_name, message)
            
            print(f"⚠️ {name} ({callsign}) encountered complications during {job_type}")
            
        else:  # 15% chance of failure/danger
            # Job failure with potential consequences
            if random.random() < 0.3:  # 30% of failures result in death
                cause_of_death = f"lost during {job_description}"
                
                # Kill the NPC
                self.db.execute_query(
                    "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                    (npc_id,)
                )
                
                # Post obituary
                galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
                if galactic_news_cog:
                    await galactic_news_cog.post_character_obituary(
                        name, location_id, cause_of_death
                    )
                
                print(f"💀 {name} ({callsign}) died during {job_type} - {cause_of_death}")
                
                # Schedule replacement
                asyncio.create_task(self._spawn_replacement_npcs(1))
                
            else:
                # Failed but survived with losses
                credits_lost = random.randint(200, 1000)
                self.db.execute_query(
                    "UPDATE dynamic_npcs SET credits = MAX(0, credits - ?) WHERE npc_id = ?",
                    (credits_lost, npc_id)
                )
                
                radio_messages = [
                    f"Mayday, mayday! {callsign} requesting assistance, job gone wrong!",
                    f"This is {name}, contract failed. Requesting immediate support.",
                    f"{callsign} reporting mission failure. Significant losses sustained.",
                    f"Emergency! {name} here, {job_description} went catastrophically wrong!"
                ]
                
                message = random.choice(radio_messages)
                await self._send_npc_radio_message(name, callsign, location_name, system_name, message)
                
                print(f"❌ {name} ({callsign}) failed {job_type}, lost {credits_lost} credits")
    async def _background_event_simulation_loop(self):
        """Background simulation of NPCs being caught in various events"""
        while True:
            try:
                # Random interval between 60-120 minutes
                next_delay = random.uniform(60 * 60, 120 * 60)
                await asyncio.sleep(next_delay)
                
                # Get all alive NPCs
                all_npcs = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.callsign, n.current_location,
                              l.name as location_name, l.system_name, l.x_coord, l.y_coord
                       FROM dynamic_npcs n
                       LEFT JOIN locations l ON n.current_location = l.location_id
                       WHERE n.is_alive = 1""",
                    fetch='all'
                )
                
                for npc_data in all_npcs:
                    npc_id, name, callsign, location_id, location_name, system_name, x_coord, y_coord = npc_data
                    
                    # 8% chance for each NPC to be involved in an event
                    if random.random() < 0.08:
                        await self._simulate_npc_event(npc_id, name, callsign, location_id, location_name, system_name, x_coord, y_coord)
                        
                        # Small delay between event simulations
                        await asyncio.sleep(random.uniform(5, 15))
                        
            except Exception as e:
                print(f"❌ Error in background event simulation: {e}")
    async def _simulate_npc_event(self, npc_id: int, name: str, callsign: str, location_id: int, location_name: str, system_name: str, x_coord: int, y_coord: int):
        """Simulate an NPC being caught in various events"""
        events = [
            {
                "name": "Equipment Malfunction",
                "radio_messages": [
                    f"{callsign} reporting equipment malfunction. Working on repairs.",
                    f"This is {name}, experiencing technical difficulties.",
                    f"{callsign} to any nearby vessels, requesting technical assistance."
                ],
                "death_chance": 0.05,
                "death_cause": "an equipment failure"
            },
            {
                "name": "Pirate Encounter",
                "radio_messages": [
                    f"Unknown vessels approaching! {callsign} requesting immediate assistance!",
                    f"This is {name}, possible hostile contact detected!",
                    f"{callsign} to all stations, suspicious activity in {system_name} system!"
                ],
                "death_chance": 0.15,
                "death_cause": "a pirate attack"
            },
            {
                "name": "Navigation Error",
                "radio_messages": [
                    f"{callsign} reporting navigation anomaly. Position uncertain.",
                    f"This is {name}, experiencing navigation difficulties in {system_name}.",
                    f"{callsign} requesting guidance, navigation systems malfunctioning."
                ],
                "death_chance": 0.08,
                "death_cause": "becoming lost in space"
            },
            {
                "name": "Medical Emergency",
                "radio_messages": [
                    f"Medical emergency aboard {callsign}! Requesting immediate assistance!",
                    f"This is {name}, declaring medical emergency. Need help!",
                    f"{callsign} to any medical vessels, urgent medical situation!"
                ],
                "death_chance": 0.12,
                "death_cause": "a medical emergency"
            },
            {
                "name": "Asteroid Field",
                "radio_messages": [
                    f"{callsign} navigating unexpected asteroid field. Proceed with caution.",
                    f"This is {name}, warning all traffic of debris field in {system_name}.",
                    f"{callsign} reporting dangerous space debris. Navigation hazardous."
                ],
                "death_chance": 0.10,
                "death_cause": "an asteroid impact"
            },
            {
                "name": "Spontaneous Explosion",
                "radio_messages": [
                    f"{callsign} reporting unknown hissing sound from ship engines.",
                    f"This is {name}, it's feeling really hot in here.",
                    f"{callsign} Here, seeing unknown objects approaching."
                ],
                "death_chance": 0.13,
                "death_cause": "a spontaneous explosion"
            },
            {
                "name": "Solar Storm",
                "radio_messages": [
                    f"{callsign} experiencing severe solar interference. Communications degraded.",
                    f"This is {name}, solar storm affecting all systems. Taking precautions.",
                    f"{callsign} warning all vessels, solar activity extremely dangerous!"
                ],
                "death_chance": 0.07,
                "death_cause": "solar radiation"
            }
        ]
        
        event = random.choice(events)
        
        # Send radio message about the event
        if location_name:
            message = random.choice(event["radio_messages"])
            await self._send_npc_radio_message(name, callsign, location_name, system_name, message)
        
        # Check for death outcome
        if random.random() < event["death_chance"]:
            # NPC dies from the event
            self.db.execute_query(
                "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                (npc_id,)
            )
            
            # Cancel any pending tasks
            if npc_id in self.dynamic_npc_tasks:
                self.dynamic_npc_tasks[npc_id].cancel()
                del self.dynamic_npc_tasks[npc_id]
            
            # Post obituary to galactic news
            galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
            if galactic_news_cog and location_id:
                await galactic_news_cog.post_character_obituary(
                    name, location_id, event["death_cause"]
                )
            
            print(f"💀 {name} ({callsign}) died from {event['name']} - {event['death_cause']}")
            
            # Schedule replacement
            asyncio.create_task(self._spawn_replacement_npcs(1))
            
        else:
            # Survived the event
            print(f"⚠️ {name} ({callsign}) survived {event['name']}")
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        for task in self.dynamic_npc_tasks.values():
            task.cancel()

    async def create_static_npcs_for_location(self, location_id: int, population: int, location_type: str = None, wealth_level: int = None) -> int:
        """Create static NPCs for a location with combat stats and alignment"""
        
        # Get location data if not provided
        if location_type is None or wealth_level is None:
            location_data = self.db.execute_query(
                "SELECT location_type, wealth_level FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )
            if location_data:
                location_type = location_type or location_data[0]
                wealth_level = wealth_level or location_data[1]
            else:
                # Fallback defaults
                location_type = location_type or 'colony'
                wealth_level = wealth_level or 5
        
        # Calculate number of NPCs (1-15 based on population)
        if location_type == 'gate':
            npc_count = random.randint(1, 3)  # Gates always have 2-4 maintenance staff
        if population < 50:
            npc_count = random.randint(1, 5)
        elif population < 200:
            npc_count = random.randint(2, 6)
        elif population < 1000:
            npc_count = random.randint(4, 10)
        elif population < 2000:
            npc_count = random.randint(6, 12)
        else:
            npc_count = random.randint(8, 15)
        
        created_count = 0
        
        for _ in range(npc_count):
            # Generate basic NPC data
            name_tuple = generate_npc_name()
            name = f"{name_tuple[0]} {name_tuple[1]}" if isinstance(name_tuple, tuple) else str(name_tuple)
            age = random.randint(25, 65)
            occupation = get_occupation(location_type, wealth_level)
            personality = random.choice(PERSONALITIES)
            trade_specialty = random.choice(TRADE_SPECIALTIES) if random.random() < 0.3 else None
            
            # Generate alignment based on location
            alignment = self.generate_npc_alignment(location_id)
            
            # Generate combat stats
            combat_rating, max_hp, credits = self.generate_npc_combat_stats(alignment)
            
            # Insert NPC with combat stats
            self.db.execute_query(
                """INSERT INTO static_npcs 
                   (location_id, name, age, occupation, personality, trade_specialty, 
                    alignment, hp, max_hp, combat_rating, credits)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (location_id, name, age, occupation, personality, trade_specialty,
                 alignment, max_hp, max_hp, combat_rating, credits)
            )
            
            created_count += 1
        
        return created_count
        
    def generate_static_npc_batch_data(self, location_id: int, population: int = None, 
                                      location_type: str = None, wealth_level: int = None, 
                                      has_black_market: bool = None, is_derelict: bool = False) -> List[tuple]:
        """Generate static NPC data for batch insertion without database calls"""
        
        # Skip NPC generation for derelict locations
        if is_derelict:
            return []
        
        # Calculate number of NPCs
        if location_type == 'gate':
            npc_count = random.randint(1, 3)
        elif population is None:
            npc_count = random.randint(3, 8)
        elif population < 50:
            npc_count = random.randint(1, 5)
        elif population < 200:
            npc_count = random.randint(2, 6)
        elif population < 1000:
            npc_count = random.randint(4, 10)
        elif population < 2000:
            npc_count = random.randint(6, 12)
        else:
            npc_count = random.randint(8, 15)
        
        npc_data_list = []
        
        for _ in range(npc_count):
            # Generate basic NPC data
            name_tuple = generate_npc_name()
            name = f"{name_tuple[0]} {name_tuple[1]}" if isinstance(name_tuple, tuple) else str(name_tuple)
            age = random.randint(25, 65)
            occupation = get_occupation(location_type or 'colony', wealth_level or 5)
            personality = random.choice(PERSONALITIES)
            
            # Use the transaction-safe alignment generation
            alignment = self.generate_npc_alignment_from_data(
                location_type or 'colony', 
                wealth_level or 5, 
                has_black_market or False
            )
            
            # Generate combat stats
            combat_rating, max_hp, credits = self.generate_npc_combat_stats(alignment)
            
            # Create tuple for batch insert (matching your INSERT statement)
            npc_data = (
                location_id, name, age, occupation, personality, 
                alignment, max_hp, max_hp, combat_rating, credits
            )
            npc_data_list.append(npc_data)
        
        return npc_data_list
        
    def generate_npc_alignment_from_data(self, location_type: str, wealth_level: int, has_black_market: bool = False) -> str:
        """
        Generate NPC alignment based on location data without database queries.
        Used during galaxy generation to avoid transaction conflicts.
        """
        # Black market locations = only bandits
        if has_black_market:
            return "bandit"
        
        # High wealth federal locations = only loyalists
        if wealth_level >= 8:
            return "loyal"
        
        # For new locations during galaxy generation, use wealth-based logic
        # since there's no reputation data yet
        if wealth_level <= 3:
            # Poor locations tend toward bandit
            return random.choices(["bandit", "neutral"], weights=[0.7, 0.3])[0]
        elif wealth_level >= 7:
            # Rich locations tend toward loyal
            return random.choices(["loyal", "neutral"], weights=[0.7, 0.3])[0]
        else:
            # Middle wealth locations are more mixed
            return random.choices(["loyal", "neutral", "bandit"], weights=[0.3, 0.4, 0.3])[0]
    async def spawn_dynamic_npc(self, start_location: int, destination_location: int = None, start_traveling: bool = True) -> Optional[int]:
        """Spawn a single dynamic NPC with combat stats"""
        
        # Validate start location exists
        location_exists = self.db.execute_query(
            "SELECT location_id FROM locations WHERE location_id = ?",
            (start_location,),
            fetch='one'
        )
        
        if not location_exists:
            print(f"⚠️ Cannot spawn dynamic NPC: location {start_location} does not exist")
            return None
        
        # Generate basic NPC data
        name_tuple = generate_npc_name()
        name = f"{name_tuple[0]} {name_tuple[1]}" if isinstance(name_tuple, tuple) else str(name_tuple)
        callsign = self._generate_unique_callsign()
        age = random.randint(25, 65)
        ship_name = generate_ship_name()
        ship_type = random.choice(SHIP_TYPES)
        
        # Generate alignment - dynamic NPCs follow same rules as static for start location
        alignment = self.generate_npc_alignment(start_location)
        
        # Generate combat stats
        combat_rating, max_hp, credits = self.generate_npc_combat_stats(alignment)
        
        # Ship hull based on ship type and combat rating
        ship_hull_ranges = {
            "Basic Hauler": (80, 150),
            "Fast Courier": (60, 120),
            "Heavy Freighter": (120, 200),
            "Combat Vessel": (100, 180),
            "Research Ship": (70, 130)
        }
        
        min_hull, max_hull = ship_hull_ranges.get(ship_type, (80, 150))
        max_ship_hull = random.randint(min_hull, max_hull) + (combat_rating * 10)
        
        # Choose destination if not provided and if starting traveling
        if start_traveling:
            if not destination_location:
                nearby_locations = self.db.execute_query(
                    """SELECT destination_location FROM corridors 
                       WHERE origin_location = ? AND is_active = 1""",
                    (start_location,),
                    fetch='all'
                )
                
                if nearby_locations:
                    destination_location = random.choice(nearby_locations)[0]
                else:
                    # If no valid destinations, don't start traveling
                    start_traveling = False
            
            # Calculate travel time if traveling
            if start_traveling:
                travel_duration = random.randint(300, 1800)  # 5-30 minutes
        
        try:
            if start_traveling and destination_location:
                # Insert dynamic NPC in traveling state
                self.db.execute_query(
                    """INSERT INTO dynamic_npcs 
                       (name, callsign, age, ship_name, ship_type, current_location, 
                        destination_location, travel_start_time, travel_duration, credits,
                        alignment, hp, max_hp, combat_rating, ship_hull, max_ship_hull)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, callsign, age, ship_name, ship_type, start_location,
                     destination_location, datetime.now().isoformat(), travel_duration, credits,
                     alignment, max_hp, max_hp, combat_rating, max_ship_hull, max_ship_hull)
                )
            else:
                # Insert dynamic NPC in stationary state
                self.db.execute_query(
                    """INSERT INTO dynamic_npcs 
                       (name, callsign, age, ship_name, ship_type, current_location, 
                        destination_location, travel_start_time, travel_duration, credits,
                        alignment, hp, max_hp, combat_rating, ship_hull, max_ship_hull)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, callsign, age, ship_name, ship_type, start_location,
                     None, None, None, credits,
                     alignment, max_hp, max_hp, combat_rating, max_ship_hull, max_ship_hull)
                )

            # Get the ID of the inserted NPC
            npc_id = self.db.execute_query(
                "SELECT npc_id FROM dynamic_npcs WHERE callsign = ? ORDER BY npc_id DESC LIMIT 1",
                (callsign,),
                fetch='one'
            )[0]
            
            # Start radio timer for the new NPC (only if stationary, traveling NPCs start when they arrive)
            if not start_traveling:
                # Get location details for the timer
                location_info = self.db.execute_query(
                    "SELECT name, system_name FROM locations WHERE location_id = ?",
                    (start_location,),
                    fetch='one'
                )
                location_name, system_name = location_info if location_info else ("Unknown", "Unknown")
                
                npc_data = (npc_id, name, callsign, ship_name, start_location, 
                           location_name, system_name, None, None, None)
                initial_delay = random.uniform(7200, 43200)  # 2-12 hours
                asyncio.create_task(self._individual_npc_timer(npc_data, initial_delay))
            
            if start_traveling and destination_location:
                # Schedule arrival
                arrival_time = datetime.now() + timedelta(seconds=travel_duration)
                delay = (arrival_time - datetime.now()).total_seconds()
                
                if delay > 0:
                    task = asyncio.create_task(self._handle_npc_arrival_delayed(npc_id, name, destination_location, self.db.execute_query("SELECT name FROM locations WHERE location_id = ?", (destination_location,), fetch='one')[0], delay))
                    self.dynamic_npc_tasks[npc_id] = task
            
            return npc_id  # Return the NPC ID on success
            
        except Exception as e:
            print(f"❌ Failed to create dynamic NPC: {e}")
            return None
    async def create_dynamic_npc(self, start_location: int = None, start_traveling: bool = None) -> Optional[int]:
        """Create a single dynamic NPC at a random or specified location"""
        
        if start_location is None:
            # Pick a random major location (not a gate) as starting point
            major_locations = self.db.execute_query(
                "SELECT location_id FROM locations WHERE location_type IN ('colony', 'space_station', 'outpost')",
                fetch='all'
            )
            
            if not major_locations:
                return None
            
            start_location = random.choice(major_locations)[0]
        
        # 60% chance to start stationary, 40% chance to start traveling
        if start_traveling is None:
            start_traveling = random.random() < 0.4
        
        return await self.spawn_dynamic_npc(start_location, start_traveling=start_traveling)
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
        
        if major_location_count == 0:
            print("⚠️ No major locations found, skipping initial dynamic NPC spawn")
            return
        
        # Target about (major_locations ÷ 3) NPCs
        target_count = max(5, major_location_count // 3)
        
        # Add some randomness (±30%)
        variation = int(target_count * 0.3)
        target_count = random.randint(target_count - variation, target_count + variation)
        
        print(f"🤖 Spawning {target_count} initial dynamic NPCs...")
        
        # Create mix of stationary and traveling NPCs
        stationary_count = int(target_count * 0.6)  # 60% stationary
        traveling_count = target_count - stationary_count  # 40% traveling
        
        # Spawn stationary NPCs first
        for _ in range(stationary_count):
            npc_id = await self.create_dynamic_npc(start_traveling=False)
            if npc_id:
                await asyncio.sleep(0.1)  # Small delay to prevent overwhelming
            else:
                break  # Stop if we can't create NPCs
        
        # Then spawn traveling NPCs
        for _ in range(traveling_count):
            npc_id = await self.create_dynamic_npc(start_traveling=True)
            if npc_id:
                await asyncio.sleep(0.1)  # Small delay to prevent overwhelming
            else:
                break  # Stop if we can't create NPCs


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
        
        # Start radio timer for the arrived NPC
        npc_details = self.db.execute_query(
            """SELECT n.npc_id, n.name, n.callsign, n.ship_name, n.current_location,
                      l.name as location_name, l.system_name, l.x_coord, l.y_coord,
                      n.last_radio_message
               FROM dynamic_npcs n
               LEFT JOIN locations l ON n.current_location = l.location_id
               WHERE n.npc_id = ?""",
            (npc_id,),
            fetch='one'
        )
        
        if npc_details:
            initial_delay = random.uniform(0, 3600)  # 0-60 minutes
            asyncio.create_task(self._individual_npc_timer(npc_details, initial_delay))
        
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
        """Perform a location-specific action for an NPC (works with or without players present)"""
        # Get action message
        action_template = get_location_action(location_type)
        action_message = action_template.format(name=name.split()[0], ship=ship_name)
        
        # Check if players are present to send the message
        players_present = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
            (location_id,),
            fetch='all'
        )
        
        # Only send Discord message if players are present
        if players_present:
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
                            description=f"👤 {action_message}",
                            color=0x6c5ce7
                        )
                        
                        try:
                            await channel.send(embed=embed)
                        except Exception:
                            pass
        
        # Always update last action time (whether players are present or not)
        self.db.execute_query(
            "UPDATE dynamic_npcs SET last_location_action = ? WHERE npc_id = ?",
            (datetime.now().isoformat(), npc_id)
        )
        
        # Log the action for background simulation tracking
        print(f"🎭 {name} performed action: {action_message}")


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
        if getattr(self, 'endgame_active', False):
            return None  # Don't spawn NPCs during endgame
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