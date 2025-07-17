# cogs/character.py
import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.location_utils import get_character_location_status
from datetime import datetime
import asyncio

class CharacterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    
    
    @app_commands.command(name="emote", description="Express an emotion or reaction")
    @app_commands.describe(emotion="The emotion or reaction to express")
    async def emote(self, interaction: discord.Interaction, emotion: str):
        char_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name = char_data[0]
        await interaction.response.send_message(f"**{char_name}** {emotion}")
        
        # Try to award passive XP
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "emote")
        if xp_awarded:
            try:
                await interaction.followup.send("✨ *Expressing yourself helps you understand the world better.* (+5 XP)", ephemeral=True)
            except:
                pass

    @app_commands.command(name="think", description="Share your character's internal thoughts")
    @app_commands.describe(thought="What your character is thinking")
    async def think(self, interaction: discord.Interaction, thought: str):
        char_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name = char_data[0]
        
        embed = discord.Embed(
            title="💭 Internal Thoughts",
            description=f"**{char_name}** thinks to themselves:",
            color=0x9370DB
        )
        embed.add_field(name="💭", value=f"*{thought}*", inline=False)
        
        # Try to award passive XP
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "think")
        if xp_awarded:
            embed.add_field(name="✨ Introspection", value="Deep thinking has expanded your awareness. (+5 XP)", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="observe", description="Describe what your character observes around them")
    @app_commands.describe(observation="What you observe in your surroundings")
    async def observe(self, interaction: discord.Interaction, observation: str):
        char_data = self.db.execute_query(
            "SELECT name, current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name, current_location = char_data
        
        # Get location name for context
        location_name = "Unknown Location"
        if current_location:
            loc_info = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (current_location,),
                fetch='one'
            )
            if loc_info:
                location_name = loc_info[0]
        
        embed = discord.Embed(
            title="👁️ Observation",
            description=f"**{char_name}** carefully observes their surroundings at **{location_name}**:",
            color=0x4682B4
        )
        embed.add_field(name="🔍 Noticed", value=observation, inline=False)
        
        # Try to award passive XP
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "observe")
        if xp_awarded:
            embed.add_field(name="✨ Awareness", value="You learn from your observations. (+5 XP)", inline=False)
        
        await interaction.response.send_message(embed=embed)

    
    character_group = app_commands.Group(name="character", description="Character management commands")

    @app_commands.command(name="status", description="Quick access to character information and management")
    async def status_shorthand(self, interaction: discord.Interaction):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name, is_logged_in = char_data
        
        # Create the character panel embed
        embed = discord.Embed(
            title=f"📋 Character Panel: {char_name}",
            description="Quick access to your character information",
            color=0x4169E1
        )
        
        # Add status indicator
        status_emoji = "🟢" if is_logged_in else "⚫"
        status_text = "Online" if is_logged_in else "Offline"
        embed.add_field(name="Status", value=f"{status_emoji} {status_text}", inline=True)
        
        embed.add_field(
            name="Available Actions",
            value="Use the buttons below to access different aspects of your character:",
            inline=False
        )
        
        embed.set_footer(text="Click the buttons below to view detailed information")
        
        view = CharacterPanelView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="here", description="Quick access to location panel and interactions")
    async def here_shorthand(self, interaction: discord.Interaction):
        # Call the existing location info logic
        await self.location_info.callback(self, interaction)
    
    @character_group.command(name="name", description="Toggle automatic nickname changing based on your character name.")
    @app_commands.describe(setting="Choose whether the bot should manage your nickname.")
    @app_commands.choices(setting=[
        app_commands.Choice(name="ON", value=1),
        app_commands.Choice(name="OFF", value=0)
    ])
    async def character_name(self, interaction: discord.Interaction, setting: app_commands.Choice[int]):
        """Toggles the automatic character nickname system."""
        if not interaction.guild.me.guild_permissions.manage_nicknames:
            await interaction.response.send_message(
                "❌ The bot lacks the `Manage Nicknames` permission to perform this action.",
                ephemeral=True
            )
            return

        char_check = self.db.execute_query(
            "SELECT 1 FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if not char_check:
            await interaction.response.send_message(
                "You don't have a character yet! Use `/character create` first.",
                ephemeral=True
            )
            return

        # Update the database
        self.db.execute_query(
            "UPDATE characters SET auto_rename = ? WHERE user_id = ?",
            (setting.value, interaction.user.id)
        )

        # Call the central nickname handler from the bot
        await self.bot.update_nickname(interaction.user)

        await interaction.response.send_message(
            f"✅ Automatic character naming has been set to **{setting.name}**.",
            ephemeral=True
        )

    
    @app_commands.command(
    name="act",
    description="Perform a roleplay action"
    )
    @app_commands.describe(
        action="Describe your character’s action"
    )
    async def act(self, interaction: discord.Interaction, action: str):
        # fetch character name from your DB
        row = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch="one"
        )
        if not row:
            await interaction.response.send_message(
                "You don’t have a character yet! Use `/character create` first.",
                ephemeral=True
            )
            return

        char_name = row[0]
        # send publicly in the channel
        await interaction.response.send_message(f"{char_name} *{action}*")
        
                # Optional: Send a follow-up message if XP was awarded
        if xp_awarded:
            try:
                await interaction.followup.send("✨ *You feel slightly more experienced from that action.* (+5 XP)", ephemeral=True)
            except:
                pass  # Ignore if follow-up fails
                
    @character_group.command(name="create", description="Create a new character")
    async def create_character(self, interaction: discord.Interaction):
        existing = self.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        current_year = 2751  # fallback default
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            current_time = time_system.calculate_current_ingame_time()
            if current_time:
                current_year = current_time.year
        except:
            pass  # Use fallback if time system unavailable
        if existing:
            await interaction.response.send_message(
                "You already have a character! Use `/character view` to see your stats.",
                ephemeral=True
            )
            return
        
        from utils.views import CharacterCreationView
        view = CharacterCreationView(self.bot)
        embed = discord.Embed(
            title="Welcome to the Galaxy",
            description=f"The year is {current_year}. Humanity is scattered across failing colonies connected by unstable Corridors. Click below to create your character and begin your journey.",
            color=0x8B4513
        )
        embed.add_field(
            name="Starting Equipment",
            value="• Basic ship with 100 fuel capacity\n• 500 credits\n• Basic stats in all skills",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @character_group.command(name="dock", description="Dock your ship at the current location")
    async def dock_ship(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, location_status = char_data
                # This is the only combat check needed.
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog and combat_cog.check_any_combat_status(interaction.user.id):
            await interaction.response.send_message(
                "❌ You cannot dock while in combat!",
                ephemeral=True
            )
            return
        
        if location_status == "docked":
            await interaction.response.send_message("You're already docked at this location!", ephemeral=True)
            return
        
        # Dock the ship
        self.db.execute_query(
            "UPDATE characters SET location_status = 'docked' WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )[0]
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character_group.command(name="undock", description="Undock and move to space near the location")
    async def undock_ship(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        # This is the only combat check needed.
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog and combat_cog.check_any_combat_status(interaction.user.id):
            await interaction.response.send_message(
                "❌ You cannot undock while in combat!",
                ephemeral=True
            )
            return
        current_location, location_status = char_data
        
        # NEW: Check for active stationary jobs
        active_jobs = self.db.execute_query(
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
            
            view = UndockJobConfirmView(self.bot, interaction.user.id, current_location)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        if not current_location:
            await interaction.response.send_message("You're in deep space!", ephemeral=True)
            return
        
        if location_status == "in_space":
            await interaction.response.send_message("You're already in space near this location!", ephemeral=True)
            return
        
        # Undock the ship
        self.db.execute_query(
            "UPDATE characters SET location_status = 'in_space' WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )[0]
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="view", description="View your character information")
    async def view_character(self, interaction: discord.Interaction):
        result = self.bot.db.execute_query(
            '''
            SELECT 
              c.name,
              c.callsign,
              c.appearance,
              c.hp,
              c.max_hp,
              c.money,
              c.engineering,
              c.navigation,
              c.combat,
              c.medical,
              c.current_location,
              c.location_status,
              l.name    AS location_name,
              s.name    AS ship_name,
              s.current_fuel,
              s.fuel_capacity,
              s.ship_type,
              c.experience,
              c.level,
              c.is_logged_in,
              c.current_ship_id,
              c.image_url
            FROM characters c
            LEFT JOIN locations l ON c.current_location = l.location_id
            LEFT JOIN ships     s ON c.ship_id       = s.ship_id
            WHERE c.user_id = ?
            ''',
            (interaction.user.id,),
            fetch='one'
        )

        if not result:
            await interaction.response.send_message(
                "You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return

        # Show full character info (with stats) to the owner
        (name, callsign, appearance, hp, max_hp, credits,
         eng, nav, combat_skill, medical_skill,
         current_location, location_status, location_name,
         ship_name, current_fuel, fuel_capacity, ship_type,
         experience, level, is_logged_in, current_ship_id, image_url) = result

        embed = discord.Embed(title=name, color=0x0099ff)
        # Add character image if available
        if image_url:
            embed.set_thumbnail(url=image_url)
        if callsign:
            embed.add_field(name="Radio Callsign", value=callsign, inline=True)
        embed.add_field(name="Health", value=f"{hp}/{max_hp}", inline=True)
        embed.add_field(name="Credits", value=f"{credits:,}", inline=True)
        
        # Login status
        login_emoji = "🟢" if is_logged_in else "⚫"
        login_status_text = "Online" if is_logged_in else "Offline"
        embed.add_field(name="Status", value=f"{login_emoji} {login_status_text}", inline=True)
        
        # Get accurate location status including ship context
        location_status_text, location_data = get_character_location_status(self.bot.db, interaction.user.id)

        if location_data and location_data['type'] == 'location':
            # Character is at a location (possibly in ship interior)
            if 'ship_context' in location_data:
                # In ship interior
                emoji = "🚀"
                embed.add_field(name="Location", value=f"{emoji} {location_status_text}", inline=True)
            else:
                # Directly at location
                emoji = "🛬" if location_status == "docked" else "🚀"
                embed.add_field(name="Location", value=f"{emoji} {location_name} ({location_status})", inline=True)
        elif location_data and location_data['type'] == 'transit':
            # Character is in transit
            embed.add_field(name="Location", value=f"🚀 {location_status_text}", inline=True)
        else:
            # Character is truly lost in space
            embed.add_field(name="Location", value="💀 Lost in Deep Space", inline=True)

        # Skills
        embed.add_field(name="Engineering", value=str(eng), inline=True)
        embed.add_field(name="Navigation", value=str(nav), inline=True)
        embed.add_field(name="Combat", value=str(combat_skill), inline=True)
        embed.add_field(name="Medical", value=str(medical_skill), inline=True)
        embed.add_field(name="⚖️ Reputation", value="Use `/reputation` to view your standings.", inline=True)
        # Level & Experience
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Experience", value=f"{experience:,} EXP", inline=True)

        # Ship info
        if ship_name:
            embed.add_field(name="Ship", value=f"{ship_name} ({ship_type})", inline=True)
            embed.add_field(name="Fuel", value=f"{current_fuel}/{fuel_capacity}", inline=True)
        else:
            embed.add_field(name="Ship", value="No Ship", inline=True)

        # Location context hints
        if current_ship_id:
            embed.add_field(
                name="🚀 Ship Interior Status",
                value="• Inside your ship\n• Radio uses ship's docking location\n• Use `/ship interior leave` to exit",
                inline=False
            )
        elif location_name:
            if location_status == "docked":
                embed.add_field(
                    name="🛬 Docked Status",
                    value="• Full location access\n• Personal combat available\n• Use `/character undock` to move to space",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🚀 In-Space Status",
                    value="• Ship combat available\n• Limited location services\n• Use `/character dock` to dock",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character_group.command(name="location", description="View current location and available actions")
    async def location_info(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT user_id, current_location, location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        user_id, current_location, location_status = char_data
        
        if not current_location:
            await interaction.response.send_message(
                "You're not at a location!",
                ephemeral=True
            )
            return
        
        # Get location info
        location_info = self.db.execute_query(
            "SELECT name, channel_id FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message(
                "Location not found!",
                ephemeral=True
            )
            return
        
        location_name, channel_id = location_info
        
        # Create ephemeral location panel
        from utils.views import EphemeralLocationView
        view = EphemeralLocationView(self.bot, user_id)
        
        embed = discord.Embed(
            title="📍 Location Panel",
            description=f"**{location_name}** - Interactive Control Panel",
            color=0x4169E1
        )
        
        # Add status indicator
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
        
        embed.set_footer(text="Use the buttons to interact with the location!")
        
        # Send ephemeral response
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    @character_group.command(name="inventory", description="View your inventory")
    async def view_inventory(self, interaction: discord.Interaction):
        char_check = self.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_check:
            await interaction.response.send_message(
                "You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        items = self.db.execute_query(
            '''SELECT item_name, item_type, quantity, description, value
               FROM inventory 
               WHERE owner_id = ?
               ORDER BY item_type, item_name''',
            (interaction.user.id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="Inventory",
            description="Your current items and equipment",
            color=0x8B4513
        )
        
        if not items:
            embed.add_field(name="Empty", value="Your inventory is empty.", inline=False)
        else:
            # Group by item type
            item_types = {}
            total_value = 0
            
            for name, item_type, quantity, description, value in items:
                if item_type not in item_types:
                    item_types[item_type] = []
                
                item_types[item_type].append((name, quantity, value))
                total_value += value * quantity
            
            for item_type, type_items in item_types.items():
                items_text = []
                for name, quantity, value in type_items[:5]:  # Limit display
                    qty_text = f" x{quantity}" if quantity > 1 else ""
                    value_text = f" ({value * quantity} credits)" if value > 0 else ""
                    items_text.append(f"{name}{qty_text}{value_text}")
                
                if len(type_items) > 5:
                    items_text.append(f"...and {len(type_items) - 5} more")
                
                embed.add_field(
                    name=item_type.replace('_', ' ').title(),
                    value="\n".join(items_text) or "None",
                    inline=True
                )
            
            embed.add_field(name="Total Value", value=f"{total_value:,} credits", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="id", description="View character ID information")
    @app_commands.describe(target="View another character's ID (if not scrubbed)")
    async def view_character_id(self, interaction: discord.Interaction, target: discord.Member = None):
        target_user = target or interaction.user
        
        # Get character and identity info
        char_result = self.bot.db.execute_query(
            '''SELECT c.name, c.callsign, c.appearance, ci.birth_month, ci.birth_day, 
                      ci.birth_year, ci.age, ci.biography, ci.id_scrubbed, l.name as birthplace,
                      c.image_url
               FROM characters c
               LEFT JOIN character_identity ci ON c.user_id = ci.user_id
               LEFT JOIN locations l ON ci.birthplace_id = l.location_id
               WHERE c.user_id = ?''',
            (target_user.id,),
            fetch='one'
        )        
        if not char_result:
            await interaction.response.send_message(
                f"{'You don\'t' if target is None else target.display_name + ' doesn\'t'} have a character!",
                ephemeral=True
            )
            return
        
        (name, callsign, appearance, birth_month, birth_day, birth_year, 
         age, biography, id_scrubbed, birthplace, image_url) = char_result
        
        # Check if ID is scrubbed and viewing someone else's ID
        if id_scrubbed and target_user.id != interaction.user.id:
            error_messages = [
                "❌ **ID LOOKUP ERROR**\n`ERR_ID_NOT_FOUND: Record corrupted or deleted`",
                "❌ **ACCESS DENIED**\n`ERR_DATABASE_CORRUPTED: Identity records unavailable`",
                "❌ **QUERY FAILED**\n`ERR_CONNECTION_TIMEOUT: Unable to retrieve identity data`",
                "❌ **ID SCRUBBED**\n`ERR_RECORD_PURGED: Identity information has been permanently removed`"
            ]
            await interaction.response.send_message(random.choice(error_messages), ephemeral=True)
            return
        
        # Show identity information
        embed = discord.Embed(
            title=f"📋 Character Identity: {name}",
            color=0x4169E1 if not id_scrubbed else 0x888888
        )

        if image_url and not id_scrubbed:
            embed.set_thumbnail(url=image_url)
        elif image_url and id_scrubbed and target_user.id == interaction.user.id:
            # Show image to owner even if ID is scrubbed
            embed.set_thumbnail(url=image_url)
        
        if id_scrubbed and target_user.id == interaction.user.id:
            embed.add_field(
                name="⚠️ ID Status",
                value="Your identity has been scrubbed. Others will see an error when viewing your ID.",
                inline=False
            )
        
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Callsign", value=callsign or "Unknown", inline=True)
        embed.add_field(name="Age", value=f"{age} years", inline=True)
        
        if birth_month and birth_day and birth_year:
            embed.add_field(name="Born", value=f"{birth_month:02d}/{birth_day:02d}/{birth_year}", inline=True)
        
        if birthplace:
            embed.add_field(name="Birthplace", value=birthplace, inline=True)
        
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        if appearance:
            embed.add_field(name="Physical Description", value=appearance, inline=False)
        
        if biography:
            embed.add_field(name="Biography", value=biography[:1000], inline=False)
        
        # Add scrubbing option for own character
        if target_user.id == interaction.user.id and not id_scrubbed:
            view = IDScrubView(self.bot, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="ship", description="View detailed ship information")
    async def view_ship(self, interaction: discord.Interaction):
        ship_data = self.db.execute_query(
            '''SELECT s.*, c.name as owner_name
               FROM ships s
               JOIN characters c ON s.owner_id = c.user_id
               WHERE s.owner_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_data:
            await interaction.response.send_message(
                "You don't have a ship! Create a character first.",
                ephemeral=True
            )
            return
        
        # FIX: The unpacking now includes the `docked_at_location` column to match the database schema.
        (ship_id,
         owner_id,
         name,
         ship_type,
         fuel_capacity,
         current_fuel,
         fuel_efficiency,
         combat_rating,
         hull_integrity,
         max_hull,
         cargo_capacity,
         cargo_used,
         ship_hp,
         max_ship_hp,
         created_at,
         ship_class,
         upgrade_slots,
         used_upgrade_slots,
         exterior_description,
         interior_description,
         channel_id,
         docked_at_location, # This was the missing column
         owner_name
        ) = ship_data
        
        embed = discord.Embed(
            title=name,
            description=f"Class: {ship_type}",
            color=0x2F4F4F
        )
        
        # Status indicators
        fuel_percent = (current_fuel / fuel_capacity) * 100 if fuel_capacity > 0 else 0
        hull_percent = (hull_integrity / max_hull) * 100 if max_hull > 0 else 0
        hp_percent = (ship_hp / max_ship_hp) * 100 if max_ship_hp > 0 else 0
        cargo_percent = (cargo_used / cargo_capacity) * 100 if cargo_capacity > 0 else 0
        
        # Fuel status
        fuel_emoji = "🟢" if fuel_percent > 70 else "🟡" if fuel_percent > 30 else "🔴"
        embed.add_field(
            name="Fuel",
            value=f"{fuel_emoji} {current_fuel}/{fuel_capacity} ({fuel_percent:.0f}%)",
            inline=True
        )
        
        # Hull status
        hull_emoji = "🟢" if hull_percent > 70 else "🟡" if hull_percent > 30 else "🔴"
        embed.add_field(
            name="Hull Integrity",
            value=f"{hull_emoji} {hull_integrity}/{max_hull} ({hull_percent:.0f}%)",
            inline=True
        )
        
        # Ship HP
        hp_emoji = "🟢" if hp_percent > 70 else "🟡" if hp_percent > 30 else "🔴"
        embed.add_field(
            name="Ship Health",
            value=f"{hp_emoji} {ship_hp}/{max_ship_hp} ({hp_percent:.0f}%)",
            inline=True
        )
        
        # Cargo
        cargo_emoji = "🟢" if cargo_percent < 70 else "🟡" if cargo_percent < 90 else "🔴"
        embed.add_field(
            name="Cargo",
            value=f"{cargo_emoji} {cargo_used}/{cargo_capacity} ({cargo_percent:.0f}% full)",
            inline=True
        )
        
        # Performance stats
        embed.add_field(name="Fuel Efficiency", value=f"{fuel_efficiency}/10", inline=True)
        embed.add_field(name="Combat Rating", value=f"{combat_rating}/10", inline=True)
        
        # Add warning if ship needs attention
        warnings = []
        if fuel_percent < 30:
            warnings.append("⚠️ Low fuel")
        if hull_percent < 50:
            warnings.append("⚠️ Hull damage")
        if hp_percent < 50:
            warnings.append("⚠️ Systems damaged")
        if cargo_percent > 90:
            warnings.append("⚠️ Cargo hold full")
        
        if warnings:
            embed.add_field(name="Alerts", value="\n".join(warnings), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="search", description="Search your current location for items")
    async def search_location(self, interaction: discord.Interaction):
        # Check character exists and get location
        char_data = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data or not char_data[0]:
            await interaction.response.send_message("You need to be at a location to search!", ephemeral=True)
            return
        
        current_location = char_data[0]
        
        # Check location type (no searching on ships or travel channels)
        location_info = self.db.execute_query(
            "SELECT name, location_type, wealth_level FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message("Invalid location!", ephemeral=True)
            return
        
        location_name, location_type, wealth_level = location_info
        
        # Check if location allows searching
        if location_type in ['ship', 'travel']:
            await interaction.response.send_message("You cannot search here!", ephemeral=True)
            return
        
        # Check cooldown
        cooldown_data = self.db.execute_query(
            "SELECT last_search_time FROM search_cooldowns WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        import datetime
        current_time = datetime.datetime.now()
        
        if cooldown_data:
            last_search = datetime.datetime.fromisoformat(cooldown_data[0])
            time_diff = current_time - last_search
            
            # 15 minute cooldown
            if time_diff.total_seconds() < 900:  # 15 minutes
                remaining = 900 - time_diff.total_seconds()
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                await interaction.response.send_message(
                    f"You must wait {minutes}m {seconds}s before searching again.", 
                    ephemeral=True
                )
                return
        
        # Start search
        search_duration = random.randint(15, 60)  # 15-60 seconds
        
        embed = discord.Embed(
            title="🔍 Searching...",
            description=f"Searching **{location_name}** for items...",
            color=0xffff00
        )
        embed.add_field(name="Time Remaining", value=f"{search_duration} seconds", inline=True)
        embed.add_field(name="Location Type", value=location_type.replace('_', ' ').title(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Update search progress every 10-15 seconds
        updates = []
        if search_duration >= 30:
            updates.append(search_duration // 2)
        if search_duration >= 45:
            updates.append(search_duration // 3)
        
        for update_time in updates:
            await asyncio.sleep(update_time)
            remaining = search_duration - update_time
            search_duration = remaining
            
            # Random search progress message
            progress_messages = [
                "Examining debris and containers...",
                "Checking hidden compartments...", 
                "Scanning for valuable materials...",
                "Searching through scattered equipment...",
                "Looking in overlooked areas..."
            ]
            
            embed = discord.Embed(
                title="🔍 Searching...",
                description=f"Searching **{location_name}** for items...\n\n*{random.choice(progress_messages)}*",
                color=0xffff00
            )
            embed.add_field(name="Time Remaining", value=f"{remaining} seconds", inline=True)
            
            try:
                await interaction.edit_original_response(embed=embed)
            except:
                pass  # Message might be deleted
        
        # Final wait
        await asyncio.sleep(search_duration - sum(updates) if updates else search_duration)
        
        # Update cooldown
        if cooldown_data:
            self.db.execute_query(
                "UPDATE search_cooldowns SET last_search_time = ?, location_id = ? WHERE user_id = ?",
                (current_time.isoformat(), current_location, interaction.user.id)
            )
        else:
            self.db.execute_query(
                "INSERT INTO search_cooldowns (user_id, last_search_time, location_id) VALUES (?, ?, ?)",
                (interaction.user.id, current_time.isoformat(), current_location)
            )
        
        # Generate search results
        from utils.item_config import ItemConfig
        found_items = ItemConfig.generate_search_loot(location_type, wealth_level)
        
        # Create results embed
        if not found_items:
            embed = discord.Embed(
                title="🔍 Search Complete",
                description=f"You thoroughly searched **{location_name}** but found nothing of value.",
                color=0x808080
            )
            embed.add_field(name="Better Luck Next Time", value="Try searching other locations or wait for the area to refresh.", inline=False)
        else:
            # Add items to inventory
            items_added = []
            for item_name, quantity in found_items:
                item_def = ItemConfig.get_item_definition(item_name)
                if not item_def:
                    continue
                
                # Check if item already exists in inventory
                existing_item = self.db.execute_query(
                    "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                    (interaction.user.id, item_name),
                    fetch='one'
                )
                
                if existing_item:
                    self.db.execute_query(
                        "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
                        (quantity, existing_item[0])
                    )
                else:
                    # Create metadata for new item
                    metadata = ItemConfig.create_item_metadata(item_name)
                    
                    self.db.execute_query(
                        '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (interaction.user.id, item_name, item_def["type"], quantity, 
                         item_def["description"], item_def["base_value"], metadata)
                    )
                
                items_added.append(f"{quantity}x **{item_name}**")
            
            embed = discord.Embed(
                title="🔍 Search Complete",
                description=f"You found items while searching **{location_name}**!",
                color=0x00ff00
            )
            embed.add_field(name="Items Found", value="\n".join(items_added), inline=False)
            embed.add_field(name="Next Search", value="You can search again in 15 minutes.", inline=False)
        
        try:
            await interaction.edit_original_response(embed=embed)
        except:
            # Fallback if edit fails
            await interaction.followup.send(embed=embed, ephemeral=True)
    @character_group.command(name="delete", description="Permanently delete your character (cannot be undone!)")
    async def delete_character(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT name, money, hp FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character to delete.",
                ephemeral=True
            )
            return
        
        char_name, money, hp = char_data
        
        # Don't allow deletion if character is dead (HP = 0)
        if hp <= 0:
            await interaction.response.send_message(
                "Your character is dead and will be automatically removed. You cannot manually delete a dead character.",
                ephemeral=True
            )
            return
        
        # Import the view class from channel_manager
        from utils.channel_manager import CharacterDeleteConfirmView
        view = CharacterDeleteConfirmView(self.bot, interaction.user.id, char_name)
        
        embed = discord.Embed(
            title="⚠️ PERMANENT CHARACTER DELETION",
            description=f"You are about to **permanently delete** your character **{char_name}**.",
            color=0xff0000
        )
        
        embed.add_field(
            name="⚠️ WARNING",
            value="This action **CANNOT BE UNDONE**!\n\n• Your character will be completely removed\n• Your ship will be deleted\n• All inventory will be lost\n• All progress will be erased",
            inline=False
        )
        
        embed.add_field(
            name="💰 Current Assets",
            value=f"Credits: {money:,}\nHP: {hp}/100\nThese will be permanently lost!",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Confirmation Required",
            value="Click the button below to confirm permanent deletion.",
            inline=False
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    async def try_award_passive_xp(self, user_id: int, action_type: str = "roleplay"):
        """Award passive XP with 25% chance for roleplay actions"""
        import random
        
        # 25% chance to gain XP
        if random.random() > 0.25:
            return False
        
        # Check if character exists and is logged in
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data or not char_data[1]:  # Character doesn't exist or not logged in
            return False
        
        char_name = char_data[0]
        xp_gained = 5
        
        # Award XP
        self.db.execute_query(
            "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
            (xp_gained, user_id)
        )
        
        # Check for level up
        await self.level_up_check(user_id)
        
        return True
        
    async def cleanup_character_homes(self, user_id: int):
        """Release all homes owned by a character when they die or are deleted"""
        
        # Get all owned homes
        owned_homes = self.db.execute_query(
            '''SELECT home_id, home_name, location_id FROM location_homes 
               WHERE owner_id = ?''',
            (user_id,),
            fetch='all'
        )
        
        if owned_homes:
            # Make all homes available again
            self.db.execute_query(
                '''UPDATE location_homes 
                   SET owner_id = NULL, is_available = 1, purchase_date = NULL
                   WHERE owner_id = ?''',
                (user_id,)
            )
            
            # Remove any market listings
            self.db.execute_query(
                '''UPDATE home_market_listings 
                   SET is_active = 0
                   WHERE seller_id = ?''',
                (user_id,)
            )
            
            # Clean up home interior threads
            for home_id, home_name, location_id in owned_homes:
                interior_info = self.db.execute_query(
                    "SELECT channel_id FROM home_interiors WHERE home_id = ?",
                    (home_id,),
                    fetch='one'
                )
                
                if interior_info and interior_info[0]:
                    try:
                        thread = self.bot.get_channel(interior_info[0])
                        if thread and isinstance(thread, discord.Thread):
                            await thread.edit(archived=True, reason="Owner character deleted")
                    except:
                        pass
            
            print(f"Released {len(owned_homes)} homes from character {user_id}")

    async def _execute_character_death(self, user_id: int, char_name: str, guild: discord.Guild, reason: str = "unknown"):
        """Execute automatic character death with enhanced descriptions."""
        member = guild.get_member(user_id)
        if member and guild.me.guild_permissions.manage_nicknames:
            # We only clear the nickname if it matches the character who is dying.
            # This avoids clearing a custom nickname the user may have set.
            if member.nick == char_name:
                try:
                    await member.edit(nick=None, reason="Character has died.")
                except Exception as e:
                    print(f"Failed to clear nickname on death for {member}: {e}")
        # Get detailed character info for the obituary and death message
        char_data = self.db.execute_query(
            "SELECT c.current_location, c.current_ship_id, l.name as loc_name "
            "FROM characters c "
            "LEFT JOIN locations l ON c.current_location = l.location_id "
            "WHERE c.user_id = ?",
            (user_id,),
            fetch='one'
        )

        location_id = None
        ship_id = None
        location_name = "Deep Space"
        if char_data:
            location_id, ship_id, location_name = char_data
            if ship_id and not location_id:
                ship_loc = self.db.execute_query(
                    "SELECT docked_at_location FROM ships WHERE ship_id = ?",
                    (ship_id,), fetch='one'
                )
                if ship_loc and ship_loc[0]:
                    location_id = ship_loc[0]
                    loc_name_result = self.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = ?",
                        (location_id,), fetch='one'
                    )
                    if loc_name_result:
                        location_name = loc_name_result[0]


        # Post obituary FIRST, before deleting character data
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog and location_id:
            await news_cog.post_obituary_news(char_name, location_id, reason)

        # Delete character and associated data
        self.db.execute_query("DELETE FROM characters WHERE user_id = ?", (user_id,))
        self.db.execute_query("DELETE FROM character_identity WHERE user_id = ?", (user_id,))
        if ship_id:
             self.db.execute_query("DELETE FROM ships WHERE ship_id = ?", (ship_id,))
        self.db.execute_query(
            "UPDATE travel_sessions SET status = 'character_death' WHERE user_id = ? AND status = 'traveling'",
            (user_id,)
        )
        self.db.execute_query("UPDATE characters SET group_id = NULL WHERE user_id = ?", (user_id,))
        self.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL WHERE taken_by = ?",
            (user_id,)
        )
        await self.cleanup_character_homes(user_id)
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        member = guild.get_member(user_id)
        if member and location_id:
            await channel_manager.remove_user_location_access(member, location_id)


        # Create death announcement with gruesome descriptions
        death_descriptions = [
            f"The last transmission from **{char_name}** was a burst of static and a final, choked scream. Their vessel was later found vented to space, the crew lost to the cold vacuum.",
            f"An emergency beacon from **{char_name}'s** ship was detected, but rescue crews arrived too late. The ship's log detailed a catastrophic life support failure. There were no survivors.",
            f"**{char_name}**'s ship was found adrift, its hull breached by pirate munitions. The interior was a scene of violence and desperation. No one was left alive.",
            f"A critical engine malfunction caused **{char_name}**'s vessel to explode during transit. Debris was scattered across several kilometers of space. The crew was lost instantly.",
            f"After a hull breach during a firefight, **{char_name}** was exposed to hard vacuum. The body was later recovered, a frozen monument to the brutality of space.",
        ]
        obituary_text = random.choice(death_descriptions)

        embed = discord.Embed(
            title="💀 CHARACTER DEATH",
            description=obituary_text,
            color=0x000000
        )

        embed.add_field(
            name="⚰️ Final Rest",
            value=f"**{char_name}**'s journey has come to a violent end. Their story is now a cautionary tale whispered in station bars across the sector.",
            inline=False
        )

        embed.add_field(
            name="🔄 Starting Over",
            value="You can create a new character with `/character create` to begin a new journey.",
            inline=False
        )

        # Announce in location channel if it exists
        if location_id:
            location_channel_id_result = self.db.execute_query("SELECT channel_id FROM locations WHERE location_id = ?", (location_id,), fetch='one')
            if location_channel_id_result and location_channel_id_result[0]:
                location_channel = guild.get_channel(location_channel_id_result[0])
                if location_channel:
                    try:
                        death_announcement = discord.Embed(
                            title="💀 Tragedy Strikes",
                            description=f"A grim discovery has been made at {location_name}. **{char_name}** is dead.",
                            color=0x8b0000
                        )
                        death_announcement.add_field(
                            name="Cause of Death",
                            value=reason.title(),
                            inline=False
                        )
                        death_announcement.set_footer(text="Another soul lost to the void.")
                        await location_channel.send(embed=death_announcement)
                    except Exception as e:
                        print(f"Error sending death announcement to channel: {e}")

        print(f"💀 Character death (automatic): {char_name} (ID: {user_id}) - {reason}")

    async def update_character_hp(self, user_id: int, hp_change: int, guild: discord.Guild, reason: str = ""):
        """Update character HP and check for death"""
        self.db.execute_query(
            "UPDATE characters SET hp = MAX(0, hp + ?) WHERE user_id = ?",
            (hp_change, user_id)
        )
        return await self.check_character_death(user_id, guild, reason)
        
    async def update_ship_hull(self, user_id: int, hull_change: int, guild: discord.Guild, reason: str = ""):
        """Update ship hull and check for death"""
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = MAX(0, hull_integrity + ?) WHERE owner_id = ?",
            (hull_change, user_id)
        )
        return await self.check_ship_death(user_id, guild, reason)    
    @character_group.command(name="login", description="Log into the game and restore your character")
    async def login_character(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT name, current_location, is_logged_in, group_id, current_ship_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name, current_location, is_logged_in, group_id, current_ship_id = char_data
        
        if is_logged_in:
            await interaction.response.send_message(
                f"**{char_name}** is already logged in!",
                ephemeral=True
            )
            return
        
        # Log in the character
        self.db.execute_query(
            "UPDATE characters SET is_logged_in = 1, login_time = CURRENT_TIMESTAMP, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        # Restore location access
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        location_name = "Deep Space"

        if current_ship_id:
            ship_info_raw = self.db.execute_query(
                "SELECT ship_id, name, ship_type, interior_description, channel_id, owner_id FROM ships WHERE ship_id = ?",
                (current_ship_id,), fetch='one'
            )
            if ship_info_raw:
                ship_id, ship_name, s_type, s_int, s_chan, owner_id = ship_info_raw
                owner = interaction.guild.get_member(owner_id)
                if owner:
                    ship_tuple = (ship_id, ship_name, s_type, s_int, s_chan)
                    await channel_manager.get_or_create_ship_channel(interaction.guild, ship_tuple, owner)
                    await channel_manager.give_user_ship_access(interaction.user, current_ship_id)
                    location_name = f"Aboard '{ship_name}'"
                else:
                    self.db.execute_query("UPDATE characters SET current_ship_id = NULL, current_location = NULL WHERE user_id = ?", (interaction.user.id,))
                    location_name = "Lost in Space (Ship's owner not found)"
            else:
                self.db.execute_query("UPDATE characters SET current_ship_id = NULL, current_location = NULL WHERE user_id = ?", (interaction.user.id,))
                location_name = "Lost in Space (Ship was destroyed)"

        elif current_location:
            success = await channel_manager.restore_user_location_on_login(interaction.user, current_location)
            location_name = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (current_location,),
                fetch='one'
            )[0]
        
        # Handle group rejoining
        group_status = ""
        if group_id:
            # Check if other group members are online
            online_members = self.db.execute_query(
                "SELECT COUNT(*) FROM characters WHERE group_id = ? AND is_logged_in = 1",
                (group_id,),
                fetch='one'
            )[0]
            
            group_info = self.db.execute_query(
                "SELECT name, leader_id FROM groups WHERE group_id = ?",
                (group_id,),
                fetch='one'
            )
            
            if group_info:
                group_name, leader_id = group_info
                
                # Check if this user is the leader
                is_leader = (leader_id == interaction.user.id)
                
                if online_members > 0:
                    group_status = f"\n🎯 Rejoined group **{group_name}** ({online_members} members online)"
                    if is_leader:
                        group_status += " - You are the leader"
                else:
                    group_status = f"\n🎯 First member online in group **{group_name}**"
                    if is_leader:
                        group_status += " - You are the leader"
                
                # Notify other online group members
                other_members = self.db.execute_query(
                    "SELECT user_id, name FROM characters WHERE group_id = ? AND user_id != ? AND is_logged_in = 1",
                    (group_id, interaction.user.id),
                    fetch='all'
                )
                
                for member_id, member_name in other_members:
                    member = self.bot.get_user(member_id)
                    if member:
                        try:
                            await member.send(f"📢 **{char_name}** from your group **{group_name}** has come online!")
                        except:
                            pass
        
        # Update activity tracker
        if hasattr(self.bot, 'activity_tracker'):
            self.bot.activity_tracker.update_activity(interaction.user.id)
        
        embed = discord.Embed(
            title="✅ Login Successful",
            description=f"Welcome back, **{char_name}**!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📍 Current Location",
            value=location_name,
            inline=True
        )
        
        embed.add_field(
            name="🕐 Session Started",
            value=f"<t:{int(datetime.now().timestamp())}:T>",
            inline=True
        )
        
        if group_status:
            embed.add_field(
                name="👥 Group Status",
                value=group_status.strip(),
                inline=False
            )
        
        embed.add_field(
            name="💡 Tip",
            value="Use `/character location` to interact with your current location.",
            inline=False
        )
        
        await self.bot.update_nickname(interaction.user)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character_group.command(name="logout", description="Log out of the game (saves your progress)")
    async def logout_character(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in, group_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character!",
                ephemeral=True
            )
            return
        
        char_name, is_logged_in, group_id = char_data
        
        if not is_logged_in:
            await interaction.response.send_message(
                f"**{char_name}** is not currently logged in.",
                ephemeral=True
            )
            return
        
        # Check for active jobs
        active_jobs = self.db.execute_query(
            "SELECT COUNT(*) FROM jobs WHERE taken_by = ? AND job_status = 'active'",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if active_jobs > 0:
            view = LogoutConfirmView(self.bot, interaction.user.id, char_name, active_jobs)
            
            embed = discord.Embed(
                title="⚠️ Active Jobs Warning",
                description=f"**{char_name}** has {active_jobs} active job(s).",
                color=0xff9900
            )
            embed.add_field(
                name="Logout Effect",
                value="Logging out will **cancel** all active jobs and you won't receive payment.",
                inline=False
            )
            embed.add_field(
                name="Confirm Logout?",
                value="Choose below to proceed or cancel.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # No active jobs, proceed with logout
            await self._execute_logout(interaction.user.id, char_name, interaction)

    async def _execute_logout(self, user_id: int, char_name: str, interaction: discord.Interaction):
        """Execute the logout process"""
        member = interaction.guild.get_member(user_id)
        if member and interaction.guild.me.guild_permissions.manage_nicknames:
            # We only clear the nickname if it matches the character name and auto-rename is on.
            auto_rename_setting = self.db.execute_query(
                "SELECT auto_rename FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            if auto_rename_setting and auto_rename_setting[0] == 1 and member.nick == char_name:
                try:
                    await member.edit(nick=None, reason="Character logged out.")
                except Exception as e:
                    print(f"Failed to clear nickname on logout for {member}: {e}")
        # Cancel any active jobs
        self.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = ?",
            (user_id,)
        )
        # Handle group notifications and management
        group_info = self.db.execute_query(
            "SELECT g.group_id, g.name FROM characters c JOIN groups g ON c.group_id = g.group_id WHERE c.user_id = ?",
            (user_id,),
            fetch='one'
        )

        if group_info:
            group_id, group_name = group_info
            
            # Notify other online group members
            other_members = self.db.execute_query(
                "SELECT user_id, name FROM characters WHERE group_id = ? AND user_id != ? AND is_logged_in = 1",
                (group_id, user_id),
                fetch='all'
            )
            
            for member_id, member_name in other_members:
                member = self.bot.get_user(member_id)
                if member:
                    try:
                        await member.send(f"📢 **{char_name}** from your group **{group_name}** has gone offline.")
                    except:
                        pass
            
            # Check if this was the last online member and handle group state
            remaining_online = self.db.execute_query(
                "SELECT COUNT(*) FROM characters WHERE group_id = ? AND is_logged_in = 1 AND user_id != ?",
                (group_id, user_id),
                fetch='one'
            )[0]
            
            if remaining_online == 0:
                # Last member logging out - could add special handling here
                print(f"🎯 Group {group_name} has no online members after {char_name} logout")
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = ?",
            (user_id,)
        )
        
        # Get current location and ship for cleanup
        char_state = self.db.execute_query(
            "SELECT current_location, current_ship_id FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        current_location, current_ship_id = char_state if char_state else (None, None)

        # Log out the character
        self.db.execute_query(
            "UPDATE characters SET is_logged_in = 0 WHERE user_id = ?",
            (user_id,)
        )

        # Remove access and cleanup
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)

        if current_location:
            await channel_manager.remove_user_location_access(interaction.user, current_location)
            await channel_manager.immediate_logout_cleanup(interaction.guild, current_location)
        elif current_ship_id:
            await channel_manager.remove_user_ship_access(interaction.user, current_ship_id)
            await channel_manager.immediate_logout_cleanup(interaction.guild, None, current_ship_id)
        
        # Clean up activity tracker
        if hasattr(self.bot, 'activity_tracker'):
            self.bot.activity_tracker.cleanup_user_tasks(user_id)
        
        embed = discord.Embed(
            title="👋 Logout Successful",
            description=f"**{char_name}** has been logged out safely.",
            color=0xff9900
        )
        
        embed.add_field(
            name="💾 Progress Saved",
            value="• Character data preserved\n• Inventory saved\n• Location remembered\n• Group membership maintained",
            inline=False
        )
        
        embed.add_field(
            name="🔄 Next Login",
            value="Use `/character login` to resume your journey exactly where you left off.",
            inline=False
        )
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def _execute_auto_logout(self, user_id: int, reason: str):
        """Execute automatic logout (called by activity tracker)"""
        char_data = self.db.execute_query(
            "SELECT name, current_location, current_ship_id FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        char_name, current_location, current_ship_id = char_data
        
        # Cancel any active jobs
        self.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = ?",
            (user_id,)
        )
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = ?",
            (user_id,)
        )
        # Handle group notifications - SAME AS ABOVE
        group_info = self.db.execute_query(
            "SELECT group_id, name FROM characters c JOIN groups g ON c.group_id = g.group_id WHERE c.user_id = ?",
            (user_id,),
            fetch='one'
        )

        if group_info:
            group_id, group_name = group_info
            
            # Notify other online group members about AFK logout
            other_members = self.db.execute_query(
                "SELECT user_id, name FROM characters WHERE group_id = ? AND user_id != ? AND is_logged_in = 1",
                (group_id, user_id),
                fetch='all'
            )
            
            for member_id, member_name in other_members:
                member = self.bot.get_user(member_id)
                if member:
                    try:
                        await member.send(f"📢 **{char_name}** from your group **{group_name}** was automatically logged out due to inactivity.")
                    except:
                        pass
        # Log out the character
        self.db.execute_query(
            "UPDATE characters SET is_logged_in = 0 WHERE user_id = ?",
            (user_id,)
        )
        
        # Remove access and cleanup
        user = self.bot.get_user(user_id)
        if user:
            # Find the guild where this user is
            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    # NEW: Clear nickname on auto-logout
                    if guild.me.guild_permissions.manage_nicknames:
                        auto_rename_setting = self.db.execute_query(
                            "SELECT auto_rename FROM characters WHERE user_id = ?",
                            (user_id,),
                            fetch='one'
                        )
                        if auto_rename_setting and auto_rename_setting[0] == 1 and member.nick == char_name:
                            try:
                                await member.edit(nick=None, reason="Character auto-logged out.")
                            except Exception as e:
                                print(f"Failed to clear nickname on auto-logout for {member}: {e}")

                    from utils.channel_manager import ChannelManager
                    channel_manager = ChannelManager(self.bot)
                    
                    if current_location:
                        await channel_manager.remove_user_location_access(member, current_location)
                        await channel_manager.immediate_logout_cleanup(guild, current_location)
                    elif current_ship_id:
                        await channel_manager.remove_user_ship_access(member, current_ship_id)
                        await channel_manager.immediate_logout_cleanup(guild, None, current_ship_id)
                    
                    break
        
        # Notify user
        if user:
            embed = discord.Embed(
                title="😴 Automatic Logout",
                description=f"**{char_name}** has been logged out due to inactivity.",
                color=0xff9900
            )
            embed.add_field(
                name="🔄 Log Back In",
                value="You can log back in with the login button or `/character login`",
                inline=False
            )
            
            try:
                await user.send(embed=embed)
            except:
                pass  # Failed to DM user
        
        print(f"🚪 Auto-logout: {char_name} (ID: {user_id}) - {reason}")
        
        print(f"🚪 Auto-logout: {char_name} (ID: {user_id}) - {reason}")
        
    
    @character_group.command(name="drop", description="Drop an item at your current location")
    @app_commands.describe(
        item_name="Name of the item to drop",
        quantity="Number of items to drop (default: 1)"
    )
    async def drop_item(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        if quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than 0.", ephemeral=True)
            return
        
        # Get character info
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[0]:
            await interaction.response.send_message("You cannot drop items while in transit!", ephemeral=True)
            return
        
        current_location = char_info[0]
        
        # Find item in inventory
        inventory_item = self.db.execute_query(
            '''SELECT item_id, item_name, quantity, item_type, description, value
               FROM inventory 
               WHERE owner_id = ? AND LOWER(item_name) LIKE LOWER(?) AND quantity >= ?''',
            (interaction.user.id, f"%{item_name}%", quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.response.send_message(f"You don't have enough '{item_name}' to drop.", ephemeral=True)
            return
        
        inv_id, actual_name, current_qty, item_type, description, value = inventory_item
        
        # Remove from inventory
        if current_qty == quantity:
            self.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (inv_id,))
        else:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                (quantity, inv_id)
            )
        
        # Add to location items
        self.db.execute_query(
            '''INSERT INTO location_items 
               (location_id, item_name, item_type, quantity, description, value, dropped_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (current_location, actual_name, item_type, quantity, description, value, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="📦 Item Dropped",
            description=f"Dropped {quantity}x **{actual_name}** at this location",
            color=0x8B4513
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character_group.command(name="pickup", description="Pick up an item from your current location")
    @app_commands.describe(item_name="Name of the item to pick up")
    async def pickup_item(self, interaction: discord.Interaction, item_name: str):
        # Get character info
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[0]:
            await interaction.response.send_message("You cannot pick up items while in transit!", ephemeral=True)
            return
        
        current_location = char_info[0]
        
        # Find item at location
        location_item = self.db.execute_query(
            '''SELECT item_id, item_name, item_type, quantity, description, value
               FROM location_items 
               WHERE location_id = ? AND LOWER(item_name) LIKE LOWER(?)
               ORDER BY dropped_at ASC LIMIT 1''',
            (current_location, f"%{item_name}%"),
            fetch='one'
        )
        
        if not location_item:
            await interaction.response.send_message(f"No '{item_name}' found at this location.", ephemeral=True)
            return
        
        item_id, actual_name, item_type, quantity, description, value = location_item
        
        # Remove from location
        self.db.execute_query("DELETE FROM location_items WHERE item_id = ?", (item_id,))
        
        # Add to inventory
        existing_item = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, actual_name),
            fetch='one'
        )
        
        if existing_item:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
                (quantity, existing_item[0])
            )
        else:
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, actual_name, item_type, quantity, description, value)
            )
        
        embed = discord.Embed(
            title="📦 Item Picked Up",
            description=f"Picked up {quantity}x **{actual_name}**",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="skills", description="View and manage your character skills")
    async def view_skills(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            '''SELECT name, level, experience, skill_points, engineering, navigation, 
                      combat, medical
               FROM characters WHERE user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        name, level, exp, skill_points, eng, nav, combat, medical = char_data
        
        # Calculate experience needed for next level
        exp_needed = self._calculate_exp_for_level(level + 1)
        exp_current_level = self._calculate_exp_for_level(level)
        exp_progress = exp - exp_current_level
        exp_to_next = exp_needed - exp
        
        embed = discord.Embed(
            title=f"📊 {name} - Character Skills",
            description=f"Level {level} Character",
            color=0x4169e1
        )
        
        # Level and experience info
        progress_bar = self._create_progress_bar(exp_progress, exp_needed - exp_current_level)
        embed.add_field(
            name="📈 Level Progress",
            value=f"Level {level} ({exp:,} EXP)\n{progress_bar}\n{exp_to_next:,} EXP to level {level + 1}",
            inline=False
        )
        
        # Skills display
        skills_text = []
        skills = [
            ("🔧 Engineering", eng, "Ship repairs, system efficiency"),
            ("🧭 Navigation", nav, "Travel time, route finding"), 
            ("⚔️ Combat", combat, "Attack power, damage resistance"),
            ("⚕️ Medical", medical, "Healing, radiation treatment")
        ]
        
        for skill_name, skill_value, skill_desc in skills:
            skill_tier = self._get_skill_tier(skill_value)
            skills_text.append(f"{skill_name}: **{skill_value}** {skill_tier}")
            skills_text.append(f"  _{skill_desc}_")
        
        embed.add_field(
            name="🎯 Skills",
            value="\n".join(skills_text),
            inline=False
        )
        
        if skill_points > 0:
            embed.add_field(
                name="💡 Available Skill Points",
                value=f"You have **{skill_points}** unspent skill points!",
                inline=False
            )
            
            view = SkillUpgradeView(self.bot, interaction.user.id, skill_points)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    def _calculate_exp_for_level(self, level):
        """Calculate total experience needed for a given level"""
        if level <= 1:
            return 0
        return int(100 * (level - 1) * (1 + (level - 1) * 0.1))

    def _create_progress_bar(self, current, total, length=10):
        """Create a visual progress bar"""
        if total == 0:
            filled = length
        else:
            filled = int((current / total) * length)
        
        bar = "🟩" * filled + "⬜" * (length - filled)
        percentage = (current / total * 100) if total > 0 else 100
        return f"{bar} {percentage:.1f}%"

    def _get_skill_tier(self, skill_value):
        """Get skill tier description"""
        if skill_value >= 50:
            return "(Master)"
        elif skill_value >= 35:
            return "(Expert)"
        elif skill_value >= 25:
            return "(Advanced)"
        elif skill_value >= 15:
            return "(Skilled)"
        elif skill_value >= 10:
            return "(Competent)"
        else:
            return "(Novice)"

    async def level_up_check(self, user_id: int):
        """Check if character should level up and handle the process"""
        char_data = self.db.execute_query(
            "SELECT level, experience FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return False
        
        current_level, current_exp = char_data
        
        while True:
            exp_needed = self._calculate_exp_for_level(current_level + 1)
            
            if current_exp >= exp_needed:
                # Level up!
                current_level += 1
                skill_points_gained = 2  # 2 skill points per level
                
                self.db.execute_query(
                    "UPDATE characters SET level = ?, skill_points = skill_points + ? WHERE user_id = ?",
                    (current_level, skill_points_gained, user_id)
                )
                
                # Notify user
                # Notify user in their location channel
                user = self.bot.get_user(user_id)
                if user:
                    try:
                        # Get user's current location
                        user_location = self.db.execute_query(
                            "SELECT current_location FROM characters WHERE user_id = ?",
                            (user_id,),
                            fetch='one'
                        )
                        
                        if user_location and user_location[0]:
                            location_channel_id = self.db.execute_query(
                                "SELECT channel_id FROM locations WHERE location_id = ?",
                                (user_location[0],),
                                fetch='one'
                            )
                            
                            if location_channel_id and location_channel_id[0]:
                                location_channel = None
                                for guild in self.bot.guilds:
                                    location_channel = guild.get_channel(location_channel_id[0])
                                    if location_channel:
                                        break
                                
                                if location_channel:
                                    embed = discord.Embed(
                                        title="🎉 LEVEL UP!",
                                        description=f"Congratulations! You've reached level {current_level}!",
                                        color=0xffd700
                                    )
                                    embed.add_field(name="Rewards", value=f"• +{skill_points_gained} skill points\n• +10 max HP", inline=False)
                                    embed.add_field(name="💡 Tip", value="Use `/character skills` to spend your skill points!", inline=False)
                                    
                                    await location_channel.send(f"{user.mention}", embed=embed)
                    except Exception as e:
                        print(f"Failed to send level up notification to location channel: {e}")
                
                # Increase max HP
                self.db.execute_query(
                    "UPDATE characters SET max_hp = max_hp + 10, hp = hp + 10 WHERE user_id = ?",
                    (user_id,)
                )
                
            else:
                break
        
        return True

    @character_group.command(name="train", description="Train skills at certain locations")
    @app_commands.describe(skill="Skill to train")
    @app_commands.choices(skill=[
        app_commands.Choice(name="Engineering", value="engineering"),
        app_commands.Choice(name="Navigation", value="navigation"),
        app_commands.Choice(name="Combat", value="combat"),
        app_commands.Choice(name="Medical", value="medical")
    ])
    async def train_skill(self, interaction: discord.Interaction, skill: str):
        # Check location capabilities
        char_location = self.db.execute_query(
            '''SELECT l.name, l.location_type, l.wealth_level, l.has_medical
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character or location not found!", ephemeral=True)
            return
        
        location_name, location_type, wealth, has_medical = char_location
        
        # Check if location supports training
        training_available = {
            'engineering': location_type in ['space_station', 'colony'] and wealth >= 5,
            'navigation': location_type in ['space_station', 'gate'] and wealth >= 4,
            'combat': location_type in ['space_station'] and wealth >= 6,
            'medical': has_medical and wealth >= 5
        }
        
        if not training_available.get(skill, False):
            await interaction.response.send_message(
                f"{location_name} doesn't offer {skill} training. Try a different location or skill.",
                ephemeral=True
            )
            return
        
        # Get character info
        char_info = self.db.execute_query(
            f"SELECT money, {skill} FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        money, current_skill = char_info
        
        # Calculate training cost (more expensive for higher skills)
        base_cost = 200
        skill_multiplier = 1 + (current_skill * 0.1)
        training_cost = int(base_cost * skill_multiplier)
        
        if money < training_cost:
            await interaction.response.send_message(
                f"Training costs {training_cost:,} credits. You only have {money:,}.",
                ephemeral=True
            )
            return
        
        # Training success chance based on location wealth
        success_chance = 0.6 + (wealth * 0.05)  # 60% base + 5% per wealth level
        
        view = TrainingConfirmView(self.bot, interaction.user.id, skill, training_cost, success_chance)
        
        embed = discord.Embed(
            title=f"🎓 {skill.title()} Training Available",
            description=f"Train your {skill} skill at {location_name}",
            color=0x4169e1
        )
        
        embed.add_field(name="Current Skill Level", value=str(current_skill), inline=True)
        embed.add_field(name="Training Cost", value=f"{training_cost:,} credits", inline=True)
        embed.add_field(name="Success Chance", value=f"{int(success_chance * 100)}%", inline=True)
        
        embed.add_field(
            name="Training Benefits",
            value=f"• +1 to {skill} skill on success\n• Experience points\n• Potential for breakthrough (+2 skill)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    # Add admin command for emergency revival
    @character_group.command(name="admin_revive", description="Admin: Revive a dead player or restore HP")
    @app_commands.describe(
        target_user="User to revive",
        hp_amount="HP to restore (default: full heal)"
    )
    async def admin_revive(self, interaction: discord.Interaction, target_user: discord.Member, hp_amount: int = 100):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        char_data = self.db.execute_query(
            "SELECT name, hp, max_hp FROM characters WHERE user_id = ?",
            (target_user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(f"{target_user.mention} does not have a character.", ephemeral=True)
            return
        
        char_name, current_hp, max_hp = char_data
        
        # Restore HP
        new_hp = min(hp_amount, max_hp)
        self.db.execute_query(
            "UPDATE characters SET hp = ? WHERE user_id = ?",
            (new_hp, target_user.id)
        )
        
        embed = discord.Embed(
            title="⚕️ Administrative Healing",
            description=f"**{char_name}** has been healed by an administrator.",
            color=0x00ff00
        )
        
        embed.add_field(name="HP Restored", value=f"{current_hp} → {new_hp}", inline=True)
        embed.add_field(name="Healed By", value=interaction.user.mention, inline=True)
        
        # Notify the player
        try:
            await target_user.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class SkillUpgradeView(discord.ui.View):
    def __init__(self, bot, user_id: int, skill_points: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.skill_points = skill_points
    
    @discord.ui.button(label="Engineering", style=discord.ButtonStyle.secondary, emoji="🔧")
    async def upgrade_engineering(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "engineering")
    
    @discord.ui.button(label="Navigation", style=discord.ButtonStyle.secondary, emoji="🧭")
    async def upgrade_navigation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "navigation")
    
    @discord.ui.button(label="Combat", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def upgrade_combat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "combat")
    
    @discord.ui.button(label="Medical", style=discord.ButtonStyle.secondary, emoji="⚕️")
    async def upgrade_medical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "medical")
    
    async def _upgrade_skill(self, interaction: discord.Interaction, skill: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your skill panel!", ephemeral=True)
            return
        
        # Check skill points
        current_points = self.bot.db.execute_query(
            "SELECT skill_points FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if current_points < 1:
            await interaction.response.send_message("No skill points available!", ephemeral=True)
            return
        
        # Upgrade skill
        self.bot.db.execute_query(
            f"UPDATE characters SET {skill} = {skill} + 1, skill_points = skill_points - 1 WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        # Get new skill level
        new_skill = self.bot.db.execute_query(
            f"SELECT {skill} FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="✅ Skill Upgraded",
            description=f"Your {skill} skill has been upgraded to level {new_skill}!",
            color=0x00ff00
        )
        
        embed.add_field(name="Skill Points Remaining", value=str(current_points - 1), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class TrainingConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, skill: str, cost: int, success_chance: float):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.skill = skill
        self.cost = cost
        self.success_chance = success_chance
    
    @discord.ui.button(label="Begin Training", style=discord.ButtonStyle.primary, emoji="🎓")
    async def begin_training(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your training session!", ephemeral=True)
            return
        
        # Deduct cost
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.cost, interaction.user.id)
        )
        
        # Roll for success
        import random
        roll = random.random()
        
        if roll < self.success_chance:
            # Success!
            skill_gain = 2 if roll < 0.1 else 1  # 10% chance for breakthrough (+2 skill)
            exp_gain = random.randint(15, 30)
            
            self.bot.db.execute_query(
                f"UPDATE characters SET {self.skill} = {self.skill} + ?, experience = experience + ? WHERE user_id = ?",
                (skill_gain, exp_gain, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="🎉 Training Successful!",
                description=f"Your {self.skill} training was successful!",
                color=0x00ff00
            )
            embed.add_field(name="Skill Gained", value=f"+{skill_gain} {self.skill}", inline=True)
            embed.add_field(name="Experience Gained", value=f"+{exp_gain} EXP", inline=True)
            
            if skill_gain == 2:
                embed.add_field(name="🌟 Breakthrough!", value="Exceptional progress made!", inline=False)
            
            # Check for level up
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.level_up_check(interaction.user.id)
        
        else:
            # Failure
            exp_gain = random.randint(5, 10)  # Small consolation experience
            
            self.bot.db.execute_query(
                "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                (exp_gain, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="❌ Training Failed",
                description=f"The {self.skill} training session didn't go as planned.",
                color=0xff4500
            )
            embed.add_field(name="Experience Gained", value=f"+{exp_gain} EXP", inline=True)
            embed.add_field(name="💡 Try Again", value="Training can be repeated for another chance.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_training(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your training session!", ephemeral=True)
            return
        
        await interaction.response.send_message("Training cancelled.", ephemeral=True)


class IDScrubView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
    
    @discord.ui.button(label="Scrub Identity Records", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def scrub_identity(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your ID panel!", ephemeral=True)
            return
        
        # Check if character has enough money (expensive service)
        char_money = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_money or char_money[0] < 15000:
            await interaction.response.send_message(
                "Identity scrubbing costs 15,000 credits. You don't have enough money!",
                ephemeral=True
            )
            return
        
        # Deduct money and scrub identity
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - 15000 WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        self.bot.db.execute_query(
            "UPDATE character_identity SET id_scrubbed = 1, scrubbed_at = datetime('now') WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        embed = discord.Embed(
            title="🗑️ Identity Scrubbed",
            description="Your identity records have been permanently scrubbed from official databases.",
            color=0x888888
        )
        
        embed.add_field(
            name="💰 Cost",
            value="15,000 credits deducted",
            inline=True
        )
        
        embed.add_field(
            name="🔒 Effect",
            value="Other players will see an error when viewing your ID",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _execute_undock(self, interaction: discord.Interaction, user_id: int):
        """Execute the actual undocking process after job confirmation"""
        # Cancel any active jobs first
        self.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = ?",
            (user_id,)
        )
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = ?",
            (user_id,)
        )
        
        char_data = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, location_status = char_data
        
        if not current_location:
            await interaction.response.send_message("You're in deep space!", ephemeral=True)
            return
        
        if location_status == "in_space":
            await interaction.response.send_message("You're already in space near this location!", ephemeral=True)
            return
        
        # Undock the ship
        self.db.execute_query(
            "UPDATE characters SET location_status = 'in_space' WHERE user_id = ?",
            (user_id,)
        )
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="🚀 Ship Undocked (Jobs Cancelled)",
            description=f"Your ship is now in space near **{location_name}**. All active jobs have been cancelled.",
            color=0x4169e1
        )
        
        embed.add_field(
            name="Status Change",
            value="• You can now engage in ship combat\n• Limited access to location services\n• Full radio range available\n• All stationary jobs cancelled",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class UndockJobConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
    
    @discord.ui.button(label="Confirm Undock", style=discord.ButtonStyle.danger, emoji="🚀")
    async def confirm_undock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Cancel active jobs
        active_jobs = self.bot.db.execute_query(
            '''SELECT j.job_id FROM jobs j 
               JOIN job_tracking jt ON j.job_id = jt.job_id
               WHERE j.taken_by = ? AND j.job_status = 'active' AND jt.start_location = ?''',
            (self.user_id, self.location_id),
            fetch='all'
        )
        
        for job_data in active_jobs:
            job_id = job_data[0]
            self.bot.db.execute_query(
                "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE job_id = ?",
                (job_id,)
            )
            self.bot.db.execute_query(
                "DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?",
                (job_id, self.user_id)
            )
        
        # Now execute the actual undock
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog._execute_undock(interaction, self.user_id)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_undock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Undocking cancelled.", ephemeral=True)

class CharacterPanelView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        
        # Check for active job and add job button if needed
        self._add_job_button_if_needed()
    
    def _check_job_status(self):
        """Check if user has active job and if it's ready for completion"""
        # Get active job info
        job_info = self.bot.db.execute_query(
            '''SELECT j.job_id, j.title, j.description, j.reward_money, j.taken_at, j.duration_minutes,
                      j.danger_level, l.name as location_name, j.job_status
               FROM jobs j
               JOIN locations l ON j.location_id = l.location_id
               WHERE j.taken_by = ? AND j.is_taken = 1''',
            (self.user_id,),
            fetch='one'
        )
        
        if not job_info:
            return None, False  # No active job
        
        job_id, title, description, reward, taken_at, duration_minutes, danger, location_name, job_status = job_info
        
        # Check if job is ready for completion
        is_ready = False
        
        # Check for transport job finalization
        if job_status == 'awaiting_finalization':
            is_ready = True
        else:
            # Determine if this is a transport job
            title_lower = title.lower()
            desc_lower = description.lower()
            is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                              any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
            
            if is_transport_job:
                # For transport jobs, check elapsed time
                from datetime import datetime
                taken_time = datetime.fromisoformat(taken_at)
                current_time = datetime.utcnow()
                elapsed_minutes = (current_time - taken_time).total_seconds() / 60
                is_ready = elapsed_minutes >= duration_minutes
            else:
                # For stationary jobs, check location tracking
                tracking = self.bot.db.execute_query(
                    "SELECT time_at_location, required_duration FROM job_tracking WHERE job_id = ? AND user_id = ?",
                    (job_id, self.user_id),
                    fetch='one'
                )
                
                if tracking:
                    time_at_location, required_duration = tracking
                    time_at_location = float(time_at_location) if time_at_location else 0.0
                    required_duration = float(required_duration) if required_duration else 1.0
                    is_ready = time_at_location >= required_duration
        
        return job_info, is_ready
    
    def _add_job_button_if_needed(self):
        """Add job button if user has an active job"""
        job_info, is_ready = self._check_job_status()
        
        if job_info:
            # User has an active job, add the appropriate button
            if is_ready:
                job_button = discord.ui.Button(
                    label="Complete Job",
                    style=discord.ButtonStyle.success,
                    emoji="✅"
                )
                job_button.callback = self.complete_job
            else:
                job_button = discord.ui.Button(
                    label="Job Status",
                    style=discord.ButtonStyle.primary,
                    emoji="💼"
                )
                job_button.callback = self.view_job_status
            
            self.add_item(job_button)
    
    async def complete_job(self, interaction: discord.Interaction):
        """Handle job completion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get the EconomyCog and call its job completion logic
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            await econ_cog.job_complete.callback(econ_cog, interaction)
        else:
            await interaction.response.send_message("Job system is currently unavailable.", ephemeral=True)
    
    async def view_job_status(self, interaction: discord.Interaction):
        """Handle viewing job status"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Force a manual update first (same as job_status command)
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            await econ_cog._manual_job_update(interaction.user.id)
        
        # Get job info (same logic as job_status command)
        job_info = self.bot.db.execute_query(
            '''SELECT j.job_id, j.title, j.description, j.reward_money, j.taken_at, j.duration_minutes,
                      j.danger_level, l.name as location_name, j.job_status
               FROM jobs j
               JOIN locations l ON j.location_id = l.location_id
               WHERE j.taken_by = ? AND j.is_taken = 1''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("You don't have any active jobs.", ephemeral=True)
            return

        job_id, title, description, reward, taken_at, duration_minutes, danger, location_name, job_status = job_info

        # Determine job type
        title_lower = title.lower()
        desc_lower = description.lower()
        is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])

        from datetime import datetime
        taken_time = datetime.fromisoformat(taken_at)
        current_time = datetime.utcnow()
        elapsed_minutes = (current_time - taken_time).total_seconds() / 60

        # Truncate description to prevent Discord limit issues
        truncated_description = description[:800] + "..." if len(description) > 800 else description
        
        embed = discord.Embed(
            title="💼 Current Job Status",
            description=f"**{title}**\n{truncated_description}",
            color=0x4169E1
        )

        # Status based on job type and current state
        if job_status == 'awaiting_finalization':
            status_text = "🚛 **Unloading cargo** - Use `/job complete` to finalize immediately"
            progress_text = "✅ Transport completed, finalizing delivery..."
        elif job_status == 'completed':
            status_text = "✅ **Completed** - Job finished!"
            progress_text = "Job has been completed successfully"
        elif is_transport_job:
            if elapsed_minutes >= duration_minutes:
                status_text = "✅ **Ready for completion** - Use `/job complete`"
                progress_text = "Minimum travel time completed"
            else:
                remaining_minutes = duration_minutes - elapsed_minutes
                status_text = f"⏳ **In Transit** - {remaining_minutes:.1f} minutes remaining"
                progress_pct = (elapsed_minutes / duration_minutes) * 100
                bars = int(progress_pct // 10)
                progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
        else:
            # Stationary job - check tracking
            tracking = self.bot.db.execute_query(
                "SELECT time_at_location, required_duration FROM job_tracking WHERE job_id = ? AND user_id = ?",
                (job_id, interaction.user.id),
                fetch='one'
            )
            
            if tracking:
                time_at_location, required_duration = tracking
                time_at_location = float(time_at_location) if time_at_location else 0.0
                required_duration = float(required_duration) if required_duration else 1.0
                
                if time_at_location >= required_duration:
                    status_text = "✅ **Ready for completion** - Use `/job complete`"
                    progress_text = "Required time at location completed"
                else:
                    remaining = max(0, required_duration - time_at_location)
                    status_text = f"📍 **Working on-site** - {remaining:.1f} minutes remaining"
                    progress_pct = min(100, (time_at_location / required_duration) * 100)
                    bars = int(progress_pct // 10)
                    progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
            else:
                status_text = "📍 **Needs location tracking** - Use `/job complete` to start"
                progress_text = "Location-based work not yet started"

        # Truncate field values to stay under Discord's 1024 character limit
        status_text = status_text[:1020] + "..." if len(status_text) > 1020 else status_text
        progress_text = progress_text[:1020] + "..." if len(progress_text) > 1020 else progress_text

        embed.add_field(name="Status", value=status_text, inline=False)
        embed.add_field(name="Progress", value=progress_text, inline=False)
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger if danger > 0 else "Safe", inline=True)
        embed.add_field(name="Location", value=location_name[:1020] if len(location_name) > 1020 else location_name, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Character Info", style=discord.ButtonStyle.primary, emoji="👤")
    async def view_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing character view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_character.callback(char_cog, interaction)
    
    @discord.ui.button(label="Ship Status", style=discord.ButtonStyle.secondary, emoji="🚀")
    async def view_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing ship view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_ship.callback(char_cog, interaction)
    
    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.success, emoji="🎒")
    async def view_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing inventory view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_inventory.callback(char_cog, interaction)
    
    @discord.ui.button(label="Skills", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_skills(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing skills view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_skills.callback(char_cog, interaction)
        
async def setup(bot):
    await bot.add_cog(CharacterCog(bot))