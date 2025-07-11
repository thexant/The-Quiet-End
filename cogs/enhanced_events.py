# cogs/enhanced_events.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from datetime import datetime, timedelta
import json

class EnhancedEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.active_encounters = {}  # Track active pirate/hostile encounters

    # Add these methods to manage the overall event system in cogs/enhanced_events.py
    async def _schedule_location_events(self):
        """Schedule events for locations with active players"""
        
        # Get locations with active players
        active_locations = self.bot.db.execute_query(
            '''SELECT DISTINCT l.location_id, l.name, l.location_type, l.wealth_level, l.population, l.channel_id
               FROM locations l
               JOIN characters c ON c.current_location = l.location_id
               WHERE c.is_logged_in = 1''',
            fetch='all'
        )
        
        for location_data in active_locations:
            location_id, name, loc_type, wealth, population, channel_id = location_data
            
            # Check last event time to avoid spam
            last_event = self.bot.db.execute_query(
                '''SELECT MAX(posted_at) FROM location_logs 
                   WHERE location_id = ? AND is_generated = 1''',
                (location_id,),
                fetch='one'
            )
            
            if last_event and last_event[0]:
                from datetime import datetime, timedelta
                last_time = datetime.fromisoformat(last_event[0])
                if datetime.now() - last_time < timedelta(minutes=30):
                    continue  # Too recent
            
            # Random chance based on location activity and type
            base_chance = {
                'colony': 0.25,
                'space_station': 0.30,
                'outpost': 0.20,
                'gate': 0.15
            }.get(loc_type, 0.20)
            
            # Wealth affects event frequency
            wealth_modifier = 1.0 + (wealth - 5) * 0.1
            final_chance = base_chance * wealth_modifier
            
            if random.random() < final_chance:
                await self.generate_location_event(location_id, loc_type, wealth, population)

    async def _schedule_travel_events(self):
        """Schedule events for active travel sessions"""
        
        active_travels = self.bot.db.execute_query(
            '''SELECT session_id, user_id, origin_location, destination_location, 
                      corridor_id, temp_channel_id, start_time
               FROM travel_sessions 
               WHERE status = 'traveling' AND temp_channel_id IS NOT NULL''',
            fetch='all'
        )
        
        for travel_data in active_travels:
            session_id = travel_data[0]
            
            # Check if event already occurred for this session
            existing_event = self.bot.db.execute_query(
                "SELECT 1 FROM corridor_events WHERE transit_channel_id = ? AND is_active = 1",
                (travel_data[5],),  # temp_channel_id
                fetch='one'
            )
            
            if existing_event:
                continue  # Event already active
            
            # Get corridor danger level for event probability
            corridor_info = self.bot.db.execute_query(
                "SELECT danger_level FROM corridors WHERE corridor_id = ?",
                (travel_data[4],),  # corridor_id
                fetch='one'
            )
            
            if not corridor_info:
                continue
            
            danger_level = corridor_info[0]
            
            # Higher danger = more events
            event_chance = 0.1 + (danger_level * 0.05)
            
            if random.random() < event_chance:
                await self.generate_travel_event(travel_data)

    async def _schedule_galaxy_event(self):
        """Schedule rare galaxy-wide events"""
        
        galaxy_events = [
            {
                'name': 'Solar Flare Storm',
                'description': '🌟 **Galaxy-Wide Solar Storm**\nMassive stellar activity is affecting communications across human space.',
                'color': 0xff4500,
                'effects': {'communication_disruption': True, 'duration_hours': 2}
            },
            {
                'name': 'Major Trade Route Collapse',
                'description': '🏢 **Major Trade Route Collapse**\nA Major Trade Route has collapsed and destroyed a cargo convoy, affecting prices galaxy-wide.',
                'color': 0x4169e1,
                'effects': {'price_fluctuation': 0.2, 'duration_hours': 6}
            },
            {
                'name': 'Pirate Alliance',
                'description': '💀 **Pirate Clans Unite**\nMultiple pirate factions have formed an alliance, increasing raids across the galaxy.',
                'color': 0x8b0000,
                'effects': {'danger_increase': 1, 'duration_hours': 8}
            }
        ]
        
        event = random.choice(galaxy_events)
        
        # Broadcast to all location channels with active players
        active_channels = self.bot.db.execute_query(
            '''SELECT DISTINCT l.channel_id
               FROM locations l
               JOIN characters c ON c.current_location = l.location_id
               WHERE c.is_logged_in = 1''',
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🌌 Galaxy-Wide Event",
            description=event['description'],
            color=event['color']
        )
        
        for channel_id, in active_channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except:
                    pass  # Failed to send
        await self.apply_galaxy_wide_npc_effects(event['name'].lower().replace(' ', '_'), 2)
    async def generate_enhanced_random_event(self, location_id: int, players_present: list):
        """Generate enhanced random events including pirates and phenomena"""
        
        if not players_present:
            return
        
        location_info = self.bot.db.execute_query(
            "SELECT name, location_type, wealth_level, x_coord, y_coord FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return
        
        location_name, location_type, wealth, x_coord, y_coord = location_info
        
        # Different event pools based on location and situation
        space_phenomena = [
            ("Solar Flare", "🌟 **Solar Flare Detected!**\nMassive solar activity is interfering with ship systems and communications.", 0xff4500, self._handle_solar_flare),
            ("Quantum Storm", "⚡ **Static Fog Storm Approaching!**\nTechnological distortions detected. Navigation and sensor systems may be affected.", 0x9400d3, self._handle_quantum_storm),
            ("Asteroid Field", "☄️ **Asteroid Field Detected!**\nMultiple objects on collision course. Evasive maneuvers required.", 0x8b4513, self._handle_asteroid_field),
            ("Gravitational Anomaly", "🌀 **Gravitational Anomaly!**\nSpace-time distortion detected. Ships may experience temporal displacement.", 0x4b0082, self._handle_gravity_anomaly),
            ("Radiation Nebula", "☢️ **Radiation cloud Encountered!**\nHigh-energy particles detected. Hull integrity and crew health at risk.", 0xff0000, self._handle_radiation_nebula)
        ]
        
        # Pirate/hostile encounters (more likely in dangerous areas)
        hostile_encounters = [
            ("Pirate Raiders", "💀 **Pirate Raiders Detected!**\nHostile ships on intercept course. Prepare for combat or evasion.", 0x8b0000, self._handle_pirate_encounter),
            ("Scavenger Drones", "🤖 **Automated Scavengers!**\nRogue mining drones attempting to strip-mine your ship. Defensive measures required.", 0x708090, self._handle_scavenger_encounter),
            ("Corporate Security", "🚔 **Corporate Security Patrol!**\nMega-corp enforcement demanding inspection. Compliance or resistance?", 0x000080, self._handle_security_encounter),
            ("Desperate Refugees", "😰 **Desperate Refugees!**\nRefugee ship requesting aid. They claim pirates destroyed their home.", 0x8fbc8f, self._handle_refugee_encounter)
        ]
        
        # Calculate event chances based on location characteristics
        phenomena_chance = 0.3  # 30% base chance
        hostile_chance = 0.1    # 10% base chance
        
        # Increase hostile chances in dangerous areas
        edge_distance = (x_coord**2 + y_coord**2)**0.5
        if edge_distance > 70:  # Far from center
            hostile_chance += 0.15
        if wealth <= 3:  # Poor areas
            hostile_chance += 0.1
        
        # Determine event type
        event_roll = random.random()
        
        if event_roll < hostile_chance:
            event_name, description, color, handler = random.choice(hostile_encounters)
            await handler(location_id, players_present, location_name, event_name, description, color)
        elif event_roll < hostile_chance + phenomena_chance:
            event_name, description, color, handler = random.choice(space_phenomena)
            await handler(location_id, players_present, location_name, event_name, description, color)

    async def _handle_pirate_encounter(self, location_id, players, location_name, event_name, description, color):
        """Handle pirate encounter - potential combat or negotiation"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        # Create encounter
        encounter_id = f"pirate_{location_id}_{int(datetime.now().timestamp())}"
        
        embed = discord.Embed(
            title=f"💀 {event_name}",
            description=f"{description}\n\n**Location:** {location_name}",
            color=color
        )
        
        # Determine pirate strength based on players present
        pirate_ships = min(3, max(1, len(players) // 2 + random.randint(0, 1)))
        
        embed.add_field(
            name="🚀 Hostile Forces",
            value=f"{pirate_ships} pirate ship{'s' if pirate_ships > 1 else ''} detected",
            inline=True
        )
        
        embed.add_field(
            name="⚔️ Options",
            value="• Engage in combat\n• Attempt to flee\n• Try to negotiate\n• Pay tribute",
            inline=True
        )
        
        view = PirateEncounterView(self.bot, encounter_id, players, pirate_ships)
        await channel.send(embed=embed, view=view)

    # Add these methods to the EnhancedEventsCog class in cogs/enhanced_events.py
    async def generate_location_event(self, location_id: int, location_type: str, wealth: int, population: int):
        """Generate enhanced location-specific events"""
        
        # Get players at location
        players_present = self.bot.db.execute_query(
            "SELECT user_id FROM characters WHERE current_location = ? AND is_logged_in = 1",
            (location_id,),
            fetch='all'
        )
        
        if not players_present:
            return None
        
        # Get location info
        location_info = self.bot.db.execute_query(
            "SELECT name, channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return None
        
        location_name, channel_id = location_info
        channel = self.bot.get_channel(channel_id)
        
        if not channel:
            return None
        
        # Select event based on location type and wealth
        event_pools = {
            'colony': self._get_colony_events(wealth, population),
            'space_station': self._get_station_events(wealth, population),
            'outpost': self._get_outpost_events(wealth, population),
            'gate': self._get_gate_events(wealth, population)
        }
        
        events = event_pools.get(location_type, [])
        if not events:
            return None
        
        # Weight events by severity and wealth
        weights = []
        for event in events:
            base_weight = event.get('base_probability', 1.0)
            
            # Wealthy locations less likely to have negative events
            if wealth >= 7 and event.get('event_type') == 'negative':
                base_weight *= 0.6
            elif wealth <= 3 and event.get('event_type') == 'negative':
                base_weight *= 1.4
            
            weights.append(base_weight)
        
        import random
        selected_event = random.choices(events, weights=weights)[0]
        
        # Trigger the event
        await self._execute_location_event(channel, selected_event, players_present, location_name)
        
        # Store event in database
        self._store_event_log(location_id, selected_event['name'], selected_event.get('description', ''))
        
        return selected_event
    async def apply_galaxy_wide_npc_effects(self, event_type: str, severity: int = 1):
        """Apply galaxy-wide events to all dynamic NPCs"""
        
        all_npcs = self.db.execute_query(
            "SELECT npc_id, name, callsign, current_location FROM dynamic_npcs WHERE is_alive = 1",
            fetch='all'
        )
        
        affected_count = 0
        casualties = 0
        
        for npc_id, name, callsign, location_id in all_npcs:
            if random.random() < 0.3:  # 30% chance to be affected
                
                if event_type == "solar_flare":
                    # Communication disruption, possible ship damage
                    if random.random() < 0.1:  # 10% chance of severe damage
                        self.db.execute_query(
                            "UPDATE dynamic_npcs SET credits = GREATEST(0, credits - ?) WHERE npc_id = ?",
                            (random.randint(500, 2000), npc_id)
                        )
                    affected_count += 1
                
                elif event_type == "corridor_collapse_wave":
                    # Widespread corridor instability
                    if location_id and random.random() < 0.05:  # 5% chance of being lost
                        self.db.execute_query(
                            "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                            (npc_id,)
                        )
                        casualties += 1
                        
                        # Post obituary
                        galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
                        if galactic_news_cog:
                            await galactic_news_cog.post_character_obituary(
                                name, location_id, "lost in corridor instability"
                            )
                    affected_count += 1
                
                elif event_type == "pirate_alliance":
                    # Increased pirate activity affects all NPCs
                    if random.random() < 0.2:  # 20% chance of being robbed
                        credits_lost = random.randint(1000, 5000)
                        self.db.execute_query(
                            "UPDATE dynamic_npcs SET credits = GREATEST(0, credits - ?) WHERE npc_id = ?",
                            (credits_lost, npc_id)
                        )
                    affected_count += 1
        
        print(f"🌌 Galaxy event '{event_type}' affected {affected_count} NPCs, {casualties} casualties")
        
        # Spawn replacement NPCs if many were lost
        if casualties > 3:
            npc_cog = self.bot.get_cog('NPCCog')
            if npc_cog:
                asyncio.create_task(npc_cog._spawn_replacement_npcs(casualties))    
    async def affect_dynamic_npcs_by_events(self, location_id: int, event_type: str, severity: int):
        """Apply event effects to dynamic NPCs at a location"""
        
        # Get dynamic NPCs at this location
        dynamic_npcs = self.db.execute_query(
            '''SELECT npc_id, name, callsign, ship_name FROM dynamic_npcs
               WHERE current_location = ? AND is_alive = 1 AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not dynamic_npcs:
            return
        
        affected_npcs = []
        
        for npc_id, name, callsign, ship_name in dynamic_npcs:
            # Each NPC has a chance to be affected
            if random.random() < 0.4:  # 40% chance
                
                if event_type == "radiation":
                    # NPCs might take damage or flee
                    if severity >= 3:
                        # High severity - NPC might die or flee
                        if random.random() < 0.15:  # 15% death chance
                            self.db.execute_query(
                                "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
                                (npc_id,)
                            )
                            affected_npcs.append(f"💀 {name} ({callsign}) was lost to radiation exposure")
                        elif random.random() < 0.3:  # 30% flee chance
                            await self._force_npc_departure(npc_id, location_id, "radiation emergency")
                            affected_npcs.append(f"🚀 {name} ({callsign}) made emergency departure")
                    else:
                        affected_npcs.append(f"⚠️ {name} ({callsign}) suffered radiation exposure")
                
                elif event_type == "industrial_accident":
                    # NPCs might help or get injured
                    if random.random() < 0.6:  # 60% help chance
                        affected_npcs.append(f"🛠️ {name} ({callsign}) assisted with emergency response")
                    else:
                        affected_npcs.append(f"🏥 {name} ({callsign}) was injured in the accident")
                
                elif event_type == "pirate_attack":
                    # NPCs might fight, flee, or get captured
                    if random.random() < 0.4:  # 40% fight chance
                        affected_npcs.append(f"⚔️ {name} ({callsign}) joined the defense")
                    elif random.random() < 0.3:  # 30% flee chance
                        await self._force_npc_departure(npc_id, location_id, "pirate threat")
                        affected_npcs.append(f"🚀 {name} ({callsign}) evacuated immediately")
                    else:  # 30% capture/damage chance
                        if random.random() < 0.5:
                            self.db.execute_query(
                                "UPDATE dynamic_npcs SET credits = GREATEST(0, credits - ?) WHERE npc_id = ?",
                                (random.randint(1000, 5000), npc_id)
                            )
                            affected_npcs.append(f"💸 {name} ({callsign}) lost credits to pirates")
        
        return affected_npcs

    async def _force_npc_departure(self, npc_id: int, current_location: int, reason: str):
        """Force an NPC to leave a location due to an emergency"""
        
        # Get available corridors
        corridors = self.db.execute_query(
            '''SELECT corridor_id, destination_location, travel_time FROM corridors
               WHERE origin_location = ? AND is_active = 1''',
            (current_location,),
            fetch='all'
        )
        
        if corridors:
            # Choose random destination
            corridor_id, dest_location, travel_time = random.choice(corridors)
            
            # Start NPC travel
            start_time = datetime.now()
            self.db.execute_query(
                '''UPDATE dynamic_npcs 
                   SET destination_location = ?, travel_start_time = ?, travel_duration = ?
                   WHERE npc_id = ?''',
                (dest_location, start_time.isoformat(), travel_time, npc_id)
            )
            
            # Schedule arrival
            npc_cog = self.bot.get_cog('NPCCog')
            if npc_cog:
                arrival_time = start_time + timedelta(seconds=travel_time)
                delay = (arrival_time - datetime.now()).total_seconds()
                
                if delay > 0:
                    npc_name = self.db.execute_query(
                        "SELECT name FROM dynamic_npcs WHERE npc_id = ?",
                        (npc_id,),
                        fetch='one'
                    )[0]
                    
                    dest_name = self.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = ?",
                        (dest_location,),
                        fetch='one'
                    )[0]
                    
                    task = asyncio.create_task(
                        npc_cog._handle_npc_arrival_delayed(npc_id, npc_name, dest_location, dest_name, delay)
                    )
                    npc_cog.dynamic_npc_tasks[npc_id] = task
    def _get_colony_events(self, wealth: int, population: int):
        """Colony-specific events"""
        return [
            {
                'name': 'Industrial Accident',
                'description': '🏭 **Industrial Accident at Processing Plant**\nA malfunction in the primary processing facility has caused delays and potential injuries.',
                'color': 0xff4444,
                'event_type': 'negative',
                'base_probability': 0.15,
                'interactive': True,
                'handler': self._handle_industrial_accident,
                'effects': {'medical_demand': 2, 'repair_demand': 1}
            },
            {
                'name': 'Resource Strike',
                'description': '💎 **Major Resource Discovery!**\nColony miners have discovered a rich vein of valuable minerals. Local prosperity increases.',
                'color': 0x00ff00,
                'event_type': 'positive',
                'base_probability': 0.08,
                'interactive': False,
                'effects': {'wealth_bonus': 1, 'job_bonus': 2}
            },
            {
                'name': 'Worker Strike',
                'description': '✊ **Labor Dispute Escalates**\nColony workers are demanding better conditions. Production has slowed significantly.',
                'color': 0xff9900,
                'event_type': 'negative',
                'base_probability': 0.12 if wealth <= 4 else 0.06,
                'interactive': True,
                'handler': self._handle_worker_strike,
                'effects': {'job_reduction': 3, 'price_increase': 0.2}
            },
            {
                'name': 'Corporate Inspection',
                'description': '🏢 **Corporate Security Audit**\nMega-corp inspectors have arrived for a surprise audit. All operations are under scrutiny.',
                'color': 0x4169e1,
                'event_type': 'neutral',
                'base_probability': 0.10,
                'interactive': True,
                'handler': self._handle_corporate_inspection,
                'effects': {'security_level': 2}
            },
            {
                'name': 'Equipment Malfunction',
                'description': '⚙️ **Critical Equipment Failure**\nPrimary life support systems are showing signs of failure. Technical expertise needed.',
                'color': 0xff0000,
                'event_type': 'negative',
                'base_probability': 0.18 if wealth <= 5 else 0.10,
                'interactive': True,
                'handler': self._handle_equipment_malfunction,
                'effects': {'repair_demand': 3, 'danger_level': 1}
            },
            {
                'name': 'Refugee Arrival',
                'description': '🚁 **Refugee Ship Requesting Sanctuary**\nA damaged civilian transport has arrived with refugees fleeing from the outer systems.',
                'color': 0x8b4513,
                'event_type': 'neutral',
                'base_probability': 0.08,
                'interactive': True,
                'handler': self._handle_refugee_arrival,
                'effects': {'population_temp': 15, 'supply_demand': 2}
            },
            {
                'name': 'Celebration Festival',
                'description': '🎉 **Colony Founding Day Celebration**\nThe colony is celebrating its founding anniversary. Morale is high and opportunities abound.',
                'color': 0xffd700,
                'event_type': 'positive',
                'base_probability': 0.05,
                'interactive': True,
                'handler': self._handle_celebration,
                'effects': {'discount': 0.15, 'bonus_jobs': 2}
            }
        ]

    def _get_station_events(self, wealth: int, population: int):
        """Space station specific events"""
        return [
            {
                'name': 'Docking System Overload',
                'description': '🛰️ **Docking Bay Critical Overload**\nTraffic control systems are failing. Multiple ships are queued for emergency docking.',
                'color': 0xff4444,
                'event_type': 'negative',
                'base_probability': 0.15,
                'interactive': True,
                'handler': self._handle_docking_overload,
                'effects': {'travel_delay': 1, 'fuel_demand': 2}
            },
            {
                'name': 'Trade Convoy Arrival',
                'description': '🚛 **Major Trade Convoy Docking**\nA large merchant fleet has arrived with exotic goods and rare materials.',
                'color': 0x00ff00,
                'event_type': 'positive',
                'base_probability': 0.12,
                'interactive': True,
                'handler': self._handle_trade_convoy,
                'effects': {'rare_items': 3, 'price_bonus': 0.2}
            },
            {
                'name': 'Pirate Warning',
                'description': '💀 **Pirate Activity Alert**\nSecurity has detected increased pirate activity in nearby corridors. Travel advisories issued.',
                'color': 0x8b0000,
                'event_type': 'negative',
                'base_probability': 0.10,
                'interactive': False,
                'effects': {'danger_level': 2, 'security_bonus': 1}
            },
            {
                'name': 'VIP Arrival',
                'description': '👑 **Corporate Executive Visit**\nA high-ranking corporate official has arrived with a substantial security detail.',
                'color': 0x9932cc,
                'event_type': 'neutral',
                'base_probability': 0.08 if wealth >= 6 else 0.03,
                'interactive': True,
                'handler': self._handle_vip_arrival,
                'effects': {'luxury_demand': 2, 'security_level': 3}
            },
            {
                'name': 'System Upgrade',
                'description': '🔧 **Station Systems Upgrade**\nTechnicians are installing new equipment. Some services may be temporarily enhanced.',
                'color': 0x00bfff,
                'event_type': 'positive',
                'base_probability': 0.10 if wealth >= 5 else 0.05,
                'interactive': False,
                'effects': {'efficiency_bonus': 1, 'upgrade_discount': 0.1}
            }
        ]

    def _get_outpost_events(self, wealth: int, population: int):
        """Outpost specific events"""
        return [
            {
                'name': 'Supply Shortage',
                'description': '📦 **Critical Supply Shortage**\nThe scheduled supply run failed to arrive. Essential resources are running low.',
                'color': 0xff4444,
                'event_type': 'negative',
                'base_probability': 0.25 if wealth <= 3 else 0.15,
                'interactive': True,
                'handler': self._handle_supply_shortage,
                'effects': {'price_increase': 0.4, 'stock_reduction': 0.5}
            },
            {
                'name': 'Salvage Discovery',
                'description': '🔍 **Valuable Salvage Found**\nOutpost scanners have detected valuable debris in the nearby area.',
                'color': 0xffd700,
                'event_type': 'positive',
                'base_probability': 0.12,
                'interactive': True,
                'handler': self._handle_salvage_discovery,
                'effects': {'salvage_job': 1, 'bonus_credits': 200}
            },
            {
                'name': 'Communication Blackout',
                'description': '📡 **Communication Array Failure**\nThe outpost has lost contact with the rest of human space. Repairs needed urgently.',
                'color': 0x696969,
                'event_type': 'negative',
                'base_probability': 0.20,
                'interactive': True,
                'handler': self._handle_comm_blackout,
                'effects': {'isolation': True, 'repair_demand': 2}
            },
            {
                'name': 'Mysterious Signal',
                'description': '❓ **Unknown Signal Detected**\nOutpost sensors are picking up an unidentified transmission from deep space.',
                'color': 0x9400d3,
                'event_type': 'mysterious',
                'base_probability': 0.05,
                'interactive': True,
                'handler': self._handle_mysterious_signal,
                'effects': {'investigation_job': 1}
            }
        ]

    def _get_gate_events(self, wealth: int, population: int):
        """Gate specific events"""
        return [
            {
                'name': 'Corridor Instability',
                'description': '🌀 **Corridor Stability Fluctuations**\nThe gate is experiencing unusual fluctuations. Travel may be dangerous.',
                'color': 0x4b0082,
                'event_type': 'negative',
                'base_probability': 0.18,
                'interactive': False,
                'effects': {'travel_danger': 2, 'travel_delay': 1}
            },
            {
                'name': 'Gate Calibration',
                'description': '🎯 **Precision Calibration Complete**\nTechnicians have finished major calibration work. Gate efficiency has improved.',
                'color': 0x00ff00,
                'event_type': 'positive',
                'base_probability': 0.10,
                'interactive': False,
                'effects': {'travel_bonus': 1, 'fuel_efficiency': 0.9}
            },
            {
                'name': 'Static Fog Storm',
                'description': '⚡ **Static Fog Storm Approaching**\nMassive disturbances detected. All non-essential travel should be delayed.',
                'color': 0xff0000,
                'event_type': 'negative',
                'base_probability': 0.08,
                'interactive': False,
                'effects': {'travel_ban': True, 'danger_level': 3}
            },
            {
                'name': 'Discovery',
                'description': '🏛️ **Drifting Ship Detected**\nGate sensors have detected what appears to be an abandoned ship nearby.',
                'color': 0xdaa520,
                'event_type': 'mysterious',
                'base_probability': 0.03,
                'interactive': True,
                'effects': {'research_job': 1, 'artifact_potential': True}
            }
        ]

    # Interactive event handlers
    async def _handle_industrial_accident(self, channel, players, event_data):
        """Handle industrial accident event"""
        embed = discord.Embed(
            title="🏭 Industrial Emergency Response",
            description="A serious accident has occurred at the processing facility. Lives are at stake!",
            color=0xff4444
        )
        
        view = discord.ui.View(timeout=300)
        
        medical_button = discord.ui.Button(
            label="Provide Medical Aid",
            style=discord.ButtonStyle.green,
            emoji="🏥"
        )
        
        repair_button = discord.ui.Button(
            label="Emergency Repairs",
            style=discord.ButtonStyle.primary,
            emoji="🔧"
        )
        
        evacuate_button = discord.ui.Button(
            label="Coordinate Evacuation",
            style=discord.ButtonStyle.secondary,
            emoji="🚁"
        )
        
        async def medical_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, medical FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, medical_skill = char_data
            
            if medical_skill >= 15:
                reward = 300 + (medical_skill * 10)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🏥 **{char_name}** successfully treats the injured workers! Earned {reward} credits for exceptional medical care.",
                    ephemeral=False
                )
            else:
                reward = 150
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🩹 **{char_name}** provides basic first aid. Earned {reward} credits, but specialized help is still needed.",
                    ephemeral=False
                )
        
        async def repair_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, engineering_skill = char_data
            
            if engineering_skill >= 18:
                reward = 400 + (engineering_skill * 8)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🔧 **{char_name}** performs emergency repairs and prevents a catastrophic failure! Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"⚡ **{char_name}** attempts repairs but lacks the expertise for this complex emergency.",
                    ephemeral=False
                )
        
        async def evacuate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, navigation_skill = char_data
            reward = 200 + (navigation_skill * 5)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🚁 **{char_name}** coordinates evacuation procedures. Earned {reward} credits for leadership.",
                ephemeral=False
            )
        
        medical_button.callback = medical_callback
        repair_button.callback = repair_callback
        evacuate_button.callback = evacuate_callback
        
        view.add_item(medical_button)
        view.add_item(repair_button)
        view.add_item(evacuate_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_worker_strike(self, channel, players, event_data):
            """Handle worker strike event"""
            embed = discord.Embed(
                title="✊ Labor Dispute Resolution",
                description="Colony workers are demanding better conditions. Your intervention could help resolve the crisis.",
                color=0xff9900
            )
            
            view = discord.ui.View(timeout=300)
            
            negotiate_button = discord.ui.Button(
                label="Mediate Negotiations",
                style=discord.ButtonStyle.primary,
                emoji="🤝"
            )
            
            support_workers_button = discord.ui.Button(
                label="Support Workers",
                style=discord.ButtonStyle.success,
                emoji="✊"
            )
            
            support_management_button = discord.ui.Button(
                label="Support Management",
                style=discord.ButtonStyle.secondary,
                emoji="🏢"
            )
            
            async def negotiate_callback(interaction):
                char_data = self.bot.db.execute_query(
                    "SELECT name, navigation FROM characters WHERE user_id = ?",
                    (interaction.user.id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name, nav_skill = char_data
                
                if nav_skill >= 12:
                    reward = 250 + (nav_skill * 10)
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money + ? WHERE user_id = ?",
                        (reward, interaction.user.id)
                    )
                    
                    await interaction.response.send_message(
                        f"🤝 **{char_name}** successfully mediates the labor dispute! Both sides reach agreement. Earned {reward} credits.",
                        ephemeral=False
                    )
                else:
                    await interaction.response.send_message(
                        f"💼 **{char_name}** attempts to mediate but lacks the experience for such complex negotiations.",
                        ephemeral=False
                    )
            
            async def support_workers_callback(interaction):
                char_data = self.bot.db.execute_query(
                    "SELECT name, money FROM characters WHERE user_id = ?",
                    (interaction.user.id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name, current_money = char_data
                cost = 100
                
                if current_money >= cost:
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money - ? WHERE user_id = ?",
                        (cost, interaction.user.id)
                    )
                    
                    await interaction.response.send_message(
                        f"✊ **{char_name}** supports the workers with {cost} credits. Strike resolved peacefully!",
                        ephemeral=False
                    )
                else:
                    await interaction.response.send_message(
                        f"💸 **{char_name}** wants to help but lacks the credits to make a meaningful contribution.",
                        ephemeral=False
                    )
            
            async def support_management_callback(interaction):
                char_data = self.bot.db.execute_query(
                    "SELECT name FROM characters WHERE user_id = ?",
                    (interaction.user.id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name = char_data[0]
                reward = 150
                
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🏢 **{char_name}** assists management with strike-breaking efforts. Earned {reward} credits, but worker relations suffer.",
                    ephemeral=False
                )
            
            negotiate_button.callback = negotiate_callback
            support_workers_button.callback = support_workers_callback
            support_management_button.callback = support_management_callback
            
            view.add_item(negotiate_button)
            view.add_item(support_workers_button)
            view.add_item(support_management_button)
            
            await channel.send(embed=embed, view=view)

    async def _handle_scavenger_swarm(self, channel, user_id, event_data):
        """Handle scavenger drone encounter"""
        embed = discord.Embed(
            title="🤖 Automated Scavenger Swarm",
            description="Drone swarms are scanning your ship for salvageable materials! They're moving to intercept.",
            color=0x708090
        )
        
        view = discord.ui.View(timeout=300)
        
        defend_button = discord.ui.Button(
            label="Defensive Measures",
            style=discord.ButtonStyle.primary,
            emoji="🛡️"
        )
        
        outrun_button = discord.ui.Button(
            label="Outrun Drones",
            style=discord.ButtonStyle.success,
            emoji="🚀"
        )
        
        async def defend_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            
            if eng_skill >= 12:
                await interaction.response.send_message(
                    f"🛡️ **{char_name}** successfully activates ship defenses, repelling the scavenger drones!",
                    ephemeral=False
                )
            else:
                damage = random.randint(5, 15)
                self.bot.db.execute_query(
                    "UPDATE ships SET hull_integrity = GREATEST(1, hull_integrity - ?) WHERE owner_id = ?",
                    (damage, user_id)
                )
                
                await interaction.response.send_message(
                    f"🤖 **{char_name}**'s defenses fail! Scavenger drones strip {damage} hull integrity from the ship.",
                    ephemeral=False
                )
        
        async def outrun_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            
            success_chance = min(75, 45 + nav_skill * 2)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"🚀 **{char_name}** successfully outruns the scavenger swarm!",
                    ephemeral=False
                )
            else:
                fuel_lost = random.randint(15, 30)
                self.bot.db.execute_query(
                    "UPDATE ships SET current_fuel = GREATEST(0, current_fuel - ?) WHERE owner_id = ?",
                    (fuel_lost, user_id)
                )
                
                await interaction.response.send_message(
                    f"🤖 **{char_name}** burns {fuel_lost} extra fuel trying to escape the persistent drones!",
                    ephemeral=False
                )
        
        defend_button.callback = defend_callback
        outrun_button.callback = outrun_callback
        
        view.add_item(defend_button)
        view.add_item(outrun_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_corporate_ambush(self, channel, user_id, event_data):
        """Handle corporate enforcement encounter"""
        embed = discord.Embed(
            title="🏢 Corporate Enforcement Checkpoint",
            description="Mega-corp security forces have set up a checkpoint. They're demanding inspection of your ship.",
            color=0x000080
        )
        
        view = discord.ui.View(timeout=300)
        
        submit_button = discord.ui.Button(
            label="Submit to Inspection",
            style=discord.ButtonStyle.secondary,
            emoji="📋"
        )
        
        bribe_button = discord.ui.Button(
            label="Attempt Bribery",
            style=discord.ButtonStyle.success,
            emoji="💰"
        )
        
        fight_button = discord.ui.Button(
            label="Fight Through",
            style=discord.ButtonStyle.danger,
            emoji="⚔️"
        )
        
        async def submit_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name = char_data[0]
            
            # Small chance of finding "contraband"
            if random.random() < 0.3:
                fine = random.randint(100, 250)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = GREATEST(0, money - ?) WHERE user_id = ?",
                    (fine, user_id)
                )
                
                await interaction.response.send_message(
                    f"📋 **{char_name}** submits to inspection. Corporate security finds 'irregularities' and issues a {fine} credit fine.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"📋 **{char_name}** submits to inspection. No violations found, cleared to proceed.",
                    ephemeral=False
                )
        
        async def bribe_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            bribe_cost = 150
            
            if current_money >= bribe_cost:
                if random.random() < 0.7:  # 70% success chance
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money - ? WHERE user_id = ?",
                        (bribe_cost, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"💰 **{char_name}** successfully bribes the checkpoint guards with {bribe_cost} credits. Waved through without inspection.",
                        ephemeral=False
                    )
                else:
                    fine = bribe_cost + 200
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = GREATEST(0, money - ?) WHERE user_id = ?",
                        (fine, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"🚨 **{char_name}**'s bribery attempt is reported! Fined {fine} credits for attempted corruption.",
                        ephemeral=False
                    )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** lacks sufficient credits to attempt bribery ({bribe_cost} credits needed).",
                    ephemeral=False
                )
        
        async def fight_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, combat FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, combat_skill = char_data
            
            # Fighting corporate security is very risky
            success_chance = min(60, 20 + combat_skill * 2)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"⚔️ **{char_name}** fights through the checkpoint! Corporate security is no match for superior tactics.",
                    ephemeral=False
                )
            else:
                damage = random.randint(25, 50)
                credits_lost = random.randint(200, 500)
                
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = GREATEST(1, hp - ?), money = GREATEST(0, money - ?) WHERE user_id = ?",
                    (damage, credits_lost, user_id)
                )
                
                await interaction.response.send_message(
                    f"💥 **{char_name}** is overwhelmed by corporate security! Lost {damage} health and {credits_lost} credits in fines and 'damages'.",
                    ephemeral=False
                )
        
        submit_button.callback = submit_callback
        bribe_button.callback = bribe_callback
        fight_button.callback = fight_callback
        
        view.add_item(submit_button)
        view.add_item(bribe_button)
        view.add_item(fight_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_debris_field(self, channel, user_id, event_data):
        """Handle asteroid debris field encounter"""
        
        embed = discord.Embed(
            title="☄️ Navigational Challenge",
            description="Dense asteroid debris blocks your path. Careful navigation is required to proceed safely.",
            color=0x8b4513
        )
        
        view = discord.ui.View(timeout=300)
        
        careful_button = discord.ui.Button(
            label="Navigate Carefully",
            style=discord.ButtonStyle.primary,
            emoji="🧭"
        )
        
        speed_button = discord.ui.Button(
            label="Push Through Quickly",
            style=discord.ButtonStyle.danger,
            emoji="🚀"
        )
        
        async def careful_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, navigation_skill = char_data
            
            import random
            success_chance = min(95, 50 + navigation_skill * 3)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"🧭 **{char_name}** expertly navigates through the debris field without incident. Extra fuel efficiency gained!",
                    ephemeral=False
                )
                # Bonus: Reduce fuel consumption for this trip
                self.bot.db.execute_query(
                    "UPDATE characters SET ship_fuel = ship_fuel + 5 WHERE user_id = ?",
                    (user_id,)
                )
            else:
                damage = random.randint(5, 15)
                await interaction.response.send_message(
                    f"💥 Despite careful navigation, **{char_name}**'s ship scrapes against debris. Hull takes {damage} damage.",
                    ephemeral=False
                )
                # Apply hull damage (if hull system exists)
        
        async def speed_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, navigation_skill = char_data
            
            import random
            success_chance = min(80, 30 + navigation_skill * 2)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"🚀 **{char_name}** successfully races through the debris field, arriving ahead of schedule!",
                    ephemeral=False
                )
                # Bonus: Reduce travel time
            else:
                damage = random.randint(15, 35)
                fuel_loss = random.randint(10, 20)
                await interaction.response.send_message(
                    f"💥 **{char_name}**'s reckless speed causes multiple collisions! Hull damage: {damage}, Fuel lost: {fuel_loss}",
                    ephemeral=False
                )
                # Apply damage and fuel loss
                self.bot.db.execute_query(
                    "UPDATE characters SET ship_fuel = GREATEST(0, ship_fuel - ?) WHERE user_id = ?",
                    (fuel_loss, user_id)
                )
        
        careful_button.callback = careful_callback
        speed_button.callback = speed_callback
        
        view.add_item(careful_button)
        view.add_item(speed_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_distress_signal(self, channel, user_id, event_data):
        """Handle distress signal encounter"""
        
        embed = discord.Embed(
            title="📡 Distress Signal Detected",
            description="A faint distress beacon is transmitting an emergency message. The signal appears to be from a civilian vessel.",
            color=0xff4500
        )
        
        import random
        signal_types = [
            ("Refugee Ship", "A civilian transport with failing life support", 0x8b4513, False),
            ("Research Vessel", "A science ship stranded after equipment failure", 0x4169e1, False),
            ("Pirate Trap", "A fake signal designed to lure unsuspecting ships", 0x8b0000, True),
            ("Corporate Executive", "A luxury yacht with engine problems", 0x9932cc, False)
        ]
        
        signal_type, signal_desc, signal_color, is_trap = random.choice(signal_types)
        
        embed.add_field(
            name="📊 Signal Analysis",
            value=f"**Source:** {signal_type}\n**Status:** {signal_desc}",
            inline=False
        )
        
        view = discord.ui.View(timeout=300)
        
        investigate_button = discord.ui.Button(
            label="Investigate Signal",
            style=discord.ButtonStyle.primary,
            emoji="🔍"
        )
        
        ignore_button = discord.ui.Button(
            label="Ignore and Continue",
            style=discord.ButtonStyle.secondary,
            emoji="➡️"
        )
        
        async def investigate_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, combat, medical FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, combat_skill, medical_skill = char_data
            
            if is_trap:
                # Pirate trap!
                combat_chance = min(90, combat_skill * 8)
                roll = random.randint(1, 100)
                
                if roll <= combat_chance:
                    reward = random.randint(200, 500)
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money + ? WHERE user_id = ?",
                        (reward, user_id)
                    )
                    await interaction.response.send_message(
                        f"⚔️ **{char_name}** sees through the pirate trap and defeats the ambushers! Salvage worth {reward} credits recovered.",
                        ephemeral=False
                    )
                else:
                    damage = random.randint(20, 40)
                    credits_lost = random.randint(50, 200)
                    self.bot.db.execute_query(
                        "UPDATE characters SET health = GREATEST(1, health - ?), money = GREATEST(0, money - ?) WHERE user_id = ?",
                        (damage, credits_lost, user_id)
                    )
                    await interaction.response.send_message(
                        f"💥 **{char_name}** falls into a pirate trap! Lost {damage} health and {credits_lost} credits.",
                        ephemeral=False
                    )
            else:
                # Genuine rescue
                base_reward = random.randint(150, 300)
                medical_bonus = medical_skill * 10 if medical_skill > 10 else 0
                total_reward = base_reward + medical_bonus
                
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (total_reward, user_id)
                )
                
                await interaction.response.send_message(
                    f"🚁 **{char_name}** successfully rescues the stranded crew! Earned {total_reward} credits in gratitude payments.",
                    ephemeral=False
                )
        
        async def ignore_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            char_name = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )[0]
            
            await interaction.response.send_message(
                f"➡️ **{char_name}** decides not to investigate the signal and continues on course.",
                ephemeral=False
            )
        
        investigate_button.callback = investigate_callback
        ignore_button.callback = ignore_callback
        
        view.add_item(investigate_button)
        view.add_item(ignore_button)
        
        await channel.send(embed=embed, view=view)

    async def _execute_travel_event(self, channel, event, user_id, corridor_name):
        """Execute a travel event"""
        embed = discord.Embed(
            title=f"🚀 Travel Event: {corridor_name}",
            description=event['description'],
            color=event['color']
        )
        
        if event.get('interactive') and event.get('handler'):
            await event['handler'](channel, user_id, event)
        else:
            await channel.send(embed=embed)


class PirateEncounterView(discord.ui.View):
    def __init__(self, bot, encounter_id, players, pirate_ships):
        super().__init__(timeout=300)
        self.bot = bot
        self.encounter_id = encounter_id
        self.players = players
        self.pirate_ships = pirate_ships
        self.player_choices = {}
    
    @discord.ui.button(label="Engage in Combat", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def engage_combat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "combat", "chose to fight the pirates!")
    
    @discord.ui.button(label="Attempt to Flee", style=discord.ButtonStyle.secondary, emoji="🏃")
    async def attempt_flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "flee", "attempts to escape!")
    
    @discord.ui.button(label="Negotiate", style=discord.ButtonStyle.primary, emoji="🤝")
    async def negotiate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "negotiate", "tries to negotiate with the pirates!")
    
    @discord.ui.button(label="Pay Tribute", style=discord.ButtonStyle.success, emoji="💰")
    async def pay_tribute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "tribute", "offers to pay tribute!")
    
    async def _handle_choice(self, interaction, choice, flavor_text):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("You're not part of this encounter!", ephemeral=True)
            return
        
        self.player_choices[interaction.user.id] = choice
        
        await interaction.response.send_message(f"🎯 {interaction.user.display_name} {flavor_text}", ephemeral=True)
        
        # Check if all players have chosen
        if len(self.player_choices) >= len(self.players):
            await self._resolve_encounter(interaction.channel)
    
    async def _resolve_encounter(self, channel):
        """Resolve the pirate encounter based on player choices"""
        
        choices = list(self.player_choices.values())
        
        # Majority decision logic
        combat_votes = choices.count("combat")
        flee_votes = choices.count("flee")
        negotiate_votes = choices.count("negotiate")
        tribute_votes = choices.count("tribute")
        
        embed = discord.Embed(title="💀 Pirate Encounter Resolution", color=0x8b0000)
        
        if combat_votes >= len(self.players) // 2 + 1:
            # Combat chosen
            embed.description = "⚔️ **Combat Initiated!**\nThe fleet engages the pirates in battle!"
            
            # Start combat encounter
            combat_cog = self.bot.get_cog('CombatCog')
            if combat_cog:
                await combat_cog.start_pirate_combat(channel, self.players, self.pirate_ships)
        
        elif flee_votes >= len(self.players) // 2 + 1:
            # Flee attempt
            success_chance = 0.6  # Base 60% chance
            if random.random() < success_chance:
                embed.description = "🏃 **Escape Successful!**\nYour ships manage to evade the pirates!"
                embed.color = 0x00ff00
            else:
                embed.description = "💥 **Escape Failed!**\nThe pirates catch up and force a fight!"
                combat_cog = self.bot.get_cog('CombatCog')
                if combat_cog:
                    await combat_cog.start_pirate_combat(channel, self.players, self.pirate_ships)
        
        elif tribute_votes >= len(self.players) // 2 + 1:
            # Pay tribute
            tribute_amount = 200 * self.pirate_ships  # Cost based on pirate fleet size
            
            for player_id in self.players:
                player_money = self.bot.db.execute_query(
                    "SELECT money FROM characters WHERE user_id = ?", (player_id,), fetch='one'
                )[0]
                
                if player_money >= tribute_amount:
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money - ? WHERE user_id = ?",
                        (tribute_amount, player_id)
                    )
            
            embed.description = f"💰 **Tribute Paid!**\nThe pirates accept {tribute_amount} credits and leave you in peace."
            embed.color = 0xffd700
        
        else:
            # Negotiate attempt
            negotiate_success = random.random() < 0.4  # 40% success chance
            
            if negotiate_success:
                embed.description = "🤝 **Negotiation Successful!**\nThe pirates agree to let you pass unharmed."
                embed.color = 0x00ff00
            else:
                embed.description = "💥 **Negotiation Failed!**\nThe pirates attack without warning!"
                combat_cog = self.bot.get_cog('CombatCog')
                if combat_cog:
                    await combat_cog.start_pirate_combat(channel, self.players, self.pirate_ships)
        
        await channel.send(embed=embed)


class AsteroidFieldView(discord.ui.View):
    def __init__(self, bot, players):
        super().__init__(timeout=180)
        self.bot = bot
        self.players = players
        self.player_choices = {}
    
    @discord.ui.button(label="Aggressive Evasion", style=discord.ButtonStyle.danger, emoji="⚡")
    async def aggressive_evasion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_evasion(interaction, "aggressive", 0.8, 20)  # High success, high damage if fail
    
    @discord.ui.button(label="Careful Navigation", style=discord.ButtonStyle.primary, emoji="🎯")
    async def careful_navigation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_evasion(interaction, "careful", 0.6, 10)  # Medium success, medium damage
    
    @discord.ui.button(label="Emergency Shields", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def emergency_shields(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_evasion(interaction, "shields", 0.4, 5)  # Low success, low damage
    
    async def _handle_evasion(self, interaction, strategy, success_chance, damage_if_fail):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("You're not part of this encounter!", ephemeral=True)
            return
        
        success = random.random() < success_chance
        self.player_choices[interaction.user.id] = (strategy, success, damage_if_fail)
        
        if success:
            await interaction.response.send_message(f"✅ {interaction.user.display_name} successfully navigates the asteroid field!", ephemeral=True)
        else:
            await interaction.response.send_message(f"💥 {interaction.user.display_name} takes asteroid damage!", ephemeral=True)
            
            # Apply damage
            self.bot.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (damage_if_fail, interaction.user.id)
            )
        
        # Check if all players have chosen
        if len(self.player_choices) >= len(self.players):
            await self._resolve_asteroid_field(interaction.channel)
    
    async def _resolve_asteroid_field(self, channel):
        """Resolve the asteroid field challenge"""
        
        embed = discord.Embed(
            title="☄️ Asteroid Field Navigation Complete",
            description="All ships have attempted to navigate through the dangerous asteroid field.",
            color=0x8b4513
        )
        
        results = []
        for player_id in self.players:
            if player_id in self.player_choices:
                strategy, success, damage = self.player_choices[player_id]
                member = channel.guild.get_member(player_id)
                if member:
                    if success:
                        results.append(f"✅ {member.display_name}: {strategy.title()} - Success!")
                    else:
                        results.append(f"💥 {member.display_name}: {strategy.title()} - {damage} hull damage")
        
        await channel.send(embed=embed)

    async def _handle_corporate_inspection(self, channel, players, event_data):
        """Handle corporate inspection event"""
        embed = discord.Embed(
            title="🏢 Corporate Security Audit",
            description="Mega-corp inspectors are conducting a surprise audit. All operations are under scrutiny.",
            color=0x4169e1
        )
        
        embed.add_field(
            name="🔍 Inspection Focus",
            value="• Ship manifests and cargo\n• Personal identification\n• Travel permits and documentation\n• Equipment and contraband",
            inline=False
        )
        
        view = discord.ui.View(timeout=300)
        
        comply_button = discord.ui.Button(
            label="Full Compliance",
            style=discord.ButtonStyle.success,
            emoji="📋"
        )
        
        partial_button = discord.ui.Button(
            label="Selective Cooperation",
            style=discord.ButtonStyle.primary,
            emoji="🎭"
        )
        
        avoid_button = discord.ui.Button(
            label="Avoid Inspection",
            style=discord.ButtonStyle.danger,
            emoji="🏃"
        )
        
        async def comply_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name = char_data[0]
            
            await interaction.response.send_message(
                f"📋 **{char_name}** fully cooperates with the inspection. Clean record confirmed, no issues found.",
                ephemeral=False
            )
        
        async def partial_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            
            if nav_skill >= 10:
                await interaction.response.send_message(
                    f"🎭 **{char_name}** skillfully navigates the inspection, revealing only what's necessary.",
                    ephemeral=False
                )
            else:
                fine = 75
                self.bot.db.execute_query(
                    "UPDATE characters SET money = GREATEST(0, money - ?) WHERE user_id = ?",
                    (fine, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚠️ **{char_name}**'s evasiveness raises suspicion. Fined {fine} credits for non-compliance.",
                    ephemeral=False
                )
        
        async def avoid_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, combat FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, combat_skill = char_data
            
            if combat_skill >= 15 and random.random() < 0.6:
                await interaction.response.send_message(
                    f"🏃 **{char_name}** successfully evades the inspection and escapes corporate attention.",
                    ephemeral=False
                )
            else:
                fine = 200
                self.bot.db.execute_query(
                    "UPDATE characters SET money = GREATEST(0, money - ?) WHERE user_id = ?",
                    (fine, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🚨 **{char_name}** is caught avoiding inspection. Heavy fine of {fine} credits imposed!",
                    ephemeral=False
                )
        
        comply_button.callback = comply_callback
        partial_button.callback = partial_callback
        avoid_button.callback = avoid_callback
        
        view.add_item(comply_button)
        view.add_item(partial_button)
        view.add_item(avoid_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_equipment_malfunction(self, channel, players, event_data):
        """Handle equipment malfunction event"""
        embed = discord.Embed(
            title="⚙️ Critical Equipment Failure",
            description="Primary life support systems are showing signs of failure. Technical expertise urgently needed!",
            color=0xff0000
        )
        
        view = discord.ui.View(timeout=300)
        
        repair_button = discord.ui.Button(
            label="Emergency Repair",
            style=discord.ButtonStyle.danger,
            emoji="🔧"
        )
        
        diagnose_button = discord.ui.Button(
            label="Run Diagnostics",
            style=discord.ButtonStyle.primary,
            emoji="🔍"
        )
        
        evacuate_button = discord.ui.Button(
            label="Coordinate Evacuation",
            style=discord.ButtonStyle.secondary,
            emoji="🚨"
        )
        
        async def repair_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            
            if eng_skill >= 18:
                reward = 400 + (eng_skill * 15)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🔧 **{char_name}** successfully repairs the critical systems! Crisis averted. Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                damage = random.randint(5, 15)
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = GREATEST(1, hp - ?) WHERE user_id = ?",
                    (damage, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚡ **{char_name}** attempts repairs but triggers a secondary failure! Took {damage} damage from electrical discharge.",
                    ephemeral=False
                )
        
        async def diagnose_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            reward = 150 + (eng_skill * 8)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🔍 **{char_name}** provides detailed diagnostics, helping the repair team identify the problem. Earned {reward} credits.",
                ephemeral=False
            )
        
        async def evacuate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            reward = 200 + (nav_skill * 6)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🚨 **{char_name}** coordinates evacuation procedures, ensuring everyone's safety. Earned {reward} credits.",
                ephemeral=False
            )
        
        repair_button.callback = repair_callback
        diagnose_button.callback = diagnose_callback
        evacuate_button.callback = evacuate_callback
        
        view.add_item(repair_button)
        view.add_item(diagnose_button)
        view.add_item(evacuate_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_refugee_arrival(self, channel, players, event_data):
        """Handle refugee arrival event"""
        embed = discord.Embed(
            title="🚁 Refugee Ship Requesting Sanctuary",
            description="A damaged civilian transport has arrived with refugees fleeing from conflict in the outer systems.",
            color=0x8b4513
        )
        
        refugee_count = random.randint(15, 50)
        embed.add_field(
            name="📊 Refugee Status",
            value=f"• Population: {refugee_count} civilians\n• Condition: Malnourished, some injured\n• Resources: Minimal supplies\n• Ship Status: Critical damage",
            inline=False
        )
        
        view = discord.ui.View(timeout=300)
        
        aid_button = discord.ui.Button(
            label="Provide Aid",
            style=discord.ButtonStyle.success,
            emoji="🤲"
        )
        
        medical_button = discord.ui.Button(
            label="Medical Assistance",
            style=discord.ButtonStyle.primary,
            emoji="⚕️"
        )
        
        ignore_button = discord.ui.Button(
            label="Turn Away",
            style=discord.ButtonStyle.secondary,
            emoji="👋"
        )
    
        async def aid_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            aid_cost = refugee_count * 2
            
            if current_money >= aid_cost:
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money - ? WHERE user_id = ?",
                    (aid_cost, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🤲 **{char_name}** provides {aid_cost} credits worth of supplies to the refugees. They are deeply grateful.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** wants to help but lacks sufficient credits to make a meaningful difference.",
                    ephemeral=False
                )
        
        async def medical_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, medical FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, medical_skill = char_data
            
            if medical_skill >= 10:
                reward = 200 + (medical_skill * 10)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚕️ **{char_name}** provides critical medical care to the injured refugees. Colonial authority pays {reward} credits for humanitarian aid.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"🩹 **{char_name}** provides basic first aid but lacks the skills for serious medical intervention.",
                    ephemeral=False
                )
        
        async def ignore_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name = char_data[0]
            
            await interaction.response.send_message(
                f"👋 **{char_name}** chooses not to get involved. The refugees continue searching for sanctuary elsewhere.",
                ephemeral=False
            )
        
        aid_button.callback = aid_callback
        medical_button.callback = medical_callback
        ignore_button.callback = ignore_callback
        
        view.add_item(aid_button)
        view.add_item(medical_button)
        view.add_item(ignore_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_celebration(self, channel, players, event_data):
        """Handle celebration festival event"""
        embed = discord.Embed(
            title="🎉 Colony Founding Day Celebration",
            description="The colony is celebrating its founding anniversary! Morale is high and special opportunities are available.",
            color=0xffd700
        )
        
        view = discord.ui.View(timeout=300)
        
        participate_button = discord.ui.Button(
            label="Join Celebration",
            style=discord.ButtonStyle.success,
            emoji="🎊"
        )
        
        organize_button = discord.ui.Button(
            label="Organize Events",
            style=discord.ButtonStyle.primary,
            emoji="🎯"
        )
        
        trade_button = discord.ui.Button(
            label="Festival Trading",
            style=discord.ButtonStyle.secondary,
            emoji="🛒"
        )
        
        async def participate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name = char_data[0]
            reward = random.randint(50, 150)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🎊 **{char_name}** enjoys the festivities and makes new connections. Earned {reward} credits in celebration bonuses!",
                ephemeral=False
            )
        
        async def organize_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            
            if nav_skill >= 12:
                reward = 300 + (nav_skill * 15)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🎯 **{char_name}** successfully organizes festival events! The colony is impressed. Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"📋 **{char_name}** tries to help organize but lacks the coordination skills for such large events.",
                    ephemeral=False
                )
        
        async def trade_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            profit = random.randint(100, 250)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (profit, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🛒 **{char_name}** takes advantage of festival trading opportunities. Made {profit} credits in profit!",
                ephemeral=False
            )
        
        participate_button.callback = participate_callback
        organize_button.callback = organize_callback
        trade_button.callback = trade_callback
        
        view.add_item(participate_button)
        view.add_item(organize_button)
        view.add_item(trade_button)
        
        await channel.send(embed=embed, view=view)

    # Add handlers for station events
    async def _handle_docking_overload(self, channel, players, event_data):
        """Handle docking system overload"""
        embed = discord.Embed(
            title="🛰️ Docking Bay Critical Overload",
            description="Traffic control systems are failing. Multiple ships queued for emergency docking assistance!",
            color=0xff4444
        )
        
        view = discord.ui.View(timeout=300)
        
        assist_button = discord.ui.Button(
            label="Assist Traffic Control",
            style=discord.ButtonStyle.primary,
            emoji="🎮"
        )
        
        manual_dock_button = discord.ui.Button(
            label="Manual Docking",
            style=discord.ButtonStyle.success,
            emoji="🎯"
        )
        
        async def assist_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            
            if nav_skill >= 15:
                reward = 350 + (nav_skill * 12)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🎮 **{char_name}** expertly manages traffic control, preventing accidents! Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"🎮 **{char_name}** tries to help but lacks the navigation expertise for complex traffic management.",
                    ephemeral=False
                )
        
        async def manual_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            reward = 200 + (eng_skill * 8)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🎯 **{char_name}** provides manual docking assistance to stranded ships. Earned {reward} credits.",
                ephemeral=False
            )
        
        assist_button.callback = assist_callback
        manual_dock_button.callback = manual_callback
        
        view.add_item(assist_button)
        view.add_item(manual_dock_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_trade_convoy(self, channel, players, event_data):
        """Handle trade convoy arrival"""
        embed = discord.Embed(
            title="🚛 Major Trade Convoy Docking",
            description="A large merchant fleet has arrived with exotic goods and rare materials from distant systems!",
            color=0x00ff00
        )
        
        view = discord.ui.View(timeout=300)
        
        trade_button = discord.ui.Button(
            label="Trade Goods",
            style=discord.ButtonStyle.success,
            emoji="💎"
        )
        
        negotiate_button = discord.ui.Button(
            label="Negotiate Deals",
            style=discord.ButtonStyle.primary,
            emoji="🤝"
        )
        
        async def trade_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            
            if current_money >= 200:
                profit = random.randint(150, 400)
                net_gain = profit - 200
                
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (net_gain, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"💎 **{char_name}** invests 200 credits in rare goods and earns {profit} credits! Net profit: {net_gain}",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** lacks sufficient credits to invest in the convoy's expensive goods.",
                    ephemeral=False
                )
        
        async def negotiate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            reward = 250 + (nav_skill * 10)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🤝 **{char_name}** negotiates favorable trade agreements for the station. Earned {reward} credits in commission!",
                ephemeral=False
            )
        
        trade_button.callback = trade_callback
        negotiate_button.callback = negotiate_callback
        
        view.add_item(trade_button)
        view.add_item(negotiate_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_vip_arrival(self, channel, players, event_data):
        """Handle VIP arrival event"""
        embed = discord.Embed(
            title="👑 Corporate Executive Visit",
            description="A high-ranking corporate official has arrived with substantial security detail and special requirements.",
            color=0x9932cc
        )
        
        view = discord.ui.View(timeout=300)
        
        security_button = discord.ui.Button(
            label="Provide Security",
            style=discord.ButtonStyle.danger,
            emoji="🛡️"
        )
        
        service_button = discord.ui.Button(
            label="VIP Services",
            style=discord.ButtonStyle.success,
            emoji="🍾"
        )
        
        async def security_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, combat FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, combat_skill = char_data
            
            if combat_skill >= 15:
                reward = 400 + (combat_skill * 15)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🛡️ **{char_name}** provides professional security services for the VIP! Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"🛡️ **{char_name}** offers to help with security but lacks the combat training required for VIP protection.",
                    ephemeral=False
                )
        
        async def service_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            service_cost = 150
            
            if current_money >= service_cost:
                tip = random.randint(200, 500)
                net_gain = tip - service_cost
                
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (net_gain, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🍾 **{char_name}** provides luxury services costing {service_cost} credits. VIP tips {tip} credits! Net: +{net_gain}",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** lacks the credits to provide the luxury services the VIP expects.",
                    ephemeral=False
                )
        
        security_button.callback = security_callback
        service_button.callback = service_callback
        
        view.add_item(security_button)
        view.add_item(service_button)
        
        await channel.send(embed=embed, view=view)

    # Add handlers for outpost events
    async def _handle_supply_shortage(self, channel, players, event_data):
        """Handle supply shortage event"""
        embed = discord.Embed(
            title="📦 Critical Supply Shortage",
            description="The scheduled supply run failed to arrive. Essential resources running dangerously low!",
            color=0xff4444
        )
        
        view = discord.ui.View(timeout=300)
        
        donate_button = discord.ui.Button(
            label="Donate Supplies",
            style=discord.ButtonStyle.success,
            emoji="📦"
        )
        
        emergency_run_button = discord.ui.Button(
            label="Emergency Supply Run",
            style=discord.ButtonStyle.primary,
            emoji="🚚"
        )
        
        async def donate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            donation = 200
            
            if current_money >= donation:
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money - ? WHERE user_id = ?",
                    (donation, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"📦 **{char_name}** donates {donation} credits worth of emergency supplies! The outpost is grateful.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** wants to help but lacks sufficient credits for meaningful supply donation.",
                    ephemeral=False
                )
        
        async def emergency_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            
            if nav_skill >= 12:
                reward = 350 + (nav_skill * 20)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🚚 **{char_name}** organizes an emergency supply run to a nearby station! Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"🚚 **{char_name}** offers to help but lacks the navigation skills for emergency supply runs.",
                    ephemeral=False
                )
        
        donate_button.callback = donate_callback
        emergency_run_button.callback = emergency_callback
        
        view.add_item(donate_button)
        view.add_item(emergency_run_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_salvage_discovery(self, channel, players, event_data):
        """Handle salvage discovery event"""
        embed = discord.Embed(
            title="🔍 Valuable Salvage Found",
            description="Outpost scanners have detected valuable debris in the nearby area! Salvage opportunities available.",
            color=0xffd700
        )
        
        view = discord.ui.View(timeout=300)
        
        investigate_button = discord.ui.Button(
            label="Investigate Salvage",
            style=discord.ButtonStyle.primary,
            emoji="🔍"
        )
        
        claim_button = discord.ui.Button(
            label="Claim Salvage Rights",
            style=discord.ButtonStyle.success,
            emoji="⚒️"
        )
        
        async def investigate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            find_value = random.randint(100, 300) + (eng_skill * 10)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (find_value, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"🔍 **{char_name}** investigates the salvage site and recovers valuable components worth {find_value} credits!",
                ephemeral=False
            )
        
        async def claim_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            claim_cost = 100
            
            if current_money >= claim_cost:
                potential_value = random.randint(150, 500)
                net_gain = potential_value - claim_cost
                
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (net_gain, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚒️ **{char_name}** claims salvage rights for {claim_cost} credits and recovers {potential_value} credits worth! Net: +{net_gain}",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** lacks the credits to file proper salvage claims.",
                    ephemeral=False
                )
        
        investigate_button.callback = investigate_callback
        claim_button.callback = claim_callback
        
        view.add_item(investigate_button)
        view.add_item(claim_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_comm_blackout(self, channel, players, event_data):
        """Handle communication blackout event"""
        embed = discord.Embed(
            title="📡 Communication Array Failure",
            description="The outpost has lost contact with the rest of human space. Repairs needed urgently!",
            color=0x696969
        )
        
        view = discord.ui.View(timeout=300)
        
        repair_button = discord.ui.Button(
            label="Repair Communications",
            style=discord.ButtonStyle.danger,
            emoji="🔧"
        )
        
        improvise_button = discord.ui.Button(
            label="Improvise Solution",
            style=discord.ButtonStyle.primary,
            emoji="💡"
        )
        
        async def repair_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            
            if eng_skill >= 15:
                reward = 400 + (eng_skill * 18)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🔧 **{char_name}** successfully repairs the communication array! Contact with human space restored. Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                damage = random.randint(5, 12)
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = GREATEST(1, hp - ?) WHERE user_id = ?",
                    (damage, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚡ **{char_name}** attempts repairs but causes additional damage! Took {damage} damage from equipment failure.",
                    ephemeral=False
                )
        
        async def improvise_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            reward = 200 + (nav_skill * 12)
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"💡 **{char_name}** creates an improvised communication solution using ship systems! Earned {reward} credits.",
                ephemeral=False
            )
        
        repair_button.callback = repair_callback
        improvise_button.callback = improvise_callback
        
        view.add_item(repair_button)
        view.add_item(improvise_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_mysterious_signal(self, channel, players, event_data):
        """Handle mysterious signal event"""
        embed = discord.Embed(
            title="❓ Unknown Signal Detected",
            description="Outpost sensors are picking up an unidentified transmission from deep space. Origin and intent unknown.",
            color=0x9400d3
        )
        
        view = discord.ui.View(timeout=300)
        
        investigate_button = discord.ui.Button(
            label="Investigate Signal",
            style=discord.ButtonStyle.primary,
            emoji="🔍"
        )
        
        decode_button = discord.ui.Button(
            label="Attempt Decoding",
            style=discord.ButtonStyle.secondary,
            emoji="💻"
        )
        
        ignore_button = discord.ui.Button(
            label="Ignore Signal",
            style=discord.ButtonStyle.danger,
            emoji="🚫"
        )
        
        async def investigate_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
            
            discovery_roll = random.randint(1, 100)
            
            if discovery_roll <= 30:  # 30% chance of finding something valuable
                reward = random.randint(300, 600)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🔍 **{char_name}** investigates and discovers a cache of ancient technology! Earned {reward} credits from the find!",
                    ephemeral=False
                )
            elif discovery_roll <= 60:  # 30% chance of neutral discovery
                reward = random.randint(50, 150)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🔍 **{char_name}** investigates and finds abandoned equipment. Earned {reward} credits in salvage.",
                    ephemeral=False
                )
            else:  # 40% chance of danger
                damage = random.randint(10, 25)
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = GREATEST(1, hp - ?) WHERE user_id = ?",
                    (damage, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚠️ **{char_name}** investigates but triggers an automated defense system! Took {damage} damage!",
                    ephemeral=False
                )
        
        async def decode_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            
            if eng_skill >= 12:
                reward = 200 + (eng_skill * 15)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"💻 **{char_name}** successfully decodes the signal - it contains valuable technical data! Earned {reward} credits.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💻 **{char_name}** attempts to decode the signal but lacks the technical expertise to understand it.",
                    ephemeral=False
                )
        
        async def ignore_callback(interaction):
            char_data = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name = char_data[0]
            
            await interaction.response.send_message(
                f"🚫 **{char_name}** decides not to investigate the mysterious signal. Sometimes discretion is the better part of valor.",
                ephemeral=False
            )
        
        investigate_button.callback = investigate_callback
        decode_button.callback = decode_callback
        ignore_button.callback = ignore_callback
        
        view.add_item(investigate_button)
        view.add_item(decode_button)
        view.add_item(ignore_button)
        
        await channel.send(embed=embed, view=view)
    # Travel Event Handlers (different signature from location handlers)
    async def _handle_travel_solar_flare(self, channel, user_id, event_data):
        """Handle solar flare during travel"""
        embed = discord.Embed(
            title="🌟 Solar Flare Detected",
            description="Massive solar activity is interfering with ship systems and communications.",
            color=0xff4500
        )
        
        char_data = self.bot.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        char_name = char_data[0]
        
        # Apply random system effects
        effects = []
        if random.random() < 0.6:  # 60% chance of fuel efficiency reduction
            self.bot.db.execute_query(
                "UPDATE ships SET fuel_efficiency = MAX(1, fuel_efficiency - 2) WHERE owner_id = ?",
                (user_id,)
            )
            effects.append("• Fuel efficiency reduced by 2")
        
        if random.random() < 0.4:  # 40% chance of minor damage
            damage = random.randint(3, 8)
            self.bot.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (damage, user_id)
            )
            effects.append(f"• Radiation exposure: -{damage} HP")
        
        if effects:
            embed.add_field(name="⚡ System Effects", value="\n".join(effects), inline=False)
        
        embed.add_field(
            name="🛠️ Recommended Actions",
            value="• Monitor ship systems\n• Check radiation shielding\n• Consider emergency protocols",
            inline=False
        )
        
        await channel.send(embed=embed)

    async def _handle_travel_quantum_storm(self, channel, user_id, event_data):
        """Handle quantum storm during travel"""
        embed = discord.Embed(
            title="⚡ Static Fog Storm",
            description="Electromagnetic interference is affecting ship systems. Navigation may be impaired.",
            color=0x9400d3
        )
        
        char_data = self.bot.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        char_name = char_data[0]
        
        # Random effects from quantum disturbance
        effect_roll = random.random()
        
        if effect_roll < 0.3:  # Negative effect
            damage = random.randint(5, 15)
            self.bot.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (damage, user_id)
            )
            embed.add_field(name="💥 Effect", value=f"Quantum disturbance causes disorientation: -{damage} HP", inline=False)
        
        elif effect_roll < 0.7:  # Neutral effect
            embed.add_field(name="⚡ Effect", value="Ship systems experience minor interference but remain functional.", inline=False)
        
        else:  # Positive effect (rare)
            bonus_exp = random.randint(10, 25)
            self.bot.db.execute_query(
                "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                (bonus_exp, user_id)
            )
            embed.add_field(name="✨ Effect", value=f"Quantum patterns provide scientific insights: +{bonus_exp} experience", inline=False)
        
        await channel.send(embed=embed)

    async def _handle_travel_radiation_nebula(self, channel, user_id, event_data):
        """Handle radiation nebula during travel"""
        embed = discord.Embed(
            title="☢️ Radiation Cloud Encountered",
            description="High-energy particles detected. Hull integrity and crew health at risk.",
            color=0xff0000
        )
        
        # Apply radiation damage
        hp_damage = random.randint(8, 20)
        hull_damage = random.randint(5, 15)
        
        self.bot.db.execute_query(
            "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
            (hp_damage, user_id)
        )
        self.bot.db.execute_query(
            "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
            (hull_damage, user_id)
        )
        
        embed.add_field(
            name="☢️ Radiation Exposure",
            value=f"• Health damage: -{hp_damage} HP\n• Hull damage: -{hull_damage} integrity",
            inline=False
        )
        
        embed.add_field(
            name="⚕️ Treatment Required",
            value="Seek medical attention at the nearest facility with medical services.",
            inline=False
        )
        
        await channel.send(embed=embed)
    def _store_event_log(self, location_id: int, event_name: str, description: str):
        """Store event in database for tracking"""
        self.bot.db.execute_query(
            '''INSERT INTO location_logs (location_id, author_id, author_name, message, is_generated)
               VALUES (?, 0, 'System Event', ?, 1)''',
            (location_id, f"[{event_name}] {description}")
        )

    async def _execute_location_event(self, channel, event, players, location_name):
        """Execute a location event"""
        embed = discord.Embed(
            title=f"📍 Event at {location_name}",
            description=event['description'],
            color=event['color']
        )
        
        if event.get('interactive') and event.get('handler'):
            await event['handler'](channel, players, event)
        else:
            await channel.send(embed=embed)

    async def _handle_solar_flare(self, location_id, players, location_name, event_name, description, color):
        """Handle solar flare - system interference"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(title=f"🌟 {event_name}", description=description, color=color)
        
        # Apply effects
        affected_players = []
        for player_id in players:
            if random.random() < 0.6:  # 60% chance to be affected
                # Temporary system failures
                self.bot.db.execute_query(
                    "UPDATE ships SET fuel_efficiency = MAX(1, fuel_efficiency - 2) WHERE owner_id = ?",
                    (player_id,)
                )
                
                member = channel.guild.get_member(player_id)
                if member:
                    affected_players.append(member.mention)
        
        if affected_players:
            embed.add_field(
                name="⚡ Systems Affected",
                value="\n".join(affected_players),
                inline=False
            )
            embed.add_field(
                name="🔧 Effects",
                value="• Fuel efficiency reduced by 2\n• Radio communications impaired\n• Navigation accuracy decreased",
                inline=False
            )
        
        await channel.send(embed=embed)

    async def _handle_quantum_storm(self, location_id, players, location_name, event_name, description, color):
        """Handle quantum storm - reality distortions"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(title=f"⚡ {event_name}", description=description, color=color)
        
        # Random beneficial or harmful effects
        for player_id in players:
            if random.random() < 0.4:  # 40% chance per player
                effect_roll = random.random()
                
                if effect_roll < 0.3:  # Negative effect
                    damage = random.randint(5, 15)
                    self.bot.db.execute_query(
                        "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                        (damage, player_id)
                    )
                    effect_text = f"You get injured in the static fog storm: -{damage} HP"
                
                elif effect_roll < 0.6:  # Neutral effect
                    effect_text = "You suffer a headache from the Static Fog Storm."
                
                else:  # Positive effect
                    bonus_exp = random.randint(10, 30)
                    self.bot.db.execute_query(
                        "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                        (bonus_exp, player_id)
                    )
                    effect_text = f"You observe the static fog storm and learn: +{bonus_exp} experience"
                
                member = channel.guild.get_member(player_id)
                if member:
                    embed.add_field(name=f"⚡ {member.display_name}", value=effect_text, inline=True)
        
        await channel.send(embed=embed)

    async def _handle_asteroid_field(self, location_id, players, location_name, event_name, description, color):
        """Handle asteroid field - evasion challenge"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(title=f"☄️ {event_name}", description=description, color=color)
        
        view = AsteroidFieldView(self.bot, players)
        embed.add_field(
            name="🎯 Navigation Challenge",
            value="Each pilot must choose their evasion strategy. Poor choices may result in hull damage.",
            inline=False
        )
        
        await channel.send(embed=embed, view=view)

    async def _handle_gravity_anomaly(self, location_id, players, location_name, event_name, description, color):
        """Handle gravitational anomaly - potential displacement"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(title=f"🌀 {event_name}", description=description, color=color)
        
        # Small chance to transport players to random location
        displaced_players = []
        for player_id in players:
            if random.random() < 0.2:  # 20% chance
                # Get random location
                random_location = self.bot.db.execute_query(
                    "SELECT location_id, name FROM locations WHERE location_id != ? ORDER BY RANDOM() LIMIT 1",
                    (location_id,),
                    fetch='one'
                )
                
                if random_location:
                    new_loc_id, new_loc_name = random_location
                    self.bot.db.execute_query(
                        "UPDATE characters SET current_location = ? WHERE user_id = ?",
                        (new_loc_id, player_id)
                    )
                    
                    member = channel.guild.get_member(player_id)
                    if member:
                        displaced_players.append(f"{member.mention} → {new_loc_name}")
        
        if displaced_players:
            embed.add_field(
                name="🌀 Spatial Displacement",
                value="\n".join(displaced_players),
                inline=False
            )
        else:
            embed.add_field(
                name="🛡️ Result",
                value="All ships maintain position despite gravitational stress.",
                inline=False
            )
        
        await channel.send(embed=embed)

    async def _handle_radiation_nebula(self, location_id, players, location_name, event_name, description, color):
        """Handle radiation nebula - health hazard"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(title=f"☢️ {event_name}", description=description, color=color)
        
        # Apply radiation damage
        casualties = []
        for player_id in players:
            damage = random.randint(8, 20)
            hull_damage = random.randint(5, 15)
            
            self.bot.db.execute_query(
                "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                (damage, player_id)
            )
            self.bot.db.execute_query(
                "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                (hull_damage, player_id)
            )
            
            member = channel.guild.get_member(player_id)
            if member:
                casualties.append(f"{member.mention}: -{damage} HP, -{hull_damage} hull")
        
        embed.add_field(
            name="☢️ Radiation Exposure",
            value="\n".join(casualties) if casualties else "Minimal exposure detected",
            inline=False
        )
        
        embed.add_field(
            name="⚕️ Treatment Required",
            value="Seek medical attention at the nearest facility with medical services.",
            inline=False
        )
        
        await channel.send(embed=embed)

    async def _get_location_channel(self, location_id):
        """Get the Discord channel for a location"""
        channel_info = self.bot.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if channel_info and channel_info[0]:
            return self.bot.get_channel(channel_info[0])
        return None

    # Add these methods to enhance travel events in cogs/enhanced_events.py
    async def generate_travel_event(self, travel_session_data):
        """Generate events during travel based on corridor and ship data"""
        
        session_id, user_id, origin_id, dest_id, corridor_id, temp_channel_id = travel_session_data[:6]
        
        if not temp_channel_id:
            return None
        
        channel = self.bot.get_channel(temp_channel_id)
        if not channel:
            return None
        
        # Get corridor danger level
        corridor_info = self.bot.db.execute_query(
            "SELECT danger_level, name FROM corridors WHERE corridor_id = ?",
            (corridor_id,),
            fetch='one'
        )
        
        if not corridor_info:
            return None
        
        danger_level, corridor_name = corridor_info
        
        # Get traveler info
        char_data = self.bot.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return None
        
        # Select event type based on danger level
        travel_events = self._get_travel_events(danger_level)
        
        if not travel_events:
            return None
        
        import random
        selected_event = random.choice(travel_events)
        
        # Execute the travel event
        await self._execute_travel_event(channel, selected_event, user_id, corridor_name)
        
        return selected_event

    def _get_travel_events(self, danger_level: int):
        """Get travel events based on corridor danger level"""
        
        base_events = [
            {
                'name': 'Space Weather',
                'description': '🌪️ **Solar Wind Turbulence**\nYour ship encounters electromagnetic interference from solar activity.',
                'color': 0xffa500,
                'severity': 1,
                'interactive': False,
                'effects': ['minor_delay']
            },
            {
                'name': 'Debris Field',
                'description': '☄️ **Asteroid Debris Field**\nNavigating through scattered asteroid debris requires careful maneuvering.',
                'color': 0x8b4513,
                'severity': 2,
                'interactive': True,
                'handler': self._handle_debris_field,
                'effects': ['navigation_test']
            },
            {
                'name': 'Energy Readings',
                'description': '⚡ **Unknown Energy Signature**\nYour sensors detect unusual energy patterns ahead.',
                'color': 0x9400d3,
                'severity': 1,
                'interactive': True,
                'handler': self._handle_energy_readings,
                'effects': ['investigation_option']
            },
            {
                'name': 'Distress Signal',
                'description': '📡 **Distress Beacon Detected**\nA faint distress signal is being transmitted from nearby.',
                'color': 0xff4500,
                'severity': 2,
                'interactive': True,
                'handler': self._handle_distress_signal,
                'effects': ['rescue_option', 'potential_danger']
            },
            {
                'name': 'Trade Opportunity',
                'description': '🚛 **Independent Trader Encounter**\nA freelance merchant ship has hailed you with trade offers.',
                'color': 0x00ff00,
                'severity': 1,
                'interactive': True,
                'handler': self._handle_trade_encounter,
                'effects': ['trade_option']
            },
            {
                'name': 'Solar Flare',
                'description': '🌟 **Solar Flare Detected**\nMassive solar activity is interfering with ship systems and communications.',
                'color': 0xff4500,
                'severity': 2,
                'interactive': True,
                'handler': self._handle_travel_solar_flare,
                'effects': ['system_interference']
            },
            {
                'name': 'Quantum Storm',
                'description': '⚡ **Static Fog Storm**\nElectromagnetic interference is affecting ship systems.',
                'color': 0x9400d3,
                'severity': 3,
                'interactive': True,
                'handler': self._handle_travel_quantum_storm,
                'effects': ['quantum_effects']
            }
        ]
        
        # High danger corridors get additional dangerous events
        if danger_level >= 3:
            base_events.extend([
                {
                    'name': 'Pirate Patrol',
                    'description': '💀 **Pirate Scouts Detected**\nHostile vessels are patrolling this area.',
                    'color': 0x8b0000,
                    'severity': 4,
                    'interactive': True,
                    'handler': self._handle_travel_pirates,
                    'effects': ['combat_or_flee']
                },
                {
                    'name': 'Scavenger Swarm',
                    'description': '🤖 **Automated Scavengers**\nDrone swarms are scanning ships for salvageable materials.',
                    'color': 0x708090,
                    'severity': 3,
                    'interactive': True,
                    'handler': self._handle_scavenger_swarm,
                    'effects': ['defense_needed']
                },
                {
                    'name': 'Radiation Nebula',
                    'description': '☢️ **Radiation Cloud**\nHigh-energy particles detected ahead.',
                    'color': 0xff0000,
                    'severity': 4,
                    'interactive': True,
                    'handler': self._handle_travel_radiation_nebula,
                    'effects': ['radiation_damage']
                }
            ])
        
        # Very high danger corridors get extreme events
        if danger_level >= 4:
            base_events.extend([
                {
                    'name': 'Corporate Ambush',
                    'description': '🏢 **Corporate Enforcement**\nMega-corp security forces have set up a checkpoint.',
                    'color': 0x000080,
                    'severity': 4,
                    'interactive': True,
                    'handler': self._handle_corporate_ambush,
                    'effects': ['inspection_or_fight']
                }
            ])
        
        return base_events
    async def _handle_trade_encounter(self, channel, user_id, event_data):
        """Handle independent trader encounter"""
        embed = discord.Embed(
            title="🚛 Independent Trader Encounter",
            description="A freelance merchant ship has hailed you. They're offering various goods at competitive prices.",
            color=0x00ff00
        )
        
        view = discord.ui.View(timeout=300)
        
        trade_button = discord.ui.Button(
            label="Browse Goods",
            style=discord.ButtonStyle.success,
            emoji="🛒"
        )
        
        ignore_button = discord.ui.Button(
            label="Decline Trade",
            style=discord.ButtonStyle.secondary,
            emoji="👋"
        )
        
        async def trade_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, money FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, current_money = char_data
            
            trade_options = [
                ("Medical Supplies", 100, 150),
                ("Fuel Cells", 75, 125),
                ("Ship Parts", 200, 300),
                ("Information", 50, 100)
            ]
            
            selected_trade = random.choice(trade_options)
            item_name, cost, value = selected_trade
            
            if current_money >= cost:
                profit = value - cost
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (profit, user_id)
                )
                
                await interaction.response.send_message(
                    f"🛒 **{char_name}** trades for {item_name} (cost: {cost} credits, value: {value} credits). Net profit: {profit} credits!",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    f"💸 **{char_name}** lacks sufficient credits for any of the trader's offerings.",
                    ephemeral=False
                )
        
        async def ignore_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_name = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )[0]
            
            await interaction.response.send_message(
                f"👋 **{char_name}** politely declines the trade offer and continues on course.",
                ephemeral=False
            )
        
        trade_button.callback = trade_callback
        ignore_button.callback = ignore_callback
        
        view.add_item(trade_button)
        view.add_item(ignore_button)
        
        await channel.send(embed=embed, view=view)    
    async def _handle_energy_readings(self, channel, user_id, event_data):
        """Handle unknown energy signature encounter"""
        embed = discord.Embed(
            title="⚡ Unknown Energy Signature",
            description="Your sensors detect unusual energy patterns ahead. Investigation could be rewarding... or dangerous.",
            color=0x9400d3
        )
        
        view = discord.ui.View(timeout=300)
        
        investigate_button = discord.ui.Button(
            label="Investigate Energy Source",
            style=discord.ButtonStyle.primary,
            emoji="🔍"
        )
        
        avoid_button = discord.ui.Button(
            label="Avoid and Continue",
            style=discord.ButtonStyle.secondary,
            emoji="➡️"
        )
        
        async def investigate_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, engineering FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            
            discovery_roll = random.randint(1, 100)
            
            if discovery_roll <= 40:  # 40% chance of valuable discovery
                reward = random.randint(200, 500) + (eng_skill * 10)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, user_id)
                )
                
                await interaction.response.send_message(
                    f"⚡ **{char_name}** discovers an energy cache! Earned {reward} credits from the valuable find!",
                    ephemeral=False
                )
            elif discovery_roll <= 70:  # 30% chance of neutral outcome
                await interaction.response.send_message(
                    f"⚡ **{char_name}** investigates but finds only background radiation. No danger, no reward.",
                    ephemeral=False
                )
            else:  # 30% chance of danger
                damage = random.randint(10, 20)
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = GREATEST(1, hp - ?) WHERE user_id = ?",
                    (damage, user_id)
                )
                
                await interaction.response.send_message(
                    f"⚠️ **{char_name}** triggers an energy discharge! Took {damage} damage from the exposure!",
                    ephemeral=False
                )
        
        async def avoid_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            char_name = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )[0]
            
            await interaction.response.send_message(
                f"➡️ **{char_name}** decides discretion is the better part of valor and continues on course.",
                ephemeral=False
            )
        
        investigate_button.callback = investigate_callback
        avoid_button.callback = avoid_callback
        
        view.add_item(investigate_button)
        view.add_item(avoid_button)
        
        await channel.send(embed=embed, view=view)
    async def _handle_travel_pirates(self, channel, user_id, event_data):
        """Handle pirate encounter during travel"""
        embed = discord.Embed(
            title="💀 Pirate Patrol Detected",
            description="Hostile vessels are patrolling this corridor! They've detected your ship.",
            color=0x8b0000
        )
        
        view = discord.ui.View(timeout=300)
        
        fight_button = discord.ui.Button(
            label="Engage Pirates",
            style=discord.ButtonStyle.danger,
            emoji="⚔️"
        )
        
        evade_button = discord.ui.Button(
            label="Attempt Evasion",
            style=discord.ButtonStyle.primary,
            emoji="🏃"
        )
        
        async def fight_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, combat FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, combat_skill = char_data
            
            success_chance = min(80, 40 + combat_skill * 3)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                reward = random.randint(200, 500)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, user_id)
                )
                
                await interaction.response.send_message(
                    f"⚔️ **{char_name}** defeats the pirates in combat! Salvage worth {reward} credits recovered.",
                    ephemeral=False
                )
            else:
                damage = random.randint(15, 35)
                credits_lost = random.randint(100, 300)
                
                self.bot.db.execute_query(
                    "UPDATE characters SET hp = GREATEST(1, hp - ?), money = GREATEST(0, money - ?) WHERE user_id = ?",
                    (damage, credits_lost, user_id)
                )
                
                await interaction.response.send_message(
                    f"💥 **{char_name}** is defeated by the pirates! Lost {damage} health and {credits_lost} credits.",
                    ephemeral=False
                )
        
        async def evade_callback(interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                return
            
            char_data = self.bot.db.execute_query(
                "SELECT name, navigation FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, nav_skill = char_data
async def setup(bot):
    await bot.add_cog(EnhancedEventsCog(bot))