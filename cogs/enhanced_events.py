# cogs/enhanced_events.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from datetime import datetime, timedelta
import json
from typing import Optional, Literal

ACTIVE_EVENT_RESPONSES = {}

def track_event_response(event_id: str, user_id: int) -> bool:
    """Track if a user has already responded to an event. Returns True if this is their first response."""
    if event_id not in ACTIVE_EVENT_RESPONSES:
        ACTIVE_EVENT_RESPONSES[event_id] = set()
    
    if user_id in ACTIVE_EVENT_RESPONSES[event_id]:
        return False  # Already responded
    
    ACTIVE_EVENT_RESPONSES[event_id].add(user_id)
    return True  # First response

def clear_event_responses(event_id: str):
    """Clear response tracking for an event after it's done"""
    if event_id in ACTIVE_EVENT_RESPONSES:
        del ACTIVE_EVENT_RESPONSES[event_id]


class FugitiveAlertView(discord.ui.View):
    def __init__(self, bot, players, location_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.players = players
        self.location_id = location_id
        self.responded_users = []

    async def check_and_record_response(self, interaction: discord.Interaction) -> bool:
        """Checks if the user is part of the event and hasn't responded yet."""
        if interaction.user.id not in self.players:
            await interaction.response.send_message("You are not directly involved in this event.", ephemeral=True)
            return False
        if interaction.user.id in self.responded_users:
            await interaction.response.send_message("You have already responded to this event.", ephemeral=True)
            return False
        
        self.responded_users.append(interaction.user.id)
        return True

    @discord.ui.button(label="Assist Security", style=discord.ButtonStyle.success, emoji="🚔")
    async def assist_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_and_record_response(interaction):
            return

        char_data = self.bot.db.execute_query("SELECT name, combat FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
        char_name, combat_skill = char_data

        if combat_skill >= 15:
            bounty = random.randint(1000, 1500)
            self.bot.db.execute_query("UPDATE characters SET money = money + ? WHERE user_id = ?", (bounty, interaction.user.id))
            
            # --- Reputation Logic Start ---
            rep_cog = self.bot.get_cog('ReputationCog')
            if rep_cog:
                karma_change = 15
                await rep_cog.update_reputation(interaction.user.id, self.location_id, karma_change)
                await interaction.response.send_message(f"🚔 **{char_name}** assists Gate Security in a swift operation, disabling the fugitive's ship. The {bounty} credit bounty is transferred to your account. Your standing with local security has improved. (+{karma_change} reputation)", ephemeral=False)
            # --- Reputation Logic End ---
        else:
            await interaction.response.send_message(f"💨 The fugitive's ship gives **{char_name}** the slip during the confrontation. A valiant effort, but no reward.", ephemeral=False)

    @discord.ui.button(label="Help Fugitive Escape", style=discord.ButtonStyle.danger, emoji="🤫")
    async def help_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_and_record_response(interaction):
            return

        char_data = self.bot.db.execute_query("SELECT name, navigation FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
        char_name, nav_skill = char_data

        if nav_skill >= 15:
            reward = random.randint(2000, 3000)
            self.bot.db.execute_query("UPDATE characters SET money = money + ? WHERE user_id = ?", (reward, interaction.user.id))
            
            # --- Reputation Logic Start ---
            rep_cog = self.bot.get_cog('ReputationCog')
            if rep_cog:
                karma_change = -20
                await rep_cog.update_reputation(interaction.user.id, self.location_id, karma_change)
                await interaction.response.send_message(f"🤫 **{char_name}** creates a diversion, allowing the fugitive to slip through the security net. A coded message arrives later with a {reward} credit 'thank you' payment. Your reputation with law-abiding citizens has suffered. ({karma_change} reputation)", ephemeral=False)
            # --- Reputation Logic End ---
        else:
            fine = 500
            self.bot.db.execute_query("UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?", (fine, interaction.user.id))
            await interaction.response.send_message(f"🚨 **{char_name}**'s attempt to help the fugitive is clumsy and obvious. You're caught and fined {fine} credits for obstructing justice.", ephemeral=False)

    @discord.ui.button(label="Ignore Alert", style=discord.ButtonStyle.secondary, emoji="👀")
    async def ignore_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_and_record_response(interaction):
            return
            
        char_name = self.bot.db.execute_query("SELECT name FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')[0]
        await interaction.response.send_message(f"👀 **{char_name}** decides this situation is too hot to handle and stays out of it.", ephemeral=False)
        








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
                if datetime.now() - last_time < timedelta(minutes=5):
                    continue  # Too recent
            
            # Random chance based on location activity and type
            base_chance = {
                'colony': 0.50,
                'space_station': 0.40,
                'outpost': 0.35,
                'gate': 0.30
            }.get(loc_type, 0.50)
            
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
            event_chance = 0.25 + (danger_level * 0.1)
            
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
            ("Quantum Storm", "⚡ **Static Fog Storm Approaching!**\nTechnological distortions detected. Navigation and sensor systems may be affected.", 0x9400d3, self._handle_travel_quantum_storm),
            ("Asteroid Field", "☄️ **Asteroid Field Detected!**\nMultiple objects on collision course. Evasive maneuvers required.", 0x8b4513, self._handle_debris_field),
            ("Gravitational Anomaly", "🌀 **Gravitational Anomaly!**\nSpace-time distortion detected. Ships may experience temporal displacement.", 0x4b0082, self._handle_gravity_anomaly),
            ("Radiation Nebula", "☢️ **Radiation cloud Encountered!**\nHigh-energy particles detected. Hull integrity and crew health at risk.", 0xff0000, self._handle_travel_radiation_nebula)
        ]
        
        # Pirate/hostile encounters (more likely in dangerous areas)
        hostile_encounters = [
            ("Pirate Raiders", "💀 **Pirate Raiders Detected!**\nHostile ships on intercept course. Prepare for combat or evasion.", 0x8b0000, self._handle_pirate_encounter),
            ("Scavenger Drones", "🤖 **Automated Scavengers!**\nRogue mining drones attempting to strip-mine your ship. Defensive measures required.", 0x708090, self._handle_scavenger_encounter),
            ("Corporate Security", "🚔 **Corporate Security Patrol!**\nMega-corp enforcement demanding inspection. Compliance or resistance?", 0x000080, self._handle_security_encounter),
            ("Desperate Refugees", "😰 **Desperate Refugees!**\nRefugee ship requesting aid. They claim pirates destroyed their home.", 0x8fbc8f, self._handle_refugee_encounter)
        ]
        
        # Calculate event chances based on location characteristics
        # Calculate event chances based on location characteristics
        phenomena_chance = 0.35  # Was 0.25
        hostile_chance = 0.30    # Was 0.15
        reputation_chance = 0.35  # Was 0.20
        
        # Increase hostile chances in dangerous areas
        edge_distance = (x_coord**2 + y_coord**2)**0.5
        if edge_distance > 70:  # Far from center
            hostile_chance += 0.15
            reputation_chance += 0.15
        if wealth <= 3:  # Poor areas
            hostile_chance += 0.1
        reputation_chance += 0.05
        if edge_distance < 20:
            reputation_chance -= 0.15
            hostile_chance -= 0.20
        # Determine event type
        event_roll = random.random()
        
        if event_roll < reputation_chance:
            await self.generate_reputation_event(location_id, players_present)
        elif event_roll < reputation_chance + hostile_chance:
            event_name, description, color, handler = random.choice(hostile_encounters)
            await handler(location_id, players_present, location_name, event_name, description, color)
        elif event_roll < reputation_chance + hostile_chance + phenomena_chance:
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
        
    async def _handle_scavenger_encounter(self, location_id, players, location_name, event_name, description, color):
        """Handle scavenger drone encounter during travel"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title=f"🤖 {event_name}",
            description=f"{description}\n\n**Location:** {location_name}",
            color=color
        )
        
        # Determine drone swarm strength
        drone_count = min(5, max(2, len(players) + random.randint(0, 2)))
        
        embed.add_field(
            name="🔧 Hostile Drones",
            value=f"{drone_count} scavenger drone{'s' if drone_count > 1 else ''} detected",
            inline=True
        )
        
        embed.add_field(
            name="⚡ Options",
            value="• Deploy countermeasures\n• Attempt evasion\n• Sacrifice cargo\n• Fight them off",
            inline=True
        )
        
        # Select a random player for the encounter
        if players:
            user_id = random.choice(players)[0]
            
            view = discord.ui.View(timeout=300)
            
            countermeasures_button = discord.ui.Button(
                label="Deploy Countermeasures",
                style=discord.ButtonStyle.primary,
                emoji="🛡️"
            )
            
            evade_button = discord.ui.Button(
                label="Evasive Maneuvers",
                style=discord.ButtonStyle.secondary,
                emoji="🚀"
            )
            
            sacrifice_button = discord.ui.Button(
                label="Jettison Cargo",
                style=discord.ButtonStyle.success,
                emoji="📦"
            )
            
            fight_button = discord.ui.Button(
                label="Fight Drones",
                style=discord.ButtonStyle.danger,
                emoji="⚔️"
            )
            
            async def countermeasures_callback(interaction):
                if interaction.user.id != user_id:
                    await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                    return
                
                char_data = self.bot.db.execute_query(
                    "SELECT name, tech FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name, tech_skill = char_data
                
                if tech_skill >= 10:
                    await interaction.response.send_message(
                        f"🛡️ **{char_name}** successfully deploys electronic countermeasures! The drones' systems are scrambled and they drift away harmlessly.",
                        ephemeral=False
                    )
                else:
                    damage = random.randint(10, 20)
                    self.bot.db.execute_query(
                        "UPDATE ships SET hull_integrity = MAX(0, hull_integrity - ?) WHERE owner_id = ?",
                        (damage, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"⚡ **{char_name}** deploys countermeasures but they're only partially effective! Ship takes {damage} hull damage from drone attacks.",
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
                
                if nav_skill >= 12:
                    await interaction.response.send_message(
                        f"🚀 **{char_name}** executes brilliant evasive maneuvers! The drones can't keep up and fall behind.",
                        ephemeral=False
                    )
                else:
                    fuel_lost = random.randint(20, 40)
                    self.bot.db.execute_query(
                        "UPDATE ships SET current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
                        (fuel_lost, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"💨 **{char_name}** burns {fuel_lost} fuel in desperate evasive maneuvers to escape the persistent drones!",
                        ephemeral=False
                    )
            
            async def sacrifice_callback(interaction):
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
                cargo_value = random.randint(100, 300)
                
                if current_money >= cargo_value:
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money - ? WHERE user_id = ?",
                        (cargo_value, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"📦 **{char_name}** jettisons {cargo_value} credits worth of cargo! The drones stop to collect it, allowing safe passage.",
                        ephemeral=False
                    )
                else:
                    await interaction.response.send_message(
                        f"📦 **{char_name}** has nothing valuable to jettison! The drones continue their approach.",
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
                
                if random.random() < (0.4 + combat_skill * 0.02):
                    salvage = random.randint(150, 400)
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = money + ? WHERE user_id = ?",
                        (salvage, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"⚔️ **{char_name}** destroys the scavenger drones! Salvaged {salvage} credits worth of components from the wreckage.",
                        ephemeral=False
                    )
                else:
                    damage = random.randint(20, 40)
                    self.bot.db.execute_query(
                        "UPDATE ships SET hull_integrity = MAX(0, hull_integrity - ?) WHERE owner_id = ?",
                        (damage, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"💥 **{char_name}** fights valiantly but the drones overwhelm the ship's defenses! Hull takes {damage} damage.",
                        ephemeral=False
                    )
            
            countermeasures_button.callback = countermeasures_callback
            evade_button.callback = evade_callback
            sacrifice_button.callback = sacrifice_callback
            fight_button.callback = fight_callback
            
            view.add_item(countermeasures_button)
            view.add_item(evade_button)
            view.add_item(sacrifice_button)
            view.add_item(fight_button)
            
            await channel.send(embed=embed, view=view)
            
    async def _handle_refugee_encounter(self, location_id, players, location_name, event_name, description, color):
        """Handle refugee ship encounter during travel"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title=f"😰 {event_name}",
            description=f"{description}\n\n**Location:** {location_name}",
            color=color
        )
        
        # Determine refugee ship status
        refugee_count = random.randint(20, 60)
        ship_damage = random.randint(40, 80)  # Percentage of damage
        
        embed.add_field(
            name="📊 Refugee Status",
            value=f"• {refugee_count} refugees aboard\n• Ship hull at {100-ship_damage}% integrity\n• Critical supplies depleted",
            inline=True
        )
        
        embed.add_field(
            name="🆘 Options",
            value="• Provide aid and supplies\n• Offer medical assistance\n• Share fuel and repairs\n• Turn them away",
            inline=True
        )
        
        # Select a random player for the encounter
        if players:
            user_id = random.choice(players)[0]
            
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
            
            fuel_button = discord.ui.Button(
                label="Share Fuel",
                style=discord.ButtonStyle.primary,
                emoji="⛽"
            )
            
            reject_button = discord.ui.Button(
                label="Turn Away",
                style=discord.ButtonStyle.danger,
                emoji="❌"
            )
            
            async def aid_callback(interaction):
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
                
                char_name, money = char_data
                
                cost = random.randint(100, 300)
                if money < cost:
                    await interaction.response.send_message(
                        f"💸 **{char_name}** wants to help but lacks the {cost} credits needed for supplies.",
                        ephemeral=False
                    )
                    return
                
                # Deduct cost, gain reputation
                rep_gain = random.randint(15, 25)
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money - ?, major_reputation = major_reputation + ? WHERE user_id = ?",
                    (cost, rep_gain, user_id)
                )
                
                await interaction.response.send_message(
                    f"🤲 **{char_name}** provides essential supplies to the refugees, spending {cost} credits. The refugees are deeply grateful! (+{rep_gain} reputation)",
                    ephemeral=False
                )
            
            async def medical_callback(interaction):
                if interaction.user.id != user_id:
                    await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                    return
                
                char_data = self.bot.db.execute_query(
                    "SELECT name, medicine FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name, medicine_skill = char_data
                
                success_chance = min(90, 50 + medicine_skill * 3)
                roll = random.randint(1, 100)
                
                if roll <= success_chance:
                    rep_gain = 10 + medicine_skill // 2
                    self.bot.db.execute_query(
                        "UPDATE characters SET major_reputation = major_reputation + ? WHERE user_id = ?",
                        (rep_gain, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"⚕️ **{char_name}** successfully treats the injured refugees! Their medical expertise saves lives. (+{rep_gain} reputation)",
                        ephemeral=False
                    )
                else:
                    await interaction.response.send_message(
                        f"⚕️ **{char_name}** does their best to help the injured, providing basic first aid.",
                        ephemeral=False
                    )
            
            async def fuel_callback(interaction):
                if interaction.user.id != user_id:
                    await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                    return
                
                # Check if player has a ship with fuel
                ship_data = self.bot.db.execute_query(
                    "SELECT s.ship_id, s.name, s.fuel FROM ships s WHERE s.owner_id = ?",
                    (user_id,),
                    fetch='one'
                )
                
                if not ship_data:
                    await interaction.response.send_message("You need a ship to share fuel!", ephemeral=True)
                    return
                
                ship_id, ship_name, current_fuel = ship_data
                char_name = self.bot.db.execute_query(
                    "SELECT name FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )[0]
                
                fuel_to_share = random.randint(20, 40)
                if current_fuel < fuel_to_share:
                    await interaction.response.send_message(
                        f"⛽ **{char_name}** doesn't have enough fuel to share. Need at least {fuel_to_share} units.",
                        ephemeral=False
                    )
                    return
                
                rep_gain = random.randint(10, 20)
                self.bot.db.execute_query(
                    "UPDATE ships SET fuel = fuel - ? WHERE ship_id = ?",
                    (fuel_to_share, ship_id)
                )
                self.bot.db.execute_query(
                    "UPDATE characters SET major_reputation = major_reputation + ? WHERE user_id = ?",
                    (rep_gain, user_id)
                )
                
                await interaction.response.send_message(
                    f"⛽ **{char_name}** transfers {fuel_to_share} fuel units to the refugee ship, enabling them to reach safety. (+{rep_gain} reputation)",
                    ephemeral=False
                )
            
            async def reject_callback(interaction):
                if interaction.user.id != user_id:
                    await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                    return
                
                char_name = self.bot.db.execute_query(
                    "SELECT name FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )[0]
                
                rep_loss = random.randint(5, 15)
                self.bot.db.execute_query(
                    "UPDATE characters SET minor_reputation = MAX(0, minor_reputation - ?) WHERE user_id = ?",
                    (rep_loss, user_id)
                )
                
                await interaction.response.send_message(
                    f"❌ **{char_name}** coldly ignores the refugees' desperate pleas and continues on course. Word of this callousness spreads. (-{rep_loss} reputation)",
                    ephemeral=False
                )
            
            aid_button.callback = aid_callback
            medical_button.callback = medical_callback
            fuel_button.callback = fuel_callback
            reject_button.callback = reject_callback
            
            view.add_item(aid_button)
            view.add_item(medical_button)
            view.add_item(fuel_button)
            view.add_item(reject_button)
            
            await channel.send(embed=embed, view=view)  
    
    async def _handle_fugitive_alert(self, channel, players, event_data, location_id):
        """Handle fugitive alert event"""
        embed = discord.Embed(
            title="🎯 Fugitive Transit Alert",
            description="Gate Security offers a bounty for a wanted fugitive in the area. This is a chance for profit or to make powerful enemies.",
            color=event_data['color']
        )
        
        # Get the user_ids from the list of player tuples
        player_ids = [p[0] for p in players]
        
        view = FugitiveAlertView(self.bot, player_ids, location_id)
        
        await channel.send(embed=embed, view=view)
        
    async def _handle_security_encounter(self, location_id, players, location_name, event_name, description, color):
        """Handle corporate security patrol encounter during travel"""
        
        channel = await self._get_location_channel(location_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title=f"🚔 {event_name}",
            description=f"{description}\n\n**Location:** {location_name}",
            color=color
        )
        
        # Determine security force strength
        security_ships = min(2, max(1, len(players) // 3 + random.randint(0, 1)))
        
        embed.add_field(
            name="🏢 Corporate Forces",
            value=f"{security_ships} security vessel{'s' if security_ships > 1 else ''} approaching",
            inline=True
        )
        
        embed.add_field(
            name="📋 Options",
            value="• Submit to inspection\n• Offer bribe\n• Show credentials\n• Resist inspection",
            inline=True
        )
        
        # Select a random player for the encounter
        if players:
            user_id = random.choice(players)[0]
            
            view = discord.ui.View(timeout=300)
            
            submit_button = discord.ui.Button(
                label="Submit to Inspection",
                style=discord.ButtonStyle.secondary,
                emoji="📋"
            )
            
            bribe_button = discord.ui.Button(
                label="Offer Bribe",
                style=discord.ButtonStyle.success,
                emoji="💰"
            )
            
            credentials_button = discord.ui.Button(
                label="Show Credentials",
                style=discord.ButtonStyle.primary,
                emoji="🆔"
            )
            
            resist_button = discord.ui.Button(
                label="Resist Inspection",
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
                
                # Random outcome - might find "contraband"
                if random.random() < 0.25:
                    fine = random.randint(200, 500)
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
                        (fine, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"📋 **{char_name}** submits to inspection. Security claims to find 'irregularities' but says they'll look the other way if you pay {fine} ",
                        ephemeral=False
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ **{char_name}** submits to inspection. After a thorough search, security finds nothing and allows passage.",
                        ephemeral=False
                    )
            
            async def bribe_callback(interaction):
                if interaction.user.id != user_id:
                    await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                    return
                
                char_data = self.bot.db.execute_query(
                    "SELECT name, money, diplomacy FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name, current_money, diplomacy_skill = char_data
                bribe_amount = random.randint(150, 350)
                
                if current_money >= bribe_amount:
                    success_chance = 0.5 + (diplomacy_skill * 0.03)
                    
                    if random.random() < success_chance:
                        self.bot.db.execute_query(
                            "UPDATE characters SET money = money - ? WHERE user_id = ?",
                            (bribe_amount, user_id)
                        )
                        
                        await interaction.response.send_message(
                            f"💰 **{char_name}** slips {bribe_amount} credits to the security captain. The patrol waves them through without inspection.",
                            ephemeral=False
                        )
                    else:
                        fine = bribe_amount * 2
                        self.bot.db.execute_query(
                            "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
                            (fine, user_id)
                        )
                        
                        await interaction.response.send_message(
                            f"🚨 **{char_name}**'s bribe attempt is rejected! Security issues a {fine} credit fine for attempted corruption.",
                            ephemeral=False
                        )
                else:
                    await interaction.response.send_message(
                        f"💸 **{char_name}** doesn't have enough credits to offer a meaningful bribe.",
                        ephemeral=False
                    )
            
            async def credentials_callback(interaction):
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
                
                # Check for any corporate reputation or connections
                rep_cog = self.bot.get_cog('ReputationCog')
                if rep_cog:
                    # Get average reputation
                    reputations = self.bot.db.execute_query(
                        "SELECT AVG(reputation_value) FROM reputation WHERE character_id = ?",
                        (user_id,),
                        fetch='one'
                    )
                    
                    avg_rep = reputations[0] if reputations[0] else 0
                    
                    if avg_rep >= 50:
                        await interaction.response.send_message(
                            f"🆔 **{char_name}** presents credentials showing good standing. Security respectfully waves them through.",
                            ephemeral=False
                        )
                        return
                
                await interaction.response.send_message(
                    f"🆔 **{char_name}** shows credentials, but security remains unimpressed and insists on a full inspection.",
                    ephemeral=False
                )
            
            async def resist_callback(interaction):
                if interaction.user.id != user_id:
                    await interaction.response.send_message("This isn't your encounter!", ephemeral=True)
                    return
                
                char_data = self.bot.db.execute_query(
                    "SELECT name, combat, navigation FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )
                
                if not char_data:
                    await interaction.response.send_message("Character not found!", ephemeral=True)
                    return
                
                char_name, combat_skill, nav_skill = char_data
                
                # Higher chance to escape than win fight
                escape_chance = 0.4 + (nav_skill * 0.03)
                
                if random.random() < escape_chance:
                    fuel_cost = random.randint(30, 60)
                    self.bot.db.execute_query(
                        "UPDATE ships SET current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
                        (fuel_cost, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"🚀 **{char_name}** makes a run for it! Burns {fuel_cost} fuel but successfully evades corporate security.",
                        ephemeral=False
                    )
                else:
                    damage = random.randint(25, 50)
                    fine = random.randint(500, 1000)
                    
                    self.bot.db.execute_query(
                        "UPDATE ships SET hull_integrity = MAX(0, hull_integrity - ?) WHERE owner_id = ?",
                        (damage, user_id)
                    )
                    
                    self.bot.db.execute_query(
                        "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
                        (fine, user_id)
                    )
                    
                    await interaction.response.send_message(
                        f"💥 **{char_name}** tries to escape but is disabled by security! Ship takes {damage} damage and receives a {fine} credit fine.",
                        ephemeral=False
                    )
            
            submit_button.callback = submit_callback
            bribe_button.callback = bribe_callback
            credentials_button.callback = credentials_callback
            resist_button.callback = resist_callback
            
            view.add_item(submit_button)
            view.add_item(bribe_button)
            view.add_item(credentials_button)
            view.add_item(resist_button)
            
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
                            "UPDATE dynamic_npcs SET credits = MAX(0, credits - ?) WHERE npc_id = ?",
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
                            "UPDATE dynamic_npcs SET credits = MAX(0, credits - ?) WHERE npc_id = ?",
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
                                "UPDATE dynamic_npcs SET credits = MAX(0, credits - ?) WHERE npc_id = ?",
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
                'name': 'Equipment Malfunction',
                'description': '⚙️ **Station Systems Failure**\nCritical station systems are malfunctioning. Technical expertise needed.',
                'color': 0xff0000,
                'event_type': 'negative',
                'base_probability': 0.15 if wealth <= 5 else 0.08,
                'interactive': True,
                'handler': self._handle_equipment_malfunction,
                'effects': {'repair_demand': 3, 'danger_level': 1}
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
            },
                        {
                'name': 'Priority Convoy Passage',
                'description': '📇 **Priority Convoy Passage**\nA heavily escorted military convoy is demanding immediate gate access, causing significant traffic delays. They are offering payment for assistance in clearing their path.',
                'color': 0x4169e1,
                'event_type': 'neutral',
                'base_probability': 0.12,
                'interactive': True,
                'handler': self._handle_priority_convoy
            },
            {
                'name': 'Gate Energy Surge',
                'description': '🔌 **Gate Energy Surge**\nThe gate\'s energy core is experiencing a critical power surge! Emergency containment teams are requesting assistance from any qualified engineers in the area before the field collapses.',
                'color': 0xffa500,
                'event_type': 'negative',
                'base_probability': 0.09,
                'interactive': True,
                'handler': self._handle_gate_energy_surge
            },
            {
                'name': 'Fugitive Transit Alert',
                'description': '⛓️‍💥 **Fugitive Transit Alert**\nGate Security has issued an alert: a high-profile fugitive is believed to be transiting the area aboard a nondescript freighter. A substantial bounty is offered for their capture.',
                'color': 0x8b0000,
                'event_type': 'neutral',
                'base_probability': 0.07,
                'interactive': True,
                'handler': self._handle_fugitive_alert
            },
            {
                'name': 'Spacetime Echo',
                'description': '🌫️ **Spacetime Echo**\nThe gate\'s spatial displacement field has created a temporary spacetime echo. A faint, ghostly image of a ship that passed through long ago flickers in and out of existence.',
                'color': 0x9932cc,
                'event_type': 'mysterious',
                'base_probability': 0.05,
                'interactive': True,
                'handler': self._handle_spacetime_echo
            }
        ]

    async def _handle_priority_convoy(self, channel, players, event_data):
        """Handle priority convoy event at a gate"""
        embed = discord.Embed(
            title="🚦 Priority Convoy Passage",
            description="A military convoy is causing traffic delays and needs assistance. Your actions can speed things up or create complications.",
            color=event_data['color']
        )

        view = discord.ui.View(timeout=300)
        event_id = f"priorityconvoy_{channel.id}_{datetime.now().timestamp()}"
        assist_button = discord.ui.Button(label="Assist Escort", style=discord.ButtonStyle.primary, emoji="🚀")
        scan_button = discord.ui.Button(label="Scan Convoy", style=discord.ButtonStyle.secondary, emoji="📡")
        wait_button = discord.ui.Button(label="Wait Patiently", style=discord.ButtonStyle.success, emoji="⏳")

        async def assist_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_data = self.bot.db.execute_query("SELECT name, navigation FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return

            char_name, nav_skill = char_data
            if nav_skill >= 12:
                reward = random.randint(200, 350) + (nav_skill * 10)
                self.bot.db.execute_query("UPDATE characters SET money = money + ? WHERE user_id = ?", (reward, interaction.user.id))
                await interaction.response.send_message(f"🚀 **{char_name}** skillfully assists the convoy escort, clearing a path through the congestion. The convoy commander sends you {reward} credits for your trouble.", ephemeral=False)
            else:
                await interaction.response.send_message(f"⚠️ **{char_name}** tries to help, but your maneuvers only add to the traffic chaos. The escort waves you off.", ephemeral=False)

        async def scan_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
            char_data = self.bot.db.execute_query("SELECT name, engineering FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            if eng_skill >= 15:
                await interaction.response.send_message(f"📡 **{char_name}** discretely scans the convoy. The ships are running hot with high-energy weapon signatures and what appears to be classified cyberwarfare suites. This is a serious military force.", ephemeral=False)
            else:
                fine = 150
                self.bot.db.execute_query("UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?", (fine, interaction.user.id))
                await interaction.response.send_message(f"🚨 **{char_name}**'s scan is detected by the convoy's counter-intel systems! You receive a warning and a {fine} credit fine for unauthorized scanning of military assets.", ephemeral=False)

        async def wait_callback(interaction: discord.Interaction):
            char_name = self.bot.db.execute_query("SELECT name FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')[0]
            await interaction.response.send_message(f"⏳ **{char_name}** decides to wait out the delay. The convoy eventually passes, and normal traffic resumes.", ephemeral=False)
            # Set up timeout to clear tracking
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout
        assist_button.callback = assist_callback
        scan_button.callback = scan_callback
        wait_button.callback = wait_callback

        view.add_item(assist_button)
        view.add_item(scan_button)
        view.add_item(wait_button)
        
        await channel.send(embed=embed, view=view)

    async def _handle_gate_energy_surge(self, channel, players, event_data):
        """Handle gate energy surge event"""
        embed = discord.Embed(
            title="⚠️ Gate Energy Surge",
            description="The gate's core is surging with energy! A containment failure is imminent without skilled intervention.",
            color=event_data['color']
        )
        
        view = discord.ui.View(timeout=300)
        event_id = f"energysurge_{channel.id}_{datetime.now().timestamp()}"
        contain_button = discord.ui.Button(label="Help Contain Surge", style=discord.ButtonStyle.danger, emoji="🔧")
        shields_button = discord.ui.Button(label="Reinforce Shields", style=discord.ButtonStyle.primary, emoji="🛡️")
        evacuate_button = discord.ui.Button(label="Evacuate Area", style=discord.ButtonStyle.secondary, emoji="🏃")

        async def contain_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return
            char_data = self.bot.db.execute_query("SELECT name, engineering FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return
            
            char_name, eng_skill = char_data
            if eng_skill >= 18:
                reward = random.randint(500, 750) + (eng_skill * 20)
                self.bot.db.execute_query("UPDATE characters SET money = money + ? WHERE user_id = ?", (reward, interaction.user.id))
                await interaction.response.send_message(f"🔧 **{char_name}**'s expert engineering assistance helps stabilize the gate's energy core, preventing a catastrophe! Gate authorities award you {reward} credits.", ephemeral=False)
            else:
                damage = random.randint(15, 30)
                self.bot.db.execute_query("UPDATE ships SET hull_integrity = MAX(0, hull_integrity - ?) WHERE owner_id = ?", (damage, interaction.user.id))
                await interaction.response.send_message(f"💥 **{char_name}** attempts to help but is caught in an energy discharge! The ship takes {damage} hull damage.", ephemeral=False)

        async def shields_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return
            char_data = self.bot.db.execute_query("SELECT name, engineering FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return

            char_name, eng_skill = char_data
            reward = 150 + (eng_skill * 5)
            self.bot.db.execute_query("UPDATE characters SET money = money + ? WHERE user_id = ?", (reward, interaction.user.id))
            await interaction.response.send_message(f"🛡️ **{char_name}** helps reinforce the shields of nearby civilian ships, earning a {reward} credit reward from Gate Traffic Control for their service.", ephemeral=False)
            
        async def evacuate_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_name = self.bot.db.execute_query("SELECT name FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')[0]
            await interaction.response.send_message(f"🏃 **{char_name}** wisely moves their ship to a safe distance to watch the events unfold.", ephemeral=False)
        
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout
        contain_button.callback = contain_callback
        shields_button.callback = shields_callback
        evacuate_button.callback = evacuate_callback

        view.add_item(contain_button)
        view.add_item(shields_button)
        view.add_item(evacuate_button)

        await channel.send(embed=embed, view=view)
        
    async def _handle_spacetime_echo(self, channel, players, event_data):
        """Handle spacetime echo event"""
        embed = discord.Embed(
            title="🌀 Spacetime Echo",
            description="A ghostly image of a long-lost vessel flickers near the gate. It seems harmless, but it's an irresistible scientific curiosity.",
            color=event_data['color']
        )
        view = discord.ui.View(timeout=300)
        event_id = f"spacetimecho_{channel.id}_{datetime.now().timestamp()}"
        analyze_button = discord.ui.Button(label="Analyze Echo", style=discord.ButtonStyle.primary, emoji="🔬")
        hail_button = discord.ui.Button(label="Hail the Echo", style=discord.ButtonStyle.secondary, emoji="👋")
        fly_button = discord.ui.Button(label="Fly Through It", style=discord.ButtonStyle.danger, emoji="✨")

        async def analyze_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_data = self.bot.db.execute_query("SELECT name, engineering FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')
            if not char_data:
                await interaction.response.send_message("Character not found!", ephemeral=True)
                return

            char_name, eng_skill = char_data
            if eng_skill >= 12:
                reward = random.randint(250, 500)
                self.bot.db.execute_query("UPDATE characters SET money = money + ? WHERE user_id = ?", (reward, interaction.user.id))
                await interaction.response.send_message(f"🔬 **{char_name}** collects valuable temporal data from the echo, selling it to a research outpost for {reward} credits.", ephemeral=False)
            else:
                await interaction.response.send_message(f"📉 **{char_name}**'s sensors can't make sense of the temporal distortions. The data is unusable.", ephemeral=False)

        async def hail_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_name = self.bot.db.execute_query("SELECT name FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')[0]
            await interaction.response.send_message(f"👋 **{char_name}** hails the echo. You receive only static, but for a moment, you think you hear a faint whisper... *'...left something behind...'* The echo then fades.", ephemeral=False)
            
        async def fly_callback(interaction: discord.Interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_name = self.bot.db.execute_query("SELECT name FROM characters WHERE user_id = ?", (interaction.user.id,), fetch='one')[0]
            roll = random.random()
            if roll < 0.25: # 25% chance of damage
                damage = random.randint(5, 10)
                self.bot.db.execute_query("UPDATE ships SET hull_integrity = MAX(0, hull_integrity - ?) WHERE owner_id = ?", (damage, interaction.user.id))
                await interaction.response.send_message(f"💥 **{char_name}** flies through the echo and a wave of temporal feedback rattles the ship! It takes {damage} hull damage.", ephemeral=False)
            elif roll > 0.9: # 10% chance of a boon
                fuel_gain = random.randint(10, 20)
                self.bot.db.execute_query("UPDATE ships SET current_fuel = current_fuel + ? WHERE owner_id = ?", (fuel_gain, interaction.user.id))
                await interaction.response.send_message(f"✨ **{char_name}** flies through the echo and the ship's fuel cells are mysteriously replenished, gaining {fuel_gain} fuel!", ephemeral=False)
            else: # 65% chance of nothing
                await interaction.response.send_message(f"💨 **{char_name}** flies through the echo. The ship feels momentarily cold, but nothing else happens.", ephemeral=False)

        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout
        analyze_button.callback = analyze_callback
        hail_button.callback = hail_callback
        fly_button.callback = fly_callback

        view.add_item(analyze_button)
        view.add_item(hail_button)
        view.add_item(fly_button)

        await channel.send(embed=embed, view=view)


        
    async def _handle_industrial_accident(self, channel, players, event_data):
        """Handle industrial accident event"""
        embed = discord.Embed(
            title="🏭 Industrial Emergency Response",
            description="A serious accident has occurred at the processing facility. Lives are at stake!",
            color=0xff4444
        )
        
        view = discord.ui.View(timeout=300)
        event_id = f"industrialaccident_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_name = se        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_name = se        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
            char_name = se        
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
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout        
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
        event_id = f"workerstrike_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return                  
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return              
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return              
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
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout              
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
        event_id = f"droneswarm_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return           
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
            
            # Rebalanced skill check
            success_chance = min(90, 40 + (eng_skill - 10) * 2.5)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"🛡️ **{char_name}** successfully activates ship defenses, repelling the scavenger drones!",
                    ephemeral=False
                )
            else:
                damage = random.randint(5, 15)
                self.bot.db.execute_query(
                    "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                    (damage, user_id)
                )
                
                await interaction.response.send_message(
                    f"🤖 **{char_name}**'s defenses fail! Scavenger drones strip {damage} hull integrity from the ship.",
                    ephemeral=False
                )
        
        async def outrun_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return           
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
            
            # Rebalanced skill check
            success_chance = min(90, 50 + (nav_skill - 10) * 2)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"🚀 **{char_name}** successfully outruns the scavenger swarm!",
                    ephemeral=False
                )
            else:
                fuel_lost = random.randint(15, 30)
                self.bot.db.execute_query(
                    "UPDATE ships SET current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
                    (fuel_lost, user_id)
                )
                
                await interaction.response.send_message(
                    f"🤖 **{char_name}** burns {fuel_lost} extra fuel trying to escape the persistent drones!",
                    ephemeral=False
                )
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout            
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
        event_id = f"corpambush_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return            
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
                    "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return             
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
                        "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return             
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
            
            # Rebalanced skill check
            success_chance = min(85, 30 + (combat_skill - 10) * 2.5)
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
                    "UPDATE characters SET hp = MAX(1, hp - ?), money = MAX(0, money - ?) WHERE user_id = ?",
                    (damage, credits_lost, user_id)
                )
                
                await interaction.response.send_message(
                    f"💥 **{char_name}** is overwhelmed by corporate security! Lost {damage} health and {credits_lost} credits in fines and 'damages'.",
                    ephemeral=False
                )
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout         
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
        event_id = f"asteroidfield_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
            
            # Rebalanced skill check
            success_chance = min(98, 60 + (navigation_skill - 10) * 2)
            roll = random.randint(1, 100)
            
            if roll <= success_chance:
                await interaction.response.send_message(
                    f"🧭 **{char_name}** expertly navigates through the debris field without incident. Extra fuel efficiency gained!",
                    ephemeral=False
                )
                # Bonus: Reduce fuel consumption for this trip
                self.bot.db.execute_query(
                    "UPDATE ships SET current_fuel = current_fuel + 5 WHERE owner_id = ?",
                    (user_id,)
                )
            else:
                damage = random.randint(5, 15)
                self.bot.db.execute_query(
                    "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                    (damage, user_id)
                )
                await interaction.response.send_message(
                    f"💥 Despite careful navigation, **{char_name}**'s ship scrapes against debris. Hull takes {damage} damage.",
                    ephemeral=False
                )
        
        async def speed_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
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
            
            # Rebalanced skill check
            success_chance = min(85, 40 + (navigation_skill - 10) * 2)
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
                self.bot.db.execute_query(
                    "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?), current_fuel = MAX(0, current_fuel - ?) WHERE owner_id = ?",
                    (damage, fuel_loss, user_id)
                )
                await interaction.response.send_message(
                    f"💥 **{char_name}**'s reckless speed causes multiple collisions! Hull damage: {damage}, Fuel lost: {fuel_loss}",
                    ephemeral=False
                )
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout         
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
        event_id = f"distress_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return           
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
                # Rebalanced skill check for pirate trap
                success_chance = min(95, 40 + (combat_skill - 10) * 3)
                roll = random.randint(1, 100)
                
                if roll <= success_chance:
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
                        "UPDATE characters SET hp = MAX(1, hp - ?), money = MAX(0, money - ?) WHERE user_id = ?",
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return           
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
        async def on_timeout():
            clear_event_responses(event_id)
    
        view.on_timeout = on_timeout         
        investigate_button.callback = investigate_callback
        ignore_button.callback = ignore_callback
        
        view.add_item(investigate_button)
        view.add_item(ignore_button)
        
        await channel.send(embed=embed, view=view)
    # Add these methods to the EnhancedEventsCog class in enhanced_events.py

    async def generate_reputation_event(self, location_id: int, players_present: list):
        """Generate reputation-based alignment events"""
        
        if not players_present:
            # No players present, handle ignored outcome
            await self._handle_ignored_reputation_event(location_id)
            return
        
        location_info = self.db.execute_query(
            "SELECT name, location_type, wealth_level FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return
        
        location_name, location_type, wealth_level = location_info
        
        # Select event type based on location characteristics
        event_categories = ['positive_only', 'negative_only', 'mixed']
        weights = [0.4, 0.3, 0.3]  # 40% positive, 30% negative, 30% mixed
        
        # Wealthy locations have more positive events
        if wealth_level >= 7:
            weights = [0.6, 0.2, 0.2]
        # Poor locations have more negative events  
        elif wealth_level <= 3:
            weights = [0.2, 0.5, 0.3]
        
        event_category = random.choices(event_categories, weights=weights)[0]
        
        # Get appropriate event pool
        if event_category == 'positive_only':
            events = self._get_positive_reputation_events(location_type, wealth_level)
        elif event_category == 'negative_only':
            events = self._get_negative_reputation_events(location_type, wealth_level)
        else:  # mixed
            events = self._get_mixed_reputation_events(location_type, wealth_level)
        
        if not events:
            return
        
        selected_event = random.choice(events)
        
        # Execute the reputation event
        channel = await self._get_location_channel(location_id)
        if channel:
            await self._execute_reputation_event(channel, selected_event, players_present, location_id, location_name)

    def _get_positive_reputation_events(self, location_type: str, wealth_level: int):
        """Events that can only increase reputation or do nothing"""
        events = [
            {
                'title': 'Lost Child Emergency',
                'description': '👶 **Missing Child Alert**\nA frantic parent reports their child has gone missing in the facility. Security is overwhelmed with other duties.',
                'color': 0x87CEEB,
                'handler': self._handle_lost_child_event,
                'ignored_outcome': 'The child was eventually found hours later, hungry and scared, after wandering into a maintenance area. The parents filed a formal complaint about the lack of immediate response from bystanders.',
                'responses': [
                    ('help_search', 'Organize Search Party', 'Help organize a systematic search of the facility', +25, +15),
                    ('offer_assistance', 'Assist Parents', 'Comfort the parents and help coordinate with security', +15, +10),
                    ('ignore', 'Not Your Problem', 'Continue with your own business', 0, 0)
                ]
            },
            {
                'title': 'Medical Emergency',
                'description': '🚑 **Medical Emergency**\nAn elderly civilian has collapsed in the common area. Medical teams are delayed due to another emergency.',
                'color': 0xFF6B6B,
                'handler': self._handle_medical_emergency_event,
                'ignored_outcome': 'The elderly civilian remained unconscious for several more minutes before medical teams arrived. Bystanders later questioned why no one with medical knowledge stepped forward to help.',
                'responses': [
                    ('provide_medical_aid', 'Provide Medical Aid', 'Use your medical skills to stabilize the patient', +30, +20),
                    ('call_for_help', 'Coordinate Assistance', 'Help coordinate emergency response and comfort bystanders', +15, +10),
                    ('stand_back', 'Stay Out of the Way', 'Keep your distance to avoid interfering', 0, 0)
                ]
            },
            {
                'title': 'Environmental Cleanup',
                'description': '🌱 **Environmental Incident**\nA small chemical leak has contaminated a section of the facility. Cleanup crews are stretched thin.',
                'color': 0x90EE90,
                'handler': self._handle_environmental_cleanup_event,
                'ignored_outcome': 'The chemical leak continued to spread slowly, contaminating a larger area before professional cleanup crews could contain it. Environmental groups later criticized the lack of citizen response.',
                'responses': [
                    ('volunteer_cleanup', 'Lead Cleanup Effort', 'Organize volunteers and lead the cleanup operation', +20, +15),
                    ('provide_supplies', 'Donate Supplies', 'Contribute cleanup materials from your inventory', +15, +10),
                    ('minimal_help', 'Report to Authorities', 'Simply report the incident to proper authorities', +5, +5)
                ]
            },
            {
                'title': 'Refugee Assistance',
                'description': '🏠 **Refugee Ship Arrives**\nA transport full of displaced families has arrived with minimal supplies. Official aid is delayed.',
                'color': 0xDDA0DD,
                'handler': self._handle_refugee_assistance_event,
                'ignored_outcome': 'The refugee families waited for hours without assistance, forced to ration their meager supplies. Several children became ill from hunger before official aid finally arrived.',
                'responses': [
                    ('organize_aid', 'Organize Community Aid', 'Rally others to provide comprehensive assistance', +25, +20),
                    ('donate_credits', 'Donate Credits', 'Contribute money for food and supplies', +15, +10),
                    ('offer_comfort', 'Provide Comfort', 'Offer emotional support and basic guidance', +10, +5)
                ]
            }
        ]
        
        # Filter by location type
        if location_type == 'outpost':
            # Outposts have fewer complex social situations
            events = [e for e in events if e['title'] in ['Medical Emergency', 'Environmental Cleanup']]
        
        return events

    def _get_negative_reputation_events(self, location_type: str, wealth_level: int):
        """Events that can only decrease reputation or do nothing"""
        events = [
            {
                'title': 'Corporate Bribery Offer',
                'description': '💰 **Discreet Business Proposal**\nA corporate representative approaches you with a "consulting opportunity" that involves overlooking certain regulatory violations.',
                'color': 0x8B4513,
                'handler': self._handle_corporate_bribery_event,
                'ignored_outcome': 'The corporate representative found someone else willing to accept their offer. The regulatory violations continued unchecked, eventually leading to safety incidents.',
                'responses': [
                    ('accept_major_bribe', 'Accept Full Package', 'Take the substantial payment and ongoing retainer', -30, -25),
                    ('accept_small_bribe', 'Accept Basic Fee', 'Take a smaller one-time payment', -15, -10),
                    ('decline', 'Decline Politely', 'Refuse the offer without reporting it', 0, 0)
                ]
            },
            {
                'title': 'Illegal Cargo Opportunity',
                'description': '📦 **No-Questions Transport Job**\nA shady contact offers excellent pay for transporting unmarked cargo with strict instructions not to inspect the contents.',
                'color': 0x696969,
                'handler': self._handle_illegal_cargo_event,
                'ignored_outcome': 'The suspicious cargo was eventually transported by a less scrupulous pilot. Customs later discovered it contained banned weapons that ended up in criminal hands.',
                'responses': [
                    ('accept_and_sell', 'Accept and Sell Info', 'Take the job but tip off customs for additional payment', -25, -20),
                    ('accept_job', 'Accept the Job', 'Transport the cargo without questions', -20, -15),
                    ('walk_away', 'Walk Away', 'Decline the suspicious offer', 0, 0)
                ]
            },
            {
                'title': 'Protection Racket',
                'description': '👊 **"Security Services" Offer**\nLocal toughs suggest that your ship would be "safer" if you paid for their "protection services" while docked.',
                'color': 0x8B0000,
                'handler': self._handle_protection_racket_event,
                'ignored_outcome': 'The protection racket continued operating, intimidating other ship owners who couldn\'t afford to pay. Several smaller vessels reported mysterious damage.',
                'responses': [
                    ('join_racket', 'Join Their Operation', 'Offer to help them "convince" other ship owners', -35, -30),
                    ('pay_protection', 'Pay for Protection', 'Pay the fee to avoid trouble', -10, -5),
                    ('refuse', 'Refuse to Pay', 'Tell them to leave you alone', 0, 0)
                ]
            },
            {
                'title': 'Witness Intimidation',
                'description': '👁️ **Convenient Amnesia Request**\nSomeone approaches you about "forgetting" what you may have witnessed regarding a recent incident involving important people.',
                'color': 0x4B0082,
                'handler': self._handle_witness_intimidation_event,
                'ignored_outcome': 'Without pressure to stay quiet, the witness later testified truthfully. Justice was served, though some powerful figures were displeased.',
                'responses': [
                    ('threaten_witness', 'Apply Pressure', 'Help convince the witness to stay quiet', -30, -25),
                    ('accept_payment', 'Take Hush Money', 'Accept payment to look the other way', -15, -10),
                    ('stay_neutral', 'Stay Out of It', 'Refuse to get involved either way', 0, 0)
                ]
            }
        ]
        
        # Wealthy locations have fewer overt criminal opportunities
        if wealth_level >= 7:
            events = [e for e in events if e['title'] in ['Corporate Bribery Offer', 'Witness Intimidation']]
        
        return events

    def _get_mixed_reputation_events(self, location_type: str, wealth_level: int):
        """Events that can increase or decrease reputation but won't do nothing"""
        events = [
            {
                'title': 'Corporate Whistleblower',
                'description': '📢 **Dangerous Information**\nYou\'ve discovered evidence of corporate malfeasance that could harm civilians. A corporate agent offers a substantial bribe to destroy the evidence.',
                'color': 0x4169E1,
                'handler': self._handle_whistleblower_event,
                'ignored_outcome': 'The evidence was eventually discovered by others through different means. The corporate scandal broke anyway, but the delayed revelation allowed more harm to occur.',
                'responses': [
                    ('expose_publicly', 'Expose the Corruption', 'Release the evidence to media and authorities', +30, +25),
                    ('report_quietly', 'Report to Authorities', 'Submit evidence through official channels', +20, +15),
                    ('take_bribe', 'Accept the Bribe', 'Destroy the evidence for payment', -25, -20)
                ]
            },
            {
                'title': 'Faction Dispute Mediation',
                'description': '⚖️ **Faction Tensions**\nTwo groups are on the verge of conflict over resource rights. Both sides want you to support their claim.',
                'color': 0xFF4500,
                'handler': self._handle_faction_dispute_event,
                'ignored_outcome': 'Without mediation, the dispute escalated into violence. Several people were injured in the fighting that could have been prevented.',
                'responses': [
                    ('mediate_fairly', 'Mediate Fairly', 'Try to find a compromise that benefits both sides', +25, +20),
                    ('support_underdogs', 'Support the Disadvantaged', 'Back the weaker faction against unfair treatment', +15, +10),
                    ('support_powerful', 'Support the Powerful', 'Back the stronger faction for personal gain', -15, -10)
                ]
            },
            {
                'title': 'Information Broker Deal',
                'description': '💻 **Sensitive Information**\nYou\'ve come across valuable information about ship movements. A broker offers payment, but the data could be used for piracy.',
                'color': 0x9932CC,
                'handler': self._handle_information_broker_event,
                'ignored_outcome': 'The information eventually became stale and worthless. However, pirates later attacked several ships that could have been warned.',
                'responses': [
                    ('warn_targets', 'Warn Potential Targets', 'Alert ships about possible danger', +20, +15),
                    ('sell_to_security', 'Sell to Security', 'Provide information to law enforcement', +15, +10),
                    ('sell_to_pirates', 'Sell to Pirates', 'Sell the information knowing it will be misused', -25, -20)
                ]
            },
            {
                'title': 'Resource Distribution Crisis',
                'description': '📦 **Supply Shortage**\nCritical supplies have arrived but there isn\'t enough for everyone. You have influence over the distribution.',
                'color': 0x20B2AA,
                'handler': self._handle_resource_distribution_event,
                'ignored_outcome': 'Without proper coordination, the distribution became chaotic. Supplies were wasted and the most vulnerable received nothing.',
                'responses': [
                    ('fair_distribution', 'Ensure Fair Distribution', 'Organize equitable distribution to those most in need', +25, +20),
                    ('help_vulnerable', 'Prioritize Vulnerable', 'Focus on helping children and elderly first', +20, +15),
                    ('personal_profit', 'Profit from Shortage', 'Divert supplies to sell at inflated prices', -20, -15)
                ]
            }
        ]
        
        return events

    async def _execute_reputation_event(self, channel, event_data, players_present, location_id, location_name):
        """Execute a reputation event with player choices"""
        embed = discord.Embed(
            title=f"📍 {event_data['title']} at {location_name}",
            description=event_data['description'],
            color=event_data['color']
        )
        
        embed.add_field(
            name="⚖️ Alignment Event",
            value="Your choices here will affect your reputation across the galaxy.",
            inline=False
        )
        
        # Create view with response options
        view = ReputationEventView(self.bot, event_data, players_present, location_id)
        
        try:
            message = await channel.send(embed=embed, view=view)
            
            # Schedule timeout handling
            timeout_task = asyncio.create_task(self._handle_reputation_event_timeout(
                channel, event_data, location_id, message, 300  # 5 minute timeout
            ))
            
            # Store timeout task for potential cancellation
            view.timeout_task = timeout_task
            
        except Exception as e:
            print(f"❌ Failed to send reputation event: {e}")

    async def _handle_reputation_event_timeout(self, channel, event_data, location_id, message, timeout_seconds):
        """Handle timeout for reputation events"""
        await asyncio.sleep(timeout_seconds)
        
        try:
            # Disable the view
            await message.edit(view=None)
            
            # Post ignored outcome
            embed = discord.Embed(
                title="⏰ Opportunity Missed",
                description=event_data['ignored_outcome'],
                color=0x808080
            )
            embed.add_field(
                name="Consequence",
                value="Sometimes inaction has consequences of its own.",
                inline=False
            )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Error handling reputation event timeout: {e}")

    async def _handle_ignored_reputation_event(self, location_id):
        """Handle reputation events when no players are present"""
        # Get a random event for simulation
        all_events = (self._get_positive_reputation_events("colony", 5) + 
                      self._get_negative_reputation_events("colony", 5) + 
                      self._get_mixed_reputation_events("colony", 5))
        
        if not all_events:
            return
        
        event = random.choice(all_events)
        
        # Check if location has a channel
        channel = await self._get_location_channel(location_id)
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        location_name = location_name[0] if location_name else "Unknown Location"
        
        if channel:
            # Post ignored outcome to channel
            embed = discord.Embed(
                title=f"📰 Incident at {location_name}",
                description=event['ignored_outcome'],
                color=0x696969
            )
            embed.add_field(
                name="Local News",
                value="Sometimes events unfold whether or not spacers are present to intervene.",
                inline=False
            )
            
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"❌ Failed to post ignored event outcome: {e}")
        else:
            # Just log it
            print(f"📰 Ignored reputation event at {location_name}: {event['title']} - {event['ignored_outcome'][:100]}...")

    # Event-specific handlers for reputation events

    async def _handle_lost_child_event(self, interaction, choice, rep_major, rep_minor):
        """Handle lost child event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'help_search':
            await interaction.response.send_message(
                f"🔍 **{char_name}** immediately organizes a systematic search, coordinating with security and gathering volunteers. The child is found quickly and safely!",
                ephemeral=False
            )
        elif choice == 'offer_assistance':
            await interaction.response.send_message(
                f"🤝 **{char_name}** comforts the frantic parents and helps coordinate with facility security, providing crucial support during the crisis.",
                ephemeral=False
            )
        else:  # ignore
            await interaction.response.send_message(
                f"⬅️ **{char_name}** decides it's not their responsibility and continues with their own business.",
                ephemeral=False
            )

    async def _handle_medical_emergency_event(self, interaction, choice, rep_major, rep_minor):
        """Handle medical emergency event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'provide_medical_aid':
            await interaction.response.send_message(
                f"⚕️ **{char_name}** immediately provides medical assistance, stabilizing the patient until professional help arrives. Their quick action likely saved a life!",
                ephemeral=False
            )
        elif choice == 'call_for_help':
            await interaction.response.send_message(
                f"📞 **{char_name}** takes charge of coordinating the emergency response and keeping bystanders calm and organized.",
                ephemeral=False
            )
        else:  # stand_back
            await interaction.response.send_message(
                f"👥 **{char_name}** stays back to avoid interfering with any potential medical response.",
                ephemeral=False
            )

    async def _handle_environmental_cleanup_event(self, interaction, choice, rep_major, rep_minor):
        """Handle environmental cleanup event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'volunteer_cleanup':
            await interaction.response.send_message(
                f"🌱 **{char_name}** immediately begins organizing volunteers and leading cleanup efforts, preventing the contamination from spreading!",
                ephemeral=False
            )
        elif choice == 'provide_supplies':
            await interaction.response.send_message(
                f"📦 **{char_name}** contributes valuable cleanup supplies and materials to help contain the environmental hazard.",
                ephemeral=False
            )
        else:  # minimal_help
            await interaction.response.send_message(
                f"📋 **{char_name}** reports the incident to the proper authorities and lets professionals handle it.",
                ephemeral=False
            )

    async def _handle_refugee_assistance_event(self, interaction, choice, rep_major, rep_minor):
        """Handle refugee assistance event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'organize_aid':
            await interaction.response.send_message(
                f"🏠 **{char_name}** rallies the community to provide comprehensive aid, organizing food, shelter, and medical care for the refugee families!",
                ephemeral=False
            )
        elif choice == 'donate_credits':
            await interaction.response.send_message(
                f"💰 **{char_name}** generously donates credits to help purchase essential supplies for the displaced families.",
                ephemeral=False
            )
        else:  # offer_comfort
            await interaction.response.send_message(
                f"🤗 **{char_name}** provides emotional support and guidance to the refugees during their difficult time.",
                ephemeral=False
            )

    async def _handle_corporate_bribery_event(self, interaction, choice, rep_major, rep_minor):
        """Handle corporate bribery event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'accept_major_bribe':
            await interaction.response.send_message(
                f"💰 **{char_name}** accepts the substantial corporate bribe, agreeing to ignore serious regulatory violations.",
                ephemeral=False
            )
        elif choice == 'accept_small_bribe':
            await interaction.response.send_message(
                f"💸 **{char_name}** takes a smaller payment to look the other way on minor infractions.",
                ephemeral=False
            )
        else:  # decline
            await interaction.response.send_message(
                f"✋ **{char_name}** politely declines the corporate offer without making a scene.",
                ephemeral=False
            )

    async def _handle_illegal_cargo_event(self, interaction, choice, rep_major, rep_minor):
        """Handle illegal cargo event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'accept_and_sell':
            await interaction.response.send_message(
                f"🕵️ **{char_name}** accepts the job but secretly tips off customs, planning to profit from both sides.",
                ephemeral=False
            )
        elif choice == 'accept_job':
            await interaction.response.send_message(
                f"📦 **{char_name}** accepts the suspicious cargo job, choosing not to ask questions about the contents.",
                ephemeral=False
            )
        else:  # walk_away
            await interaction.response.send_message(
                f"🚶 **{char_name}** decides the job is too risky and walks away from the offer.",
                ephemeral=False
            )

    async def _handle_protection_racket_event(self, interaction, choice, rep_major, rep_minor):
        """Handle protection racket event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'join_racket':
            await interaction.response.send_message(
                f"👊 **{char_name}** offers to help intimidate other ship owners, joining the protection racket operation.",
                ephemeral=False
            )
        elif choice == 'pay_protection':
            await interaction.response.send_message(
                f"💳 **{char_name}** reluctantly pays the protection fee to avoid any trouble with their ship.",
                ephemeral=False
            )
        else:  # refuse
            await interaction.response.send_message(
                f"🛡️ **{char_name}** firmly refuses to pay protection money and tells them to leave.",
                ephemeral=False
            )

    async def _handle_witness_intimidation_event(self, interaction, choice, rep_major, rep_minor):
        """Handle witness intimidation event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'threaten_witness':
            await interaction.response.send_message(
                f"😠 **{char_name}** helps apply pressure to convince the witness to stay quiet about what they saw.",
                ephemeral=False
            )
        elif choice == 'accept_payment':
            await interaction.response.send_message(
                f"💰 **{char_name}** accepts payment to look the other way and not encourage the witness to testify.",
                ephemeral=False
            )
        else:  # stay_neutral
            await interaction.response.send_message(
                f"🤐 **{char_name}** refuses to get involved in either direction and stays neutral.",
                ephemeral=False
            )

    async def _handle_whistleblower_event(self, interaction, choice, rep_major, rep_minor):
        """Handle whistleblower event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'expose_publicly':
            await interaction.response.send_message(
                f"📢 **{char_name}** courageously exposes the corporate corruption to the media and authorities, despite personal risk!",
                ephemeral=False
            )
        elif choice == 'report_quietly':
            await interaction.response.send_message(
                f"📋 **{char_name}** submits the evidence through proper official channels, letting justice take its course.",
                ephemeral=False
            )
        else:  # take_bribe
            await interaction.response.send_message(
                f"💰 **{char_name}** accepts the substantial bribe and destroys the incriminating evidence.",
                ephemeral=False
            )

    async def _handle_faction_dispute_event(self, interaction, choice, rep_major, rep_minor):
        """Handle faction dispute event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'mediate_fairly':
            await interaction.response.send_message(
                f"⚖️ **{char_name}** skillfully mediates between the factions, finding a fair compromise that prevents violence!",
                ephemeral=False
            )
        elif choice == 'support_underdogs':
            await interaction.response.send_message(
                f"🛡️ **{char_name}** stands with the disadvantaged faction against unfair treatment, defending justice.",
                ephemeral=False
            )
        else:  # support_powerful
            await interaction.response.send_message(
                f"💪 **{char_name}** backs the stronger faction, prioritizing personal gain over fairness.",
                ephemeral=False
            )

    async def _handle_information_broker_event(self, interaction, choice, rep_major, rep_minor):
        """Handle information broker event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'warn_targets':
            await interaction.response.send_message(
                f"⚠️ **{char_name}** uses the information to warn potential targets about possible pirate attacks, prioritizing safety!",
                ephemeral=False
            )
        elif choice == 'sell_to_security':
            await interaction.response.send_message(
                f"🚔 **{char_name}** sells the information to security forces to help them prevent pirate attacks.",
                ephemeral=False
            )
        else:  # sell_to_pirates
            await interaction.response.send_message(
                f"☠️ **{char_name}** sells the ship movement data to pirates, knowing it will be used for attacks.",
                ephemeral=False
            )

    async def _handle_resource_distribution_event(self, interaction, choice, rep_major, rep_minor):
        """Handle resource distribution event response"""
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if choice == 'fair_distribution':
            await interaction.response.send_message(
                f"⚖️ **{char_name}** organizes fair and equitable distribution of the critical supplies to those most in need!",
                ephemeral=False
            )
        elif choice == 'help_vulnerable':
            await interaction.response.send_message(
                f"❤️ **{char_name}** prioritizes helping the most vulnerable members of the community first.",
                ephemeral=False
            )
        else:  # personal_profit
            await interaction.response.send_message(
                f"💰 **{char_name}** diverts supplies to sell at inflated prices, profiting from the shortage.",
                ephemeral=False
            )


    def _get_available_events(self):
        """Get a mapping of all available events for admin commands"""
        return {
            # Colony Events
            "industrial_accident": {
                "name": "Industrial Accident",
                "description": "Factory malfunction requiring emergency response",
                "types": ["colony"],
                "handler": "location_event",
                "event_key": "Industrial Accident"
            },
            "worker_strike": {
                "name": "Worker Strike", 
                "description": "Labor dispute requiring mediation",
                "types": ["colony"],
                "handler": "location_event",
                "event_key": "Worker Strike"
            },
            "equipment_malfunction": {
                "name": "Equipment Malfunction",
                "description": "Critical system failure needing repairs",
                "types": ["colony", "space_station", "outpost"],
                "handler": "location_event", 
                "event_key": "Equipment Malfunction"
            },
            "refugee_arrival": {
                "name": "Refugee Arrival",
                "description": "Displaced civilians requesting sanctuary",
                "types": ["colony", "space_station"],
                "handler": "location_event",
                "event_key": "Refugee Arrival"
            },
            "celebration": {
                "name": "Celebration Festival",
                "description": "Colony anniversary celebration",
                "types": ["colony"],
                "handler": "location_event",
                "event_key": "Celebration Festival"
            },
            
            # Station Events
            "docking_overload": {
                "name": "Docking Overload",
                "description": "Traffic control systems failing",
                "types": ["space_station"],
                "handler": "location_event",
                "event_key": "Docking System Overload"
            },
            "trade_convoy": {
                "name": "Trade Convoy",
                "description": "Major merchant fleet arrival",
                "types": ["space_station"],
                "handler": "location_event",
                "event_key": "Trade Convoy Arrival"
            },
            "vip_arrival": {
                "name": "VIP Arrival",
                "description": "Corporate executive visit",
                "types": ["space_station"],
                "handler": "location_event",
                "event_key": "VIP Arrival"
            },
            
            # Outpost Events
            "supply_shortage": {
                "name": "Supply Shortage",
                "description": "Critical resources running low",
                "types": ["outpost"],
                "handler": "location_event",
                "event_key": "Supply Shortage"
            },
            "salvage_discovery": {
                "name": "Salvage Discovery",
                "description": "Valuable debris detected nearby",
                "types": ["outpost"],
                "handler": "location_event",
                "event_key": "Salvage Discovery"
            },
            "comm_blackout": {
                "name": "Communication Blackout",
                "description": "Array failure isolating outpost",
                "types": ["outpost"],
                "handler": "location_event",
                "event_key": "Communication Blackout"
            },
            "mysterious_signal": {
                "name": "Mysterious Signal",
                "description": "Unknown transmission from deep space",
                "types": ["outpost", "gate"],
                "handler": "location_event",
                "event_key": "Mysterious Signal"
            },
            
            # Space Phenomena (work anywhere)
            "solar_flare": {
                "name": "Solar Flare",
                "description": "Massive solar activity interfering with systems",
                "types": ["colony", "space_station", "outpost", "gate"],
                "handler": "space_phenomena",
                "event_key": "Solar Flare"
            },
            "quantum_storm": {
                "name": "Static Fog Storm",
                "description": "Electromagnetic interference affecting systems",
                "types": ["colony", "space_station", "outpost", "gate"],
                "handler": "space_phenomena",
                "event_key": "Quantum Storm"
            },
            "asteroid_field": {
                "name": "Asteroid Field",
                "description": "Debris field requiring navigation",
                "types": ["colony", "space_station", "outpost", "gate"],
                "handler": "space_phenomena",
                "event_key": "Asteroid Field"
            },
            "radiation_nebula": {
                "name": "Radiation Nebula",
                "description": "High-energy particles causing damage",
                "types": ["colony", "space_station", "outpost", "gate"],
                "handler": "space_phenomena",
                "event_key": "Radiation Nebula"
            },
            
            # Hostile Encounters
            "pirate_raiders": {
                "name": "Pirate Raiders",
                "description": "Hostile ships on intercept course",
                "types": ["colony", "space_station", "outpost", "gate"],
                "handler": "hostile_encounter",
                "event_key": "Pirate Raiders"
            },
            "scavenger_drones": {
                "name": "Scavenger Drones",
                "description": "Automated mining drones targeting ships",
                "types": ["colony", "space_station", "outpost", "gate"],
                "handler": "hostile_encounter",
                "event_key": "Scavenger Drones"
            },
            "corporate_security": {
                "name": "Corporate Security",
                "description": "Mega-corp enforcement demanding inspection",
                "types": ["space_station", "colony"],
                "handler": "hostile_encounter",
                "event_key": "Corporate Security"
            },
            
            # Reputation Events
            "lost_child": {
                "name": "Lost Child Emergency",
                "description": "Missing child requiring search assistance",
                "types": ["colony", "space_station"],
                "handler": "reputation_event",
                "event_key": "Lost Child Emergency"
            },
            "medical_emergency": {
                "name": "Medical Emergency",
                "description": "Civilian collapse requiring medical aid",
                "types": ["colony", "space_station", "outpost"],
                "handler": "reputation_event",
                "event_key": "Medical Emergency"
            },
            "whistleblower": {
                "name": "Corporate Whistleblower",
                "description": "Evidence of corporate malfeasance discovered",
                "types": ["colony", "space_station"],
                "handler": "reputation_event", 
                "event_key": "Corporate Whistleblower"
            }
        }

    @app_commands.command(name="trigger_event", description="Manually trigger a location event (Admin only)")
    @app_commands.describe(
        event="The event to trigger",
        player="Player whose location to use for the event",
        location="Location name to trigger event at (if no player specified)"
    )
    @app_commands.choices(event=[
        app_commands.Choice(name="Industrial Accident", value="industrial_accident"),
        app_commands.Choice(name="Worker Strike", value="worker_strike"),
        app_commands.Choice(name="Equipment Malfunction", value="equipment_malfunction"),
        app_commands.Choice(name="Refugee Arrival", value="refugee_arrival"),
        app_commands.Choice(name="Celebration Festival", value="celebration"),
        app_commands.Choice(name="Docking Overload", value="docking_overload"),
        app_commands.Choice(name="Trade Convoy", value="trade_convoy"),
        app_commands.Choice(name="VIP Arrival", value="vip_arrival"),
        app_commands.Choice(name="Supply Shortage", value="supply_shortage"),
        app_commands.Choice(name="Salvage Discovery", value="salvage_discovery"),
        app_commands.Choice(name="Communication Blackout", value="comm_blackout"),
        app_commands.Choice(name="Mysterious Signal", value="mysterious_signal"),
        app_commands.Choice(name="Solar Flare", value="solar_flare"),
        app_commands.Choice(name="Static Fog Storm", value="quantum_storm"),
        app_commands.Choice(name="Asteroid Field", value="asteroid_field"),
        app_commands.Choice(name="Radiation Nebula", value="radiation_nebula"),
        app_commands.Choice(name="Pirate Raiders", value="pirate_raiders"),
        app_commands.Choice(name="Scavenger Drones", value="scavenger_drones"),
        app_commands.Choice(name="Corporate Security", value="corporate_security"),
        app_commands.Choice(name="Lost Child Emergency", value="lost_child"),
        app_commands.Choice(name="Medical Emergency", value="medical_emergency"),
        app_commands.Choice(name="Corporate Whistleblower", value="whistleblower"),
    ])
    async def trigger_event(
        self, 
        interaction: discord.Interaction, 
        event: str,
        player: Optional[discord.Member] = None,
        location: Optional[str] = None
    ):
        """Manually trigger a location event"""
        
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        # Get event info
        available_events = self._get_available_events()
        if event not in available_events:
            await interaction.response.send_message(f"❌ Unknown event: {event}", ephemeral=True)
            return
        
        event_info = available_events[event]
        
        # Determine target location
        target_location_id = None
        target_location_name = None
        target_location_type = None
        
        if player:
            # Get player's current location
            char_data = self.db.execute_query(
                """SELECT c.current_location, l.name, l.location_type 
                   FROM characters c 
                   JOIN locations l ON c.current_location = l.location_id 
                   WHERE c.user_id = ?""",
                (player.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.response.send_message(f"❌ {player.display_name} has no character or location.", ephemeral=True)
                return
            
            target_location_id, target_location_name, target_location_type = char_data
            
        elif location:
            # Find location by name
            location_data = self.db.execute_query(
                "SELECT location_id, name, location_type FROM locations WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{location}%",),
                fetch='one'
            )
            
            if not location_data:
                await interaction.response.send_message(f"❌ Location '{location}' not found.", ephemeral=True)
                return
            
            target_location_id, target_location_name, target_location_type = location_data
            
        else:
            await interaction.response.send_message("❌ Must specify either a player or location.", ephemeral=True)
            return
        
        # Check if event is compatible with location type
        if target_location_type not in event_info["types"]:
            compatible_types = ", ".join(event_info["types"])
            await interaction.response.send_message(
                f"❌ Event '{event_info['name']}' cannot occur at {target_location_type} locations.\n"
                f"Compatible types: {compatible_types}", 
                ephemeral=True
            )
            return
        
        # Check for players at location
        players_present = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_location = ?",
            (target_location_id,),
            fetch='all'
        )
        
        if not players_present:
            await interaction.response.send_message(
                f"❌ No players present at {target_location_name}.", 
                ephemeral=True
            )
            return
        
        player_ids = [p[0] for p in players_present]
        
        # Get location channel
        channel = await self._get_location_channel(target_location_id)
        if not channel:
            await interaction.response.send_message(
                f"❌ No Discord channel found for {target_location_name}.", 
                ephemeral=True
            )
            return
        
        # Trigger the event based on type
        try:
            await interaction.response.send_message(
                f"🎲 Triggering '{event_info['name']}' at {target_location_name}...", 
                ephemeral=True
            )
            
            if event_info["handler"] == "location_event":
                await self._trigger_specific_location_event(
                    target_location_id, target_location_type, event_info["event_key"], player_ids
                )
                
            elif event_info["handler"] == "space_phenomena":
                await self._trigger_space_phenomena_event(
                    target_location_id, event_info["event_key"], player_ids, target_location_name
                )
                
            elif event_info["handler"] == "hostile_encounter":
                await self._trigger_hostile_encounter_event(
                    target_location_id, event_info["event_key"], player_ids, target_location_name
                )
                
            elif event_info["handler"] == "reputation_event":
                await self._trigger_reputation_event_specific(
                    target_location_id, event_info["event_key"], player_ids
                )
            
            # Log the admin action
            print(f"🎲 Admin {interaction.user.display_name} triggered '{event_info['name']}' at {target_location_name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error triggering event: {str(e)}", ephemeral=True)
            print(f"❌ Error in admin event trigger: {e}")

    async def _trigger_specific_location_event(self, location_id: int, location_type: str, event_key: str, player_ids: list):
        """Trigger a specific location event by key"""
        wealth = 5  # Default wealth for admin events
        population = 100  # Default population
        
        # Get the appropriate event pool
        if location_type == 'colony':
            events = self._get_colony_events(wealth, population)
        elif location_type == 'space_station':
            events = self._get_station_events(wealth, population)
        elif location_type == 'outpost':
            events = self._get_outpost_events(wealth, population)
        elif location_type == 'gate':
            events = self._get_gate_events(wealth, population)
        else:
            return
        
        # Find the specific event
        target_event = None
        for event in events:
            if event['name'] == event_key:
                target_event = event
                break
        
        if not target_event:
            return
        
        # Execute the event
        channel = await self._get_location_channel(location_id)
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0]
        
        await self._execute_location_event(channel, target_event, player_ids, location_name)

    async def _trigger_space_phenomena_event(self, location_id: int, event_key: str, player_ids: list, location_name: str):
        """Trigger a space phenomena event"""
        phenomena_map = {
            "Solar Flare": (self._handle_solar_flare, 0xff4500),
            "Quantum Storm": (self._handle_quantum_storm, 0x9400d3), 
            "Asteroid Field": (self._handle_asteroid_field, 0x8b4513),
            "Radiation Nebula": (self._handle_radiation_nebula, 0xff0000)
        }
        
        if event_key in phenomena_map:
            handler, color = phenomena_map[event_key]
            description = f"Admin-triggered {event_key} event at {location_name}."
            await handler(location_id, player_ids, location_name, event_key, description, color)

    async def _trigger_hostile_encounter_event(self, location_id: int, event_key: str, player_ids: list, location_name: str):
        """Trigger a hostile encounter event"""
        encounter_map = {
            "Pirate Raiders": (self._handle_pirate_encounter, 0x8b0000),
            "Scavenger Drones": (self._handle_scavenger_encounter, 0x708090),
            "Corporate Security": (self._handle_security_encounter, 0x000080)
        }
        
        if event_key in encounter_map:
            handler, color = encounter_map[event_key]
            description = f"Admin-triggered {event_key} detected at {location_name}."
            await handler(location_id, player_ids, location_name, event_key, description, color)

    async def _trigger_reputation_event_specific(self, location_id: int, event_key: str, player_ids: list):
        """Trigger a specific reputation event"""
        # Get appropriate reputation events
        all_reputation_events = (
            self._get_positive_reputation_events("colony", 5) +
            self._get_negative_reputation_events("colony", 5) +
            self._get_mixed_reputation_events("colony", 5)
        )
        
        # Find the specific event
        target_event = None
        for event in all_reputation_events:
            if event['title'] == event_key:
                target_event = event
                break
        
        if target_event:
            channel = await self._get_location_channel(location_id)
            location_name = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )[0]
            
            await self._execute_reputation_event(channel, target_event, player_ids, location_id, location_name)
    
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
        event_id = f"corpinspection_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return    
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
                    "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
                    (fine, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚠️ **{char_name}**'s evasiveness raises suspicion. Fined {fine} credits for non-compliance.",
                    ephemeral=False
                )
        
        async def avoid_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
                    "UPDATE characters SET money = MAX(0, money - ?) WHERE user_id = ?",
                    (fine, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"🚨 **{char_name}** is caught avoiding inspection. Heavy fine of {fine} credits imposed!",
                    ephemeral=False
                )
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout        
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
        event_id = f"corpinspection_{channel.id}_{datetime.now().timestamp()}"        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
                    "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                    (damage, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚡ **{char_name}** attempts repairs but triggers a secondary failure! Took {damage} damage from electrical discharge.",
                    ephemeral=False
                )
        
        async def diagnose_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return            
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout            
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
        event_id = f"corpinspection_{channel.id}_{datetime.now().timestamp()}"         
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return              
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout          
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
        event_id = f"celebration_{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return            
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
        
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout
        
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
        event_id = f"dockingoverload_{channel.id}_{datetime.now().timestamp()}"       
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return            
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout        
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
        event_id = f"tradeconvoy_{channel.id}_{datetime.now().timestamp()}"          
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return                
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return       
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout          
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
        event_id = f"viparrival_{channel.id}_{datetime.now().timestamp()}"       
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout          
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
        event_id = f"supplyshortage_{channel.id}_{datetime.now().timestamp()}"        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout         
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
        event_id = f"salvagediscovery{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout       
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
        event_id = f"commsblackout{channel.id}_{datetime.now().timestamp()}"       
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
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
                    "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                    (damage, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚡ **{char_name}** attempts repairs but causes additional damage! Took {damage} damage from equipment failure.",
                    ephemeral=False
                )
        
        async def improvise_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout          
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
        event_id = f"mysterysignal{channel.id}_{datetime.now().timestamp()}"       
        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
                    "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                    (damage, interaction.user.id)
                )
                
                await interaction.response.send_message(
                    f"⚠️ **{char_name}** investigates but triggers an automated defense system! Took {damage} damage!",
                    ephemeral=False
                )
        
        async def decode_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout         
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
        event_id = f"tradencounter{channel.id}_{datetime.now().timestamp()}"
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return       
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout        
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
        event_id = f"energyreadings{channel.id}_{datetime.now().timestamp()}"        
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return         
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
                    "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                    (damage, user_id)
                )
                
                await interaction.response.send_message(
                    f"⚠️ **{char_name}** triggers an energy discharge! Took {damage} damage from the exposure!",
                    ephemeral=False
                )
        
        async def avoid_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return          
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
        async def on_timeout():
            clear_event_responses(event_id)
        
        view.on_timeout = on_timeout          
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
        event_id = f"travellingpirates{channel.id}_{datetime.now().timestamp()}"         
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
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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
                    "UPDATE characters SET hp = MAX(1, hp - ?), money = MAX(0, money - ?) WHERE user_id = ?",
                    (damage, credits_lost, user_id)
                )
                
                await interaction.response.send_message(
                    f"💥 **{char_name}** is defeated by the pirates! Lost {damage} health and {credits_lost} credits.",
                    ephemeral=False
                )
        
        async def evade_callback(interaction):
            if not track_event_response(event_id, interaction.user.id):
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return        
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





class ReputationEventView(discord.ui.View):
    def __init__(self, bot, event_data, players_present, location_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.event_data = event_data
        self.players_present = players_present
        self.location_id = location_id
        self.responses = {}  # Track who has responded
        self.timeout_task = None
        
        # Create buttons for each response option
        for i, (choice_id, label, description, rep_major, rep_minor) in enumerate(event_data['responses']):
            button = discord.ui.Button(
                label=label,
                style=self._get_button_style(choice_id),
                emoji=self._get_button_emoji(choice_id),
                row=i // 3  # Up to 3 buttons per row
            )
            button.callback = self._create_callback(choice_id, rep_major, rep_minor)
            self.add_item(button)
    
    def _get_button_style(self, choice_id):
        """Get appropriate button style based on choice morality"""
        if any(word in choice_id for word in ['help', 'assist', 'aid', 'fair', 'warn', 'expose', 'mediate']):
            return discord.ButtonStyle.success
        elif any(word in choice_id for word in ['bribe', 'illegal', 'threaten', 'racket', 'profit', 'pirates']):
            return discord.ButtonStyle.danger
        else:
            return discord.ButtonStyle.secondary
    
    def _get_button_emoji(self, choice_id):
        """Get appropriate emoji for choice"""
        emoji_map = {
            'help_search': '🔍', 'offer_assistance': '🤝', 'ignore': '⬅️',
            'provide_medical_aid': '⚕️', 'call_for_help': '📞', 'stand_back': '👥',
            'volunteer_cleanup': '🌱', 'provide_supplies': '📦', 'minimal_help': '📋',
            'organize_aid': '🏠', 'donate_credits': '💰', 'offer_comfort': '🤗',
            'accept_major_bribe': '💰', 'accept_small_bribe': '💸', 'decline': '✋',
            'accept_and_sell': '🕵️', 'accept_job': '📦', 'walk_away': '🚶',
            'join_racket': '👊', 'pay_protection': '💳', 'refuse': '🛡️',
            'threaten_witness': '😠', 'accept_payment': '💰', 'stay_neutral': '🤐',
            'expose_publicly': '📢', 'report_quietly': '📋', 'take_bribe': '💰',
            'mediate_fairly': '⚖️', 'support_underdogs': '🛡️', 'support_powerful': '💪',
            'warn_targets': '⚠️', 'sell_to_security': '🚔', 'sell_to_pirates': '☠️',
            'fair_distribution': '⚖️', 'help_vulnerable': '❤️', 'personal_profit': '💰'
        }
        return emoji_map.get(choice_id, '❓')
    
    def _create_callback(self, choice_id, rep_major, rep_minor):
        """Create callback function for button"""
        async def callback(interaction):
            if interaction.user.id not in self.players_present:
                await interaction.response.send_message("You're not present at this location!", ephemeral=True)
                return
            
            if interaction.user.id in self.responses:
                await interaction.response.send_message("You've already responded to this event!", ephemeral=True)
                return
            
            # Record response
            self.responses[interaction.user.id] = choice_id
            
            # Apply reputation changes
            rep_cog = self.bot.get_cog('ReputationCog')
            if rep_cog and (rep_major != 0 or rep_minor != 0):
                # Apply major reputation change at this location
                if rep_major != 0:
                    await rep_cog.update_reputation(interaction.user.id, self.location_id, rep_major)
                
                # Apply minor reputation change to nearby locations
                if rep_minor != 0:
                    nearby_locations = self.bot.db.execute_query(
                        "SELECT destination_location FROM corridors WHERE origin_location = ? AND is_active = 1",
                        (self.location_id,),
                        fetch='all'
                    )
                    for (nearby_id,) in nearby_locations[:3]:  # Limit to 3 nearby locations
                        await rep_cog.update_reputation(interaction.user.id, nearby_id, rep_minor)
            
            # Call the event-specific handler
            handler = self.event_data['handler']
            await handler(interaction, choice_id, rep_major, rep_minor)
            
            # Check if all players have responded
            if len(self.responses) >= len(self.players_present):
                # Cancel timeout task
                if self.timeout_task:
                    self.timeout_task.cancel()
                
                # Disable buttons
                for item in self.children:
                    item.disabled = True
                
                try:
                    await interaction.message.edit(view=self)
                except:
                    pass
        
        return callback
async def setup(bot):
    await bot.add_cog(EnhancedEventsCog(bot))
    

class BaseEventView(discord.ui.View):
    """Base view for all events that tracks player responses"""
    def __init__(self, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.player_responses = {}  # Track who has responded
    
    def has_responded(self, user_id: int) -> bool:
        """Check if a user has already responded to this event"""
        return user_id in self.player_responses
    
    def record_response(self, user_id: int, response: str):
        """Record a user's response"""
        self.player_responses[user_id] = response
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is valid"""
        if self.has_responded(interaction.user.id):
            await interaction.response.send_message(
                "You've already responded to this event!", 
                ephemeral=True
            )
            return False
        return True