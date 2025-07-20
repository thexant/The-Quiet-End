import discord
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        # DON'T start tasks in __init__
        
    async def cog_load(self):
            """Start background tasks after cog is loaded"""
            print("🎲 Events cog loaded, scheduling background tasks...")
            
            # Wait a bit before starting tasks to ensure everything is ready
            await asyncio.sleep(2)
            
            try:
                # Start all the background tasks with error handling
                print("🎲 Starting cleanup tasks...")
                self.cleanup_tasks.start()
                
                print("🎲 Starting random events...")
                self.random_events.start()
                
                print("🎲 Starting job generation...")
                self.job_generation.start()
                
                print("🎲 Starting micro events...")
                self.micro_events.start()
                
                print("🎲 Starting enhanced random events...")
                self.enhanced_random_events.start()
                
                print("🎲 Scheduling corridor check...")
                self.bot.loop.create_task(self._start_corridor_management_loop())
                
                print("✅ All event tasks started successfully")
                
            except Exception as e:
                print(f"❌ Error starting event tasks: {e}")
                import traceback
                traceback.print_exc()
            print("📈 Starting economic fluctuation...")
            self.economic_fluctuation.start()
    def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        print("🎲 Stopping event background tasks...")
        try:
            self.cleanup_tasks.cancel()
            self.random_events.cancel()
            self.job_generation.cancel()
            self.micro_events.cancel()
            self.economic_fluctuation.cancel()
            self.enhanced_random_events.cancel()
        except:
            pass
    async def _start_corridor_management_loop(self):
        """Start variable interval corridor management"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed(): # Use is_closed() for better shutdown handling
            try:
                # Random interval between 3-9 hours
                delay_hours = random.uniform(3.0, 9.0)
                delay_seconds = delay_hours * 3600
                
                print(f"🕐 Next corridor check scheduled in {delay_hours:.1f} hours")
                
                # Wait for the delay
                await asyncio.sleep(delay_seconds)
                
                # Run corridor management
                await self.corridor_management()
                
            except asyncio.CancelledError:
                # This is expected on shutdown, so we can just break the loop
                break
            except Exception as e:
                print(f"❌ Error in corridor management loop: {e}")
                # Wait 1 hour before retrying if there's an error
                await asyncio.sleep(3600)

    def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        # Cancel all background tasks correctly
        self.corridor_management.cancel()
        self.cleanup_tasks.cancel()
        self.random_events.cancel()
        self.job_generation.cancel()
        self.micro_events.cancel()
        self.enhanced_random_events.cancel()
        self.shift_change_monitor.cancel()
    async def corridor_management(self):
        """Periodically shift corridors and manage gate movements - now called randomly"""
        try:
            print("🌀 Running corridor management...")
            
            # Get all active corridors with gate status
            corridors = self.db.execute_query(
                '''SELECT c.corridor_id, c.name, c.last_shift, 
                          CASE WHEN c.name LIKE '%Ungated%' THEN 0 ELSE 1 END as has_gate
                   FROM corridors c WHERE c.is_active = 1''',
                fetch='all'
            )
            
            shifts_occurred = 0
            collapses_occurred = 0
            
            for corridor_id, name, last_shift, has_gate in corridors:
                # Calculate time since last shift
                if last_shift:
                    last_shift_time = datetime.fromisoformat(last_shift)
                    hours_since_shift = (datetime.now() - last_shift_time).total_seconds() / 3600
                else:
                    hours_since_shift = random.uniform(12, 48)  # Random starting point
                
                # Base chances vary by gate status and add randomness
                if has_gate:
                    # Gated corridors (stable)
                    base_shift_chance = random.uniform(3, 8)  # 3-8% base chance
                    base_collapse_chance = random.uniform(0.2, 1.0)  # 0.2-1% base chance
                else:
                    # Ungated corridors (very unstable)
                    base_shift_chance = random.uniform(12, 20)  # 12-20% base chance
                    base_collapse_chance = random.uniform(2, 5)   # 2-5% base chance
                
                # Add time-based multiplier with randomness
                time_multiplier = min(hours_since_shift / 24, random.uniform(2.5, 4.0))
                shift_chance = base_shift_chance * time_multiplier
                collapse_chance = base_collapse_chance * time_multiplier
                
                # Add random events (very small chance of sudden instability)
                if random.random() < 0.02:  # 2% chance of random instability
                    shift_chance *= random.uniform(2, 4)
                    collapse_chance *= random.uniform(1.5, 3)
                    print(f"🌀 Random instability affects {name}!")
                
                roll = random.uniform(0, 100)
                
                if roll < collapse_chance:
                    # Corridor collapse!
                    await self._handle_corridor_collapse(corridor_id, name)
                    collapses_occurred += 1
                elif roll < collapse_chance + shift_chance:
                    # Corridor shift
                    await self._handle_corridor_shift(corridor_id, name)
                    shifts_occurred += 1
            
            # Random bonus events
            if random.random() < 0.1:  # 10% chance of additional random events
                await self._random_corridor_event()
            
            if shifts_occurred > 0 or collapses_occurred > 0:
                print(f"Corridor events: {shifts_occurred} shifts, {collapses_occurred} collapses")
            # After deactivating corridors, add this to handle NPC deaths
            if collapses_occurred > 0:
                npc_cog = self.bot.get_cog('NPCCog')
                if npc_cog:
                    # Handle NPC deaths for each collapsed corridor
                    collapsed_corridors = self.db.execute_query(
                        "SELECT corridor_id FROM corridors WHERE is_active = 0 AND last_shift = ?",
                        (current_time.isoformat(),),
                        fetch='all'
                    )
                    
                    for corridor_tuple in collapsed_corridors:
                        await npc_cog.handle_corridor_collapse(corridor_tuple[0])    
                # Notify admins if there were significant changes
                if collapses_occurred > 0:
                    await self._notify_admins_of_collapses(collapses_occurred)
        
        except Exception as e:
            print(f"Error in corridor management: {e}")
    @tasks.loop(hours=6)  # Economic changes every 6 hours
    async def economic_fluctuation(self):
        """Generate economic supply and demand changes"""
        try:
            # Get all locations with shops
            locations = self.db.execute_query(
                "SELECT location_id, name, wealth_level, location_type FROM locations WHERE has_shops = 1",
                fetch='all'
            )
            
            changes_made = 0
            news_events = []
            
            for location_id, location_name, wealth_level, location_type in locations:
                # 5% chance for economic change per location
                if random.random() < 0.01:
                    change_type = await self._generate_economic_change(location_id, location_name, wealth_level, location_type)
                    if change_type:
                        changes_made += 1
                        news_events.append((location_id, location_name, change_type))
            
            # Post economic news if changes occurred
            if changes_made > 0:
                await self._post_economic_news(news_events)
                print(f"📈 Generated {changes_made} economic changes")
                
        except Exception as e:
            print(f"Error in economic fluctuation: {e}")

    async def _generate_economic_change(self, location_id: int, location_name: str, wealth_level: int, location_type: str) -> dict:
        """Generate a specific economic change for a location"""
        from utils.item_config import ItemConfig
        
        # Clear expired economic statuses
        self.db.execute_query(
            "DELETE FROM location_economy WHERE location_id = ? AND expires_at <= datetime('now')",
            (location_id,)
        )
        
        # Check current economic events
        current_events = self.db.execute_query(
            "SELECT COUNT(*) FROM location_economy WHERE location_id = ? AND expires_at > datetime('now')",
            (location_id,),
            fetch='one'
        )[0]
        
        # Limit to 2 economic events per location
        if current_events >= 2:
            return None
        
        # Determine event type
        event_types = ['demand', 'surplus']
        weights = [0.7, 0.3]  # Demand more common than surplus
        event_type = random.choices(event_types, weights=weights)[0]
        
        # Determine scope (category vs specific item)
        is_category = random.random() < 0.6  # 60% chance for category-wide
        
        if is_category:
            # Category-wide event
            categories = list(ItemConfig.LOCATION_SPAWN_MODIFIERS.get(location_type, {}).keys())
            if not categories:
                categories = ["medical", "equipment", "consumable", "fuel", "trade"]
            
            target_category = random.choice(categories)
            target_item = None
            event_description = f"{target_category.replace('_', ' ').title()} items"
        else:
            # Specific item event
            all_items = list(ItemConfig.ITEM_DEFINITIONS.keys())
            target_item = random.choice(all_items)
            target_category = None
            event_description = target_item
        
        # Set modifiers based on event type
        if event_type == 'demand':
            price_modifier = random.uniform(1.1, 1.3)  # 10-30% price increase
            stock_modifier = random.uniform(0.2, 0.5)  # 20-50% stock reduction
            status = 'in_demand'
            event_title = f"High Demand for {event_description}"
        else:  # surplus
            price_modifier = random.uniform(0.7, 0.9)  # 10-30% price decrease
            stock_modifier = random.uniform(1.5, 2.5)  # 50-150% stock increase
            status = 'surplus'
            event_title = f"Market Surplus of {event_description}"
        
        # Duration: 12-48 hours
        duration_hours = random.randint(12, 48)
        expire_time = datetime.now() + timedelta(hours=duration_hours)
        
        # Insert economic event
        self.db.execute_query(
            '''INSERT INTO location_economy 
               (location_id, item_category, item_name, status, price_modifier, stock_modifier, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (location_id, target_category, target_item, status, price_modifier, stock_modifier, expire_time.isoformat())
        )
        
        # Clear existing shop items for this location to force regeneration
        if target_category:
            self.db.execute_query(
                "DELETE FROM shop_items WHERE location_id = ? AND item_type = ?",
                (location_id, target_category)
            )
        elif target_item:
            self.db.execute_query(
                "DELETE FROM shop_items WHERE location_id = ? AND item_name = ?",
                (location_id, target_item)
            )
        
        return {
            'type': event_type,
            'status': status,
            'item_description': event_description,
            'title': event_title,
            'duration': duration_hours,
            'location_id': location_id,
            'location_name': location_name
        }

    async def _post_economic_news(self, news_events: list):
        """Post economic news about market changes"""
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if not news_cog:
            return
        
        # Group events by type for news
        demand_events = [e for e in news_events if e[2]['type'] == 'demand']
        surplus_events = [e for e in news_events if e[2]['type'] == 'surplus']
        
        # Post demand news
        if demand_events:
            await self._post_demand_news(news_cog, demand_events)
        
        # Post surplus news  
        if surplus_events:
            await self._post_surplus_news(news_cog, surplus_events)

    async def _post_demand_news(self, news_cog, demand_events: list):
        """Post news about items in high demand"""
        if len(demand_events) == 1:
            event = demand_events[0][2]
            title = f"Market Alert: {event['title']}"
            description = f"Economic analysts report increased demand for {event['item_description']} at {demand_events[0][1]}. Traders are advised that selling these items to this location may yield higher profits than usual."
        else:
            locations = [e[1] for e in demand_events]
            title = "Multiple Market Opportunities Detected"
            description = f"High demand situations have been identified at {len(demand_events)} locations: {', '.join(locations[:3])}{' and others' if len(locations) > 3 else ''}. Various commodities are experiencing supply shortages."
        
        description += " Market conditions are expected to remain active for 12-48 hours."
        
        # Get all guilds with galactic updates
        guilds_with_updates = news_cog.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            await news_cog.queue_news(guild_id, 'economic', title, description, demand_events[0][0])

    async def _post_surplus_news(self, news_cog, surplus_events: list):
        """Post news about items in surplus"""
        if len(surplus_events) == 1:
            event = surplus_events[0][2]
            title = f"Market Alert: {event['title']}"
            description = f"Market analysts report oversupply of {event['item_description']} at {surplus_events[0][1]}. Reduced prices and increased availability expected, though profit margins for sellers may be lower."
        else:
            locations = [e[1] for e in surplus_events]
            title = "Market Surplus Conditions Reported"
            description = f"Surplus conditions identified at {len(surplus_events)} locations: {', '.join(locations[:3])}{'and others' if len(locations) > 3 else ''}. Various commodities are experiencing oversupply."
        
        description += " Buyers may find discounted prices during this period."
        
        # Get all guilds with galactic updates
        guilds_with_updates = news_cog.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            await news_cog.queue_news(guild_id, 'economic', title, description, surplus_events[0][0])

    @economic_fluctuation.before_loop
    async def before_economic_fluctuation(self):
        await self.bot.wait_until_ready()
    async def _random_corridor_event(self):
        """Generate a random corridor-wide event"""
        events = [
            "Solar flare activity increases corridor instability",
            "Gravitational anomaly detected in local space",
            "Quantum resonance cascade affects corridor networks",
            "Temporal disturbance shifts corridor alignments"
        ]
        
        event = random.choice(events)
        print(f"EVENT: {event}")
    async def _find_route_to_destination(self, origin_id: int, max_jumps: int = 3) -> List[Tuple[int, str, int]]:
        """Find all reachable destinations within max_jumps from origin with async yielding"""
        # Use breadth-first search to find routes
        visited = set()
        routes = []  # (destination_id, destination_name, jump_count)
        queue = [(origin_id, 0)]  # (location_id, jump_count)
        iterations = 0
        
        while queue:
            current_loc, jumps = queue.pop(0)
            iterations += 1
            
            if current_loc in visited or jumps >= max_jumps:
                continue
                
            visited.add(current_loc)
            
            # Yield control every 5 iterations during search
            if iterations % 5 == 0:
                await asyncio.sleep(0)
            
            # Get all connections from current location
            connections = self.db.execute_query(
                '''SELECT c.destination_location, l.name, l.location_type
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = ? AND c.is_active = 1''',
                (current_loc,),
                fetch='all'
            )
            
            for dest_id, dest_name, dest_type in connections:
                if dest_id not in visited:
                    if jumps + 1 > 0:  # Don't include origin
                        routes.append((dest_id, dest_name, jumps + 1))
                    
                    if jumps + 1 < max_jumps:
                        queue.append((dest_id, jumps + 1))
        
        return routes

    async def _validate_route_exists(self, origin_id: int, destination_id: int) -> bool:
        """Validate that a route exists from origin to destination with async yielding"""
        # Use breadth-first search to check connectivity
        visited = set()
        queue = [origin_id]
        iterations = 0
        
        while queue:
            current_loc = queue.pop(0)
            iterations += 1
            
            if current_loc == destination_id:
                return True
                
            if current_loc in visited:
                continue
                
            visited.add(current_loc)
            
            # Yield control every 10 iterations to prevent blocking
            if iterations % 10 == 0:
                await asyncio.sleep(0)
            
            # Get connections
            connections = self.db.execute_query(
                '''SELECT destination_location FROM corridors 
                   WHERE origin_location = ? AND is_active = 1''',
                (current_loc,),
                fetch='all'
            )
            
            for dest_id, in connections:
                if dest_id not in visited:
                    queue.append(dest_id)
            
            # Limit search depth to prevent infinite loops
            if len(visited) > 100:  # Reasonable limit for galaxy size
                break
        
        return False
    async def _get_route_description(self, origin_id: int, destination_id: int) -> str:
        """Get a description of the route from origin to destination with async yielding"""
        # Simple pathfinding to get route description
        visited = set()
        queue = [(origin_id, [])]  # (location_id, path)
        iterations = 0
        
        while queue:
            current_loc, path = queue.pop(0)
            iterations += 1
            
            if current_loc == destination_id:
                if len(path) <= 1:
                    return "Direct route"
                elif len(path) == 2:
                    return f"1 jump via {path[1]}"
                else:
                    return f"{len(path)-1} jumps via {path[1]} and others"
                    
            if current_loc in visited:
                continue
                
            visited.add(current_loc)
            
            # Yield control every 5 iterations
            if iterations % 5 == 0:
                await asyncio.sleep(0)
            
            # Get connections with names
            connections = self.db.execute_query(
                '''SELECT c.destination_location, l.name
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = ? AND c.is_active = 1''',
                (current_loc,),
                fetch='all'
            )
            
            for dest_id, dest_name in connections:
                if dest_id not in visited and len(path) < 4:  # Limit search depth
                    queue.append((dest_id, path + [dest_name]))
        
        return "Complex route"
    @tasks.loop(minutes=45)  # Check every 45 minutes for micro-events
    async def micro_events(self):
        """Very small random events that can happen at any time"""
        try:
            # Small chance of mini-events
            if random.random() < 0.15:  # 15% chance every 45 minutes
                
                # Job burst event
                if random.random() < 0.4:
                    locations = self.db.execute_query(
                        "SELECT location_id, wealth_level, location_type FROM locations WHERE has_jobs = 1",
                        fetch='all'
                    )
                    if locations:
                        lucky_location = random.choice(locations)
                        await self._generate_travel_job(lucky_location[0], lucky_location[1], lucky_location[2])
                        print("🎲 Micro-event: Emergency job posted!")
                
                # Corridor micro-shift
                elif random.random() < 0.3:
                    corridors = self.db.execute_query(
                        "SELECT corridor_id, name FROM corridors WHERE is_active = 1",
                        fetch='all'
                    )
                    if corridors:
                        corridor = random.choice(corridors)
                        # Just update the last_shift time for now
                        self.db.execute_query(
                            "UPDATE corridors SET last_shift = datetime('now') WHERE corridor_id = ?",
                            (corridor[0],)
                        )
                        print(f"🎲 Micro-event: Minor fluctuation in {corridor[1]}")
        
        except Exception as e:
            print(f"Error in micro events: {e}")
    @tasks.loop(hours=1)
    async def cleanup_tasks(self):
        """Regular cleanup of expired data"""
        try:
            # Cleanup expired jobs
            expired_jobs = self.db.execute_query(
                "DELETE FROM jobs WHERE expires_at < datetime('now')"
            )
            
            # Cleanup old travel sessions
            self.db.execute_query(
                "DELETE FROM travel_sessions WHERE status IN ('completed', 'failed_exit') AND start_time < datetime('now', '-1 day')"
            )
            
            # Cleanup shop items with 0 stock (non-unlimited)
            self.db.execute_query(
                "DELETE FROM shop_items WHERE stock = 0"
            )
            
            # Update character last_active for online users
            # This would need to be implemented based on actual activity tracking
            
        except Exception as e:
            print(f"Error in cleanup tasks: {e}")
    
    @tasks.loop(hours=2)  # Every 2 hours
    async def random_events(self):
        """Generate random events across the galaxy"""
        try:
            # Get all locations
            locations = self.db.execute_query(
                "SELECT location_id, name, location_type, wealth_level FROM locations",
                fetch='all'
            )
            
            events_generated = 0
            
            for location_id, name, location_type, wealth in locations:
                # Each location has a small chance of an event
                if random.random() < 0.1:  # 10% chance per location every 2 hours
                    await self._generate_location_event(location_id, name, location_type, wealth)
                    events_generated += 1
            
            if events_generated > 0:
                print(f"Generated {events_generated} random events")
        
        except Exception as e:
            print(f"Error in random events: {e}")

    def stop_all_tasks(self):
        """Stop all background tasks in EventsCog"""
        tasks_to_stop = [
            'cleanup_tasks',
            'random_events', 
            'job_generation',
            'micro_events',
            'economic_fluctuation',
            'enhanced_random_events',
            'shift_change_monitor'
        ]
        
        for task_name in tasks_to_stop:
            task = getattr(self, task_name, None)
            if task and hasattr(task, 'cancel'):
                task.cancel()
                print(f"❌ Cancelled {task_name}")
        
        # Also cancel any corridor management tasks
        if hasattr(self, '_corridor_management_task'):
            if self._corridor_management_task and not self._corridor_management_task.done():
                self._corridor_management_task.cancel()
                
    @tasks.loop(minutes=30)
    async def job_generation(self):
        """Generate new jobs at locations with increased frequency and quantity"""
        try:
            # Get locations that can have jobs
            locations = self.db.execute_query(
                "SELECT location_id, wealth_level, location_type FROM locations WHERE has_jobs = 1",
                fetch='all'
            )
            
            # ADD THIS CHECK RIGHT HERE:
            if not locations:
                print("⚠️ No locations available for job generation")
                return
            
            jobs_generated = 0
            
            for location_id, wealth, location_type in locations:
                # Check current job count
                current_jobs = self.db.execute_query(
                    "SELECT COUNT(*) FROM jobs WHERE location_id = ? AND is_taken = 0",
                    (location_id,),
                    fetch='one'
                )[0]
                
                # Increased job limits based on wealth and type
                if location_type == 'space_station':
                    max_jobs = max(6, wealth + 1)  # Increased from max(6, wealth)
                elif location_type == 'colony':
                    max_jobs = max(8, wealth + 3)  # Increased from max(4, wealth)
                elif location_type == 'outpost':
                    max_jobs = max(4, wealth // 2 + 2)  # Increased from max(2, wealth // 3 + 1)
                else:  # gates
                    max_jobs = 3  # Increased from 1-2

                # Generate multiple jobs if under limit
                jobs_to_generate = min(max_jobs - current_jobs, 8)  # Increased from 3
                
                if jobs_to_generate > 0 and random.random() < 0.85:  # 80% chance
                    for _ in range(jobs_to_generate):
                        if random.random() < 0.75:  # 70% chance for each job
                            await self._generate_location_job(location_id, wealth, location_type)
                            jobs_generated += 1
            
            # Random bonus job generation burst
            if random.random() < 0.3:  # 20% chance for bonus generation
                # CHANGE this line to ADD the check:
                if locations:  # ADD THIS CHECK
                    bonus_location = random.choice(locations)
                    await self._generate_location_job(bonus_location[0], bonus_location[1], bonus_location[2])
                    jobs_generated += 1
                    print(f"🎲 Bonus job generated!")
            
            if jobs_generated > 0:
                print(f"Generated {jobs_generated} new jobs")
        
        except Exception as e:
            print(f"Error in job generation: {e}")
            # ADD this line for better debugging:
            import traceback
            traceback.print_exc()

    @job_generation.before_loop
    async def before_job_generation(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()

    @commands.group(name="events", description="Event system management")
    async def events_group(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return

    
    @tasks.loop(hours=1)
    async def shift_change_monitor(self):
        """Monitors for in-game shift changes and sends announcements."""
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            current_time = time_system.calculate_current_ingame_time()

            if not current_time:
                return

            hour = current_time.hour
            
            # Check the last known shift from a simple file or database key
            # to prevent spamming announcements every hour within the same shift.
            last_shift_hour = -1
            try:
                with open("last_shift.txt", "r") as f:
                    last_shift_hour = int(f.read())
            except (FileNotFoundError, ValueError):
                pass # First run or invalid file

            current_shift_hour = -1
            shift_name = ""
            description = ""

            if 6 <= hour < 12 and last_shift_hour < 6:
                current_shift_hour = 6
                shift_name = "Morning Shift"
                description = "Sunrise over the colonies. Morning work shifts are beginning across human space. Expect an increase in local traffic and job availability."
            elif 12 <= hour < 18 and last_shift_hour < 12:
                current_shift_hour = 12
                shift_name = "Day Shift"
                description = "Mid-day operations are at peak efficiency. Corridors are experiencing maximum traffic. Prime time for trade and transport."
            elif 18 <= hour < 24 and last_shift_hour < 18:
                current_shift_hour = 18
                shift_name = "Evening Shift"
                description = "Systems are transitioning to night operations. Security patrols are increased and non-essential services are winding down."
            elif hour < 6 and (last_shift_hour >= 18 or last_shift_hour == -1):
                current_shift_hour = 0
                shift_name = "Night Shift"
                description = "A quiet descends on the galaxy. Most colonies are on standby. Low traffic offers opportunities for discreet travel."

            if shift_name and current_shift_hour != last_shift_hour:
                news_cog = self.bot.get_cog('GalacticNewsCog')
                if news_cog:
                    await news_cog.post_shift_change_news(shift_name, description)
                    with open("last_shift.txt", "w") as f:
                        f.write(str(current_shift_hour))
                        print(f"📰 Shift change announced: {shift_name}")

        except Exception as e:
            print(f"Error in shift change monitor: {e}")

    @shift_change_monitor.before_loop
    async def before_shift_change_monitor(self):
        await self.bot.wait_until_ready()
        
    @commands.group(name="events", description="Event system management")
    async def events_group(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return

    @events_group.command(name="trigger_corridor")
    async def trigger_corridor_check(self, ctx):
        """Manually trigger corridor management"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return
        
        await ctx.send("🌀 Triggering corridor management check...")
        await self.corridor_management()
        await ctx.send("✅ Corridor management completed.")

    @events_group.command(name="generate_jobs")
    async def trigger_job_generation(self, ctx, location_name: str = None):
        """Manually trigger job generation"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return
        
        if location_name:
            # Generate jobs for specific location
            location = self.db.execute_query(
                "SELECT location_id, wealth_level, location_type FROM locations WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{location_name}%",),
                fetch='one'
            )
            if not location:
                await ctx.send(f"Location '{location_name}' not found.")
                return
            
            await ctx.send(f"🎯 Generating jobs for {location_name}...")
            for _ in range(3):  # Generate 3 jobs
                await self._generate_location_job(location[0], location[1], location[2])
            await ctx.send(f"✅ Generated 3 jobs for {location_name}.")
        else:
            # Generate jobs for all locations
            await ctx.send("🔄 Triggering job generation for all locations...")
            await self.job_generation()
            await ctx.send("✅ Job generation completed.")

    @events_group.command(name="status")
    async def event_status(self, ctx):
        """Show event system status"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return
        
        # Get various statistics
        total_jobs = self.db.execute_query("SELECT COUNT(*) FROM jobs WHERE is_taken = 0", fetch='one')[0]
        total_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = 1", fetch='one')[0]
        gated_corridors = self.db.execute_query("SELECT COUNT(*) FROM corridors WHERE is_active = 1 AND name NOT LIKE '%Ungated%'", fetch='one')[0]
        ungated_corridors = total_corridors - gated_corridors
        
        recent_shifts = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE last_shift > datetime('now', '-24 hours')",
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="🎲 Event System Status",
            description="Current state of the event management system",
            color=0x4169E1
        )
        
        embed.add_field(name="💼 Available Jobs", value=str(total_jobs), inline=True)
        embed.add_field(name="🔒 Gated Corridors", value=str(gated_corridors), inline=True)
        embed.add_field(name="⚠️ Ungated Corridors", value=str(ungated_corridors), inline=True)
        embed.add_field(name="🌀 Recent Shifts (24h)", value=str(recent_shifts), inline=True)
        
        # Task status
        task_status = []
        if self.cleanup_tasks.is_running():
            task_status.append("✅ Cleanup Tasks")
        else:
            task_status.append("❌ Cleanup Tasks")
        
        if self.random_events.is_running():
            task_status.append("✅ Random Events")
        else:
            task_status.append("❌ Random Events")
        
        if self.job_generation.is_running():
            task_status.append("✅ Job Generation")
        else:
            task_status.append("❌ Job Generation")
        
        if self.micro_events.is_running():
            task_status.append("✅ Micro Events")
        else:
            task_status.append("❌ Micro Events")
        
        embed.add_field(name="🔧 Task Status", value="\n".join(task_status), inline=False)
        
        embed.add_field(
            name="⏰ Next Scheduled Events",
            value="• Corridor Check: Random (3-9 hours)\n• Job Generation: Every 2 hours\n• Random Events: Every 2 hours\n• Micro Events: Every 45 minutes",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @events_group.command(name="force_collapse")
    async def force_corridor_collapse(self, ctx, *, corridor_name: str):
        """Force a specific corridor to collapse (testing/emergency)"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return
        
        corridor = self.db.execute_query(
            "SELECT corridor_id, name FROM corridors WHERE LOWER(name) LIKE LOWER(?) AND is_active = 1",
            (f"%{corridor_name}%",),
            fetch='one'
        )
        
        if not corridor:
            await ctx.send(f"Active corridor '{corridor_name}' not found.")
            return
        
        corridor_id, full_name = corridor
        await ctx.send(f"💥 Forcing collapse of {full_name}...")
        await self._handle_corridor_collapse(corridor_id, full_name)
        await ctx.send(f"✅ {full_name} has been collapsed.")

    @events_group.command(name="emergency_jobs")
    async def emergency_job_burst(self, ctx, count: int = 5):
        """Generate emergency jobs across the galaxy"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permissions required.")
            return
        
        if count < 1 or count > 20:
            await ctx.send("Count must be between 1 and 20.")
            return
        
        locations = self.db.execute_query(
            "SELECT location_id, wealth_level, location_type FROM locations WHERE has_jobs = 1",
            fetch='all'
        )
        
        if not locations:
            await ctx.send("No locations available for job generation.")
            return
        
        await ctx.send(f"🚨 Generating {count} emergency jobs across the galaxy...")
        
        jobs_generated = 0
        for _ in range(count):
            location = random.choice(locations)
            try:
                await self._generate_travel_job(location[0], location[1], location[2])
                jobs_generated += 1
            except:
                # Fallback to stationary job
                await self._generate_stationary_job(location[0], location[1], location[2])
                jobs_generated += 1
        
        await ctx.send(f"✅ Generated {jobs_generated} emergency jobs!")
    async def _handle_corridor_collapse(self, corridor_id: int, corridor_name: str):
        """Handle a corridor collapse event"""
        # Get corridor info
        corridor_info = self.db.execute_query(
            '''SELECT c.origin_location, c.destination_location, ol.name, dl.name
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.corridor_id = ?''',
            (corridor_id,),
            fetch='one'
        )
        
        if not corridor_info:
            return
        
        origin_id, dest_id, origin_name, dest_name = corridor_info
        
        # Check if anyone is traveling through this corridor
        travelers = self.db.execute_query(
            '''SELECT ts.user_id, ts.temp_channel_id, c.name
               FROM travel_sessions ts
               JOIN characters c ON ts.user_id = c.user_id
               WHERE ts.corridor_id = ? AND ts.status = 'traveling' ''',
            (corridor_id,),
            fetch='all'
        )
        
        # Handle travelers caught in collapse
        for user_id, temp_channel_id, char_name in travelers:
            await self._handle_traveler_in_collapse(user_id, temp_channel_id, char_name, corridor_name)
        
        # Mark corridor as inactive
        self.db.execute_query(
            "UPDATE corridors SET is_active = 0 WHERE corridor_id = ?",
            (corridor_id,)
        )
        
        # Log the event
        print(f"🌀 CORRIDOR COLLAPSE: {corridor_name} ({origin_name} ↔ {dest_name})")
        
        # Notify players at affected locations
        await self._notify_location_of_corridor_loss(origin_id, corridor_name, dest_name)
        await self._notify_location_of_corridor_loss(dest_id, corridor_name, origin_name)

    
    async def _handle_corridor_shift(self, corridor_id: int, corridor_name: str):
        """Handle a corridor shift event"""
        # Update last shift time
        self.db.execute_query(
            "UPDATE corridors SET last_shift = datetime('now') WHERE corridor_id = ?",
            (corridor_id,)
        )
        
        # For now, just log it. In a full implementation, this would:
        # 1. Move the corridor endpoints
        # 2. Update gate positions
        # 3. Potentially create new route connections
        print(f"🔄 CORRIDOR SHIFT: {corridor_name}")
    async def _trigger_corridor_event(self, channel: discord.TextChannel, travelers: list, danger_level: int):
        """Trigger a random corridor event with potential death checking"""
        events = [
            ("Radiation Spike", "⚡ **Radiation Spike Detected!**\nCorridor radiation levels have increased. Monitor your exposure carefully.", 0xffaa00, 5, 15),
            ("Static Fog", "🌫️ **Static Fog Encountered!**\nElectromagnetic interference is affecting ship systems. Navigation may be impaired.", 0x808080, 0, 5),
            ("Vacuum Bloom", "🦠 **Vacuum Bloom Spores Detected!**\nOrganic contaminants in the corridor. Seal air filtration systems.", 0x8b4513, 3, 10),
            ("Corridor Turbulence", "💫 **Corridor Instability!**\nSpace-time fluctuations detected. Maintain course and speed.", 0x4b0082, 2, 8),
            ("System Malfunction", "⚠️ **Ship System Alert!**\nMinor system malfunction detected. Check ship status.", 0xff4444, 1, 5)
        ]
        
        # Higher danger levels get more severe events
        if danger_level >= 4:
            events.extend([
                ("Severe Radiation", "☢️ **SEVERE RADIATION WARNING!**\nDangerous radiation levels detected! Take immediate protective action!", 0xff0000, 15, 30),
                ("Corridor Collapse Warning", "💥 **CORRIDOR INSTABILITY CRITICAL!**\nMajor structural instability detected! Prepare for emergency procedures!", 0x8b0000, 10, 25)
            ])
        
        event_name, event_desc, color, min_damage, max_damage = random.choice(events)
        
        embed = discord.Embed(
            title=f"⚠️ Corridor Event: {event_name}",
            description=event_desc,
            color=color
        )
        
        embed.add_field(
            name="🛠️ Recommended Actions",
            value="• Check `/character ship` for system status\n• Use medical supplies if needed\n• Monitor travel progress\n• Coordinate with crew members",
            inline=False
        )
        
        # Apply effects to travelers with death checking
        char_cog = self.bot.get_cog('CharacterCog')
        affected_players = []
        
        for traveler_id in travelers:
            if random.random() < 0.4:  # 40% chance of effect
                damage = random.randint(min_damage, max_damage) if max_damage > 0 else 0
                
                if damage > 0 and char_cog:
                    # Apply HP damage and check for death
                    died = await char_cog.update_character_hp(
                        traveler_id, -damage, channel.guild, f"Corridor event: {event_name}"
                    )
                    
                    if died:
                        affected_players.append(f"💀 Player lost to {event_name}")
                    else:
                        affected_players.append(f"⚠️ Player took {damage} damage")
                
                # Apply ship damage for certain events
                if "System" in event_name or "Malfunction" in event_name:
                    ship_damage = random.randint(1, 8)
                    self.db.execute_query(
                        "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                        (ship_damage, traveler_id)
                    )
        
        if affected_players:
            embed.add_field(
                name="💥 Event Impact",
                value="\n".join(affected_players),
                inline=False
            )
        
        try:
            await channel.send(embed=embed)
        except:
            pass
            
    @tasks.loop(minutes=10)  # Run enhanced events every 10 minutes
    async def enhanced_random_events(self):
        """Generate enhanced random events including pirates and phenomena"""
        try:
            # Get all locations with active players INCLUDING population data
            active_locations = self.db.execute_query(
                '''SELECT c.current_location, COUNT(*) as player_count, 
                          l.location_type, l.wealth_level, l.population
                   FROM characters c 
                   JOIN locations l ON c.current_location = l.location_id
                   WHERE c.current_location IS NOT NULL
                     AND c.is_logged_in = 1
                   GROUP BY c.current_location''',
                fetch='all'
            )
            
            events_cog = self.bot.get_cog('EnhancedEventsCog')
            if not events_cog:
                print("❌ EnhancedEventsCog not found!")
                return
            
            for location_id, player_count, location_type, wealth, population in active_locations:
                # Small chance for enhanced events
                if random.random() < 0.30:  # 35% chance per 15mins per active location
                    
                    # Get players at this location
                    players = self.db.execute_query(
                        "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
                        (location_id,),
                        fetch='all'
                    )
                    
                    if players:
                        # Pass the correct population parameter (not player count!)
                        await events_cog.generate_location_event(
                            location_id, 
                            location_type, 
                            wealth, 
                            population  # THIS WAS THE BUG - was passing len(players) instead
                        )
                        print(f"🎲 Triggered enhanced event check at location {location_id}")
                        
        except Exception as e:
            print(f"❌ Error in enhanced_random_events: {e}")
            import traceback
            traceback.print_exc()
            
    async def _handle_traveler_in_collapse(self, user_id: int, temp_channel_id: int, char_name: str, corridor_name: str):
        """Handle a traveler caught in a corridor collapse with death checking"""
        user = self.bot.get_user(user_id)
        if not user:
            return
        
        # Roll for survival
        survival_roll = random.randint(1, 100)
        
        if survival_roll <= 60:  # 60% survival chance
            # Survived but damaged
            damage_roll = random.randint(1, 100)
            
            if damage_roll <= 50:  # Moderate damage
                hp_loss = random.randint(20, 40)
                hull_loss = random.randint(30, 60)
                fuel_loss = random.randint(20, 50)
                outcome = "survived with moderate damage"
            else:  # Severe damage
                hp_loss = random.randint(40, 70)
                hull_loss = random.randint(60, 90)
                fuel_loss = random.randint(50, 80)
                outcome = "survived with severe damage"
            
            # Apply damage and check for death
            char_cog = self.bot.get_cog('CharacterCog')
            guild = user.mutual_guilds[0] if user.mutual_guilds else None
            
            if guild and char_cog:
                died = await char_cog.update_character_hp(
                    user_id, -hp_loss, guild, f"Corridor collapse in {corridor_name}"
                )
                
                if died:
                    # Character died from the damage - death handling is automatic
                    return
            
            # If survived, apply other damage
            self.db.execute_query(
                '''UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?),
                   current_fuel = MAX(0, current_fuel - ?)
                   WHERE owner_id = ?''',
                (hull_loss, fuel_loss, user_id)
            )
            
            # Return to random nearby location (or origin)
            # For now, just clear current location (stranded)
            self.db.execute_query(
                "UPDATE characters SET current_location = NULL WHERE user_id = ?",
                (user_id,)
            )
            
            embed = discord.Embed(
                title="💥 CORRIDOR COLLAPSE",
                description=f"**{corridor_name}** has collapsed while you were in transit!",
                color=0xff0000
            )
            embed.add_field(name="Status", value=f"You {outcome}", inline=False)
            embed.add_field(name="Damage Sustained", value=f"Health: -{hp_loss}\nHull: -{hull_loss}\nFuel: -{fuel_loss}", inline=False)
            embed.add_field(name="Location", value="Stranded in deep space", inline=False)
            embed.add_field(name="🆘 Critical", value="You need immediate rescue or assistance!", inline=False)
            
        else:  # Didn't survive
            # Character dies from the collapse
            char_cog = self.bot.get_cog('CharacterCog')
            guild = user.mutual_guilds[0] if user.mutual_guilds else None
            
            if guild and char_cog:
                # Set HP to 0 to trigger automatic death
                await char_cog.update_character_hp(
                    user_id, -200, guild, f"Lost in corridor collapse: {corridor_name}"
                )
                return  # Death handled automatically
            
            # Fallback if char_cog not available
            embed = discord.Embed(
                title="💀 LOST IN THE VOID",
                description=f"**{corridor_name}** collapsed while you were in transit. You have been lost to the void...",
                color=0x000000
            )
            embed.add_field(name="Status", value="Lost to the void", inline=False)
            embed.add_field(name="⚰️ Final Rest", value="Your journey ends here. Create a new character to continue.", inline=False)
        
        # Update travel session
        self.db.execute_query(
            "UPDATE travel_sessions SET status = 'corridor_collapse' WHERE user_id = ? AND status = 'traveling'",
            (user_id,)
        )
        
        # Send message to user
        try:
            await user.send(embed=embed)
        except:
            pass  # Failed to DM user
        
        # Clean up temp channel
        if temp_channel_id:
            temp_channel = self.bot.get_channel(temp_channel_id)
            if temp_channel:
                try:
                    await temp_channel.send(embed=embed)
                    await asyncio.sleep(30)  # Give time to read
                    await temp_channel.delete(reason="Corridor collapsed")
                except:
                    pass
    
    async def _notify_location_of_corridor_loss(self, location_id: int, corridor_name: str, destination: str):
        """Notify players at a location that a corridor has been lost"""
        location_channel = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_channel or not location_channel[0]:
            return
        
        channel = self.bot.get_channel(location_channel[0])
        if not channel:
            return
        
        embed = discord.Embed(
            title="🌀 CORRIDOR COLLAPSE DETECTED",
            description=f"**{corridor_name}** to {destination} has collapsed and is no longer accessible.",
            color=0xff9900
        )
        embed.add_field(
            name="⚠️ Travel Advisory",
            value="Route is permanently lost. Alternative routes may be available.",
            inline=False
        )
        
        try:
            await channel.send(embed=embed)
        except:
            pass  # Failed to send to channel
    
    async def _notify_admins_of_collapses(self, collapse_count: int):
        """Notify administrators of corridor collapses"""
        # This would send DMs to admins or post in an admin channel
        # For now, just log it
        print(f"⚠️ {collapse_count} corridor collapses occurred - admins should be notified")
    
    async def _generate_location_event(self, location_id: int, name: str, location_type: str, wealth: int):
            """Generate a random event at a location using enhanced events system"""
            # Get players at location
            players_present = self.db.execute_query(
                "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
                (location_id,),
                fetch='all'
            )
            
            if not players_present:
                return
            
            player_ids = [p[0] for p in players_present]
            
            # Use enhanced events system
            enhanced_events_cog = self.bot.get_cog('EnhancedEventsCog')
            if enhanced_events_cog:
                await enhanced_events_cog.generate_location_event(location_id, location_type, wealth, len(players_present))
    
    async def _generate_location_job(self, location_id: int, wealth: int, location_type: str):
        """Generate a new job at a location with more variety, including desperation jobs."""
        
        job_generated = False

        # Check for Desperation Job possibility
        if wealth <= 3 and random.random() < 0.30: # 25% chance for a desperation job in poor locations
            desperation_jobs = [
                ("Smuggle 'Medical Supplies'", "Transport a discreet package of 'medical supplies' to a nearby system. No questions asked. High risk, high reward.", random.randint(300, 700), -15, 4),
                ("Silence a Witness", "A local contact needs a problem to 'disappear'. Handle it quietly.", random.randint(500, 800), -25, 5),
                ("Plant a 'Device'", "A local concealing his face has offered you a reward to plant a suspicious looking electronic device on government infrastructure, no questions asked.", random.randint(650, 1000), -30, 5),
                ("Staged Robbery", "Commit an armed robbery at a rival shopfront to drive customers away due to 'danger'.", random.randint(200, 400), -10, 5),
                ("Fuel Siphon", "Tap fuel lines from docked ships for a reward from a man with an 'offer'.", random.randint(150, 250), -5, 1),
                ("Cut Line", "Sabotage localized life support systems to drive out stubborn tenants.", random.randint(250, 300), -8, 2),
                ("Emergency Supply Theft", "Steal medical supplies from a charity clinic.", random.randint(300, 500), -10, 3),
                ("Broken Arm Deal", "Convince a stubborn contractor to accept new terms.", random.randint(200, 400), -5, 2),
                ("Water Ration Tamper", "Poison or tamper with a rival’s water supply to cause panic.", random.randint(250, 350), -10, 3),
                ("Space Terrorism", "Take a bomb to an occupied area. Plant it. Get paid.", random.randint(700, 1200), -40, 5)
            ]
            title, desc, reward, karma, danger = random.choice(desperation_jobs)
            
            duration = random.randint(5, 15)
            expire_time = datetime.now() + timedelta(hours=random.randint(2, 6))
            expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")

            self.db.execute_query(
                '''INSERT INTO jobs
                   (location_id, title, description, reward_money, danger_level, duration_minutes, expires_at, is_taken, job_status, karma_change)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'available', ?)''',
                (location_id, title, desc, reward, danger, duration, expire_str, karma)
            )
            print(f"🩸 Generated Desperation Job at location {location_id}: {title}")
            job_generated = True

        # Check for Good Deeds Job possibility
        elif wealth <= 7 and random.random() < 0.30:  # 30% chance for good deeds in wealthy locations
            good_deeds_jobs = [
                ("Volunteer Medical Aid", "Provide free medical assistance to refugees and displaced persons. Dangerous but morally rewarding work.", random.randint(50, 150), +20, 1),
                ("Rescue Stranded Civilians", "Search and rescue mission for civilians stranded in dangerous territory. Low pay, high risk, high honor.", random.randint(75, 200), +25, 3),
                ("Humanitarian Supply Drop", "Deliver essential supplies to disaster-stricken areas despite hostile conditions.", random.randint(100, 250), +15, 2),
                ("Evacuate Endangered Settlement", "Help evacuate civilians from areas under threat. Minimal compensation but saves lives.", random.randint(80, 180), +30, 3),
                ("Protect Relief Workers", "Escort and protect humanitarian workers in dangerous zones. Payment covers expenses only.", random.randint(60, 140), +20, 2),
                ("Orphanage Supply Run", "Deliver food and medical supplies to remote orphanages in pirate-controlled space.", random.randint(40, 120), +25, 2),
                ("Emergency Evacuation", "Shuttle wounded civvies off a station after an industrial accident.", random.randint(100, 200), +10, 1),
                ("Missing Person Search", "Track down lost workers who vanished on shift.", random.randint(75, 150), +5, 1)
            ]
            title, desc, reward, karma, danger = random.choice(good_deeds_jobs)
            
            duration = random.randint(6, 15)
            expire_time = datetime.now() + timedelta(hours=random.randint(3, 8))
            expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")

            self.db.execute_query(
                '''INSERT INTO jobs
                   (location_id, title, description, reward_money, danger_level, duration_minutes, expires_at, is_taken, job_status, karma_change)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'available', ?)''',
                (location_id, title, desc, reward, danger, duration, expire_str, karma)
            )
            print(f"😇 Generated Good Deeds Job at location {location_id}: {title}")
            job_generated = True
        
        # If no special job was generated, create a standard one
        if not job_generated:
            if random.random() < 0.8:
                travel_job_generated = await self._generate_travel_job(location_id, wealth, location_type)
                if not travel_job_generated:
                    await self._generate_stationary_job(location_id, wealth, location_type)
            else:
                await self._generate_stationary_job(location_id, wealth, location_type)
    async def _generate_travel_job(self, location_id: int, wealth: int, location_type: str) -> bool:
        """Generate a travel job with support for multi-jump destinations and async yielding"""
        
        # Get this location's info
        loc_info = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        if not loc_info:
            return False
        
        loc_name = loc_info[0]
        
        # Get both direct and multi-jump destinations
        direct_destinations = self.db.execute_query(
            """SELECT DISTINCT l.location_id, l.name, l.x_coord, l.y_coord, l.location_type, l.wealth_level,
                      c.travel_time, c.fuel_cost, c.danger_level
               FROM corridors c 
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1""",
            (location_id,),
            fetch='all'
        )
        
        # Yield control after database query
        await asyncio.sleep(0)
        
        # Get multi-jump destinations (up to 3 jumps away)
        multi_jump_routes = await self._find_route_to_destination(location_id, max_jumps=3)
        
        # Combine direct and multi-jump destinations
        all_destinations = []
        
        # Add direct destinations (preferred - 70% chance)
        if direct_destinations and random.random() < 0.7:
            for dest_info in direct_destinations:
                dest_id, dest_name, x1, y1, dest_type, dest_wealth, travel_time, fuel_cost, danger = dest_info
                all_destinations.append({
                    'dest_id': dest_id,
                    'dest_name': dest_name,
                    'dest_type': dest_type,
                    'dest_wealth': dest_wealth,
                    'travel_time': travel_time,
                    'fuel_cost': fuel_cost,
                    'danger': danger,
                    'jumps': 1,
                    'route_desc': "Direct route"
                })
        
        # Add multi-jump destinations (30% chance for variety)
        if multi_jump_routes and random.random() < 0.3:
            processed_routes = 0
            for dest_id, dest_name, jump_count in multi_jump_routes:
                processed_routes += 1
                
                # Yield control every 5 routes processed
                if processed_routes % 5 == 0:
                    await asyncio.sleep(0)
                
                # Validate route still exists
                if await self._validate_route_exists(location_id, dest_id):
                    dest_info = self.db.execute_query(
                        "SELECT location_type, wealth_level FROM locations WHERE location_id = ?",
                        (dest_id,),
                        fetch='one'
                    )
                    
                    if dest_info:
                        dest_type, dest_wealth = dest_info
                        route_desc = await self._get_route_description(location_id, dest_id)
                        
                        # Estimate travel time and cost for multi-jump
                        base_time = 300  # 5 minutes base
                        estimated_time = base_time * jump_count * random.uniform(1.2, 2.0)
                        estimated_fuel = 20 * jump_count * random.uniform(1.1, 1.5)
                        estimated_danger = min(5, jump_count + random.randint(0, 2))
                        
                        all_destinations.append({
                            'dest_id': dest_id,
                            'dest_name': dest_name,
                            'dest_type': dest_type,
                            'dest_wealth': dest_wealth,
                            'travel_time': int(estimated_time),
                            'fuel_cost': int(estimated_fuel),
                            'danger': estimated_danger,
                            'jumps': jump_count,
                            'route_desc': route_desc
                        })
        
        if not all_destinations:
            return False
        
        # Select random destination
        dest_info = random.choice(all_destinations)
        
        # Calculate rewards - multi-jump jobs pay significantly more
        base_reward = max(100, dest_info['travel_time'] // 60 * random.randint(15, 25))
        jump_bonus = (dest_info['jumps'] - 1) * 150  # Extra 150 credits per additional jump
        danger_bonus = dest_info['danger'] * 30
        wealth_bonus = (dest_info['dest_wealth'] + wealth) * 8
        final_reward = base_reward + jump_bonus + danger_bonus + wealth_bonus + random.randint(-30, 50)
        
        # Work time calculation
        travel_minutes = dest_info['travel_time'] // 60
        work_time = random.randint(5, 15) + int(travel_minutes * 0.5)
        
        # Total duration includes estimated round trip for multi-jump
        if dest_info['jumps'] > 1:
            total_duration = (travel_minutes * dest_info['jumps'] * 2) + work_time + random.randint(10, 30)
        else:
            total_duration = (travel_minutes * 2) + work_time + random.randint(5, 15)
        
        total_duration = max(15, total_duration)  # Minimum 15 minutes
        
        # Generate job title and description
        job_types = [
            ("Priority Cargo to {dest_name}", "Transport urgent cargo from {loc_name} to {dest_name}. {route_desc}."),
            ("Passenger Service to {dest_name}", "Safely transport passengers from {loc_name} to {dest_name}. {route_desc}."),
            ("Medical Supply Run to {dest_name}", "Deliver critical medical supplies to {dest_name}. {route_desc}."),
            ("Technical Parts to {dest_name}", "Transport specialized equipment to {dest_name}. {route_desc}."),
            ("Data Courier to {dest_name}", "Securely deliver encrypted data to {dest_name}. {route_desc}."),
            ("Emergency Relief to {dest_name}", "Rush emergency supplies to {dest_name}. {route_desc}."),
            ("Trade Goods to {dest_name}", "Transport valuable trade goods to {dest_name}. {route_desc}."),
            ("Scientific Samples to {dest_name}", "Carefully transport research materials to {dest_name}. {route_desc}."),
            ("Waste Containers to {dest_name}", "Haul sealed industrial waste to disposal facilities at {dest_name}. {route_desc}."),
            ("Emergency Generators to {dest_name}", "Deliver backup power units to {dest_name}. {route_desc}."),
            ("Construction Crews to {dest_name}", "Transport contracted workers and gear to build sites at {dest_name}. {route_desc}."),
            ("Frozen Bodies to {dest_name}", "Transport cryo-coffin pods to the creamtor services at {dest_name}. {route_desc}."),
            ("Atmospheric Filters to {dest_name}", "Haul clean air filtration units to domes at {dest_name}. {route_desc}."),
            ("Demolition Charges to {dest_name}", "Deliver controlled charges for mining or deconstruction at {dest_name}. {route_desc}."),
            ("Strange Fellow to {dest_name}", "A strange man asks you to bring him to {dest_name}. He refuses to answer any other questions. {route_desc}.")
        ]
        
        title_template, desc_template = random.choice(job_types)
        title = title_template.format(dest_name=dest_info['dest_name'])
        desc = desc_template.format(
            loc_name=loc_name, 
            dest_name=dest_info['dest_name'],
            route_desc=dest_info['route_desc']
        )
        
        # Add route complexity indicators
        if dest_info['jumps'] > 1:
            final_reward = int(final_reward * 1.3)  # 30% bonus for multi-jump
            title = f"MULTI-JUMP: {title}"
            desc += f" Route requires {dest_info['jumps']} jumps - high-value cargo!"
        
        if dest_info['danger'] >= 4:
            final_reward = int(final_reward * 1.4)
            title = f"HIGH RISK: {title}"
        
        expire_time = datetime.now() + timedelta(hours=random.randint(4, 12))
        expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")
        
        self.db.execute_query(
            '''INSERT INTO jobs
               (location_id, title, description, reward_money, required_skill, min_skill_level,
                danger_level, duration_minutes, expires_at, is_taken, job_status, destination_location_id)
               VALUES (?, ?, ?, ?, NULL, 0, ?, ?, ?, 0, 'available', ?)''', # ADD destination_location_id and its placeholder
            (location_id, title, desc, final_reward, dest_info['danger'], total_duration, expire_str, dest_info['dest_id']) # ADD dest_info['dest_id']
        )
        
        return True
    async def _generate_stationary_job(self, location_id: int, wealth: int, location_type: str):
        """Generate a stationary job at this location"""
        
        loc_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        # ADD THIS CHECK RIGHT HERE:
        if not loc_name:
            return
        
        # CHANGE this line from loc_name[0] to:
        loc_name = loc_name[0]
        
        # Location-specific stationary jobs
        job_pools = {
            'colony': [
                ("Systems Maintenance", f"Perform routine system checks at {loc_name}."),
                ("Inventory Audit", f"Audit and organize supplies at {loc_name}."),
                ("Security Patrol", f"Patrol the perimeter of {loc_name}."),
                ("Equipment Calibration", f"Calibrate industrial equipment at {loc_name}."),
                ("Quality Control", f"Inspect production quality at {loc_name}."),
                ("Environmental Check", f"Monitor life support systems at {loc_name}."),
                ("Data Processing", f"Process operational data for {loc_name}."),
                ("Communications Test", f"Test communication systems at {loc_name}."),
            ],
            'space_station': [
                ("Docking Operations", f"Coordinate ship docking at {loc_name}."),
                ("Traffic Control", f"Manage shipping traffic at {loc_name}."),
                ("Station Inspection", f"Inspect critical station systems at {loc_name}."),
                ("Inventory Processing", f"Process incoming inventory at {loc_name}."),
                ("Navigation Update", f"Update navigation databases at {loc_name}."),
                ("Security Sweep", f"Conduct security checks at {loc_name}."),
                ("Power Systems Check", f"Monitor power systems at {loc_name}."),
                ("Life Support Test", f"Test life support systems at {loc_name}."),
            ],
            'outpost': [
                ("Perimeter Check", f"Inspect outpost boundaries at {loc_name}."),
                ("Supply Count", f"Count and organize supplies at {loc_name}."),
                ("Equipment Repair", f"Repair basic equipment at {loc_name}."),
                ("Communications Relay", f"Maintain communication equipment at {loc_name}."),
                ("Weather Monitoring", f"Monitor environmental conditions at {loc_name}."),
                ("Basic Maintenance", f"Perform general maintenance at {loc_name}."),
            ],
            'gate': [
                ("Gate Diagnostics", f"Run diagnostic tests on gate systems at {loc_name}."),
                ("Radiation Monitoring", f"Monitor radiation levels at {loc_name}."),
                ("Stabilization Check", f"Check corridor stabilization at {loc_name}."),
                ("Safety Inspection", f"Inspect safety systems at {loc_name}."),
                ("Gate Calibration", f"Fine-tune gate parameters at {loc_name}."),
                ("Emergency Drill", f"Conduct emergency procedures at {loc_name}."),
            ]
        }
        
        job_list = job_pools.get(location_type, job_pools['colony'])
        title, desc = random.choice(job_list)
        
        # Stationary jobs pay less but are safer and quicker
        base_reward = random.randint(40, 100)
        wealth_modifier = 0.8 + (wealth * 0.04)
        reward = int(base_reward * wealth_modifier) + random.randint(-15, 25)
        
        duration = random.randint(3, 15)
        danger = random.randint(0, 2)  # Low danger for stationary work
        
        expire_time = datetime.now() + timedelta(hours=random.randint(4, 12))
        expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")
        
        self.db.execute_query(
            '''INSERT INTO jobs
               (location_id, title, description, reward_money, required_skill, min_skill_level,
                danger_level, duration_minutes, expires_at, is_taken, destination_location_id)
               VALUES (?, ?, ?, ?, NULL, 0, ?, ?, ?, 0, ?)''',
            (location_id, title, desc, reward, danger, duration, expire_str, None)
        )
        
async def setup(bot):
    await bot.add_cog(EventsCog(bot))
