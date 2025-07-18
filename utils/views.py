# utils/views.py
import discord
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict
import uuid
import math
from utils.ship_data import get_random_starter_ship
    
# Replace the entire create_random_character function at the end of utils/views.py
from cogs.character import RadioModal
        
async def create_random_character(bot, interaction: discord.Interaction):
    """Create a random character for the user"""
    
    # Check if character already exists
    existing_char = bot.db.execute_query(
        "SELECT user_id FROM characters WHERE user_id = ?",
        (interaction.user.id,),
        fetch='one'
    )

    existing_identity = bot.db.execute_query(
        "SELECT user_id FROM character_identity WHERE user_id = ?",
        (interaction.user.id,),
        fetch='one'
    )

    if existing_char:
        await interaction.response.send_message(
            "You already have a character! Use the Login button instead.",
            ephemeral=True
        )
        return

    # Clean up orphaned identity records (from incomplete deletions)
    if existing_identity and not existing_char:
        bot.db.execute_query(
            "DELETE FROM character_identity WHERE user_id = ?",
            (interaction.user.id,)
        )
        print(f"🧹 Cleaned up orphaned identity record for user {interaction.user.id}")
    
    # Generate random name using the NPC naming system
    from utils.npc_data import generate_npc_name
    first_name, last_name = generate_npc_name()
    random_name = f"{first_name} {last_name}"
    
    # Generate random age
    age = random.randint(18, 80)
    
    # Generate random birth date
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)  # Safe day that works for all months
    
    # Get galaxy start date
    galaxy_info = bot.db.execute_query(
        "SELECT start_date FROM galaxy_info WHERE galaxy_id = 1",
        fetch='one'
    )

    if galaxy_info and galaxy_info[0]:
        raw_date = galaxy_info[0]
        parts = raw_date.split('-')
        if len(parts) == 3:
            try:
                start_year = int(parts[0]) if len(parts[0]) == 4 else int(parts[2])
            except ValueError:
                start_year = 2751
        else:
            start_year = 2751
    else:
        start_year = 2751  # Default
    
    # Calculate birth year
    birth_year = start_year - age
    
    # Generate unique callsign
    import string
    
    def generate_callsign():
        letters = ''.join(random.choices(string.ascii_uppercase, k=4))
        numbers = ''.join(random.choices(string.digits, k=4))
        return f"{letters}-{numbers}"
    
    callsign = generate_callsign()
    while bot.db.execute_query("SELECT user_id FROM characters WHERE callsign = ?", (callsign,), fetch='one'):
        callsign = generate_callsign()
    
    # Generate balanced starting stats (total of 50 points)
    stats = [10, 10, 10, 10]  # Base stats
    bonus_points = 10

    # Randomly distribute bonus points
    for _ in range(bonus_points):
        stat_idx = random.randint(0, 3)
        stats[stat_idx] += 1

    engineering, navigation, combat, medical = stats

    # Generate random starting ship
    ship_type, ship_name, exterior_desc, interior_desc = get_random_starter_ship()

    # Create basic ship
    bot.db.execute_query(
        "INSERT INTO ships (owner_id, name, ship_type, exterior_description, interior_description) VALUES (?, ?, ?, ?, ?)",
        (interaction.user.id, ship_name, ship_type, exterior_desc, interior_desc)
    )

    ship_id = bot.db.execute_query(
        "SELECT ship_id FROM ships WHERE owner_id = ? ORDER BY ship_id DESC LIMIT 1",
        (interaction.user.id,),
        fetch='one'
    )[0]

    # Add the ship to player_ships table and set as active
    bot.db.execute_query(
        '''INSERT INTO player_ships (owner_id, ship_id, is_active) VALUES (?, ?, 1)''',
        (interaction.user.id, ship_id)
    )
    # Generate ship activities
    from utils.ship_activities import ShipActivityManager
    activity_manager = ShipActivityManager(bot)
    activity_manager.generate_ship_activities(ship_id, ship_type)
    # Get random colony for spawning
    rows = bot.db.execute_query(
        "SELECT location_id FROM locations WHERE location_type = 'colony'",
        fetch='all'
    )

    if not rows:
        await interaction.response.send_message(
            "No colonies available! Contact an administrator to generate locations first.",
            ephemeral=True
        )
        return

    # First, try to find colonies that have at least one active corridor
    valid = []
    for row in rows:
        loc_id = row[0]
        has_route = bot.db.execute_query(
            "SELECT 1 FROM corridors WHERE origin_location = ? AND is_active = 1 LIMIT 1",
            (loc_id,),
            fetch='one'
        )
        if has_route:
            valid.append(loc_id)

    # If no colonies with active routes are found, fall back to any colony
    if not valid:
        valid = [row[0] for row in rows]

    spawn_location = random.choice(valid)
    
    # Create character with active_ship_id set (no appearance or biography)
    bot.db.execute_query(
        '''INSERT INTO characters 
           (user_id, name, callsign, appearance, current_location, ship_id, active_ship_id,
            engineering, navigation, combat, medical) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (interaction.user.id, random_name, callsign, "", 
         spawn_location, ship_id, ship_id, engineering, navigation, combat, medical)
    )
    
    # Create character identity record (no biography)
    bot.db.execute_query(
        '''INSERT OR REPLACE INTO character_identity 
           (user_id, birth_month, birth_day, birth_year, age, birthplace_id)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (interaction.user.id, birth_month, birth_day, birth_year, age, spawn_location)
    )
    
    # Give starting inventory with proper metadata
    from utils.item_config import ItemConfig

    starting_items = [
        "Emergency Rations",
        "Basic Tools", 
        "Basic Med Kit"
    ]

    for item_name in starting_items:
        item_def = ItemConfig.get_item_definition(item_name)
        if item_def:
            metadata = ItemConfig.create_item_metadata(item_name)
            quantity = 5 if item_name == "Emergency Rations" else 1
            
            bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, item_name, item_def["type"], quantity, 
                 item_def["description"], item_def["base_value"], metadata)
            )
    
    # Get location info for response
    location_info = bot.db.execute_query(
        "SELECT name FROM locations WHERE location_id = ?",
        (spawn_location,),
        fetch='one'
    )
    
    # Auto-login the character
    bot.db.execute_query(
        "UPDATE characters SET is_logged_in = 1, login_time = CURRENT_TIMESTAMP, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
        (interaction.user.id,)
    )

    # Update activity tracker
    if hasattr(bot, 'activity_tracker'):
        bot.activity_tracker.update_activity(interaction.user.id)
    
    # Give location access
    from utils.channel_manager import ChannelManager
    channel_manager = ChannelManager(bot)
    
    # Change user's display name to character name
    try:
        display_name = random_name[:32]  # Discord limit is 32 characters
        await interaction.user.edit(nick=display_name, reason="Random character name sync")
        print(f"🏷️ Changed {interaction.user.name}'s nickname to '{display_name}'")
    except discord.Forbidden:
        print(f"❌ No permission to change nickname for {interaction.user.name}")
    except discord.HTTPException as e:
        print(f"❌ Failed to change nickname for {interaction.user.name}: {e}")
    except Exception as e:
        print(f"❌ Unexpected error changing nickname for {interaction.user.name}: {e}")
    
    success = await channel_manager.give_user_location_access(interaction.user, spawn_location)
    location_name = location_info[0] if location_info else "Unknown Colony"
    
    embed = discord.Embed(
        title="🎲 Random Character Created!",
        description=f"Welcome to the galaxy, **{random_name}**!",
        color=0x00ff00
    )
    
    embed.add_field(name="Generated Name", value=random_name, inline=True)
    embed.add_field(name="Age", value=f"{age} years old", inline=True)
    embed.add_field(name="Radio Callsign", value=callsign, inline=True)
    embed.add_field(name="Birthplace", value=location_name, inline=True)
    embed.add_field(name="Born", value=f"{birth_month:02d}/{birth_day:02d}/{birth_year}", inline=True)
    embed.add_field(name="Starting Ship", value=f"{ship_name} ({ship_type})", inline=True)
    embed.add_field(name="Starting Credits", value="500", inline=True)
    embed.add_field(name="Stats", value=f"ENG: {engineering}, NAV: {navigation}, CMB: {combat}, MED: {medical}", inline=True)
    
    embed.add_field(
        name="🎲 Random Generation", 
        value="This character was randomly generated. You can customize your name, DoB, age, appearance and biography later at an Administration location.",
        inline=False
    )
    
    if success:
        embed.add_field(
            name="📍 Location Access", 
            value=f"A channel has been created for {location_name}. Check your channel list!",
            inline=False
        )
    else:
        embed.add_field(
            name="⚠️ Location Access", 
            value=f"Character created but couldn't create channel for {location_name}. Contact an admin.",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
class CharacterCreationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
    
    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.primary, emoji="👤")
    async def create_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CharacterCreationModal(self.bot))

class CharacterCreationModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Create Your Character")
        self.bot = bot
        
        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character's name...",
            max_length=50,
            required=True
        )
        
        self.age_input = discord.ui.TextInput(
            label="Age",
            placeholder="Enter your character's age (18-80)...",
            max_length=3,
            required=True
        )
        
        self.birth_date_input = discord.ui.TextInput(
            label="Birth Date",
            placeholder="MM/DD (e.g., 03/15 for March 15th)...",
            max_length=5,
            required=True
        )
        
        self.appearance_input = discord.ui.TextInput(
            label="Appearance",
            placeholder="Describe your character's appearance...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        
        self.biography_input = discord.ui.TextInput(
            label="Biography (Optional)",
            placeholder="Tell us about your character's background...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        
        # Only add 5 components (Discord's limit)
        self.add_item(self.name_input)
        self.add_item(self.age_input)
        self.add_item(self.birth_date_input)
        self.add_item(self.appearance_input)
        self.add_item(self.biography_input)
        # Removed image_url_input to stay within Discord's 5-component limit
    # Updated function in views.py - replace the previous version


    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if character already exists
        existing_char = self.bot.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        existing_identity = self.bot.db.execute_query(
            "SELECT user_id FROM character_identity WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )

        if existing_char:
            await interaction.followup.send(
                "You already have a character! Use `/character view` to see your stats.",
                ephemeral=True
            )
            return

        # Clean up orphaned identity records (from incomplete deletions)
        if existing_identity and not existing_char:
            self.bot.db.execute_query(
                "DELETE FROM character_identity WHERE user_id = ?",
                (interaction.user.id,)
            )
            print(f"🧹 Cleaned up orphaned identity record for user {interaction.user.id}")
        
        # Validate age
        try:
            age = int(self.age_input.value)
            if age < 18 or age > 80:
                await interaction.followup.send("Age must be between 18 and 80.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Please enter a valid age.", ephemeral=True)
            return
        
        # Validate birth date
        try:
            birth_month, birth_day = map(int, self.birth_date_input.value.split('/'))
            if birth_month < 1 or birth_month > 12 or birth_day < 1 or birth_day > 31:
                raise ValueError
        except ValueError:
            await interaction.followup.send("Please enter birth date in MM/DD format.", ephemeral=True)
            return
        
        # Get galaxy start date
        galaxy_info = self.bot.db.execute_query(
            "SELECT start_date FROM galaxy_info WHERE galaxy_id = 1",
            fetch='one'
        )

        if galaxy_info and galaxy_info[0]:
            raw_date = galaxy_info[0]
            parts = raw_date.split('-')
            if len(parts) == 3:
                try:
                    start_year = int(parts[0]) if len(parts[0]) == 4 else int(parts[2])
                except ValueError:
                    start_year = 2751
            else:
                start_year = 2751
        else:
            start_year = 2751  # Default
        
        # Calculate birth year
        birth_year = start_year - age
        
        # Generate unique callsign
        import random
        import string
        
        def generate_callsign():
            letters = ''.join(random.choices(string.ascii_uppercase, k=4))
            numbers = ''.join(random.choices(string.digits, k=4))
            return f"{letters}-{numbers}"
        
        callsign = generate_callsign()
        while self.bot.db.execute_query("SELECT user_id FROM characters WHERE callsign = ?", (callsign,), fetch='one'):
            callsign = generate_callsign()
        
        # Generate balanced starting stats (total of 50 points)
        stats = [10, 10, 10, 10]  # Base stats
        bonus_points = 10

        # Randomly distribute bonus points
        for _ in range(bonus_points):
            stat_idx = random.randint(0, 3)
            stats[stat_idx] += 1

        engineering, navigation, combat, medical = stats

        # Generate random starting ship
        ship_type, ship_name, exterior_desc, interior_desc = get_random_starter_ship()

        # Create basic ship
        self.bot.db.execute_query(
            "INSERT INTO ships (owner_id, name, ship_type, exterior_description, interior_description) VALUES (?, ?, ?, ?, ?)",
            (interaction.user.id, ship_name, ship_type, exterior_desc, interior_desc)
        )

        ship_id = self.bot.db.execute_query(
            "SELECT ship_id FROM ships WHERE owner_id = ? ORDER BY ship_id DESC LIMIT 1",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # Add the ship to player_ships table and set as active
        self.bot.db.execute_query(
            '''INSERT INTO player_ships (owner_id, ship_id, is_active) VALUES (?, ?, 1)''',
            (interaction.user.id, ship_id)
        )
        # Generate ship activities
        from utils.ship_activities import ShipActivityManager
        activity_manager = ShipActivityManager(self.bot)
        activity_manager.generate_ship_activities(ship_id, ship_type)
        # Get random colony for spawning
        rows = self.bot.db.execute_query(
            "SELECT location_id FROM locations WHERE location_type = 'colony'",
            fetch='all'
        )

        if not rows:
            await interaction.followup.send(
                "No colonies available! Contact an administrator to generate locations first.",
                ephemeral=True
            )
            return

        # First, try to find colonies that have at least one active corridor
        valid = []
        for row in rows:
            loc_id = row[0]
            has_route = self.bot.db.execute_query(
                "SELECT 1 FROM corridors WHERE origin_location = ? AND is_active = 1 LIMIT 1",
                (loc_id,),
                fetch='one'
            )
            if has_route:
                valid.append(loc_id)

        # If no colonies with active routes are found, fall back to any colony
        if not valid:
            valid = [row[0] for row in rows]

        spawn_location = random.choice(valid)

        # Validate image URL if provided
        image_url = None
        # Image URL can be set later using a separate command since Discord modals are limited to 5 inputs
        
        # Create character with active_ship_id set
        self.bot.db.execute_query(
            '''INSERT INTO characters 
               (user_id, name, callsign, appearance, image_url, current_location, ship_id, active_ship_id,
                engineering, navigation, combat, medical) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (interaction.user.id, self.name_input.value, callsign,
             self.appearance_input.value or "No description provided", image_url,
             spawn_location, ship_id, ship_id, engineering, navigation, combat, medical)
        )
        # Create character identity record
        self.bot.db.execute_query(
            '''INSERT OR REPLACE INTO character_identity 
               (user_id, birth_month, birth_day, birth_year, age, biography, birthplace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (interaction.user.id, birth_month, birth_day, birth_year, age, 
             self.biography_input.value or None, spawn_location)
        )
        
        # Give starting inventory with proper metadata
        from .item_config import ItemConfig

        starting_items = [
            "Emergency Rations",
            "Basic Tools", 
            "Basic Med Kit"
        ]

        for item_name in starting_items:
            item_def = ItemConfig.get_item_definition(item_name)
            if item_def:
                metadata = ItemConfig.create_item_metadata(item_name)
                quantity = 5 if item_name == "Emergency Rations" else 1
                
                self.bot.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (interaction.user.id, item_name, item_def["type"], quantity, 
                     item_def["description"], item_def["base_value"], metadata)
                )
        
        # Get location info for response
        location_info = self.bot.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (spawn_location,),
            fetch='one'
        )
        
        # Auto-login the character
        self.bot.db.execute_query(
            "UPDATE characters SET is_logged_in = 1, login_time = CURRENT_TIMESTAMP, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
            (interaction.user.id,)
        )

        # Update activity tracker
        if hasattr(self.bot, 'activity_tracker'):
            self.bot.activity_tracker.update_activity(interaction.user.id)
        
        # Give location access
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Change user's display name to character name
        try:
            display_name = self.name_input.value[:32]  # Discord limit is 32 characters
            await interaction.user.edit(nick=display_name, reason="Character name sync")
            print(f"🏷️ Changed {interaction.user.name}'s nickname to '{display_name}'")
        except discord.Forbidden:
            print(f"❌ No permission to change nickname for {interaction.user.name}")
        except discord.HTTPException as e:
            print(f"❌ Failed to change nickname for {interaction.user.name}: {e}")
        except Exception as e:
            print(f"❌ Unexpected error changing nickname for {interaction.user.name}: {e}")
        
        success = await channel_manager.give_user_location_access(interaction.user, spawn_location)
        location_name = location_info[0] if location_info else "Unknown Colony"
        
        embed = discord.Embed(
            title="Character Created!",
            description=f"Welcome to the galaxy, {self.name_input.value}!",
            color=0x00ff00
        )
        
        embed.add_field(name="Birthplace", value=location_name, inline=True)
        embed.add_field(name="Age", value=f"{age} years old", inline=True)
        embed.add_field(name="Radio Callsign", value=callsign, inline=True)
        embed.add_field(name="Born", value=f"{birth_month:02d}/{birth_day:02d}/{birth_year}", inline=True)
        embed.add_field(name="Starting Ship", value=f"{ship_name} ({ship_type})", inline=True)
        embed.add_field(name="Starting Credits", value="500", inline=True)
        
        if success:
            embed.add_field(
                name="📍 Location Access", 
                value=f"A channel has been created for {location_name}. Check your channel list!",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ Location Access", 
                value=f"Character created but couldn't create channel for {location_name}. Contact an admin.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
class LocationView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        # Fetch current location for travel
        loc_row = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        self.current_location_id = loc_row[0] if loc_row else None
        # Determine current dock status
        status_row = self.bot.db.execute_query(
            "SELECT location_status FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        location_status = status_row[0] if status_row else "docked"

        # Enable/disable buttons based on dock status
        for item in self.children:
            # Travel only when undocked
            if getattr(item, 'label', None) == "Travel":
                item.disabled = (location_status == "docked")
            # Jobs, Shop & Services only when docked
            if getattr(item, 'label', None) in ("Jobs", "Shop", "Services", "NPCs"):
                item.disabled = (location_status != "docked")
                        # Sub-Areas only when docked
            if getattr(item, 'label', None) == "Sub-Areas":
                item.disabled = (location_status != "docked")
        cog = bot.get_cog('CharacterCog')

        # Add Dock/Undock button dynamically
        if location_status == "docked":
            undock_btn = discord.ui.Button(
                label="Undock",
                style=discord.ButtonStyle.primary,
                emoji="🚀"
            )
            async def undock_callback(interaction: discord.Interaction):
                # call the underlying callback of the slash command
                await cog.undock_ship.callback(cog, interaction)
            undock_btn.callback = undock_callback
            self.add_item(undock_btn)
        else:
            dock_btn = discord.ui.Button(
                label="Dock",
                style=discord.ButtonStyle.primary,
                emoji="🛬"
            )
            async def dock_callback(interaction: discord.Interaction):
                # same here
                await cog.dock_ship.callback(cog, interaction)
            dock_btn.callback = dock_callback
            self.add_item(dock_btn)
            
    # Add this method to LocationView class
    async def _check_ownership_status(self, location_id: int) -> dict:
        """Get ownership information for a location"""
        ownership = self.bot.db.execute_query(
            '''SELECT lo.owner_id, lo.custom_name, lo.custom_description,
                      c.name as owner_name, g.name as group_name
               FROM location_ownership lo
               LEFT JOIN characters c ON lo.owner_id = c.user_id
               LEFT JOIN groups g ON lo.group_id = g.group_id
               WHERE lo.location_id = ?''',
            (location_id,),
            fetch='one'
        )
        
        if ownership:
            return {
                'owned': True,
                'owner_id': ownership[0],
                'custom_name': ownership[1],
                'custom_description': ownership[2],
                'owner_name': ownership[3],
                'group_name': ownership[4]
            }
        
        return {'owned': False}
    @discord.ui.button(label="Travel", style=discord.ButtonStyle.primary, emoji="🚀")
    async def travel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # only the character owner can click
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🚫 This is not your character.", ephemeral=True)
            return

        # check if the character is currently docked
        row = self.bot.db.execute_query(
            "SELECT location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if row and row[0] == "docked":
            await interaction.response.send_message(
                "❌ You must undock before travelling! Use `/character undock`.",
                ephemeral=True
            )
            return

        # check if already in a travel session
        traveling = self.bot.db.execute_query(
            "SELECT session_id FROM travel_sessions WHERE user_id = ? AND status = 'traveling'",
            (interaction.user.id,),
            fetch='one'
        )
        if traveling:
            await interaction.response.send_message(
                "🚧 You’re already travelling along a corridor.",
                ephemeral=True
            )
            return
            
        # Get the travel cog and call the travel_go command
        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog:
            await travel_cog.travel_go.callback(travel_cog, interaction)
        else:
            await interaction.response.send_message("Travel system is currently unavailable.", ephemeral=True)
    
    @discord.ui.button(label="Jobs", style=discord.ButtonStyle.success, emoji="💼")
    async def jobs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get current location
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        # Check if location has jobs
        location_info = self.bot.db.execute_query(
            "SELECT has_jobs, name FROM locations WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.response.send_message("No jobs available at this location.", ephemeral=True)
            return
        
        # Get available jobs
        jobs = self.bot.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
               FROM jobs 
               WHERE location_id = ? AND is_taken = 0 AND expires_at > datetime('now')
               ORDER BY reward_money DESC''',
            (char_location[0],),
            fetch='all'
        )
        
        if not jobs:
            # Generate some random jobs if none exist
            await self._generate_random_jobs(char_location[0])
            jobs = self.bot.db.execute_query(
                '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
                   FROM jobs 
                   WHERE location_id = ? AND is_taken = 0 AND expires_at > datetime('now')
                   ORDER BY reward_money DESC''',
                (char_location[0],),
                fetch='all'
            )
        
        view = JobSelectView(self.bot, interaction.user.id, jobs, location_info[1])
        
        embed = discord.Embed(
            title=f"Jobs Available - {location_info[1]}",
            description="Available work opportunities",
            color=0xffd700
        )
        
        if jobs:
            job_text = []
            for job in jobs[:5]:
                job_id, title, desc, reward, skill, min_level, danger, duration = job
                danger_text = "⭐" * danger
                skill_text = f" (Requires {skill} {min_level}+)" if skill else ""
                time_text = f"{duration}min"
                
                job_text.append(f"**{title}** - {reward} credits {danger_text}")
                job_text.append(f"  {desc[:80]}{'...' if len(desc) > 80 else ''}")
                job_text.append(f"  ⏱️ {time_text}{skill_text}")
                job_text.append("")
            
            embed.description = "\n".join(job_text)
        else:
            embed.description = "No jobs currently available."
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Shop", style=discord.ButtonStyle.secondary, emoji="🛒")
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your panel!", ephemeral=True)

        # Call the actual /shop list command from EconomyCog
        econ_cog = self.bot.get_cog('EconomyCog')
        if not econ_cog:
            return await interaction.response.send_message(
                "❌ Shop system is unavailable right now.", ephemeral=True
            )

        # Forward the interaction into the shop_list handler
        await econ_cog.shop_list.callback(econ_cog, interaction)
    
    @discord.ui.button(label="Services", style=discord.ButtonStyle.secondary, emoji="🔧")
    async def services(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get current location services
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        location_services = self.bot.db.execute_query(
            '''SELECT name, has_medical, has_repairs, has_fuel, has_upgrades, wealth_level, has_shipyard
               FROM locations WHERE location_id = ?''',
            (char_location[0],),
            fetch='one'
        )
        
        if not location_services:
            await interaction.response.send_message("Location information not found!", ephemeral=True)
            return
        
        
        name, has_medical, has_repairs, has_fuel, has_upgrades, wealth, has_shipyard = location_services
        
        embed = discord.Embed(
            title=f"Services - {name}",
            description="Available services at this location",
            color=0x4169E1
        )
        
        services = []
        if has_fuel:
            fuel_price = max(5, 10 - wealth)  # Better locations have cheaper fuel
            services.append(f"⛽ **Fuel Refill** - {fuel_price} credits per unit")
        
        if has_repairs:
            repair_quality = "Premium" if wealth >= 7 else "Standard" if wealth >= 4 else "Basic"
            services.append(f"🔨 **Ship Repairs** - {repair_quality} quality")
        
        if has_medical:
            medical_quality = "Advanced" if wealth >= 8 else "Standard" if wealth >= 5 else "Basic"
            services.append(f"⚕️ **Medical Treatment** - {medical_quality} care")
        
        if has_upgrades:
            services.append(f"⬆️ **Ship Upgrades** - Performance enhancements available")
        # Check for logbook availability
        has_logbook = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )[0] > 0
        
        if has_shipyard:  # Add this block
            shipyard_quality = "Advanced" if wealth >= 8 else "Standard" if wealth >= 5 else "Basic"
            services.append(f"🏗️ **Shipyard** - {shipyard_quality} ship trading and management")
        if has_logbook:
            services.append(f"📜 **Logbook Access** - View and add entries")
        if services:
            embed.add_field(name="Available Services", value="\n".join(services), inline=False)
        else:
            embed.add_field(name="No Services", value="This location offers no services.", inline=False)
        
        # Add wealth indicator
        wealth_text = "💰" * min(wealth // 2, 5) if wealth > 0 else "💸"
        embed.add_field(name="Economic Status", value=f"{wealth_text} Wealth Level: {wealth}/10", inline=False)
        
        view = ServicesView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="Sub-Areas", style=discord.ButtonStyle.secondary, emoji="🏢")
    async def sub_locations(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get current location
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        from utils.sub_locations import SubLocationManager
        sub_manager = SubLocationManager(self.bot)
        
        available_subs = await sub_manager.get_available_sub_locations(char_location[0])
        
        if not available_subs:
            await interaction.response.send_message("No sub-areas available at this location.", ephemeral=True)
            return
        
        view = SubLocationSelectView(self.bot, interaction.user.id, char_location[0], available_subs)
        
        embed = discord.Embed(
            title="🏢 Sub-Areas",
            description="Choose an area to visit within this location",
            color=0x6a5acd
        )
        
        for sub in available_subs:
            status = "🟢 Active" if sub['exists'] else "⚫ Create"
            embed.add_field(
                name=f"{sub['icon']} {sub['name']}",
                value=f"{sub['description'][:100]}...\n**Status:** {status}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="NPCs", style=discord.ButtonStyle.secondary, emoji="👤")
    async def npc_interactions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle NPC interactions button"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get character's current location
        char_info = self.bot.db.execute_query(
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
        static_npcs = self.bot.db.execute_query(
            '''SELECT npc_id, name, age, occupation, personality, trade_specialty
               FROM static_npcs WHERE location_id = ?''',
            (location_id,),
            fetch='all'
        )
        
        dynamic_npcs = self.bot.db.execute_query(
            '''SELECT npc_id, name, age, ship_name, ship_type
               FROM dynamic_npcs 
               WHERE current_location = ? AND is_alive = 1 AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not static_npcs and not dynamic_npcs:
            await interaction.response.send_message("No NPCs are available for interaction at this location.", ephemeral=True)
            return
        
        # Import the NPCSelectView class and create the view
        from cogs.npc_interactions import NPCSelectView
        view = NPCSelectView(self.bot, interaction.user.id, location_id, static_npcs, dynamic_npcs)
        
        embed = discord.Embed(
            title="👥 NPCs at Location",
            description="Select an NPC to interact with:",
            color=0x6c5ce7
        )
        
        # Add some info about available NPCs
        if static_npcs:
            static_list = [f"• **{name}** - {occupation}" for npc_id, name, age, occupation, personality, trade_specialty in static_npcs[:5]]
            embed.add_field(
                name="🏢 Residents and locals",
                value="\n".join(static_list) + (f"\n*...and {len(static_npcs)-5} more*" if len(static_npcs) > 5 else ""),
                inline=False
            )
        
        if dynamic_npcs:
            dynamic_list = [f"• **{name}** - Captain of {ship_name}" for npc_id, name, age, ship_name, ship_type in dynamic_npcs[:5]]
            embed.add_field(
                name="🚀 Visiting Travellers",
                value="\n".join(dynamic_list) + (f"\n*...and {len(dynamic_npcs)-5} more*" if len(dynamic_npcs) > 5 else ""),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    async def _generate_random_jobs(self, location_id: int):
        """Generate some random jobs for a location"""
        job_templates = [
            ("Cargo Loading", "...", 80, None, 0, 1, 4),         # Was 30, now 4
            ("System Maintenance", "...", 120, "engineering", 5, 2, 8),   # Was 60, now 8
            ("Medical Assistance", "...", 150, "medical", 8, 1, 10),       # Was 45, now 10
            ("Security Patrol", "...", 200, "combat", 10, 3, 10),          # Was 90, now 10
            ("Navigation Calibration", "...", 180, "navigation", 12, 2, 8), # Was 75, now 8
            ("Emergency Repairs", "...", 300, "engineering", 15, 4, 10),     # Was 120, now 10
            ("Hazmat Cleanup", "...", 250, None, 0, 3, 6),               # Was 60, now 6
            ("Data Recovery", "...", 350, "engineering", 18, 2, 6)       # Was 90, now 6
        ]


        
        # Generate 2-4 random jobs
        num_jobs = random.randint(2, 4)
        for _ in range(num_jobs):
            template = random.choice(job_templates)
            title, desc, base_reward, skill, min_skill, danger, duration = template
            
            # Add some randomization
            reward = base_reward + random.randint(-20, 50)
            # And reduce the randomization range:
            duration = duration + random.randint(-5, 10)  # Was ±15-30, now ±5-10
            
            # Set expiration time (2-8 hours from now)
            expire_hours = random.randint(2, 8)
            
            self.bot.db.execute_query(
                '''INSERT INTO jobs 
                   (location_id, title, description, reward_money, required_skill, 
                    min_skill_level, danger_level, duration_minutes, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+{} hours'))'''.format(expire_hours),
                (location_id, title, desc, reward, skill, min_skill, danger, duration)
            )
class RoutePlottingModal(discord.ui.Modal, title="Plot Route"):
    """A modal for plotting a route to a destination."""
    destination_input = discord.ui.TextInput(
        label="Destination Name",
        placeholder="Enter the name of your destination...",
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, travel_cog):
        super().__init__()
        self.travel_cog = travel_cog

    async def on_submit(self, interaction: discord.Interaction):
        # This calls the handler function in the TravelCog
        await self.travel_cog.plot_route_callback(interaction, self.destination_input.value)
class TravelSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, corridors: List[Tuple]):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        
        # Get current location name for clearer display
        current_location_name = "Unknown"
        if corridors:
            # Get current location from character
            char_location = self.bot.db.execute_query(
                "SELECT l.name FROM characters c JOIN locations l ON c.current_location = l.location_id WHERE c.user_id = ?",
                (self.user_id,),
                fetch='one'
            )
            if char_location:
                current_location_name = char_location[0]

        # Create select options
        options = []
        for corridor in corridors[:25]:  # Discord limit
            corridor_id, name, dest_name, travel_time, danger, fuel_cost = corridor
            
            # Use actual travel time from database - NO clamping
            mins, secs = divmod(travel_time, 60)
            hours = mins // 60
            mins = mins % 60
            
            if hours > 0:
                time_text = f"{hours}h {mins}m {secs}s"
            else:
                time_text = f"{mins}m {secs}s"
                
            danger_text = "⚠️" * danger
            
            # IMPROVED: Clear departure → destination format
            label = f"{current_location_name} → {dest_name}"
            description = f"via {name[:25]} · {time_text} · {fuel_cost} fuel {danger_text}"
            
            options.append(
                discord.SelectOption(
                    label=label[:100],  # Truncate if too long
                    description=description[:100],
                    value=str(corridor_id)
                )
            )
        
        if options:
            select = discord.ui.Select(placeholder="Choose destination...", options=options)
            select.callback = self.travel_callback
            self.add_item(select)
    
    async def travel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        corridor_id = int(interaction.data['values'][0])
        
        # Get corridor and ship info
        corridor_info = self.db.execute_query(
            '''SELECT c.*, ol.name as origin_name, dl.name as dest_name
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.corridor_id = ?''',
            (corridor_id,),
            fetch='one'
        )
        
        ship_info = self.db.execute_query(
            '''SELECT s.current_fuel, s.fuel_capacity, c.group_id
               FROM characters c
               JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not corridor_info or not ship_info:
            await interaction.response.send_message("Error retrieving travel information!", ephemeral=True)
            return
        
        # Check fuel requirements
        fuel_needed = corridor_info[5]  # fuel_cost
        current_fuel = ship_info[0]
        
        if current_fuel < fuel_needed:
            await interaction.response.send_message(
                f"❌ **Insufficient fuel!**\nNeed: {fuel_needed} units\nHave: {current_fuel} units\n\nRefuel at this location first.",
                ephemeral=True
            )
            return
        
        # Get current location name for clearer display
        current_location_name = self.bot.db.execute_query(
            "SELECT l.name FROM characters c JOIN locations l ON c.current_location = l.location_id WHERE c.user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]

        embed = discord.Embed(
            title="Confirm Travel",
            description=f"Travel from **{current_location_name}** → **{corridor_info[8]}** via {corridor_info[1]}?",
            color=0xff6600
        )
        
        # Use ACTUAL travel time from database - no clamping!
        actual_secs = corridor_info[4]  # travel_time from database
        mins, secs = divmod(actual_secs, 60)
        hours = mins // 60
        mins = mins % 60
        
        if hours > 0:
            time_text = f"{hours}h {mins}m {secs}s"
        else:
            time_text = f"{mins}m {secs}s"
        
        danger_text = "⚠️" * corridor_info[6] if corridor_info[6] > 0 else "Safe"
        
        embed.add_field(name="Travel Time", value=time_text, inline=True)
        embed.add_field(name="Fuel Cost", value=f"{fuel_needed} units", inline=True)
        embed.add_field(name="Danger Level", value=danger_text, inline=True)
        
        view = TravelConfirmView(self.bot, self.user_id, corridor_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class TravelConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, corridor_id: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.user_id = user_id
        self.corridor_id = corridor_id
    

    @discord.ui.button(label="Confirm Travel", style=discord.ButtonStyle.danger, emoji="🚀")
    async def confirm_travel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        # Get up-to-date corridor and character info
        corridor_info = self.db.execute_query(
            '''SELECT c.corridor_id, c.name, c.destination_location, c.travel_time, c.fuel_cost, 
                      l.name as dest_name, c.origin_location
               FROM corridors c JOIN locations l ON c.destination_location = l.location_id
               WHERE c.corridor_id = ?''',
            (self.corridor_id,), fetch='one'
        )
        char_info = self.db.execute_query(
            '''SELECT s.current_fuel FROM characters c JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.user_id = ?''',
            (self.user_id,), fetch='one'
        )

        if not corridor_info or not char_info:
            await interaction.followup.send("Error starting travel: Info not found.", ephemeral=True)
            return
        
        # Final fuel check
        fuel_needed = corridor_info[4]
        if char_info[0] < fuel_needed:
            await interaction.followup.send(f"Not enough fuel! Need {fuel_needed}, have {char_info[0]}.", ephemeral=True)
            return
            
        # Use the working logic from travel.py
        travel_cog = self.bot.get_cog('TravelCog')
        if not travel_cog:
            await interaction.followup.send("Travel system is currently unavailable.", ephemeral=True)
            return

        cid, cname, dest_loc_id, actual_travel_time, cost, dest_name, origin_id = corridor_info

        # Create transit channel
        transit_chan = await travel_cog.channel_mgr.create_transit_channel(
            interaction.guild, interaction.user, cname, dest_name
        )

        # Deduct fuel
        self.bot.db.execute_query(
            "UPDATE ships SET current_fuel = current_fuel - ? WHERE owner_id = ?",
            (cost, interaction.user.id)
        )

        # Record the session using ACTUAL travel time from database
        start = datetime.utcnow()
        end = start + timedelta(seconds=actual_travel_time)  # Use actual time, no clamping!
        self.bot.db.execute_query(
            """
            INSERT INTO travel_sessions
              (user_id, corridor_id, origin_location, destination_location,
               start_time, end_time, temp_channel_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'traveling')
            """,
            (interaction.user.id, cid, origin_id, dest_loc_id, start.isoformat(), end.isoformat(), transit_chan.id if transit_chan else None)
        )

        # Confirm departure
        mins, secs = divmod(actual_travel_time, 60)
        hours = mins // 60
        mins = mins % 60
        
        if hours > 0:
            time_display = f"{hours}h {mins}m {secs}s"
        else:
            time_display = f"{mins}m {secs}s"
        
        await interaction.followup.send(
            content=f"🚀 Departure confirmed for {dest_name}. ETA: {time_display}. Your transit channel is {transit_chan.mention if transit_chan else 'unavailable'}.",
            ephemeral=True
        )

        # Define and schedule the completion task
        async def complete_travel():
            await asyncio.sleep(actual_travel_time)  # Use actual time

            # Mark session completed
            self.bot.db.execute_query(
                "UPDATE travel_sessions SET status='completed' WHERE user_id=? AND corridor_id=?",
                (interaction.user.id, cid)
            )
            # Move character
            self.bot.db.execute_query(
                "UPDATE characters SET current_location=? WHERE user_id=?",
                (dest_loc_id, interaction.user.id)
            )
            # Announce arrival
            dest_chan = await travel_cog.channel_mgr.get_or_create_location_channel(interaction.guild, dest_loc_id, interaction.user)
            if dest_chan:
                await dest_chan.send(f"🚀 {interaction.user.mention} has arrived at **{dest_name}**! Welcome.")

            # Cleanup transit channel
            if transit_chan:
                await transit_chan.send(f"🚀 Arrived at **{dest_name}**! Journey complete.")
                await travel_cog.channel_mgr.cleanup_transit_channel(transit_chan.id, delay_seconds=30)
        
        self.bot.loop.create_task(complete_travel())
    
    async def _initiate_travel(self, interaction: discord.Interaction, corridor_info: tuple, char_info: tuple):
        """
        Initiate the actual travel process
        """
        from utils.channel_manager import ChannelManager
        import asyncio
        from datetime import datetime, timedelta
        
        # Extract info
        corridor_id = corridor_info[0]
        corridor_name = corridor_info[1]
        origin_location = corridor_info[2]
        destination_location = corridor_info[3]
        travel_time = corridor_info[4]
        fuel_cost = corridor_info[5]
        danger_level = corridor_info[6]
        origin_name = corridor_info[8]
        dest_name = corridor_info[9]
        
        user_id = char_info[0]
        current_location = char_info[1]
        current_fuel = char_info[2]
        group_id = char_info[3]
        
        channel_manager = ChannelManager(self.bot)
        
        # Determine travelers (solo or group)
        travelers = [user_id]
        if group_id:
            group_members = self.bot.db.execute_query(
                "SELECT user_id FROM characters WHERE group_id = ? AND current_location = ?",
                (group_id, current_location),
                fetch='all'
            )
            travelers = [member[0] for member in group_members]
        
        # Create transit channel
        if len(travelers) > 1:
            transit_channel = await channel_manager.create_transit_channel(
                interaction.guild, 
                travelers,
                corridor_name, 
                dest_name
            )
        else:
            transit_channel = await channel_manager.create_transit_channel(
                interaction.guild,
                interaction.user,
                corridor_name,
                dest_name
            )
        
        if not transit_channel:
            await interaction.followup.send("❌ Failed to create transit channel!", ephemeral=True)
            return
        
        # Remove access from origin location for all travelers
        for traveler_id in travelers:
            await channel_manager.remove_user_location_access(
                interaction.guild.get_member(traveler_id), 
                current_location
            )
            
            # Update character status to traveling
            self.bot.db.execute_query(
                "UPDATE characters SET status = 'traveling' WHERE user_id = ?",
                (traveler_id,)
            )
            
            # Consume fuel for each traveler's ship
            self.bot.db.execute_query(
                "UPDATE ships SET current_fuel = current_fuel - ? WHERE owner_id = ?",
                (fuel_cost, traveler_id)
            )
        
        # Create travel session
        end_time = datetime.now() + timedelta(seconds=travel_time)
        
        # Create sessions for each traveler
        for traveler_id in travelers:
            self.bot.db.execute_query(
                '''INSERT INTO travel_sessions 
                   (user_id, group_id, origin_location, destination_location, corridor_id, 
                    temp_channel_id, end_time, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'traveling')''',
                (traveler_id, group_id, origin_location, destination_location, 
                 corridor_id, transit_channel.id, end_time)
            )
        
        # Send departure message
        traveler_names = []
        for traveler_id in travelers:
            char_name = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (traveler_id,),
                fetch='one'
            )
            if char_name:
                traveler_names.append(char_name[0])
        
        departure_embed = discord.Embed(
            title="🚀 Journey Initiated",
            description=f"**{', '.join(traveler_names)}** {'have' if len(travelers) > 1 else 'has'} departed {origin_name}",
            color=0xff6600
        )
        
        departure_embed.add_field(name="Destination", value=dest_name, inline=True)
        departure_embed.add_field(name="Via", value=corridor_name, inline=True)
        departure_embed.add_field(name="Travel Time", value=f"{travel_time//60}m {travel_time%60}s", inline=True)
        departure_embed.add_field(name="Travelers", value=str(len(travelers)), inline=True)
        departure_embed.add_field(name="Transit Channel", value=transit_channel.mention, inline=True)
        departure_embed.add_field(name="Danger Level", value="⚠️" * danger_level, inline=True)
        
        await interaction.followup.send(embed=departure_embed, ephemeral=True)
        
        # Send initial status to transit channel
        status_embed = discord.Embed(
            title="📊 Transit Status",
            description="Journey in progress...",
            color=0x800080
        )
        
        status_embed.add_field(name="Progress", value="🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜ 30%", inline=False)
        status_embed.add_field(name="Estimated Arrival", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        
        status_message = await transit_channel.send(embed=status_embed)
        
        # Schedule travel completion and periodic updates
        asyncio.create_task(self._handle_travel_progress(
            travelers, corridor_info, transit_channel, status_message, travel_time
        ))
    
    async def _handle_travel_progress(self, travelers: list, corridor_info: tuple, 
                                    transit_channel: discord.TextChannel, status_message: discord.Message, 
                                    travel_time: int):
        """
        Handle travel progress updates and completion
        """
        corridor_id = corridor_info[0]
        corridor_name = corridor_info[1]
        destination_location = corridor_info[3]
        danger_level = corridor_info[6]
        dest_name = corridor_info[9]
        
        # Send periodic updates
        update_intervals = [0.25, 0.5, 0.75]  # 25%, 50%, 75% progress
        
        for progress in update_intervals:
            await asyncio.sleep(travel_time * progress)
            
            # Check if travel is still active
            active_sessions = self.bot.db.execute_query(
                "SELECT COUNT(*) FROM travel_sessions WHERE corridor_id = ? AND status = 'traveling'",
                (corridor_id,),
                fetch='one'
            )[0]
            
            if active_sessions == 0:
                return  # Travel was interrupted
            
            # Random corridor event chance
            if random.random() < (danger_level * 0.1):  # Higher danger = more events
                await self._trigger_corridor_event(transit_channel, travelers, danger_level)
            
            # Update progress
            progress_percent = int((progress + 0.25) * 100)
            progress_bar = "🟩" * (progress_percent // 10) + "⬜" * (10 - progress_percent // 10)
            
            try:
                embed = status_message.embeds[0]
                embed.set_field_at(0, name="Progress", value=f"{progress_bar} {progress_percent}%", inline=False)
                await status_message.edit(embed=embed)
            except:
                pass  # Failed to update progress
        
        # Complete travel
        await asyncio.sleep(travel_time * 0.25)  # Wait for final 25%
        await self._complete_travel(travelers, corridor_info, transit_channel)
    
    async def _trigger_corridor_event(self, channel: discord.TextChannel, travelers: list, danger_level: int):
        """
        Trigger a random corridor event
        """
        events = [
            ("Radiation Spike", "⚡ **Radiation Spike Detected!**\nCorridor radiation levels have increased. Monitor your exposure carefully.", 0xffaa00),
            ("Static Fog", "🌫️ **Static Fog Encountered!**\nElectromagnetic interference is affecting ship systems. Navigation may be impaired.", 0x808080),
            ("Vacuum Bloom", "🦠 **Vacuum Bloom Spores Detected!**\nOrganic contaminants in the corridor. Seal air filtration systems.", 0x8b4513),
            ("Corridor Turbulence", "💫 **Corridor Instability!**\nSpace-time fluctuations detected. Maintain course and speed.", 0x4b0082),
            ("System Malfunction", "⚠️ **Ship System Alert!**\nMinor system malfunction detected. Check ship status.", 0xff4444)
        ]
        
        # Higher danger levels get more severe events
        if danger_level >= 4:
            events.extend([
                ("Severe Radiation", "☢️ **SEVERE RADIATION WARNING!**\nDangerous radiation levels detected! Take immediate protective action!", 0xff0000),
                ("Corridor Collapse Warning", "💥 **CORRIDOR INSTABILITY CRITICAL!**\nMajor structural instability detected! Prepare for emergency procedures!", 0x8b0000)
            ])
        
        event_name, event_desc, color = random.choice(events)
        
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
        
        # Apply minor effects to travelers
        for traveler_id in travelers:
            if random.random() < 0.3:  # 30% chance of effect
                if "Radiation" in event_name:
                    # Minor health loss
                    self.bot.db.execute_query(
                        "UPDATE characters SET hp = MAX(1, hp - ?) WHERE user_id = ?",
                        (random.randint(2, 8), traveler_id)
                    )
                elif "System" in event_name:
                    # Minor ship damage
                    self.bot.db.execute_query(
                        "UPDATE ships SET hull_integrity = MAX(1, hull_integrity - ?) WHERE owner_id = ?",
                        (random.randint(1, 5), traveler_id)
                    )
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    async def _complete_travel(self, travelers: list, corridor_info: tuple, transit_channel: discord.TextChannel):
        """
        Complete the travel process
        """
        from utils.channel_manager import ChannelManager
        
        destination_location = corridor_info[3]
        dest_name = corridor_info[9]
        
        channel_manager = ChannelManager(self.bot)
        
        # Move all travelers to destination
        for traveler_id in travelers:
            # Update character location and status
            self.bot.db.execute_query(
                "UPDATE characters SET current_location = ?, status = 'active' WHERE user_id = ?",
                (destination_location, traveler_id)
            )
            
            # Give access to destination
            member = transit_channel.guild.get_member(traveler_id)
            if member:
                await channel_manager.give_user_location_access(member, destination_location)
        
        # Update travel sessions
        self.bot.db.execute_query(
            "UPDATE travel_sessions SET status = 'completed' WHERE temp_channel_id = ? AND status = 'traveling'",
            (transit_channel.id,)
        )
        
        # Send completion message
        completion_embed = discord.Embed(
            title="✅ Journey Complete!",
            description=f"Successfully arrived at **{dest_name}**!",
            color=0x00ff00
        )
        
        completion_embed.add_field(
            name="🎉 Welcome",
            value=f"You have safely exited the corridor and arrived at your destination. Check your new location channel for available services and opportunities.",
            inline=False
        )
        
        completion_embed.add_field(
            name="⏰ Transit Cleanup",
            value="This channel will be automatically deleted in 30 seconds.",
            inline=False
        )
        
        try:
            await transit_channel.send(embed=completion_embed)
        except:
            pass
        
        # Schedule channel cleanup
        asyncio.create_task(channel_manager.cleanup_transit_channel(transit_channel.id, 30))
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_travel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Travel cancelled.", ephemeral=True)

class PersistentLocationView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=None)  # No timeout for persistent view
        self.bot = bot
        self.user_id = user_id
        
        # Get current location and status
        char_data = self.bot.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if char_data:
            self.current_location_id = char_data[0]
            location_status = char_data[1]
        else:
            self.current_location_id = None
            location_status = "docked"
        
        # Configure buttons based on dock status and location services
        self._configure_buttons(location_status)
        
    def _configure_buttons(self, location_status: str):
        """Configure button states based on dock status"""
        self.clear_items()
        
        # Status-dependent buttons
        if location_status == "docked":
            self.add_item(self.jobs_panel)
            self.add_item(self.shop_management)
            self.add_item(self.sub_areas)
            self.add_item(self.npc_interactions)
            self.add_item(self.undock_button)
            self.add_item(self.route_button)
            
        else:  # in_space
            self.add_item(self.travel_button)
            self.add_item(self.dock_button)
            self.add_item(self.route_button)
            self.add_item(self.plot_route_button)

    from cogs.travel import TravelCog
    async def refresh_view(self, interaction: discord.Interaction = None):
        """Refresh the view when dock status changes"""
        char_data = self.bot.db.execute_query(
            "SELECT location_status FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if char_data:
            location_status = char_data[0]
            self._configure_buttons(location_status)
            
            # Update embed
            embed = discord.Embed(
                title="📍 Location Panel",
                description="Interactive Control Panel",
                color=0x4169E1
            )
            
            status_emoji = "🛬" if location_status == "docked" else "🚀"
            embed.add_field(
                name="Status",
                value=f"{status_emoji} {location_status.replace('_', ' ').title()}",
                inline=True
            )
            
            embed.add_field(
                name="Available Actions",
                value="Use the buttons below to interact with this location",
                inline=False
            )
            
            embed.set_footer(text="This panel updates automatically when your status changes")
            
            if interaction:
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                # Update without interaction (for background updates)
                panel_data = self.bot.db.execute_query(
                    "SELECT message_id, channel_id FROM user_location_panels WHERE user_id = ?",
                    (self.user_id,),
                    fetch='one'
                )
                
                if panel_data:
                    message_id, channel_id = panel_data
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.edit(embed=embed, view=self)
                        except:
                            pass
    
    @discord.ui.button(label="NPCs", style=discord.ButtonStyle.secondary, emoji="👤")
    async def npc_interactions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle NPC interactions button"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Same NPC logic as before
        char_info = self.bot.db.execute_query(
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
        static_npcs = self.bot.db.execute_query(
            '''SELECT npc_id, name, age, occupation, personality, trade_specialty
               FROM static_npcs WHERE location_id = ?''',
            (location_id,),
            fetch='all'
        )
        
        dynamic_npcs = self.bot.db.execute_query(
            '''SELECT npc_id, name, age, ship_name, ship_type
               FROM dynamic_npcs 
               WHERE current_location = ? AND is_alive = 1 AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not static_npcs and not dynamic_npcs:
            await interaction.response.send_message("No NPCs are available for interaction at this location.", ephemeral=True)
            return
        
        # Import the NPCSelectView class and create the view
        from cogs.npc_interactions import NPCSelectView
        view = NPCSelectView(self.bot, interaction.user.id, location_id, static_npcs, dynamic_npcs)
        
        embed = discord.Embed(
            title="👥 NPCs at Location",
            description="Select an NPC to interact with:",
            color=0x6c5ce7
        )
        
        # Add some info about available NPCs
        if static_npcs:
            static_list = [f"• **{name}** - {occupation}" for npc_id, name, age, occupation, personality, trade_specialty in static_npcs[:5]]
            embed.add_field(
                name="🏢 Residents and locals",
                value="\n".join(static_list) + (f"\n*...and {len(static_npcs)-5} more*" if len(static_npcs) > 5 else ""),
                inline=False
            )
        
        if dynamic_npcs:
            dynamic_list = [f"• **{name}** - Captain of {ship_name}" for npc_id, name, age, ship_name, ship_type in dynamic_npcs[:5]]
            embed.add_field(
                name="🚀 Visiting Travellers",
                value="\n".join(dynamic_list) + (f"\n*...and {len(dynamic_npcs)-5} more*" if len(dynamic_npcs) > 5 else ""),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="Plot Route", style=discord.ButtonStyle.success, emoji="📐", row=1)
    async def plot_route_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Opens a modal to plot a travel route."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return

        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog: 
            modal = RoutePlottingModal(travel_cog)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Travel system is currently unavailable.", ephemeral=True)
    @discord.ui.button(label="Jobs", style=discord.ButtonStyle.primary, emoji="💼")
    async def jobs_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        economy_cog = self.bot.get_cog('EconomyCog')
        if economy_cog:
            await economy_cog.job_list.callback(economy_cog, interaction)
    
    @discord.ui.button(label="Shop", style=discord.ButtonStyle.success, emoji="🛒")
    async def shop_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        economy_cog = self.bot.get_cog('EconomyCog')
        if economy_cog:
            await economy_cog.shop_list.callback(economy_cog, interaction)
    
    @discord.ui.button(label="Sub-Areas", style=discord.ButtonStyle.secondary, emoji="🏢")
    async def sub_areas(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Sub-areas logic (same as before)
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        from utils.sub_locations import SubLocationManager
        sub_manager = SubLocationManager(self.bot)
        
        available_subs = await sub_manager.get_available_sub_locations(char_location[0])
        
        if not available_subs:
            await interaction.response.send_message("No sub-areas available at this location.", ephemeral=True)
            return
        
        view = SubLocationSelectView(self.bot, interaction.user.id, char_location[0], available_subs)
        
        embed = discord.Embed(
            title="🏢 Sub-Areas",
            description="Choose an area to visit within this location",
            color=0x6a5acd
        )
        
        for sub in available_subs:
            status = "🟢 Active" if sub['exists'] else "⚫ Create"
            embed.add_field(
                name=f"{sub['icon']} {sub['name']}",
                value=f"{sub['description'][:100]}...\n**Status:** {status}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Travel", style=discord.ButtonStyle.primary, emoji="🚀")
    async def travel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog:
            await travel_cog.travel_go.callback(travel_cog, interaction)
    @discord.ui.button(label="View Routes", style=discord.ButtonStyle.primary, emoji="📋")
    async def route_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog:
            await travel_cog.view_routes.callback(travel_cog, interaction)
    @discord.ui.button(label="Dock", style=discord.ButtonStyle.success, emoji="🛬")
    async def dock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.dock_ship.callback(char_cog, interaction)
            # Refresh the view after docking
            await self.refresh_view()
    
    @discord.ui.button(label="Undock", style=discord.ButtonStyle.primary, emoji="🚀")
    async def undock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.undock_ship.callback(char_cog, interaction)
            # Refresh the view after undocking
            await self.refresh_view()
class EphemeralLocationView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=600)  # 5 minute timeout for ephemeral views
        self.bot = bot
        self.user_id = user_id
        
        # Get current location and status
        char_data = self.bot.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if char_data:
            self.current_location_id = char_data[0]
            location_status = char_data[1]
        else:
            self.current_location_id = None
            location_status = "docked"
        
        # Configure buttons based on dock status and location services
        self._configure_buttons(location_status)
    
    def _configure_buttons(self, location_status: str):
        """Configure button states based on dock status and location services"""
        self.clear_items()
        
        # Get current location services to determine which buttons to show
        char_data = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        has_federal_supplies = False
        has_black_market = False
        
        if char_data and char_data[0]:
            location_services = self.bot.db.execute_query(
                "SELECT has_federal_supplies, has_black_market FROM locations WHERE location_id = ?",
                (char_data[0],),
                fetch='one'
            )
            if location_services:
                has_federal_supplies, has_black_market = location_services
        
        # Status-dependent buttons
        if location_status == "docked":
            # Standard location buttons
            self.add_item(self.jobs_panel)
            self.add_item(self.shop_management)
            self.add_item(self.services)
            
            # Add Federal Depot button if location has federal supplies
            if has_federal_supplies:
                self.add_item(self.federal_depot)
            
            # Add Black Market button if location has black market
            if has_black_market:
                self.add_item(self.black_market)
            
            # Continue with other docked buttons
            self.add_item(self.sub_areas)
            self.add_item(self.npc_interactions)
            self.add_item(self.undock_button)
            self.add_item(self.route_button)
            
            # Add location info button if it exists in your implementation
            self.add_item(self.location_info_button)
                
        else:  # in_space
            self.add_item(self.travel_button)
            self.add_item(self.dock_button)
            self.add_item(self.route_button)
            self.add_item(self.plot_route_button)
            self.add_item(self.location_info_button)
    
    
    async def refresh_view(self, interaction: discord.Interaction):
        """Refresh the view when dock status changes"""
        char_data = self.bot.db.execute_query(
            "SELECT location_status, current_location FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if char_data:
            location_status, current_location = char_data
            self._configure_buttons(location_status)
            
            # Get location name
            location_name = "Unknown Location"
            if current_location:
                location_info = self.bot.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = ?",
                    (current_location,),
                    fetch='one'
                )
                if location_info:
                    location_name = location_info[0]
            
            # Update embed
            embed = discord.Embed(
                title="📍 Location Panel",
                description=f"**{location_name}** - Interactive Control Panel",
                color=0x4169E1
            )
            
            status_emoji = "🛬" if location_status == "docked" else "🚀"
            embed.add_field(
                name="Status",
                value=f"{status_emoji} {location_status.replace('_', ' ').title()}",
                inline=True
            )
            
            embed.add_field(
                name="Available Actions",
                value="Use the buttons below to interact with this location",
                inline=False
            )
            
            embed.set_footer(text="This panel is private to you and will update when your status changes")
            
            await interaction.edit_original_response(embed=embed, view=self)
    
    # Copy all the button methods from PersistentLocationView but modify dock/undock to refresh
    @discord.ui.button(label="NPCs", style=discord.ButtonStyle.secondary, emoji="👤")
    async def npc_interactions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle NPC interactions button - same as PersistentLocationView"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Same NPC logic as PersistentLocationView
        char_info = self.bot.db.execute_query(
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
        static_npcs = self.bot.db.execute_query(
            '''SELECT npc_id, name, age, occupation, personality, trade_specialty
               FROM static_npcs WHERE location_id = ?''',
            (location_id,),
            fetch='all'
        )
        
        dynamic_npcs = self.bot.db.execute_query(
            '''SELECT npc_id, name, age, ship_name, ship_type
               FROM dynamic_npcs 
               WHERE current_location = ? AND is_alive = 1 AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not static_npcs and not dynamic_npcs:
            await interaction.response.send_message("No NPCs are available for interaction at this location.", ephemeral=True)
            return
        
        # Import the NPCSelectView class and create the view
        from cogs.npc_interactions import NPCSelectView
        view = NPCSelectView(self.bot, interaction.user.id, location_id, static_npcs, dynamic_npcs)
        
        embed = discord.Embed(
            title="👥 NPCs at Location",
            description="Select an NPC to interact with:",
            color=0x6c5ce7
        )
        
        # Add some info about available NPCs
        if static_npcs:
            static_list = [f"• **{name}** - {occupation}" for npc_id, name, age, occupation, personality, trade_specialty in static_npcs[:5]]
            embed.add_field(
                name="🏢 Residents and locals",
                value="\n".join(static_list) + (f"\n*...and {len(static_npcs)-5} more*" if len(static_npcs) > 5 else ""),
                inline=False
            )
        
        if dynamic_npcs:
            dynamic_list = [f"• **{name}** - Captain of {ship_name}" for npc_id, name, age, ship_name, ship_type in dynamic_npcs[:5]]
            embed.add_field(
                name="🚀 Visiting Travellers",
                value="\n".join(dynamic_list) + (f"\n*...and {len(dynamic_npcs)-5} more*" if len(dynamic_npcs) > 5 else ""),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="Services", style=discord.ButtonStyle.secondary, emoji="🔧")
    async def services(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get current location services
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        location_services = self.bot.db.execute_query(
            '''SELECT name, has_medical, has_repairs, has_fuel, has_upgrades, wealth_level
               FROM locations WHERE location_id = ?''',
            (char_location[0],),
            fetch='one'
        )
        
        if not location_services:
            await interaction.response.send_message("Location information not found!", ephemeral=True)
            return
        
        name, has_medical, has_repairs, has_fuel, has_upgrades, wealth = location_services
        
        embed = discord.Embed(
            title=f"Services - {name}",
            description="Available services at this location",
            color=0x4169E1
        )
        
        services = []
        if has_fuel:
            fuel_price = max(5, 10 - wealth)  # Better locations have cheaper fuel
            services.append(f"⛽ **Fuel Refill** - {fuel_price} credits per unit")
        
        if has_repairs:
            repair_quality = "Premium" if wealth >= 7 else "Standard" if wealth >= 4 else "Basic"
            services.append(f"🔨 **Ship Repairs** - {repair_quality} quality")
        
        if has_medical:
            medical_quality = "Advanced" if wealth >= 8 else "Standard" if wealth >= 5 else "Basic"
            services.append(f"⚕️ **Medical Treatment** - {medical_quality} care")
        
        if has_upgrades:
            services.append(f"⬆️ **Ship Upgrades** - Performance enhancements available")
        
        # Check for logbook availability
        has_logbook = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )[0] > 0

        if has_logbook:
            services.append(f"📜 **Logbook Access** - View and add entries")
        
        if services:
            embed.add_field(name="Available Services", value="\n".join(services), inline=False)
        else:
            embed.add_field(name="No Services", value="This location offers no services.", inline=False)
        
        # Add wealth indicator
        wealth_text = "💰" * min(wealth // 2, 5) if wealth > 0 else "💸"
        embed.add_field(name="Economic Status", value=f"{wealth_text} Wealth Level: {wealth}/10", inline=False)
        
        view = ServicesView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Federal Depot", style=discord.ButtonStyle.primary, emoji="🏛️")
    async def federal_depot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your panel!", ephemeral=True)

        # Check if location has federal supplies
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        
        location_info = self.bot.db.execute_query(
            "SELECT has_federal_supplies FROM locations WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            return await interaction.response.send_message("No Federal Depot available at this location.", ephemeral=True)

        # Call the interactive federal depot command from EconomyCog
        econ_cog = self.bot.get_cog('EconomyCog')
        if not econ_cog:
            return await interaction.response.send_message(
                "❌ Federal depot system is unavailable right now.", ephemeral=True
            )

        # Forward the interaction to the federal_depot_interface handler
        await econ_cog.federal_depot_interface.callback(econ_cog, interaction)

    @discord.ui.button(label="Black Market", style=discord.ButtonStyle.danger, emoji="💀")
    async def black_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your panel!", ephemeral=True)

        # Check if location has black market
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        
        location_info = self.bot.db.execute_query(
            "SELECT has_black_market FROM locations WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            return await interaction.response.send_message("No black market available at this location.", ephemeral=True)

        # Call the interactive black market command from EconomyCog
        econ_cog = self.bot.get_cog('EconomyCog')
        if not econ_cog:
            return await interaction.response.send_message(
                "❌ Black market system is unavailable right now.", ephemeral=True
            )

        # Forward the interaction to the black_market_interface handler
        await econ_cog.black_market_interface.callback(econ_cog, interaction)
    
    @discord.ui.button(label="Plot Route", style=discord.ButtonStyle.success, emoji="📐", row=1)
    async def plot_route_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Opens a modal to plot a travel route."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return

        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog: 
            modal = RoutePlottingModal(travel_cog)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Travel system is currently unavailable.", ephemeral=True)

    @discord.ui.button(label="Jobs", style=discord.ButtonStyle.primary, emoji="💼")
    async def jobs_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        economy_cog = self.bot.get_cog('EconomyCog')
        if economy_cog:
            await economy_cog.job_list.callback(economy_cog, interaction)

    @discord.ui.button(label="Shop", style=discord.ButtonStyle.success, emoji="🛒")
    async def shop_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        economy_cog = self.bot.get_cog('EconomyCog')
        if economy_cog:
            await economy_cog.shop_list.callback(economy_cog, interaction)

    @discord.ui.button(label="Sub-Areas", style=discord.ButtonStyle.secondary, emoji="🏢")
    async def sub_areas(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Same sub-areas logic as PersistentLocationView
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        from utils.sub_locations import SubLocationManager
        sub_manager = SubLocationManager(self.bot)
        
        available_subs = await sub_manager.get_available_sub_locations(char_location[0])
        
        if not available_subs:
            await interaction.response.send_message("No sub-areas available at this location.", ephemeral=True)
            return
        
        view = SubLocationSelectView(self.bot, interaction.user.id, char_location[0], available_subs)
        
        embed = discord.Embed(
            title="🏢 Sub-Areas",
            description="Choose an area to visit within this location",
            color=0x6a5acd
        )
        
        for sub in available_subs:
            status = "🟢 Active" if sub['exists'] else "⚫ Create"
            embed.add_field(
                name=f"{sub['icon']} {sub['name']}",
                value=f"{sub['description'][:100]}...\n**Status:** {status}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Travel", style=discord.ButtonStyle.primary, emoji="🚀")
    async def travel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog:
            await travel_cog.travel_go.callback(travel_cog, interaction)

    @discord.ui.button(label="View Routes", style=discord.ButtonStyle.primary, emoji="📋")
    async def route_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        travel_cog = self.bot.get_cog('TravelCog')
        if travel_cog:
            await travel_cog.view_routes.callback(travel_cog, interaction)

    @discord.ui.button(label="Dock", style=discord.ButtonStyle.success, emoji="🛬")
    async def dock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Defer the response since we'll be doing database operations
        await interaction.response.defer(ephemeral=True)
        
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            # Call the dock ship logic directly
            char_data = char_cog.db.execute_query(
                "SELECT current_location, location_status FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.followup.send("Character not found!", ephemeral=True)
                return
            
            current_location, location_status = char_data
            
            if not current_location:
                await interaction.followup.send("You're in deep space and cannot dock!", ephemeral=True)
                return
            
            if location_status == "docked":
                await interaction.followup.send("You're already docked at this location!", ephemeral=True)
                return
            
            # Dock the ship
            char_cog.db.execute_query(
                "UPDATE characters SET location_status = 'docked' WHERE user_id = ?",
                (interaction.user.id,)
            )
            
            location_name = char_cog.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (current_location,),
                fetch='one'
            )[0]
            
            # Send confirmation message
            embed = discord.Embed(
                title="🛬 Ship Docked",
                description=f"Your ship has docked at **{location_name}**.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="Status Change",
                value="• You can now engage in personal combat\n• Access to all location services\n• Limited radio range (location only)",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Refresh the view to show updated buttons
            await self.refresh_view(interaction)
        else:
            await interaction.followup.send("Character system unavailable.", ephemeral=True)

    @discord.ui.button(label="Undock", style=discord.ButtonStyle.primary, emoji="🚀")
    async def undock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Defer the response since we'll be doing database operations
        await interaction.response.defer(ephemeral=True)
        
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            char_data = char_cog.db.execute_query(
                "SELECT current_location, location_status FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.followup.send("Character not found!", ephemeral=True)
                return
            
            current_location, location_status = char_data
            
            # Check for active stationary jobs
            active_jobs = char_cog.db.execute_query(
                '''SELECT COUNT(*) FROM jobs j 
                   JOIN job_tracking jt ON j.job_id = jt.job_id
                   WHERE j.taken_by = ? AND j.job_status = 'active' AND jt.start_location = ?''',
                (interaction.user.id, current_location),
                fetch='one'
            )[0]
            
            if active_jobs > 0:
                embed = discord.Embed(
                    title="⚠️ Active Job Warning",
                    description=f"You have {active_jobs} active job(s) at this location. Undocking will cancel them!",
                    color=0xff9900
                )
                embed.add_field(
                    name="Confirm Undocking?",
                    value="This will cancel your active jobs without reward.",
                    inline=False
                )
                
                view = UndockJobConfirmView(char_cog.bot, interaction.user.id, current_location)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                return
            
            if not current_location:
                await interaction.followup.send("You're in deep space!", ephemeral=True)
                return
            
            if location_status == "in_space":
                await interaction.followup.send("You're already in space near this location!", ephemeral=True)
                return
            
            # Undock the ship
            char_cog.db.execute_query(
                "UPDATE characters SET location_status = 'in_space' WHERE user_id = ?",
                (interaction.user.id,)
            )
            
            location_name = char_cog.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (current_location,),
                fetch='one'
            )[0]
            
            # Send confirmation message
            embed = discord.Embed(
                title="🚀 Ship Undocked",
                description=f"Your ship is now in space near **{location_name}**.",
                color=0x4169e1
            )
            
            embed.add_field(
                name="Status Change",
                value="• You can now engage in ship combat\n• Limited access to location services\n• Full radio range available",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Refresh the view to show updated buttons
            await self.refresh_view(interaction)
        else:
            await interaction.followup.send("Character system unavailable.", ephemeral=True)
        
    @discord.ui.button(label="Info", style=discord.ButtonStyle.secondary, emoji="ℹ️", row=2)
    async def location_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get current location
        char_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location or not char_location[0]:
            await interaction.response.send_message("You must be at a location to view info!", ephemeral=True)
            return
        
        location_id = char_location[0]
        
        # Get location info
        location_info = self.bot.db.execute_query(
            '''SELECT location_id, channel_id, name, location_type, description, wealth_level,
                      population, has_jobs, has_shops, has_medical, has_repairs, has_fuel, 
                      has_upgrades, has_federal_supplies, has_black_market
               FROM locations WHERE location_id = ?''',
            (location_id,),
            fetch='one'
        )
        faction_ownership = self.bot.db.execute_query(
            '''SELECT f.name, f.emoji, lo.custom_name, lo.docking_fee
               FROM location_ownership lo
               JOIN factions f ON lo.faction_id = f.faction_id
               WHERE lo.location_id = ?''',
            (location_id,),
            fetch='one'
        )
        if not location_info:
            await interaction.response.send_message("Location information not found!", ephemeral=True)
            return
        
        (loc_id, channel_id, name, loc_type, description, wealth, population, 
         has_jobs, has_shops, has_medical, has_repairs, has_fuel, has_upgrades,
         has_federal_supplies, has_black_market) = location_info
        
        # Create the same embed as the welcome message
        # Determine location status and enhance description
        location_status = None
        status_emoji = ""
        enhanced_description = description
        embed_color = 0x4169E1  # Default blue
        
        if has_federal_supplies:
            location_status = "Loyal"
            status_emoji = "🏛️"
            embed_color = 0x0066cc  # Federal blue
            # Add federal flair to description
            if enhanced_description:
                enhanced_description += "\n\n🏛️ **Federal Territory:** This location operates under direct federal oversight with enhanced security protocols and premium government-grade supplies."
            else:
                enhanced_description = "🏛️ **Federal Territory:** This location operates under direct federal oversight with enhanced security protocols and premium government-grade supplies."
        elif has_black_market:
            location_status = "Bandit"
            status_emoji = "💀"
            embed_color = 0x8b0000  # Dark red
            # Add bandit flair to description
            if enhanced_description:
                enhanced_description += "\n\n💀 **Outlaw Haven:** This location operates outside federal jurisdiction. Discretion is advised, and contraband trade flourishes in the shadows."
            else:
                enhanced_description = "💀 **Outlaw Haven:** This location operates outside federal jurisdiction. Discretion is advised, and contraband trade flourishes in the shadows."
        
        # Create info embed with status-aware styling
        title_with_status = f"📍 {name} - Location Info"
        if location_status:
            title_with_status = f"{status_emoji} {name} - Location Info"
        
        embed = discord.Embed(
            title=title_with_status,
            description=enhanced_description,
            color=embed_color
        )
        
        # Location details
        type_emoji = {
            'colony': '🏭',
            'space_station': '🛰️',
            'outpost': '🛤️',
            'gate': '🚪'
        }.get(loc_type, '📍')
        
        embed.add_field(
            name="Location Type",
            value=f"{type_emoji} {loc_type.replace('_', ' ').title()}",
            inline=True
        )
        
        embed.add_field(
            name="Population",
            value=f"{population:,}",
            inline=True
        )
        
        # Add status field if location has special alignment
        if location_status:
            embed.add_field(
                name="Status",
                value=f"{status_emoji} **{location_status}**",
                inline=True
            )
        else:
            # Keep the wealth field in the same position for normal locations
            wealth_text = "⭐" * min(wealth // 2, 5) if wealth > 0 else "💸"
            embed.add_field(
                name="Wealth Level",
                value=f"{wealth_text} {wealth}/10",
                inline=True
            )
        if faction_ownership:
            faction_name, faction_emoji, custom_name, docking_fee = faction_ownership
            ownership_text = f"{faction_emoji} **{faction_name}**"
            if docking_fee and docking_fee > 0:
                ownership_text += f"\n💰 Docking Fee: {docking_fee:,} credits (non-members)"
            embed.add_field(
                name="Controlled By",
                value=ownership_text,
                inline=False
            )
        # For aligned locations, show wealth in a separate row for better formatting
        if location_status:
            wealth_text = "⭐" * min(wealth // 2, 5) if wealth > 0 else "💸"
            embed.add_field(
                name="Wealth Level",
                value=f"{wealth_text} {wealth}/10",
                inline=True
            )
            # Add empty field for better formatting
            embed.add_field(name="", value="", inline=True)
        
        # Available services with status-aware enhancements
        services = []
        if has_jobs:   services.append("💼 Jobs")
        if has_shops:  services.append("🛒 Shopping")
        if has_medical:services.append("⚕️ Medical")
        if has_repairs:services.append("🔨 Repairs")
        if has_fuel:   services.append("⛽ Fuel")
        if has_upgrades:services.append("⬆️ Upgrades")
        
        # Add special services based on status
        if has_federal_supplies:
            services.append("🏛️ Federal Supplies")
        if has_black_market:
            services.append("💀 Black Market")

        if services:
            embed.add_field(
                name="Available Services",
                value=" • ".join(services),
                inline=False
            )
        
        # Get available homes info
        homes_info = self.bot.db.execute_query(
            '''SELECT COUNT(*), MIN(price), MAX(price), home_type
               FROM location_homes 
               WHERE location_id = ? AND is_available = 1
               GROUP BY home_type''',
            (location_id,),
            fetch='all'
        )
        
        if homes_info:
            homes_text = []
            for count, min_price, max_price, home_type in homes_info:
                if count == 1:
                    homes_text.append(f"• **{count} {home_type}** - {min_price:,} credits")
                else:
                    homes_text.append(f"• **{count} {home_type}s** - {min_price:,}-{max_price:,} credits")
            
            embed.add_field(
                name="🏠 Available Homes",
                value="\n".join(homes_text),
                inline=True
            )
        
        # STATIC NPCS
        npc_cog = self.bot.get_cog('NPCCog')
        if npc_cog:
            static_npcs = npc_cog.get_static_npcs_for_location(loc_id)
            if static_npcs:
                npc_list = [f"{name} - {age}" for name, age in static_npcs[:5]]  # Limit to 5 for space
                if len(static_npcs) > 5:
                    npc_list.append(f"...and {len(static_npcs) - 5} more")
                
                npc_field_name = "Notable NPCs"
                if location_status == "Loyal":
                    npc_field_name = "🏛️ Federal Personnel"
                elif location_status == "Bandit":
                    npc_field_name = "💀 Local Contacts"
                
                embed.add_field(
                    name=npc_field_name,
                    value="\n".join(npc_list),
                    inline=False
                )
        
        # LOGBOOK PRESENCE
        log_count = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (loc_id,),
            fetch='one'
        )[0]
        embed.add_field(
            name="📓 Logbook",
            value="Available" if log_count > 0 else "None",
            inline=True
        )

        # Get available routes and display them
        routes = self.bot.db.execute_query(
            '''SELECT c.name, l.name as dest_name, l.location_type as dest_type, c.travel_time, c.danger_level
               FROM corridors c
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1
               ORDER BY c.travel_time
               LIMIT 8''',
            (loc_id,),
            fetch='all'
        )
        
        if routes:
            route_lines = []
            for corridor_name, dest_name, dest_type, travel_time, danger in routes:
                # Determine route type and emoji
                if "Approach" in corridor_name:
                    route_emoji = "🌌"  # Local space
                elif "Ungated" in corridor_name:
                    route_emoji = "⭕️"  # Dangerous ungated
                else:
                    route_emoji = "🔵"  # Safe gated
                
                dest_emoji = {
                    'colony': '🏭',
                    'space_station': '🛰️',
                    'outpost': '🛤️',
                    'gate': '🚪'
                }.get(dest_type, '📍')
                
                # Format time
                mins = travel_time // 60
                secs = travel_time % 60
                if mins > 60:
                    hours = mins // 60
                    mins = mins % 60
                    time_text = f"{hours}h{mins}m"
                elif mins > 0:
                    time_text = f"{mins}m{secs}s" if secs > 0 else f"{mins}m"
                else:
                    time_text = f"{secs}s"
                
                danger_text = "⚠️" * danger if danger > 0 else ""
                # Clear departure → destination format
                route_lines.append(f"{route_emoji} **{name} → {dest_emoji} {dest_name}** · {time_text} {danger_text}")
            
            embed.add_field(
                name="🗺️ Available Routes",
                value="\n".join(route_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="🗺️ Available Routes",
                value="*No active routes from this location*",
                inline=False
            )
        
        embed.set_footer(text="Use the other buttons to interact with this location")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
class JobSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, jobs: List[Tuple], location_name: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.location_name = location_name
        
        if jobs:
            options = []
            for job in jobs[:25]:  # Discord limit
                job_id, title, desc, reward, skill, min_level, danger, duration = job
                danger_text = "⚠️" * danger
                skill_text = f" ({skill} {min_level}+)" if skill else ""
                
                options.append(
                    discord.SelectOption(
                        label=f"{title} - {reward} credits",
                        description=f"{desc[:50]}{'...' if len(desc) > 50 else ''} - {duration}min{skill_text} {danger_text}"[:100],
                        value=str(job_id)
                    )
                )
            
            select = discord.ui.Select(placeholder="Choose a job...", options=options)
            select.callback = self.job_callback
            self.add_item(select)
    
    async def job_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        job_id = int(interaction.data['values'][0])
        
        # Get the EconomyCog and call its job acceptance logic
        econ_cog = self.bot.get_cog('EconomyCog')
        if not econ_cog:
            await interaction.response.send_message("Job system is currently unavailable.", ephemeral=True)
            return
        
        # Find the job details
        job_info = self.bot.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
               FROM jobs WHERE job_id = ?''',
            (job_id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("Job no longer available.", ephemeral=True)
            return
        
        # Check if user already has a job
        has_job = self.bot.db.execute_query(
            "SELECT job_id FROM jobs WHERE taken_by = ? AND is_taken = 1",
            (interaction.user.id,),
            fetch='one'
        )
        
        if has_job:
            await interaction.response.send_message("You already have an active job. Complete or abandon it first.", ephemeral=True)
            return
        
        # Call the job acceptance logic
        await econ_cog._accept_solo_job(interaction, job_id, job_info)
class ServicesView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        
        # Check which services are available at this location
        location_services = self.bot.db.execute_query(
            '''SELECT has_fuel, has_repairs, has_medical, has_upgrades, l.location_id
               FROM locations l
               JOIN characters c ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (user_id,),
            fetch='one'
        )
        
        if location_services:
            has_fuel, has_repairs, has_medical, has_upgrades, location_id = location_services
            
            # Check for logbook
            has_logbook = self.bot.db.execute_query(
                "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )[0] > 0
            
            # Remove buttons for unavailable services
            if not has_fuel:
                self.remove_item(self.refuel)
            if not has_repairs:
                self.remove_item(self.repair)
            if not has_medical:
                self.remove_item(self.medical)
            if not has_upgrades:
                self.remove_item(self.ship_upgrades)
            if not has_logbook:
                self.remove_item(self.logbook)
        
    def _get_fuel_cost_per_unit(self, location_id: int) -> int:
        """Get fuel cost based on location wealth"""
        wealth = self.bot.db.execute_query(
            "SELECT wealth_level FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        if wealth:
            # Better locations have cheaper fuel (5-10 credits per unit)
            return max(5, 10 - wealth[0])
        return 10  # Default cost
    
    @discord.ui.button(label="Refuel Ship", style=discord.ButtonStyle.primary, emoji="⛽")
    async def refuel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get character and ship info
        char_info = self.bot.db.execute_query(
            """SELECT c.name, c.money, c.current_location, s.ship_id, 
                      s.fuel_capacity, s.current_fuel
               FROM characters c
               JOIN ships s ON c.user_id = s.owner_id
               WHERE c.user_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Ship data not found!", ephemeral=True)
            return
        
        char_name, money, location_id, ship_id, fuel_capacity, current_fuel = char_info
        
        if current_fuel >= fuel_capacity:
            embed = discord.Embed(
                title="⛽ Refueling Station",
                description=f"**{char_name}**, your ship's fuel tanks are already full.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate costs
        fuel_needed = fuel_capacity - current_fuel
        cost_per_unit = self._get_fuel_cost_per_unit(location_id)
        max_affordable = min(fuel_needed, money // cost_per_unit)
        
        # Create quantity selection view
        view = FuelQuantityView(
            self.bot, interaction.user.id, char_name, money,
            ship_id, current_fuel, fuel_capacity, fuel_needed,
            cost_per_unit, max_affordable
        )
        
        embed = discord.Embed(
            title="⛽ Refueling Station",
            description=f"**{char_name}**, select how much fuel you want to purchase.",
            color=0x4169E1
        )
        
        embed.add_field(name="Current Fuel", value=f"{current_fuel}/{fuel_capacity}", inline=True)
        embed.add_field(name="Cost per Unit", value=f"{cost_per_unit} credits", inline=True)
        embed.add_field(name="Your Credits", value=f"{money:,}", inline=True)
        
        if max_affordable < fuel_needed:
            embed.add_field(
                name="⚠️ Limited Funds",
                value=f"You can afford up to {max_affordable} units.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Repair Ship", style=discord.ButtonStyle.secondary, emoji="🔨")
    async def repair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get character and ship info
        char_info = self.bot.db.execute_query(
            """SELECT c.name, c.money, s.ship_id, s.hull_integrity, s.max_hull
               FROM characters c
               JOIN ships s ON c.user_id = s.owner_id
               WHERE c.user_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Ship data not found!", ephemeral=True)
            return
        
        char_name, money, ship_id, hull_integrity, max_hull = char_info
        
        if hull_integrity >= max_hull:
            embed = discord.Embed(
                title="🔧 Ship Repair Bay",
                description=f"**{char_name}**, your ship's hull is in perfect condition.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate repair costs
        repairs_needed = max_hull - hull_integrity
        cost_per_point = 25
        max_affordable = min(repairs_needed, money // cost_per_point)
        
        # Create quantity selection view
        view = RepairQuantityView(
            self.bot, interaction.user.id, char_name, money,
            ship_id, hull_integrity, max_hull, repairs_needed,
            cost_per_point, max_affordable
        )
        
        embed = discord.Embed(
            title="🔧 Ship Repair Bay",
            description=f"**{char_name}**, select how many hull points to repair.",
            color=0x4169E1
        )
        
        embed.add_field(name="Hull Integrity", value=f"{hull_integrity}/{max_hull}", inline=True)
        embed.add_field(name="Cost per Point", value=f"{cost_per_point} credits", inline=True)
        embed.add_field(name="Your Credits", value=f"{money:,}", inline=True)
        
        if max_affordable < repairs_needed:
            embed.add_field(
                name="⚠️ Limited Funds",
                value=f"You can afford to repair up to {max_affordable} points.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Medical Treatment", style=discord.ButtonStyle.success, emoji="⚕️")
    async def medical(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        char_info = self.bot.db.execute_query(
            "SELECT name, hp, max_hp, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        char_name, hp, max_hp, money = char_info
        
        if hp >= max_hp:
            embed = discord.Embed(
                title="⚕️ Medical Bay",
                description=f"**{char_name}**, your vitals are optimal. No treatment required.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate healing costs
        healing_needed = max_hp - hp
        cost_per_hp = 15
        max_affordable = min(healing_needed, money // cost_per_hp)
        
        # Create quantity selection view
        view = MedicalQuantityView(
            self.bot, interaction.user.id, char_name, money,
            hp, max_hp, healing_needed, cost_per_hp, max_affordable
        )
        
        embed = discord.Embed(
            title="⚕️ Medical Bay",
            description=f"**{char_name}**, select how much healing you need.",
            color=0x4169E1
        )
        
        embed.add_field(name="Current Health", value=f"{hp}/{max_hp} HP", inline=True)
        embed.add_field(name="Cost per HP", value=f"{cost_per_hp} credits", inline=True)
        embed.add_field(name="Your Credits", value=f"{money:,}", inline=True)
        
        if max_affordable < healing_needed:
            embed.add_field(
                name="⚠️ Limited Funds",
                value=f"You can afford to heal up to {max_affordable} HP.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Ship Upgrades", style=discord.ButtonStyle.primary, emoji="⬆️")
    async def ship_upgrades(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Check if location has upgrades
        location_info = self.bot.db.execute_query(
            '''SELECT l.has_upgrades, l.name FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.response.send_message("This location doesn't offer ship upgrade services.", ephemeral=True)
            return
        
        # Call the ship upgrade command from ShipSystemsCog
        ship_cog = self.bot.get_cog('ShipSystemsCog')
        if ship_cog:
            await ship_cog.upgrade_ship.callback(ship_cog, interaction)
        else:
            await interaction.response.send_message("Ship upgrade system unavailable.", ephemeral=True)

    @discord.ui.button(label="Logbook", style=discord.ButtonStyle.secondary, emoji="📜")
    async def logbook(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get current location
        char_location = self.bot.db.execute_query(
            '''SELECT c.current_location, l.name, l.location_type
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Location not found!", ephemeral=True)
            return
        
        location_id, location_name, location_type = char_location
        
        # Check if this location has a logbook
        has_log = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0] > 0
        
        if not has_log:
            await interaction.response.send_message(
                f"📜 No logbook found at {location_name}.", 
                ephemeral=True
            )
            return
        
        # Create logbook interaction view (assuming this exists)
        from utils.views import LogbookInteractionView
        view = LogbookInteractionView(self.bot, interaction.user.id, location_id, location_name)
        
        embed = discord.Embed(
            title=f"📜 {location_name} - Logbook",
            description="Access the location's logbook to view entries or add your own.",
            color=0x8b4513
        )
        
        # Get recent entries count
        recent_count = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ? AND posted_at > datetime('now', '-7 days')",
            (location_id,),
            fetch='one'
        )[0]
        
        total_count = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0]
        
        embed.add_field(name="Total Entries", value=str(total_count), inline=True)
        embed.add_field(name="Recent Entries", value=f"{recent_count} (past week)", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# Quantity Selection Views

class FuelQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, money: int,
                 ship_id: int, current_fuel: int, fuel_capacity: int, 
                 fuel_needed: int, cost_per_unit: int, max_affordable: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.money = money
        self.ship_id = ship_id
        self.current_fuel = current_fuel
        self.fuel_capacity = fuel_capacity
        self.fuel_needed = fuel_needed
        self.cost_per_unit = cost_per_unit
        self.max_affordable = max_affordable
        
        # Add quantity select dropdown
        self.add_item(FuelQuantitySelect(fuel_needed, max_affordable, cost_per_unit))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Refueling cancelled.",
            embed=None,
            view=None
        )


class FuelQuantitySelect(discord.ui.Select):
    def __init__(self, fuel_needed: int, max_affordable: int, cost_per_unit: int):
        self.cost_per_unit = cost_per_unit
        
        options_dict = {}  # Use a dictionary to store unique options, with amount as key

        # Helper to add options, automatically handles duplicates
        def add_option(amount, label_suffix=""):
            amount = int(amount)
            if amount > 0 and amount <= max_affordable:
                # The dictionary key automatically handles uniqueness
                cost = amount * self.cost_per_unit
                label = f"{amount} units{label_suffix}"
                options_dict[amount] = discord.SelectOption(
                    label=label,
                    description=f"Cost: {cost:,} credits",
                    value=str(amount),
                    emoji="⛽"
                )

        # Quick options: 25%, 50%, 75%, 100% of needed
        for percent in [25, 50, 75, 100]:
            add_option(fuel_needed * (percent / 100), f" ({percent}%)")

        # Add some fixed amounts if affordable
        for amount in [10, 25, 50, 100]:
            if amount <= fuel_needed:
                add_option(amount)

        # Add maximum affordable amount
        add_option(max_affordable, " (Maximum)")
        
        # Set the emoji for the maximum affordable option
        if max_affordable in options_dict:
            options_dict[max_affordable].emoji = "💰"

        # Convert dict to list and sort
        options = sorted(list(options_dict.values()), key=lambda opt: int(opt.value))
        
        # Handle case with no options
        if not options:
            options.append(discord.SelectOption(label="No affordable amount", value="0", disabled=True))

        super().__init__(
            placeholder="Select fuel amount...",
            min_values=1,
            max_values=1,
            options=options[:25]  # Discord limit
        )

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])
        total_cost = amount * self.cost_per_unit
        
        # Show confirmation
        view = self.view
        confirm_view = FuelConfirmView(
            view.bot, view.user_id, view.char_name, view.money,
            view.ship_id, view.current_fuel, amount, total_cost
        )
        
        embed = discord.Embed(
            title="⛽ Confirm Refueling",
            description=f"**{view.char_name}**, please confirm your purchase.",
            color=0x4169E1
        )
        
        embed.add_field(name="Fuel Amount", value=f"{amount} units", inline=True)
        embed.add_field(name="Total Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="Remaining Credits", value=f"{view.money - total_cost:,}", inline=True)
        
        embed.add_field(
            name="Fuel After Purchase",
            value=f"{view.current_fuel + amount}/{view.fuel_capacity}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class FuelConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, money: int,
                 ship_id: int, current_fuel: int, amount: int, total_cost: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.money = money
        self.ship_id = ship_id
        self.current_fuel = current_fuel
        self.amount = amount
        self.total_cost = total_cost

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Apply refueling
        self.bot.db.execute_query(
            "UPDATE ships SET current_fuel = current_fuel + ? WHERE ship_id = ?",
            (self.amount, self.ship_id)
        )
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.total_cost, self.user_id)
        )
        
        embed = discord.Embed(
            title="⛽ Refueling Complete",
            description=f"**{self.char_name}**, your ship has been refueled.",
            color=0x00ff00
        )
        embed.add_field(name="⛽ Fuel Added", value=f"+{self.amount} units", inline=True)
        embed.add_field(name="💰 Cost", value=f"{self.total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{self.money - self.total_cost:,}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Refueling cancelled.",
            embed=None,
            view=None
        )


# Similar implementations for RepairQuantityView and MedicalQuantityView
class RepairQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, money: int,
                 ship_id: int, hull_integrity: int, max_hull: int,
                 repairs_needed: int, cost_per_point: int, max_affordable: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.money = money
        self.ship_id = ship_id
        self.hull_integrity = hull_integrity
        self.max_hull = max_hull
        self.repairs_needed = repairs_needed
        self.cost_per_point = cost_per_point
        self.max_affordable = max_affordable
        
        # Add quantity select dropdown
        self.add_item(RepairQuantitySelect(repairs_needed, max_affordable, cost_per_point))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Repairs cancelled.",
            embed=None,
            view=None
        )


class RepairQuantitySelect(discord.ui.Select):
    def __init__(self, repairs_needed: int, max_affordable: int, cost_per_point: int):
        self.cost_per_point = cost_per_point
        
        options_dict = {}  # Use a dictionary to store unique options, with amount as key

        # Helper to add options, automatically handles duplicates
        def add_option(amount, label_suffix=""):
            amount = int(amount)
            if amount > 0 and amount <= max_affordable:
                # The dictionary key automatically handles uniqueness
                cost = amount * self.cost_per_point
                label = f"{amount} hull points{label_suffix}"
                options_dict[amount] = discord.SelectOption(
                    label=label,
                    description=f"Cost: {cost:,} credits",
                    value=str(amount),
                    emoji="🔧"
                )

        # Quick options: 25%, 50%, 75%, 100% of needed
        for percent in [25, 50, 75, 100]:
            add_option(repairs_needed * (percent / 100), f" ({percent}%)")
        
        # Add maximum affordable amount
        add_option(max_affordable, " (Maximum)")

        # Set the emoji for the maximum affordable option
        if max_affordable in options_dict:
            options_dict[max_affordable].emoji = "💰"
        
        # Convert dict to list and sort
        options = sorted(list(options_dict.values()), key=lambda opt: int(opt.value))

        if not options:
            options.append(discord.SelectOption(label="No affordable amount", value="0", disabled=True))

        super().__init__(
            placeholder="Select repair amount...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])
        total_cost = amount * self.cost_per_point
        
        view = self.view
        confirm_view = RepairConfirmView(
            view.bot, view.user_id, view.char_name, view.money,
            view.ship_id, view.hull_integrity, amount, total_cost
        )
        
        embed = discord.Embed(
            title="🔧 Confirm Repairs",
            description=f"**{view.char_name}**, please confirm your repairs.",
            color=0x4169E1
        )
        
        embed.add_field(name="Repair Amount", value=f"{amount} hull points", inline=True)
        embed.add_field(name="Total Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="Remaining Credits", value=f"{view.money - total_cost:,}", inline=True)
        
        embed.add_field(
            name="Hull After Repairs",
            value=f"{view.hull_integrity + amount}/{view.max_hull}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class RepairConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, money: int,
                 ship_id: int, hull_integrity: int, amount: int, total_cost: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.money = money
        self.ship_id = ship_id
        self.hull_integrity = hull_integrity
        self.amount = amount
        self.total_cost = total_cost

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Apply repairs
        self.bot.db.execute_query(
            "UPDATE ships SET hull_integrity = hull_integrity + ? WHERE ship_id = ?",
            (self.amount, self.ship_id)
        )
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.total_cost, self.user_id)
        )
        
        embed = discord.Embed(
            title="🔧 Ship Repairs Complete",
            description=f"**{self.char_name}**, your ship has been repaired.",
            color=0x00ff00
        )
        embed.add_field(name="🛠️ Hull Repaired", value=f"+{self.amount} points", inline=True)
        embed.add_field(name="💰 Cost", value=f"{self.total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{self.money - self.total_cost:,}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Repairs cancelled.",
            embed=None,
            view=None
        )


# Medical Quantity Views
class MedicalQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, money: int,
                 hp: int, max_hp: int, healing_needed: int,
                 cost_per_hp: int, max_affordable: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.money = money
        self.hp = hp
        self.max_hp = max_hp
        self.healing_needed = healing_needed
        self.cost_per_hp = cost_per_hp
        self.max_affordable = max_affordable
        
        # Add quantity select dropdown
        self.add_item(MedicalQuantitySelect(healing_needed, max_affordable, cost_per_hp))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Medical treatment cancelled.",
            embed=None,
            view=None
        )


class MedicalQuantitySelect(discord.ui.Select):
    def __init__(self, healing_needed: int, max_affordable: int, cost_per_hp: int):
        self.cost_per_hp = cost_per_hp
        
        options_dict = {}  # Use a dictionary to store unique options, with amount as key

        # Helper to add options, automatically handles duplicates
        def add_option(amount, label_suffix=""):
            amount = int(amount)
            if amount > 0 and amount <= max_affordable:
                # The dictionary key automatically handles uniqueness
                cost = amount * self.cost_per_hp
                label = f"{amount} HP{label_suffix}"
                options_dict[amount] = discord.SelectOption(
                    label=label,
                    description=f"Cost: {cost:,} credits",
                    value=str(amount),
                    emoji="⚕️"
                )

        # Quick options: 25%, 50%, 75%, 100% of needed
        for percent in [25, 50, 75, 100]:
            add_option(healing_needed * (percent / 100), f" ({percent}%)")

        # Add some fixed amounts if affordable
        for amount in [5, 10, 25, 50]:
            if amount <= healing_needed:
                add_option(amount)
        
        # Add maximum affordable amount
        add_option(max_affordable, " (Maximum)")

        # Set the emoji for the maximum affordable option
        if max_affordable in options_dict:
            options_dict[max_affordable].emoji = "💰"

        # Convert dict to list and sort
        options = sorted(list(options_dict.values()), key=lambda opt: int(opt.value))
        
        if not options:
            options.append(discord.SelectOption(label="No affordable amount", value="0", disabled=True))

        super().__init__(
            placeholder="Select healing amount...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])
        total_cost = amount * self.cost_per_hp
        
        view = self.view
        confirm_view = MedicalConfirmView(
            view.bot, view.user_id, view.char_name, view.money,
            view.hp, amount, total_cost
        )
        
        embed = discord.Embed(
            title="⚕️ Confirm Medical Treatment",
            description=f"**{view.char_name}**, please confirm your treatment.",
            color=0x4169E1
        )
        
        embed.add_field(name="Healing Amount", value=f"{amount} HP", inline=True)
        embed.add_field(name="Total Cost", value=f"{total_cost} credits", inline=True)
        embed.add_field(name="Remaining Credits", value=f"{view.money - total_cost:,}", inline=True)
        
        embed.add_field(
            name="Health After Treatment",
            value=f"{view.hp + amount}/{view.max_hp} HP",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class MedicalConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, money: int,
                 hp: int, amount: int, total_cost: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.money = money
        self.hp = hp
        self.amount = amount
        self.total_cost = total_cost

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Apply healing
        self.bot.db.execute_query(
            "UPDATE characters SET hp = hp + ?, money = money - ? WHERE user_id = ?",
            (self.amount, self.total_cost, self.user_id)
        )
        
        embed = discord.Embed(
            title="⚕️ Medical Treatment Complete",
            description=f"**{self.char_name}**, you have been healed.",
            color=0x00ff00
        )
        embed.add_field(name="💚 Health Restored", value=f"+{self.amount} HP", inline=True)
        embed.add_field(name="💰 Cost", value=f"{self.total_cost} credits", inline=True)
        embed.add_field(name="🏦 Remaining Credits", value=f"{self.money - self.total_cost:,}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Medical treatment cancelled.",
            embed=None,
            view=None
        )
class SubLocationSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, available_subs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id

        # ─── Navigation buttons (row 0 auto) ───
        back_btn = discord.ui.Button(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            custom_id=f"nav_back_{self.user_id}_{uuid.uuid4().hex}"
        )
        async def back_cb(interaction: discord.Interaction):
            # your existing back logic here
            await self.handle_back(interaction)
        back_btn.callback = back_cb
        self.add_item(back_btn)

        cancel_btn = discord.ui.Button(
            label="Cancel",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"nav_cancel_{self.user_id}_{uuid.uuid4().hex}"
        )
        async def cancel_cb(interaction: discord.Interaction):
            await interaction.response.edit_message(view=None)
        cancel_btn.callback = cancel_cb
        self.add_item(cancel_btn)

        # ─── Sub-location buttons (auto-wrapped) ───
        for sub in available_subs:
            # generate a guaranteed-unique custom_id
            unique_id = f"sub_{sub['type']}_{uuid.uuid4().hex}"
            btn = discord.ui.Button(
                label=sub['name'],
                emoji=sub['icon'],
                style=discord.ButtonStyle.primary if sub['exists'] else discord.ButtonStyle.secondary,
                custom_id=unique_id
            )

            async def sub_cb(interaction: discord.Interaction, sub_type=sub['type']):
                # your existing create/access logic here
                await self.handle_sub_location_access(interaction, sub_type)
            btn.callback = sub_cb

            self.add_item(btn)
    async def handle_sub_location_access(self, interaction: discord.Interaction, sub_type: str):
        """Handle accessing a sub-location"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        # Get character and location info
        char_info = self.bot.db.execute_query(
            "SELECT name, current_location FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        char_name, location_id = char_info

        location_info = self.bot.db.execute_query(
            "SELECT channel_id, name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.followup.send("Location channel not found!", ephemeral=True)
            return
        
        location_channel = interaction.guild.get_channel(location_info[0])
        location_name = location_info[1]

        if not location_channel:
            await interaction.followup.send("Location channel is not accessible!", ephemeral=True)
            return
        
        from utils.sub_locations import SubLocationManager
        sub_manager = SubLocationManager(self.bot)
        
        # Create or access the sub-location thread
        thread = await sub_manager.create_sub_location(
            interaction.guild, 
            location_channel, 
            self.location_id, 
            sub_type, 
            interaction.user
        )
        
        if thread:
            # Public announcement embed
            announce_embed = discord.Embed(
                title="🚪 Area Movement",
                description=f"**{char_name}** enters the **{thread.name}**.",
                color=0x7289DA  # Discord Blurple
            )
            await location_channel.send(embed=announce_embed)

            # Ephemeral confirmation for the user
            await interaction.followup.send(
                f"✅ You have entered {thread.mention}. Check your active threads.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Failed to create or access the sub-location.",
                ephemeral=True
            )


    async def handle_back(self, interaction: discord.Interaction):
        """Handle back button to return to main location view"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Create a new LocationView
        from utils.views import LocationView
        new_view = LocationView(self.bot, self.user_id)
        
        embed = discord.Embed(
            title="📍 Location Menu",
            description="Choose an action:",
            color=0x4169E1
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
class LogoutConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, char_name: str, active_jobs: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.active_jobs = active_jobs
    
    @discord.ui.button(label="Confirm Logout", style=discord.ButtonStyle.danger, emoji="👋")
    async def confirm_logout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logout panel!", ephemeral=True)
            return
        
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog._execute_logout(self.user_id, self.char_name, interaction)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_logout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logout panel!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="✅ Logout Cancelled",
            description=f"**{self.char_name}** remains logged in.",
            color=0x00ff00
        )
        embed.add_field(
            name="Active Jobs",
            value=f"Your {self.active_jobs} active job(s) will continue.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
 
# In views.py, add this new class

class LogbookInteractionView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, location_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.location_name = location_name
    
    @discord.ui.button(label="View Entries", style=discord.ButtonStyle.primary, emoji="👁️")
    async def view_entries(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get log entries (most recent first)
        entries = self.bot.db.execute_query(
            '''SELECT author_name, message, posted_at, is_generated
               FROM location_logs
               WHERE location_id = ?
               ORDER BY posted_at DESC
               LIMIT 10''',
            (self.location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"📜 {self.location_name} - Logbook Entries",
            description=f"Recent entries from this location's logbook",
            color=0x8b4513
        )
        
        if entries:
            log_text = []
            for author, message, posted_at, is_generated in entries:
                # Format timestamp - try to use in-game time if available
                try:
                    from utils.time_system import TimeSystem
                    time_system = TimeSystem(self.bot)
                    
                    # Convert stored time to display format
                    if posted_at:
                        posted_time = datetime.fromisoformat(posted_at.replace('Z', '+00:00') if 'Z' in posted_at else posted_at)
                        time_str = posted_time.strftime("%d-%m-%Y")
                    else:
                        time_str = "Unknown date"
                except:
                    # Fallback to simple date format
                    if posted_at:
                        posted_time = datetime.fromisoformat(posted_at.replace('Z', '+00:00') if 'Z' in posted_at else posted_at)
                        time_str = posted_time.strftime("%Y-%m-%d")
                    else:
                        time_str = "Unknown date"
                
                # Different formatting for generated vs player entries
                if is_generated:
                    log_text.append(f"**[{time_str}] {author}**")
                    log_text.append(f"*{message}*")
                else:
                    log_text.append(f"**[{time_str}] {author}**")
                    log_text.append(f'"{message}"')
                log_text.append("")
            
            # Split into multiple fields if too long
            full_text = "\n".join(log_text)
            if len(full_text) > 1024:
                # Split into chunks
                chunks = []
                current_chunk = ""
                for line in log_text:
                    if len(current_chunk + line + "\n") > 1000:
                        chunks.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                if current_chunk:
                    chunks.append(current_chunk)
                
                for i, chunk in enumerate(chunks[:3]):  # Max 3 fields
                    field_name = "📖 Log Entries" if i == 0 else f"📖 Log Entries (cont. {i+1})"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            else:
                embed.add_field(name="📖 Log Entries", value=full_text, inline=False)
        else:
            embed.add_field(name="📖 Empty Log", value="No entries found.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Add Entry", style=discord.ButtonStyle.success, emoji="✍️")
    async def add_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = LogbookEntryModal(self.bot, self.location_id, self.location_name)
        await interaction.response.send_modal(modal)
        
# In views.py, add this new class

class LogbookEntryModal(discord.ui.Modal):
    def __init__(self, bot, location_id: int, location_name: str):
        super().__init__(title=f"Add Entry - {location_name}")
        self.bot = bot
        self.location_id = location_id
        self.location_name = location_name
        
        self.message_input = discord.ui.TextInput(
            label="Logbook Entry",
            placeholder="Write your entry for the location logbook...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        )
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Get character info
        char_info = self.bot.db.execute_query(
            '''SELECT name FROM characters WHERE user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        char_name = char_info[0]
        message = self.message_input.value
        
        # Get in-game timestamp
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            current_ingame = time_system.calculate_current_ingame_time()
            
            if current_ingame:
                # Use in-game time
                timestamp = current_ingame.isoformat()
            else:
                # Fallback to real time
                timestamp = datetime.now().isoformat()
        except:
            # Fallback to real time if time system fails
            timestamp = datetime.now().isoformat()
        
        # Add entry with in-game timestamp
        self.bot.db.execute_query(
            '''INSERT INTO location_logs (location_id, author_id, author_name, message, posted_at)
               VALUES (?, ?, ?, ?, ?)''',
            (self.location_id, interaction.user.id, char_name, message, timestamp)
        )
        
        embed = discord.Embed(
            title="✍️ Logbook Entry Added",
            description=f"Your entry has been added to the {self.location_name} logbook.",
            color=0x00ff00
        )
        
        embed.add_field(name="Your Entry", value=f'"{message}"', inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
      
      
class UndockJobConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, current_location: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.current_location = current_location
    
    @discord.ui.button(label="Confirm Undock (Cancel Jobs)", style=discord.ButtonStyle.danger, emoji="🚀")
    async def confirm_undock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your undock panel!", ephemeral=True)
            return
        
        # Cancel active jobs
        active_jobs = self.bot.db.execute_query(
            '''SELECT j.job_id FROM jobs j 
               JOIN job_tracking jt ON j.job_id = jt.job_id
               WHERE j.taken_by = ? AND j.job_status = 'active' AND jt.start_location = ?''',
            (self.user_id, self.current_location),
            fetch='all'
        )
        
        for job_row in active_jobs:
            job_id = job_row[0]
            self.bot.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            self.bot.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, self.user_id))
        
        # Undock the ship
        self.bot.db.execute_query(
            "UPDATE characters SET location_status = 'in_space' WHERE user_id = ?",
            (self.user_id,)
        )
        
        location_name = self.bot.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (self.current_location,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="🚀 Ship Undocked",
            description=f"Your ship is now in space near **{location_name}**.",
            color=0x4169e1
        )
        
        embed.add_field(
            name="⚠️ Jobs Cancelled",
            value=f"{len(active_jobs)} active job(s) were cancelled without reward.",
            inline=False
        )
        
        embed.add_field(
            name="Status Change",
            value="• You can now engage in ship combat\n• Limited access to location services\n• Full radio range available",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel Undocking", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_undock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your undock panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Undocking cancelled. Your jobs remain active.", ephemeral=True)
        
        
# Personal Log View Classes
class PersonalLogMainView(discord.ui.View):
    def __init__(self, bot, user_id: int, logbook_id: str, char_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.logbook_id = logbook_id
        self.char_name = char_name

    @discord.ui.button(label="View Logs", style=discord.ButtonStyle.primary, emoji="📖")
    async def view_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        # Get all log entries for this logbook
        entries = self.bot.db.execute_query(
            '''SELECT entry_id, entry_title, created_at, author_name 
               FROM logbook_entries 
               WHERE logbook_id = ? 
               ORDER BY created_at DESC''',
            (self.logbook_id,),
            fetch='all'
        )
        
        if not entries:
            await interaction.response.send_message("This logbook is empty. Create your first entry!", ephemeral=True)
            return
        
        # Create log selection view
        view = PersonalLogSelectView(self.bot, self.user_id, self.logbook_id, entries, 0)
        
        embed = discord.Embed(
            title="📖 Select Log Entry",
            description=f"**{len(entries)}** entries found in this logbook",
            color=0x4169E1
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Create New Log", style=discord.ButtonStyle.success, emoji="✏️")
    async def create_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        # Get current in-game time
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            current_time = time_system.get_current_time()
            ingame_date = current_time.strftime("%Y-%m-%d %H:%M")
        except:
            # Fallback to real time if time system isn't available
            ingame_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Create log entry modal
        modal = PersonalLogEntryModal(self.bot, self.logbook_id, self.char_name, ingame_date)
        await interaction.response.send_modal(modal)

class PersonalLogSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, logbook_id: str, entries: list, page: int = 0):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.logbook_id = logbook_id
        self.entries = entries
        self.page = page
        self.items_per_page = 25
        
        self.setup_pagination()

    def setup_pagination(self):
        self.clear_items()
        
        total_pages = math.ceil(len(self.entries) / self.items_per_page)
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.entries))
        
        current_entries = self.entries[start_idx:end_idx]
        
        # Create dropdown for current page entries
        if current_entries:
            options = []
            for entry_id, title, created_at, author_name in current_entries:
                # Limit option label and description length
                display_title = title[:80] + "..." if len(title) > 80 else title
                created_date = created_at[:16]  # YYYY-MM-DD HH:MM
                
                options.append(
                    discord.SelectOption(
                        label=display_title,
                        description=f"By {author_name} on {created_date}",
                        value=str(entry_id)
                    )
                )
            
            select = discord.ui.Select(
                placeholder=f"Choose a log entry... (Page {self.page + 1}/{total_pages})",
                options=options
            )
            select.callback = self.entry_selected
            self.add_item(select)
        
        # Add pagination buttons if needed
        if total_pages > 1:
            prev_button = discord.ui.Button(
                label="Previous", 
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == 0),
                emoji="⬅️"
            )
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
            
            next_button = discord.ui.Button(
                label="Next",
                style=discord.ButtonStyle.secondary, 
                disabled=(self.page >= total_pages - 1),
                emoji="➡️"
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Back button
        back_button = discord.ui.Button(
            label="Back to Logbook",
            style=discord.ButtonStyle.primary,
            emoji="📖"
        )
        back_button.callback = self.back_to_main
        self.add_item(back_button)

    async def entry_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        entry_id = int(interaction.data['values'][0])
        
        # Get the full log entry
        entry = self.bot.db.execute_query(
            '''SELECT entry_title, entry_content, created_at, author_name, ingame_date
               FROM logbook_entries 
               WHERE entry_id = ?''',
            (entry_id,),
            fetch='one'
        )
        
        if not entry:
            await interaction.response.send_message("Log entry not found.", ephemeral=True)
            return
        
        title, content, created_at, author_name, ingame_date = entry
        
        # Create sci-fi styled embed
        embed = discord.Embed(
            title="📖 Personal Log Entry",
            color=0x00ff88
        )
        
        embed.add_field(
            name="🏷️ Entry Title",
            value=f"**{title}**",
            inline=False
        )
        
        embed.add_field(
            name="👤 Author",
            value=author_name,
            inline=True
        )
        
        embed.add_field(
            name="📅 Stardate",
            value=ingame_date,
            inline=True
        )
        
        embed.add_field(
            name="🕐 Recorded",
            value=created_at[:16],
            inline=True
        )
        
        # Format content with sci-fi styling
        if len(content) > 1000:
            embed.add_field(
                name="📝 Log Content",
                value=content[:1000] + "...",
                inline=False
            )
        else:
            embed.add_field(
                name="📝 Log Content",
                value=f"```\n--- PERSONAL LOG ENTRY ---\nSTARDATE: {ingame_date}\nAUTHOR: {author_name}\n\n{content}\n\n--- END LOG ENTRY ---```",
                inline=False
            )
        
        embed.set_footer(text=f"Logbook ID: {self.logbook_id[:8]}...")
        
        view = PersonalLogEntryView(self.bot, self.user_id, self.logbook_id, self.entries, self.page)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        self.page = max(0, self.page - 1)
        self.setup_pagination()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        total_pages = math.ceil(len(self.entries) / self.items_per_page)
        self.page = min(total_pages - 1, self.page + 1)
        self.setup_pagination()
        await interaction.response.edit_message(view=self)

    async def back_to_main(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        # Get character name
        char_name = self.bot.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )[0]
        
        view = PersonalLogMainView(self.bot, self.user_id, self.logbook_id, char_name)
        
        embed = discord.Embed(
            title="📖 Personal Logbook Interface",
            description="Access your personal logs and create new entries.",
            color=0x4169E1
        )
        
        embed.add_field(
            name="📋 Logbook ID", 
            value=f"`{self.logbook_id[:8]}...`",
            inline=True
        )
        
        entry_count = len(self.entries)
        embed.add_field(
            name="📊 Total Entries",
            value=str(entry_count),
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class PersonalLogEntryView(discord.ui.View):
    def __init__(self, bot, user_id: int, logbook_id: str, entries: list, page: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.logbook_id = logbook_id
        self.entries = entries
        self.page = page

    @discord.ui.button(label="Back to List", style=discord.ButtonStyle.secondary, emoji="📋")
    async def back_to_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your logbook!", ephemeral=True)
            return
        
        view = PersonalLogSelectView(self.bot, self.user_id, self.logbook_id, self.entries, self.page)
        
        embed = discord.Embed(
            title="📖 Select Log Entry",
            description=f"**{len(self.entries)}** entries found in this logbook",
            color=0x4169E1
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class PersonalLogEntryModal(discord.ui.Modal):
    def __init__(self, bot, logbook_id: str, char_name: str, ingame_date: str):
        super().__init__(title="Create Personal Log Entry")
        self.bot = bot
        self.logbook_id = logbook_id
        self.char_name = char_name
        self.ingame_date = ingame_date
        
        self.title_input = discord.ui.TextInput(
            label="Log Entry Title",
            placeholder=f"{char_name} - {ingame_date}",
            default=f"{char_name} - {ingame_date}",
            max_length=200
        )
        self.add_item(self.title_input)
        
        self.content_input = discord.ui.TextInput(
            label="Log Content",
            placeholder="Enter your personal log entry here...",
            style=discord.TextStyle.paragraph,
            max_length=1800,
            required=True
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Get user ID for the entry
        user_id = interaction.user.id
        
        # Save the log entry
        self.bot.db.execute_query(
            '''INSERT INTO logbook_entries 
               (logbook_id, author_name, author_id, entry_title, entry_content, ingame_date)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (self.logbook_id, self.char_name, user_id, 
             self.title_input.value, self.content_input.value, self.ingame_date)
        )
        
        embed = discord.Embed(
            title="✅ Log Entry Created",
            description="Your personal log entry has been saved successfully!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📝 Title",
            value=self.title_input.value,
            inline=False
        )
        
        embed.add_field(
            name="📅 Stardate",
            value=self.ingame_date,
            inline=True
        )
        
        embed.add_field(
            name="📖 Logbook",
            value=f"`{self.logbook_id[:8]}...`",
            inline=True
        )
        char_cog = self.bot.get_cog('CharacterCog')
        xp_awarded = False
        if char_cog:
            xp_awarded = await char_cog.try_award_passive_xp(interaction.user.id, "personal_log")

        if xp_awarded:
            embed.add_field(
                name="✨ Reflection", 
                value="Taking time to document your experiences has made you wiser. (+5 XP)", 
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
# Add this to your utils/views.py file
# Add this to your utils/views.py file
# Add this to your utils/views.py file
# Make sure to import discord at the top of the file if not already imported
# This class should be placed in the same file where CharacterPanelView is defined

class TQEOverviewView(discord.ui.View):
    """View for The Quiet End overview panel with navigation buttons"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.user_id = user_id
    
    @discord.ui.button(label="Location", style=discord.ButtonStyle.primary, emoji="📍")
    async def location_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the location panel (/here)"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the actual location_info command logic from CharacterCog
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            # Call the location_info command directly
            await char_cog.location_info.callback(char_cog, interaction)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)
    
    @discord.ui.button(label="Character", style=discord.ButtonStyle.secondary, emoji="👤")
    async def character_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the character panel (/status)"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # The /status command is in CharacterCog, so we need to call it directly
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            # Call the status_shorthand command directly
            await char_cog.status_shorthand.callback(char_cog, interaction)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)
    
    @discord.ui.button(label="Radio", style=discord.ButtonStyle.primary, emoji="📡")
    async def radio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open radio transmission modal"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Check if character exists and is logged in
        char_data = self.bot.db.execute_query(
            "SELECT is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You need a character to use the radio!",
                ephemeral=True
            )
            return
        
        if not char_data[0]:
            await interaction.response.send_message(
                "You must be logged in to use the radio!",
                ephemeral=True
            )
            return
        
        # Open the radio modal
        modal = RadioModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.success, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the overview panel"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Defer the response
        await interaction.response.defer()
        
        # Get updated character data
        char_data = self.bot.db.execute_query(
            """SELECT name, is_logged_in, current_location, current_ship_id, 
               location_status, money
               FROM characters WHERE user_id = ?""",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.followup.send(
                "Character data not found!",
                ephemeral=True
            )
            return
        
        char_name, is_logged_in, current_location, current_ship_id, location_status, money = char_data
        
        # Get age from character_identity table
        age_data = self.bot.db.execute_query(
            "SELECT age FROM character_identity WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        age = age_data[0] if age_data else "Unknown"
        
        # Recreate the embed with updated data
        embed = discord.Embed(
            title="🌌 The Quiet End - Overview",
            description=f"**{char_name}**'s Status Overview",
            color=0x1a1a2e
        )
        
        # Character Information Section
        status_emoji = "🟢" if is_logged_in else "⚫"
        status_text = "Online" if is_logged_in else "Offline"
        embed.add_field(
            name="👤 Character",
            value=f"**Status:** {status_emoji} {status_text}\n"
                  f"**Age:** {age} years\n"
                  f"**Credits:** {money:,}",
            inline=True
        )
        
        # Location/Transit Information Section
        if location_status == "traveling":
            # Get travel session info
            travel_info = self.bot.db.execute_query(
                """SELECT destination_location, arrival_time, 
                   julianday(arrival_time) - julianday('now') as time_remaining
                   FROM travel_sessions 
                   WHERE user_id = ? AND status = 'traveling'""",
                (interaction.user.id,),
                fetch='one'
            )
            
            if travel_info:
                dest_id, arrival_time, time_remaining = travel_info
                dest_info = self.bot.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = ?",
                    (dest_id,),
                    fetch='one'
                )
                dest_name = dest_info[0] if dest_info else "Unknown"
                
                # Convert time remaining to hours and minutes
                hours_remaining = int(time_remaining * 24)
                minutes_remaining = int((time_remaining * 24 - hours_remaining) * 60)
                
                embed.add_field(
                    name="🚀 Transit Status",
                    value=f"**En Route to:** {dest_name}\n"
                          f"**Time Remaining:** {hours_remaining}h {minutes_remaining}m",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📍 Location",
                    value="**Status:** In Transit\n**Destination:** Unknown",
                    inline=True
                )
        else:
            # Get current location info
            location_name = "Unknown Location"
            location_type = ""
            if current_location:
                location_info = self.bot.db.execute_query(
                    "SELECT name, location_type FROM locations WHERE location_id = ?",
                    (current_location,),
                    fetch='one'
                )
                if location_info:
                    location_name = location_info[0]
                    location_type = location_info[1]
            
            status_emoji = "🛬" if location_status == "docked" else "🚀"
            embed.add_field(
                name="📍 Location",
                value=f"**Current:** {location_name}\n"
                      f"**Type:** {location_type.replace('_', ' ').title()}\n"
                      f"**Status:** {status_emoji} {location_status.replace('_', ' ').title()}",
                inline=True
            )
        
        # Galaxy Information Section
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            current_datetime = time_system.calculate_current_ingame_time()
            if current_datetime:
                current_date = time_system.format_ingame_datetime(current_datetime)
            else:
                current_date = "Unknown Date"
        except:
            current_date = "Unknown Date"
        
        # Get logged in players count
        logged_in_count = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE is_logged_in = 1",
            fetch='one'
        )[0]
        
        # Get galaxy name from galaxy_info table
        galaxy_info = self.bot.db.execute_query(
            "SELECT name FROM galaxy_info WHERE galaxy_id = 1",
            fetch='one'
        )
        galaxy_name = galaxy_info[0] if galaxy_info else "Unknown Galaxy"
        
        embed.add_field(
            name="🌍 Galaxy",
            value=f"**Name:** {galaxy_name}\n"
                  f"**Date:** {current_date}\n"
                  f"**Players Online:** {logged_in_count}",
            inline=True
        )
        
        # Add instructions
        embed.add_field(
            name="📱 Quick Access",
            value="Use the buttons below to access detailed panels:",
            inline=False
        )
        
        embed.set_footer(text="The Quiet End • Panel refreshed!")
        
        # Edit the message with updated embed
        await interaction.edit_original_response(embed=embed, view=self)