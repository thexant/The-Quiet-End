# cogs/npc_interactions.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.item_config import ItemConfig

class NPCInteractionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="npc", description="Interact with NPCs at your current location")
    async def npc_interact(self, interaction: discord.Interaction):
        # Get character's current location
        char_info = self.db.execute_query(
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in to interact with NPCs!", ephemeral=True)
            return
        
        location_id = char_info[0]
        if not location_id:
            await interaction.response.send_message("You must be at a location to interact with NPCs!", ephemeral=True)
            return
        
        # Get NPCs at this location
        static_npcs = self.db.execute_query(
            '''SELECT npc_id, name, age, occupation, personality, trade_specialty
               FROM static_npcs WHERE location_id = ?''',
            (location_id,),
            fetch='all'
        )
        
        dynamic_npcs = self.db.execute_query(
            '''SELECT npc_id, name, age, ship_name, ship_type
               FROM dynamic_npcs 
               WHERE current_location = ? AND is_alive = 1 AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not static_npcs and not dynamic_npcs:
            await interaction.response.send_message("No NPCs are available for interaction at this location.", ephemeral=True)
            return
        
        view = NPCSelectView(self.bot, interaction.user.id, location_id, static_npcs, dynamic_npcs)
        
        embed = discord.Embed(
            title="👥 Available NPCs",
            description="Choose an NPC to interact with:",
            color=0x6c5ce7
        )
        
        if static_npcs:
            static_list = []
            for npc_id, name, age, occupation, personality, trade_specialty in static_npcs:
                specialty_text = f" ({trade_specialty})" if trade_specialty else ""
                static_list.append(f"**{name}** - {occupation}{specialty_text}")
            
            embed.add_field(
                name="🏢 Local Residents",
                value="\n".join(static_list[:10]),
                inline=False
            )
        
        if dynamic_npcs:
            dynamic_list = []
            for npc_id, name, age, ship_name, ship_type in dynamic_npcs:
                dynamic_list.append(f"**{name}** - Captain of {ship_name}")
            
            embed.add_field(
                name="🚀 Visiting Travelers",
                value="\n".join(dynamic_list[:10]),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def generate_npc_jobs(self, npc_id: int, npc_type: str, location_id: int, occupation: str = None):
        """Generate jobs for an NPC based on their role, including escort missions."""
        
        # 20% chance to generate an escort job instead of a regular one
        if random.random() < 0.2:
            # Get possible destinations (at least 2 jumps away)
            galaxy_cog = self.bot.get_cog('GalaxyGeneratorCog')
            if galaxy_cog:
                routes = await galaxy_cog._find_route_to_destination(location_id, max_jumps=4)
                # Filter for routes with 2 or 3 jumps
                valid_destinations = [r for r in routes if r[2] in [2, 3]]
                
                if valid_destinations:
                    dest_id, dest_name, jumps = random.choice(valid_destinations)
                    
                    # Create escort job
                    title = f"[ESCORT] Escort to {dest_name}"
                    description = f"Safely escort this NPC from their current location to {dest_name}. The journey is estimated to be {jumps} jumps."
                    reward = 150 * jumps + random.randint(50, 200)
                    danger = jumps + random.randint(0, 2)
                    duration = 30 * jumps  # Rough duration estimate

                    self.db.execute_query(
                        '''INSERT INTO npc_jobs 
                           (npc_id, npc_type, job_title, job_description, reward_money,
                            required_skill, min_skill_level, danger_level, duration_minutes, expires_at)
                           VALUES (?, ?, ?, ?, ?, 'combat', 10, ?, ?, datetime('now', '+1 day'))''',
                        (npc_id, npc_type, title, description, reward, danger, duration)
                    )
                    return # Stop after creating an escort job

        # Job templates based on occupation
        job_templates = {
            "Farmer": [
                ("Harvest Assistant Needed", "Help harvest crops during the busy season", 150, None, 0, 1, 30),
                ("Livestock Care", "Tend to farm animals and ensure their health", 200, "medical", 5, 1, 45),
                ("Equipment Maintenance", "Repair and maintain farming equipment", 250, "engineering", 8, 2, 60)
            ],
            "Engineer": [
                ("System Diagnostics", "Run diagnostics on critical station systems", 300, "engineering", 10, 2, 45),
                ("Equipment Calibration", "Calibrate sensitive technical equipment", 400, "engineering", 15, 1, 60),
                ("Emergency Repair", "Fix urgent system failures", 500, "engineering", 18, 3, 30)
            ],
            "Medic": [
                ("Medical Supply Inventory", "Organize and catalog medical supplies", 180, "medical", 5, 1, 30),
                ("Health Screening", "Assist with routine health examinations", 220, "medical", 10, 1, 60),
                ("Emergency Response", "Provide medical aid during emergencies", 400, "medical", 15, 2, 20)
            ],
            "Merchant": [
                ("Market Research", "Investigate trade opportunities", 200, "navigation", 8, 1, 60),
                ("Cargo Escort", "Provide security for valuable shipments", 350, "combat", 12, 3, 90),
                ("Price Negotiation", "Help negotiate better trade deals", 300, "navigation", 10, 1, 45)
            ],
            "Security Guard": [
                ("Patrol Duty", "Conduct security patrols of the facility", 180, "combat", 5, 2, 60),
                ("Equipment Check", "Inspect and maintain security equipment", 200, "engineering", 8, 1, 30),
                ("Threat Assessment", "Evaluate security risks and vulnerabilities", 300, "combat", 15, 2, 60)
            ],
            "Escort": [
                ("Escort to {dest_name}", "Provide safe passage for an NPC to a new location.", 300, "combat", 10, 2, 60)
            ]
        }
        
        # Default jobs for unknown occupations
        default_jobs = [
            ("General Labor", "Assist with various manual tasks", 100, None, 0, 1, 60),
            ("Information Gathering", "Collect and organize local information", 150, "navigation", 5, 1, 90),
            ("Equipment Testing", "Test functionality of various devices", 200, "engineering", 8, 1, 120)
        ]
        
        # Get appropriate job templates
        templates = job_templates.get(occupation, default_jobs)
        
        # Generate 1-3 jobs
        num_jobs = random.randint(1, 3)
        for _ in range(num_jobs):
            title, desc, base_reward, skill, min_skill, danger, duration = random.choice(templates)
            
            # Add some variation
            reward = base_reward + random.randint(-20, 50)
            duration = duration + random.randint(-15, 30)
            
            # Random rare item reward chance
            reward_items = None
            if random.random() < 0.15:  # 15% chance
                rare_items = ItemConfig.get_items_by_rarity("rare") + ItemConfig.get_items_by_rarity("legendary")
                if rare_items:
                    reward_items = json.dumps([random.choice(rare_items)])
            
            # Set expiration (1-7 days)
            expires_at = datetime.now() + timedelta(days=random.randint(1, 7))
            
            self.db.execute_query(
                '''INSERT INTO npc_jobs 
                   (npc_id, npc_type, job_title, job_description, reward_money, reward_items,
                    required_skill, min_skill_level, danger_level, duration_minutes, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (npc_id, npc_type, title, desc, reward, reward_items, skill, min_skill, danger, duration, expires_at)
            )
    async def generate_npc_trade_inventory(self, npc_id: int, npc_type: str, trade_specialty: str = None):
        """Generate trade inventory for an NPC"""
        
        # Base items all NPCs might have
        base_items = ["Data Chip", "Emergency Rations", "Basic Med Kit", "Fuel Cell"]
        
        # Specialty items based on trade specialty
        specialty_items = {
            "Rare minerals": ["Rare Minerals", "Crystal Formations", "Exotic Alloys"],
            "Technical components": ["Scanner Module", "Engine Booster", "Hull Reinforcement"],
            "Medical supplies": ["Advanced Med Kit", "Radiation Treatment", "Combat Stims"],
            "Luxury goods": ["Artifact", "Cultural Items", "Fine Wine"],
            "Information": ["Navigation Data", "Market Intelligence", "Historical Records"],
            "Contraband": ["Illegal Substances", "Stolen Goods", "Black Market Tech"]
        }
        
        items_to_add = random.sample(base_items, random.randint(1, 3))
        
        if trade_specialty and trade_specialty in specialty_items:
            specialty_list = specialty_items[trade_specialty]
            items_to_add.extend(random.sample(specialty_list, random.randint(1, 2)))
        
        # Add items to inventory
        for item_name in items_to_add:
            if item_name in ItemConfig.ITEM_DEFINITIONS:
                item_def = ItemConfig.get_item_definition(item_name)
                base_price = item_def["base_value"]
                
                # NPCs charge 20-50% markup
                markup = random.uniform(1.2, 1.5)
                price = int(base_price * markup)
                
                # Some items might require trade instead of credits
                trade_for_item = None
                trade_quantity = 1
                
                if random.random() < 0.3:  # 30% chance to require trade
                    trade_items = ["Rare Minerals", "Data Chip", "Artifact", "Technical Components"]
                    trade_for_item = random.choice(trade_items)
                    trade_quantity = random.randint(1, 3)
                    price = None  # No credit price if trade required
                
                quantity = random.randint(1, 5)
                rarity = item_def.get("rarity", "common")
                
                # Rare items restock less frequently
                restock_hours = {"common": 24, "uncommon": 48, "rare": 96, "legendary": 168}
                restock_time = datetime.now() + timedelta(hours=restock_hours.get(rarity, 24))
                
                self.db.execute_query(
                    '''INSERT INTO npc_trade_inventory
                       (npc_id, npc_type, item_name, item_type, quantity, price_credits,
                        trade_for_item, trade_quantity_required, rarity, description, restocks_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (npc_id, npc_type, item_name, item_def["type"], quantity, price,
                     trade_for_item, trade_quantity, rarity, item_def["description"], restock_time)
                )

class NPCSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, static_npcs: list, dynamic_npcs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        # Create select menu for NPCs
        options = []
        
        # Add static NPCs
        for npc_id, name, age, occupation, personality, trade_specialty in static_npcs[:15]:
            specialty_text = f" ({trade_specialty})" if trade_specialty else ""
            options.append(
                discord.SelectOption(
                    label=f"{name} - {occupation}",
                    description=f"{personality}{specialty_text}"[:100],
                    value=f"static_{npc_id}",
                    emoji="🏢"
                )
            )
        
        # Add dynamic NPCs
        for npc_id, name, age, ship_name, ship_type in dynamic_npcs[:10]:
            options.append(
                discord.SelectOption(
                    label=f"{name} - Ship Captain",
                    description=f"Captain of {ship_name} ({ship_type})"[:100],
                    value=f"dynamic_{npc_id}",
                    emoji="🚀"
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an NPC to interact with...",
                options=options[:25]  # Discord limit
            )
            select.callback = self.npc_selected
            self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_type, npc_id = interaction.data['values'][0].split('_', 1)
        npc_id = int(npc_id)
        
        view = NPCActionView(self.bot, self.user_id, npc_id, npc_type)
        
        if npc_type == "static":
            npc_info = self.bot.db.execute_query(
                "SELECT name, occupation, personality, trade_specialty FROM static_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if npc_info:
                name, occupation, personality, trade_specialty = npc_info
                embed = discord.Embed(
                    title=f"👤 Talking to {name}",
                    description=f"**{name}** is a {occupation} who is {personality}.",
                    color=0x6c5ce7
                )
                if trade_specialty:
                    embed.add_field(
                        name="Trade Specialty",
                        value=trade_specialty,
                        inline=True
                    )
        else:  # dynamic
            npc_info = self.bot.db.execute_query(
                "SELECT name, ship_name, ship_type FROM dynamic_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            if npc_info:
                name, ship_name, ship_type = npc_info
                embed = discord.Embed(
                    title=f"👤 Talking to {name}",
                    description=f"**{name}** is the captain of {ship_name}, a {ship_type}.",
                    color=0x6c5ce7
                )
        
        embed.add_field(
            name="Available Actions",
            value="• 💼 View available jobs\n• 🛒 Browse trade inventory\n• 💬 General conversation",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class NPCActionView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
    
    @discord.ui.button(label="View Jobs", style=discord.ButtonStyle.primary, emoji="💼")
    async def view_jobs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        # Get available jobs from this NPC
        jobs = self.bot.db.execute_query(
            '''SELECT npc_job_id, job_title, job_description, reward_money, reward_items,
                      required_skill, min_skill_level, danger_level, duration_minutes
               FROM npc_jobs 
               WHERE npc_id = ? AND npc_type = ? AND is_available = 1 
               AND (expires_at IS NULL OR expires_at > datetime('now'))''',
            (self.npc_id, self.npc_type),
            fetch='all'
        )
        
        if not jobs:
            # Generate jobs if none exist
            npc_cog = self.bot.get_cog('NPCInteractionsCog')
            if self.npc_type == "static":
                occupation = self.bot.db.execute_query(
                    "SELECT occupation FROM static_npcs WHERE npc_id = ?",
                    (self.npc_id,),
                    fetch='one'
                )
                if occupation and npc_cog:
                    await npc_cog.generate_npc_jobs(self.npc_id, self.npc_type, 0, occupation[0])
                    
                    jobs = self.bot.db.execute_query(
                        '''SELECT npc_job_id, job_title, job_description, reward_money, reward_items,
                                  required_skill, min_skill_level, danger_level, duration_minutes
                           FROM npc_jobs 
                           WHERE npc_id = ? AND npc_type = ? AND is_available = 1''',
                        (self.npc_id, self.npc_type),
                        fetch='all'
                    )
        
        if not jobs:
            await interaction.response.send_message("This NPC has no jobs available right now.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="💼 Available Jobs",
            description="Jobs offered by this NPC:",
            color=0x4169E1
        )
        
        for job in jobs[:5]:  # Show up to 5 jobs
            npc_job_id, title, desc, reward_money, reward_items, skill, min_skill, danger, duration = job
            
            reward_text = f"{reward_money:,} credits"
            if reward_items:
                items = json.loads(reward_items)
                reward_text += f" + {', '.join(items)}"
            
            skill_text = f"Requires {skill} {min_skill}+" if skill else "No skill requirement"
            danger_text = "⚠️" * danger if danger > 0 else "Safe"
            
            embed.add_field(
                name=f"**{title}**",
                value=f"{desc}\n💰 {reward_text}\n⏱️ {duration} min | {skill_text} | {danger_text}",
                inline=False
            )
        
        view = NPCJobSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, jobs)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Trade", style=discord.ButtonStyle.success, emoji="🛒")
    async def view_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        # Get NPC's trade inventory
        trade_items = self.bot.db.execute_query(
            '''SELECT trade_item_id, item_name, quantity, price_credits, trade_for_item,
                      trade_quantity_required, rarity, description
               FROM npc_trade_inventory 
               WHERE npc_id = ? AND npc_type = ? AND is_available = 1 
               AND quantity > 0''',
            (self.npc_id, self.npc_type),
            fetch='all'
        )
        
        if not trade_items:
            # Generate trade inventory if none exists
            npc_cog = self.bot.get_cog('NPCInteractionsCog')
            if self.npc_type == "static":
                trade_specialty = self.bot.db.execute_query(
                    "SELECT trade_specialty FROM static_npcs WHERE npc_id = ?",
                    (self.npc_id,),
                    fetch='one'
                )
                if npc_cog:
                    specialty = trade_specialty[0] if trade_specialty else None
                    await npc_cog.generate_npc_trade_inventory(self.npc_id, self.npc_type, specialty)
                    
                    trade_items = self.bot.db.execute_query(
                        '''SELECT trade_item_id, item_name, quantity, price_credits, trade_for_item,
                                  trade_quantity_required, rarity, description
                           FROM npc_trade_inventory 
                           WHERE npc_id = ? AND npc_type = ? AND is_available = 1 
                           AND quantity > 0''',
                        (self.npc_id, self.npc_type),
                        fetch='all'
                    )
        
        if not trade_items:
            await interaction.response.send_message("This NPC has no items for trade right now.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛒 Trade Inventory",
            description="Items available for trade:",
            color=0x00ff00
        )
        
        for item in trade_items[:8]:  # Show up to 8 items
            trade_item_id, name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description = item
            
            rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "legendary": "🟣"}[rarity]
            
            if price_credits:
                price_text = f"{price_credits:,} credits"
            elif trade_for_item:
                price_text = f"{trade_quantity_required}x {trade_for_item}"
            else:
                price_text = "Make offer"
            
            embed.add_field(
                name=f"{rarity_emoji} **{name}** (x{quantity})",
                value=f"{description[:100]}...\n💰 {price_text}",
                inline=True
            )
        
        view = NPCTradeSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, trade_items)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class NPCJobSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, jobs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        
        if jobs:
            options = []
            for job in jobs[:25]:  # Discord limit
                npc_job_id, title, desc, reward_money, reward_items, skill, min_skill, danger, duration = job
                
                reward_text = f"{reward_money:,} credits"
                if reward_items:
                    items = json.loads(reward_items)
                    reward_text += f" + items"
                
                skill_text = f" ({skill} {min_skill}+)" if skill else ""
                danger_text = "⚠️" * danger if danger > 0 else ""
                
                options.append(
                    discord.SelectOption(
                        label=f"{title} - {reward_text}",
                        description=f"{desc[:50]}{'...' if len(desc) > 50 else ''} {duration}min{skill_text} {danger_text}"[:100],
                        value=str(npc_job_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose a job to accept...", options=options)
                select.callback = self.job_selected
                self.add_item(select)
    
Hello! As a specialist in Python, Javascript, CSS, and SQL, I'd be happy to help you with your Discord bot. I've reviewed your request and the provided files. Here are the code fixes to address the issues with NPC jobs and to implement the NPC escort missions.

Part 1: Fixing NPC Job Durations and Acceptance

The main problems are that NPC job durations are too long, and when a player accepts an NPC job, it's not being correctly tracked by the main job system. Here are the changes to fix this.

In cogs/npc_interactions.py:

To make the job durations more reasonable, we'll adjust the base values in the generate_npc_jobs method. Replace the existing job_templates dictionary with this updated version:
Python

# In cogs/npc_interactions.py, inside the NPCInteractionsCog class, replace the job_templates dictionary
        job_templates = {
            "Farmer": [
                ("Harvest Assistant Needed", "Help harvest crops during the busy season", 150, None, 0, 1, 30),
                ("Livestock Care", "Tend to farm animals and ensure their health", 200, "medical", 5, 1, 45),
                ("Equipment Maintenance", "Repair and maintain farming equipment", 250, "engineering", 8, 2, 60)
            ],
            "Engineer": [
                ("System Diagnostics", "Run diagnostics on critical station systems", 300, "engineering", 10, 2, 45),
                ("Equipment Calibration", "Calibrate sensitive technical equipment", 400, "engineering", 15, 1, 60),
                ("Emergency Repair", "Fix urgent system failures", 500, "engineering", 18, 3, 30)
            ],
            "Medic": [
                ("Medical Supply Inventory", "Organize and catalog medical supplies", 180, "medical", 5, 1, 30),
                ("Health Screening", "Assist with routine health examinations", 220, "medical", 10, 1, 60),
                ("Emergency Response", "Provide medical aid during emergencies", 400, "medical", 15, 2, 20)
            ],
            "Merchant": [
                ("Market Research", "Investigate trade opportunities", 200, "navigation", 8, 1, 60),
                ("Cargo Escort", "Provide security for valuable shipments", 350, "combat", 12, 3, 90),
                ("Price Negotiation", "Help negotiate better trade deals", 300, "navigation", 10, 1, 45)
            ],
            "Security Guard": [
                ("Patrol Duty", "Conduct security patrols of the facility", 180, "combat", 5, 2, 60),
                ("Equipment Check", "Inspect and maintain security equipment", 200, "engineering", 8, 1, 30),
                ("Threat Assessment", "Evaluate security risks and vulnerabilities", 300, "combat", 15, 2, 60)
            ]
        }

    async def job_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_job_id = int(interaction.data['values'][0])
        
        # Check if user already has an active job
        has_job = self.bot.db.execute_query(
            "SELECT job_id FROM jobs WHERE taken_by = ? AND is_taken = 1",
            (interaction.user.id,),
            fetch='one'
        )
        
        if has_job:
            await interaction.response.send_message("You already have an active job. Complete or abandon it first.", ephemeral=True)
            return
        
        # Get job details
        job_info = self.bot.db.execute_query(
            '''SELECT job_title, job_description, reward_money, reward_items, required_skill, 
                      min_skill_level, danger_level, duration_minutes
               FROM npc_jobs WHERE npc_job_id = ?''',
            (npc_job_id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("Job no longer available.", ephemeral=True)
            return
        
        title, desc, reward_money, reward_items, required_skill, min_skill_level, danger_level, duration_minutes = job_info
        
        # Check skill requirements
        if required_skill:
            char_skills = self.bot.db.execute_query(
                f"SELECT {required_skill} FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_skills or char_skills[0] < min_skill_level:
                await interaction.response.send_message(
                    f"You need at least {min_skill_level} {required_skill} skill for this job.",
                    ephemeral=True
                )
                return

        # Get character's current location to assign the job correctly
        char_location_id = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # Accept the job (create a regular job entry)
        expire_time = datetime.now() + timedelta(hours=6)
        
        self.bot.db.execute_query(
            '''INSERT INTO jobs 
               (location_id, title, description, reward_money, required_skill, min_skill_level,
                danger_level, duration_minutes, expires_at, is_taken, taken_by, taken_at, job_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, datetime('now'), 'active')''',
            (char_location_id, title, desc, reward_money, required_skill, min_skill_level, danger_level, 
             duration_minutes, expire_time.isoformat(), interaction.user.id)
        )
        
        # Get the new job_id
        new_job_id = self.bot.db.execute_query(
            "SELECT last_insert_rowid()",
            fetch='one'
        )[0]

        # Add to job_tracking for stationary jobs
        self.bot.db.execute_query(
            '''INSERT INTO job_tracking (job_id, user_id, start_location, required_duration)
               VALUES (?, ?, ?, ?)''',
            (new_job_id, interaction.user.id, char_location_id, duration_minutes)
        )

        # Record completion for tracking
        self.bot.db.execute_query(
            "INSERT INTO npc_job_completions (npc_job_id, user_id) VALUES (?, ?)",
            (npc_job_id, interaction.user.id)
        )
        
        # Update completion count
        self.bot.db.execute_query(
            "UPDATE npc_jobs SET current_completions = current_completions + 1 WHERE npc_job_id = ?",
            (npc_job_id,)
        )
        
        # Check if job should be disabled (max completions reached)
        job_status = self.bot.db.execute_query(
            "SELECT max_completions, current_completions FROM npc_jobs WHERE npc_job_id = ?",
            (npc_job_id,),
            fetch='one'
        )
        
        if job_status and job_status[0] > 0 and job_status[1] >= job_status[0]:
            self.bot.db.execute_query(
                "UPDATE npc_jobs SET is_available = 0 WHERE npc_job_id = ?",
                (npc_job_id,)
            )
        
        embed = discord.Embed(
            title="✅ Job Accepted",
            description=f"You have accepted: **{title}**",
            color=0x00ff00
        )
        
        reward_text = f"{reward_money:,} credits"
        if reward_items:
            items = json.loads(reward_items)
            reward_text += f" + {', '.join(items)}"
        
        embed.add_field(name="Reward", value=reward_text, inline=True)
        embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger_level if danger_level > 0 else "Safe", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class NPCTradeSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, trade_items: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        
        if trade_items:
            options = []
            for item in trade_items[:25]:  # Discord limit
                trade_item_id, name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description = item
                
                if price_credits:
                    price_text = f"{price_credits:,} credits"
                elif trade_for_item:
                    price_text = f"{trade_quantity_required}x {trade_for_item}"
                else:
                    price_text = "Make offer"
                
                rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "legendary": "🟣"}[rarity]
                
                options.append(
                    discord.SelectOption(
                        label=f"{name} (x{quantity}) - {price_text}",
                        description=f"{rarity_emoji} {description[:80]}{'...' if len(description) > 80 else ''}",
                        value=str(trade_item_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose an item to trade for...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        trade_item_id = int(interaction.data['values'][0])
        
        # Get trade item details
        trade_info = self.bot.db.execute_query(
            '''SELECT item_name, quantity, price_credits, trade_for_item, trade_quantity_required,
                      rarity, description, item_type
               FROM npc_trade_inventory WHERE trade_item_id = ?''',
            (trade_item_id,),
            fetch='one'
        )
        
        if not trade_info:
            await interaction.response.send_message("Item no longer available.", ephemeral=True)
            return
        
        item_name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description, item_type = trade_info
        
        # Check if player can afford/has required items
        if price_credits:
            player_money = self.bot.db.execute_query(
                "SELECT money FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            if player_money < price_credits:
                await interaction.response.send_message(
                    f"You need {price_credits:,} credits but only have {player_money:,}.",
                    ephemeral=True
                )
                return
        
        elif trade_for_item:
            player_item = self.bot.db.execute_query(
                "SELECT quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                (interaction.user.id, trade_for_item),
                fetch='one'
            )
            
            if not player_item or player_item[0] < trade_quantity_required:
                have = player_item[0] if player_item else 0
                await interaction.response.send_message(
                    f"You need {trade_quantity_required}x {trade_for_item} but only have {have}.",
                    ephemeral=True
                )
                return
        
        # Process the trade
        if price_credits:
            # Credit transaction
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (price_credits, interaction.user.id)
            )
        
        elif trade_for_item:
            # Item trade
            # Remove required items
            player_item = self.bot.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                (interaction.user.id, trade_for_item),
                fetch='one'
            )
            
            if player_item[1] == trade_quantity_required:
                # Remove completely
                self.bot.db.execute_query(
                    "DELETE FROM inventory WHERE item_id = ?",
                    (player_item[0],)
                )
            else:
                # Reduce quantity
                self.bot.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                    (trade_quantity_required, player_item[0])
                )
        
        # Give item to player
        existing_item = self.bot.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, item_name),
            fetch='one'
        )
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + 1 WHERE item_id = ?",
                (existing_item[0],)
            )
        else:
            # Create metadata
            metadata = ItemConfig.create_item_metadata(item_name)
            
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, metadata)
                   VALUES (?, ?, ?, 1, ?, ?)''',
                (interaction.user.id, item_name, item_type, description, metadata)
            )
        
        # Update NPC inventory
        if quantity == 1:
            self.bot.db.execute_query(
                "DELETE FROM npc_trade_inventory WHERE trade_item_id = ?",
                (trade_item_id,)
            )
        else:
            self.bot.db.execute_query(
                "UPDATE npc_trade_inventory SET quantity = quantity - 1 WHERE trade_item_id = ?",
                (trade_item_id,)
            )
        
        embed = discord.Embed(
            title="✅ Trade Successful",
            description=f"You traded for **{item_name}**!",
            color=0x00ff00
        )
        
        if price_credits:
            embed.add_field(name="Cost", value=f"{price_credits:,} credits", inline=True)
        elif trade_for_item:
            embed.add_field(name="Traded", value=f"{trade_quantity_required}x {trade_for_item}", inline=True)
        
        embed.add_field(name="Received", value=f"1x {item_name}", inline=True)
        embed.add_field(name="Rarity", value=rarity.title(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(NPCInteractionsCog(bot))