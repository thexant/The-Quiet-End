# cogs/admin.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import io
import zipfile
import re
from datetime import datetime
import asyncio
import math
from discord.app_commands import Choice
from typing import Optional, List



class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    admin_group = app_commands.Group(name="admin", description="Administrative commands")
    
    
    @admin_group.command(name="afk", description="Trigger AFK warning for a player")
    @app_commands.describe(player="Player to send AFK warning to")
    async def admin_afk_warning(self, interaction: discord.Interaction, player: discord.Member):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Check if player has a character and is logged in
        char_info = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
            return
        
        char_name, is_logged_in = char_info
        
        if not is_logged_in:
            await interaction.response.send_message(f"**{char_name}** is not currently logged in.", ephemeral=True)
            return
        
        # Check if player already has an active AFK warning
        existing_warning = self.db.execute_query(
            "SELECT warning_id FROM afk_warnings WHERE user_id = %s AND is_active = true",
            (player.id,),
            fetch='one'
        )
        
        if existing_warning:
            await interaction.response.send_message(f"**{char_name}** already has an active AFK warning.", ephemeral=True)
            return
        
        # Get the activity tracker and start AFK warning process
        if hasattr(self.bot, 'activity_tracker'):
            # Import here to avoid circular imports
            import asyncio
            
            # Start the AFK warning process (same as automatic system)
            warning_task = asyncio.create_task(
                self.bot.activity_tracker._start_afk_warning(player.id, char_name)
            )
            
            # Store the task in the activity tracker
            self.bot.activity_tracker.warning_tasks[player.id] = warning_task
            
            embed = discord.Embed(
                title="⚠️ AFK Warning Sent",
                description=f"AFK warning sent to **{char_name}**.",
                color=0xff9900
            )
            embed.add_field(name="Player", value=player.mention, inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            embed.add_field(name="Status", value="Player has 10 minutes to respond", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            print(f"⚠️ Admin AFK warning: {char_name} ({player.id}) warned by {interaction.user.name}")
        else:
            await interaction.response.send_message("Activity tracker not found. Please try again.", ephemeral=True)
            
    @admin_group.command(name="setup", description="Initial server setup and configuration")
    async def setup_server(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.send_message("🔧 Starting server setup...", ephemeral=True)
        
        # Check if setup already completed
        existing_config = self.db.execute_query(
            "SELECT setup_completed FROM server_config WHERE guild_id = %s",
            (interaction.guild.id,),
            fetch='one'
        )
        
        if existing_config and existing_config[0]:
            # Setup already done, show current config
            await self._show_current_config(interaction)
            return
        
        try:
            # Find existing main GALAXY category first (created by auto-setup or previous runs)
            main_galaxy_category = None
            main_category_name = " ==== 🌌 GALAXY 🌌 ==== "
            
            # Search for existing category
            for category in interaction.guild.categories:
                if category.name.strip() == main_category_name.strip():
                    main_galaxy_category = category
                    break
            
            if main_galaxy_category:
                created_categories = [f"✅ Found existing main: {main_category_name}"]
                print(f"Found existing main galaxy category: {main_galaxy_category.id}")
            else:
                try:
                    main_galaxy_category = await interaction.guild.create_category(
                        main_category_name,
                        reason="Setup - main galaxy category"
                    )
                    created_categories = [f"🆕 Created main: {main_category_name}"]
                    print(f"Created new main galaxy category: {main_galaxy_category.id}")
                except Exception as e:
                    await interaction.edit_original_response(content=f"❌ Failed to create main galaxy category: {e}")
                    return
            
            # Find or create galactic news channel in the main galaxy category
            news_channel = None
            news_channel_name = "📡-galactic-news"
            
            # First check database for existing configured channel
            existing_news_config = self.db.execute_query(
                "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = %s",
                (interaction.guild.id,),
                fetch='one'
            )
            
            if existing_news_config and existing_news_config[0]:
                news_channel = interaction.guild.get_channel(existing_news_config[0])
                if news_channel:
                    created_categories.append(f"✅ Found configured news channel: {news_channel_name}")
                    print(f"Found existing configured news channel: {news_channel.id}")
            
            # If no configured channel found, look for one in the main category
            if not news_channel:
                for channel in main_galaxy_category.text_channels:
                    if channel.name == news_channel_name:
                        news_channel = channel
                        created_categories.append(f"✅ Found existing news channel: {news_channel_name}")
                        print(f"Found existing news channel in category: {news_channel.id}")
                        
                        # Update database to point to this existing channel
                        self.db.execute_query(
                            "UPDATE server_config SET galactic_updates_channel_id = %s WHERE guild_id = %s",
                            (news_channel.id, interaction.guild.id)
                        )
                        break
            
            # If still no news channel, create one
            if not news_channel:
                try:
                    news_channel = await main_galaxy_category.create_text_channel(
                        news_channel_name,
                        topic="INFORMATION SYSTEM UPLINK",
                        reason="CONNECTING TO GNN DATA SERVERS..."
                    )
                    created_categories.append(f"🆕 Created news channel: {news_channel_name}")
                    print(f"Created new news channel: {news_channel.id}")
                    
                    # Send welcome message to newly created channel
                    welcome_embed = discord.Embed(
                        title="📡 Data Uplink Started...",
                        description="Establishing Connection..",
                        color=0x4169E1
                    )
                    welcome_embed.add_field(
                        name="⏰ Transmission Delays",
                        value="Delays in information transmissions may be experienced.",
                        inline=False
                    )
                    welcome_embed.set_footer(text="Stay informed, stay alive. - Galactic News Network")
                    
                    try:
                        await news_channel.send(embed=welcome_embed)
                    except:
                        pass  # Don't fail setup if we can't send the welcome message
                        
                except Exception as e:
                    created_categories.append(f"❌ Failed to create news channel: {e}")
            
            status_voice_channel = None
            status_channel_name = f"🌐| INITIALIZING..."

            # First check database for existing configured channel
            existing_status_config = self.db.execute_query(
                "SELECT status_voice_channel_id FROM server_config WHERE guild_id = %s",
                (interaction.guild.id,),
                fetch='one'
            )

            if existing_status_config and existing_status_config[0]:
                status_voice_channel = interaction.guild.get_channel(existing_status_config[0])
                if status_voice_channel:
                    created_categories.append(f"✅ Found configured status channel")
                    print(f"Found existing configured status voice channel: {status_voice_channel.id}")

            # If no configured channel found, look for one in the main category
            if not status_voice_channel:
                for channel in main_galaxy_category.voice_channels:
                    if channel.name.startswith("🌐|"):
                        status_voice_channel = channel
                        created_categories.append(f"✅ Found existing status channel")
                        print(f"Found existing status voice channel in category: {status_voice_channel.id}")
                        break

            # If still no status channel, create one
            if not status_voice_channel:
                try:
                    # Set permissions to deny connection for non-admins
                    overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(connect=False),
                    }
                    
                    status_voice_channel = await main_galaxy_category.create_voice_channel(
                        status_channel_name,
                        overwrites=overwrites,
                        reason="RPG Bot setup - status voice channel"
                    )
                    created_categories.append(f"🆕 Created status voice channel")
                    print(f"Created new status voice channel: {status_voice_channel.id}")
                    
                except Exception as e:
                    created_categories.append(f"❌ Failed to create status voice channel: {e}")
            
            # Immediately save news channel configuration if we created or found one
            if news_channel:
                existing_config = self.db.execute_query(
                    "SELECT guild_id FROM server_config WHERE guild_id = %s",
                    (interaction.guild.id,),
                    fetch='one'
                )
                
                if existing_config:
                    self.db.execute_query(
                        "UPDATE server_config SET galactic_updates_channel_id = %s WHERE guild_id = %s",
                        (news_channel.id, interaction.guild.id)
                    )
                else:
                    self.db.execute_query(
                        "INSERT INTO server_config (guild_id, galactic_updates_channel_id) VALUES (%s, %s)",
                        (interaction.guild.id, news_channel.id)
                    )
                
                print(f"📰 Early configuration save: galactic news channel {news_channel.id}")      
            # Create location categories as children of the main galaxy category
            categories = {}
            category_names = {
                'colony': '🏭 COLONIES',
                'station': '🛰️ SPACE STATIONS', 
                'outpost': '🛤️ OUTPOSTS',
                'gate': '🚪 GATES',
                'transit': '🚀 IN TRANSIT',
                'ship_interiors': '🚀 SHIP INTERIORS',
                'residences': '🏠 RESIDENCES'
            }
            
            for cat_type, cat_name in category_names.items():
                # Check if category already exists
                existing_cat = None
                for category in interaction.guild.categories:
                    if category.name.strip() == cat_name.strip():
                        existing_cat = category
                        break
                
                if existing_cat:
                    categories[cat_type] = existing_cat.id
                    created_categories.append(f"✅ Found existing: {cat_name}")
                    
                    # Move to be under main galaxy category if not already
                    if existing_cat.position <= main_galaxy_category.position:
                        try:
                            await existing_cat.edit(position=main_galaxy_category.position + 1)
                            created_categories.append(f"📍 Repositioned: {cat_name}")
                        except:
                            pass  # Ignore if we can't reposition
                else:
                    try:
                        new_category = await interaction.guild.create_category(
                            cat_name,
                            position=main_galaxy_category.position + len(categories) + 1,
                            reason="RPG Bot setup - location categories"
                        )
                        categories[cat_type] = new_category.id
                        created_categories.append(f"🆕 Created: {cat_name}")
                    except Exception as e:
                        created_categories.append(f"❌ Failed to create {cat_name}: {e}")
                        categories[cat_type] = None
            
            self.db.execute_query(
                '''INSERT INTO server_config 
                   (guild_id, colony_category_id, station_category_id, outpost_category_id, 
                    gate_category_id, transit_category_id, ship_interiors_category_id, residences_category_id, galactic_updates_channel_id, 
                    status_voice_channel_id, setup_completed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                   ON CONFLICT (guild_id) DO UPDATE SET
                   colony_category_id = EXCLUDED.colony_category_id,
                   station_category_id = EXCLUDED.station_category_id,
                   outpost_category_id = EXCLUDED.outpost_category_id,
                   gate_category_id = EXCLUDED.gate_category_id,
                   transit_category_id = EXCLUDED.transit_category_id,
                   ship_interiors_category_id = EXCLUDED.ship_interiors_category_id,
                   residences_category_id = EXCLUDED.residences_category_id,
                   galactic_updates_channel_id = EXCLUDED.galactic_updates_channel_id,
                   status_voice_channel_id = EXCLUDED.status_voice_channel_id,
                   setup_completed = EXCLUDED.setup_completed,
                   updated_at = NOW()''',
                (
                    interaction.guild.id, 
                    categories.get('colony'), 
                    categories.get('station'),
                    categories.get('outpost'), 
                    categories.get('gate'), 
                    categories.get('transit'),
                    categories.get('ship_interiors'), 
                    categories.get('residences'), 
                    news_channel.id if news_channel else None,
                    status_voice_channel.id if status_voice_channel else None
                )
            )
            
            # Create setup complete embed
            embed = discord.Embed(
                title="✅ Server Setup Complete!",
                description="Your server has been configured successfully with organized galaxy structure.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="🌌 Galaxy Structure",
                value="\n".join(created_categories),
                inline=False
            )
            
            embed.add_field(
                name="📡 Galactic News",
                value=f"News channel: {news_channel.mention if news_channel else 'Failed to configure'}\nAutomatically configured for galactic updates",
                inline=False
            )
            embed.add_field(
                name="📊 Status Channel",
                value=f"Voice channel: {status_voice_channel.mention if status_voice_channel else 'Failed to configure'}\nAutomatically updates every 10 minutes with live statistics",
                inline=False
            )
            embed.add_field(
                name="⚙️ Settings Applied",
                value="• Max location channels: 50\n• Channel timeout: 48 hours\n• Auto-cleanup: Enabled\n• Setup status: Completed",
                inline=True
            )
            
            embed.add_field(
                name="🚀 Next Steps",
                value="• Use `/galaxy generate` to create your universe\n• Radio system is automatically configured\n• Use `/admin config` to modify settings\n• Players can `/character create` to start playing",
                inline=True
            )
            
            # Check if galaxy exists
            location_count = self.db.execute_query(
                "SELECT COUNT(*) FROM locations",
                fetch='one'
            )[0]
            
            if location_count == 0:
                embed.add_field(
                    name="🌌 Ready for Galaxy Generation",
                    value="Run `/galaxy generate num_locations:100` to create your universe!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🌍 Galaxy Already Exists", 
                    value=f"{location_count} locations ready for exploration",
                    inline=False
                )
            
            await interaction.edit_original_response(content=None, embed=embed)
            
            print(f"✅ Setup completed for {interaction.guild.name} - setup_completed flag set to 1")
            
        except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Setup Failed",
                    description=f"An error occurred during setup: {str(e)}",
                    color=0xff0000
                )
                await interaction.edit_original_response(content=None, embed=error_embed)
    @admin_group.command(name="server_reset", description="Complete server reset - removes ALL bot channels and data")
    async def server_reset(self, interaction: discord.Interaction):
        """Complete server reset including all channels and database"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Show warning with confirmation view
        view = ServerResetConfirmView(self.bot, interaction.user.id)
        
        embed = discord.Embed(
            title="🚨 COMPLETE SERVER RESET",
            description="This will **PERMANENTLY DELETE**:\n\n"
                        "• ALL bot-created channels and categories\n"
                        "• ALL player characters and ships\n"
                        "• ALL locations and corridors\n"
                        "• ALL jobs and inventory\n"
                        "• ALL server configuration\n"
                        "• The entire galaxy and its history\n\n"
                        "**The server will be returned to a fresh install state!**",
            color=0xff0000
        )
        
        embed.add_field(
            name="⚠️ THIS CANNOT BE UNDONE",
            value="All game progress will be lost forever.",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Confirmation Required",
            value="Click the button below to confirm this complete server reset.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    async def _show_current_config(self, interaction: discord.Interaction):
        """Show current server configuration"""
        config = self.db.execute_query(
            '''SELECT colony_category_id, station_category_id, outpost_category_id,
                      gate_category_id, transit_category_id, max_location_channels,
                      channel_timeout_hours, auto_cleanup_enabled
               FROM server_config WHERE guild_id = %s''',
            (interaction.guild.id,),
            fetch='one'
        )
        
        if not config:
            await interaction.edit_original_response(content="No configuration found. Setup will create new config.")
            return
        
        embed = discord.Embed(
            title="⚙️ Current Server Configuration",
            description="Server is already set up. Use `/admin config` to modify settings.",
            color=0x4169E1
        )
        
        # Check category status
        categories = {
            'Colonies': config[0],
            'Space Stations': config[1], 
            'Outposts': config[2],
            'Gates': config[3],
            'Transit': config[4]
        }
        
        category_status = []
        for name, cat_id in categories.items():
            if cat_id:
                category = interaction.guild.get_channel(cat_id)
                if category:
                    category_status.append(f"✅ {name}: {category.name}")
                else:
                    category_status.append(f"❌ {name}: Missing (ID: {cat_id})")
            else:
                category_status.append(f"❓ {name}: Not configured")
        
        embed.add_field(
            name="📁 Categories",
            value="\n".join(category_status),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Channel Settings",
            value=f"• Max channels: {config[5]}\n• Timeout: {config[6]} hours\n• Auto-cleanup: {'Enabled' if config[7] else 'Disabled'}",
            inline=True
        )
        
        try:
            # Get channel statistics
            from utils.channel_manager import ChannelManager
            channel_manager = ChannelManager(self.bot)
            stats = await channel_manager.get_location_statistics(interaction.guild)
            
            embed.add_field(
                name="📊 Current Usage",
                value=f"• Active channels: {stats['active_channels']}/{stats['channel_capacity']}\n• Recently active: {stats['recently_active']}\n• Usage: {stats['capacity_usage']:.1f}%",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="📊 Current Usage",
                value="Unable to retrieve statistics",
                inline=True
            )
        
        embed.add_field(
            name="📊 Current Usage",
            value=f"• Active channels: {stats['active_channels']}/{stats['channel_capacity']}\n• Recently active: {stats['recently_active']}\n• Usage: {stats['capacity_usage']:.1f}%",
            inline=True
        )
        
        await interaction.edit_original_response(content=None, embed=embed)
    @admin_group.command(name="broadcast_news", description="Send a custom news broadcast to all servers")
    @app_commands.describe(
        title="News headline/title",
        description="News content/description",
        location_name="Location name to simulate distance delay (optional - instant if not provided)",
        news_type="Type of news broadcast"
    )
    @app_commands.choices(news_type=[
        app_commands.Choice(name="Earth Government", value="admin_announcement"),
        app_commands.Choice(name="Breaking News", value="major_event"),
        app_commands.Choice(name="General News", value="fluff_news"),
        app_commands.Choice(name="Security Alert", value="pirate_activity"),
        app_commands.Choice(name="Corporate News", value="corporate_news"),
        app_commands.Choice(name="Discovery", value="discovery"),
        app_commands.Choice(name="Economic", value="economic")
    ])
    async def broadcast_custom_news(self, interaction: discord.Interaction, title: str, 
                                   description: str, location_name: str = None, 
                                   news_type: str = "admin_announcement"):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Validate input lengths (Discord's embed limits)
        if len(title) > 256:
            await interaction.followup.send("Title too long (max 256 characters for embed titles).", ephemeral=True)
            return
            
        if len(description) > 4096:
            await interaction.followup.send("Description too long (max 4096 characters for embed descriptions).", ephemeral=True)
            return
        
        location_id = None
        location_display_name = "Galactic Central"
        delay_info = "instant broadcast"
        
        # If location specified, find it and calculate delay
        if location_name:
            location = self.db.execute_query(
                "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
                (f"%{location_name}%",),
                fetch='one'
            )
            
            if not location:
                await interaction.followup.send(f"Location '{location_name}' not found.", ephemeral=True)
                return
                
            location_id, location_display_name = location
            
            # Get the news cog to calculate delay
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                delay_hours = news_cog.calculate_news_delay(location_id)
                if delay_hours > 0:
                    if delay_hours < 1:
                        delay_info = f"~{int(delay_hours * 60)} minute delay"
                    elif delay_hours < 24:
                        delay_info = f"~{delay_hours:.1f} hour delay"
                    else:
                        delay_info = f"~{delay_hours/24:.1f} day delay"
                else:
                    delay_info = "instant broadcast"
        
        # Get galactic news cog
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if not news_cog:
            await interaction.followup.send("Galactic news system not available.", ephemeral=True)
            return
        
        # Get all guilds with galactic updates channels
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        if not guilds_with_updates:
            await interaction.followup.send("No servers have galactic news configured.", ephemeral=True)
            return
        
        # Queue news for all configured guilds
        queued_count = 0
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            await news_cog.queue_news(guild_id, news_type, title, description, location_id)
            queued_count += 1
        
        # Create confirmation embed
        embed = discord.Embed(
            title="📰 News Broadcast Queued",
            description=f"Custom news broadcast has been queued for delivery.",
            color=0x00ff00
        )
        
        embed.add_field(name="📰 Title", value=title, inline=False)
        embed.add_field(name="📝 Preview", value=description[:500] + ("..." if len(description) > 500 else ""), inline=False)
        embed.add_field(name="📍 Source Location", value=location_display_name, inline=True)
        embed.add_field(name="⏰ Delivery", value=delay_info, inline=True)
        embed.add_field(name="🌐 Servers", value=f"{queued_count} server{'s' if queued_count != 1 else ''}", inline=True)
        embed.add_field(name="📡 News Type", value=news_type.replace('_', ' ').title(), inline=True)
        
        embed.set_footer(text=f"Broadcast by {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        print(f"📰 Admin news broadcast: {interaction.user.name} sent '{title}' to {queued_count} servers")

    debug_group = app_commands.Group(name="debug", description="Additional administrative debug commands")
    
    @debug_group.command(name="setmoney", description="Set a player's money to a specific amount")
    @app_commands.describe(
        player="The player whose money to set",
        amount="The amount of money to set"
    )
    async def set_money(self, interaction: discord.Interaction, player: discord.Member, amount: int):
        """Set a player's money to a specific amount"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Check if player has a character
        char_data = self.db.execute_query(
            "SELECT name, money FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                f"{player.mention} doesn't have a character.",
                ephemeral=True
            )
            return
        
        char_name, old_money = char_data
        
        # Validate amount
        if amount < 0:
            await interaction.response.send_message(
                "Money amount cannot be negative.",
                ephemeral=True
            )
            return
        
        # Update the money
        self.db.execute_query(
            "UPDATE characters SET money = %s WHERE user_id = %s",
            (amount, player.id)
        )
        
        # Create confirmation embed
        embed = discord.Embed(
            title="💰 Money Set",
            description=f"Successfully set **{char_name}**'s money.",
            color=0x00ff00
        )
        
        embed.add_field(name="Player", value=player.mention, inline=True)
        embed.add_field(name="Character", value=char_name, inline=True)
        embed.add_field(name="Previous Amount", value=f"{old_money:,} credits", inline=True)
        embed.add_field(name="New Amount", value=f"{amount:,} credits", inline=True)
        embed.add_field(name="Change", value=f"{amount - old_money:+,} credits", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log the action
        print(f"💰 Admin money set: {char_name} ({player.id}) set to {amount} credits by {interaction.user.name}")

    @debug_group.command(name="setxp", description="Set a player's experience to a specific amount")
    @app_commands.describe(
        player="The player whose XP to set",
        amount="The amount of XP to set"
    )
    async def set_xp(self, interaction: discord.Interaction, player: discord.Member, amount: int):
        """Set a player's XP to a specific amount and adjust level accordingly"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Check if player has a character
        char_data = self.db.execute_query(
            "SELECT name, experience, level, skill_points FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                f"{player.mention} doesn't have a character.",
                ephemeral=True
            )
            return
        
        char_name, old_xp, old_level, old_skill_points = char_data
        
        # Validate amount
        if amount < 0:
            await interaction.response.send_message(
                "XP amount cannot be negative.",
                ephemeral=True
            )
            return
        
        # Calculate what level the character should be at with this XP
        new_level = self._calculate_level_from_xp(amount)
        
        # Calculate skill point difference
        # Each level gives 2 skill points, starting from level 1
        # Level 1 = 5 base skill points
        # Level 2 = 5 + 2 = 7 total skill points
        # Level 3 = 5 + 4 = 9 total skill points, etc.
        base_skill_points = 5
        earned_skill_points_old = (old_level - 1) * 2
        earned_skill_points_new = (new_level - 1) * 2
        
        # Calculate how many skill points they should have spent
        total_skill_points_old = base_skill_points + earned_skill_points_old
        spent_skill_points = total_skill_points_old - old_skill_points
        
        # Calculate new available skill points
        total_skill_points_new = base_skill_points + earned_skill_points_new
        new_skill_points = max(0, total_skill_points_new - spent_skill_points)
        
        # Calculate HP changes
        # Base HP is 100, +10 per level after 1
        old_max_hp = 100 + (old_level - 1) * 10
        new_max_hp = 100 + (new_level - 1) * 10
        hp_difference = new_max_hp - old_max_hp
        
        # Update the character
        self.db.execute_query(
            """UPDATE characters 
               SET experience = %s, level = %s, skill_points = %s, 
                   max_hp = max_hp + %s, hp = CASE 
                       WHEN hp + %s > max_hp + %s THEN max_hp + %s
                       WHEN hp + %s < 1 THEN 1
                       ELSE hp + %s
                   END
               WHERE user_id = %s""",
            (amount, new_level, new_skill_points, 
             hp_difference, hp_difference, hp_difference, hp_difference, 
             hp_difference, hp_difference, player.id)
        )
        
        # Get updated HP for display
        updated_hp_data = self.db.execute_query(
            "SELECT hp, max_hp FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        new_hp, new_max_hp_actual = updated_hp_data
        
        # Create confirmation embed
        embed = discord.Embed(
            title="✨ Experience Set",
            description=f"Successfully set **{char_name}**'s experience.",
            color=0x00ff00
        )
        
        embed.add_field(name="Player", value=player.mention, inline=True)
        embed.add_field(name="Character", value=char_name, inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        
        embed.add_field(name="Experience", value=f"{old_xp:,} → {amount:,} XP", inline=True)
        embed.add_field(name="Level", value=f"{old_level} → {new_level}", inline=True)
        embed.add_field(name="Skill Points", value=f"{old_skill_points} → {new_skill_points}", inline=True)
        
        embed.add_field(name="Max HP", value=f"{old_max_hp} → {new_max_hp_actual}", inline=True)
        embed.add_field(name="Current HP", value=f"{new_hp}/{new_max_hp_actual}", inline=True)
        
        # Add level change description
        if new_level > old_level:
            level_change = f"🎉 Leveled up {new_level - old_level} time(s)!"
        elif new_level < old_level:
            level_change = f"📉 Level reduced by {old_level - new_level}"
        else:
            level_change = "↔️ Level unchanged"
        
        embed.add_field(name="Level Change", value=level_change, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log the action
        print(f"✨ Admin XP set: {char_name} ({player.id}) set to {amount} XP (Level {old_level} → {new_level}) by {interaction.user.name}")
        
        def _calculate_level_from_xp(self, total_xp: int) -> int:
            """Calculate what level a character should be based on total XP"""
            level = 1
            
            while True:
                # Calculate XP needed for next level
                xp_for_next_level = self._calculate_exp_for_level(level + 1)
                
                if total_xp < xp_for_next_level:
                    return level
                
                level += 1
                
                # Safety cap at level 100
                if level >= 100:
                    return 100
        
        def _calculate_exp_for_level(self, level):
            """Calculate total experience needed for a given level"""
            if level <= 1:
                return 0
            return int(100 * (level - 1) * (1 + (level - 1) * 0.1))
    
    @admin_group.command(name="fix_item_metadata", description="Fix metadata for items in shops and inventories")
    async def fix_item_metadata(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        from utils.item_config import ItemConfig
        import json
        
        # Fix shop items first
        shop_items = self.db.execute_query(
            "SELECT item_id, item_name, metadata FROM shop_items",
            fetch='all'
        )
        
        shop_fixed = 0
        for item_id, item_name, current_metadata in shop_items:
            if not current_metadata or current_metadata == '{}' or current_metadata == '':
                item_def = ItemConfig.get_item_definition(item_name)
                if item_def:
                    new_metadata = ItemConfig.create_item_metadata(item_name)
                    self.db.execute_query(
                        "UPDATE shop_items SET metadata = %s WHERE item_id = %s",
                        (new_metadata, item_id)
                    )
                    shop_fixed += 1
        
        # Fix inventory items
        inv_items = self.db.execute_query(
            "SELECT item_id, item_name, metadata FROM inventory",
            fetch='all'
        )
        
        inv_fixed = 0
        for item_id, item_name, current_metadata in inv_items:
            if not current_metadata or current_metadata == '{}' or current_metadata == '':
                item_def = ItemConfig.get_item_definition(item_name)
                if item_def:
                    new_metadata = ItemConfig.create_item_metadata(item_name)
                    self.db.execute_query(
                        "UPDATE inventory SET metadata = %s WHERE item_id = %s",
                        (new_metadata, item_id)
                    )
                    inv_fixed += 1
        
        embed = discord.Embed(
            title="✅ Metadata Fix Complete",
            description="Fixed missing metadata for items",
            color=0x00ff00
        )
        embed.add_field(name="Shop Items Fixed", value=str(shop_fixed), inline=True)
        embed.add_field(name="Inventory Items Fixed", value=str(inv_fixed), inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @admin_group.command(name="teleport", description="Teleport a character to a different location")
    @app_commands.describe(
        player="Player to teleport",
        destination="Destination location name"
    )
    async def teleport_character(self, interaction: discord.Interaction, player: discord.Member, destination: str):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Check if player has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
            return
        
        current_location_id, char_name = char_info
        
        # Find destination location - prioritize exact matches
        # First try exact match
        dest_location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) = LOWER(%s)",
            (destination,),
            fetch='one'
        )
        
        # If no exact match, try partial match as fallback
        if not dest_location:
            dest_location = self.db.execute_query(
                "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
                (f"%{destination}%",),
                fetch='one'
            )
        
        if not dest_location:
            await interaction.response.send_message(f"Location '{destination}' not found.", ephemeral=True)
            return
        
        dest_location_id, dest_name = dest_location
        
        if current_location_id == dest_location_id:
            await interaction.response.send_message(f"{player.mention} is already at {dest_name}.", ephemeral=True)
            return
        
        # Get current location name for logging
        current_location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (current_location_id,),
            fetch='one'
        )[0] if current_location_id else "Unknown"
        
        # Cancel any active travel
        self.db.execute_query(
            "UPDATE travel_sessions SET status = 'admin_teleport' WHERE user_id = %s AND status = 'traveling'",
            (player.id,)
        )
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_location = %s WHERE user_id = %s",
            (dest_location_id, player.id)
        )
        
        # Update channel access using channel manager
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Remove access from old location
        if current_location_id:
            await channel_manager.remove_user_location_access(player, current_location_id)
        
        # Give access to new location
        success = await channel_manager.give_user_location_access(player, dest_location_id)
        
        embed = discord.Embed(
            title="🌀 Character Teleported",
            description=f"**{char_name}** has been teleported by an administrator.",
            color=0x800080
        )
        
        embed.add_field(name="From", value=current_location_name, inline=True)
        embed.add_field(name="To", value=dest_name, inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        
        if success:
            embed.add_field(name="Channel Access", value="✅ Updated successfully", inline=False)
        else:
            embed.add_field(name="Channel Access", value="⚠️ May need manual update", inline=False)
        
        # Notify the player
        try:
            await player.send(embed=embed)
        except:
            pass  # Failed to DM user
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        print(f"🌀 Admin teleport: {char_name} ({player.id}) moved from {current_location_name} to {dest_name} by {interaction.user.name}")
    @admin_group.command(name="set_galactic_updates", description="Set the channel for galactic news updates")
    @app_commands.describe(channel="Channel to receive galactic news updates")
    async def set_galactic_updates_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Check if server config exists, create if not
        existing_config = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE guild_id = %s",
            (interaction.guild.id,),
            fetch='one'
        )
        
        if existing_config:
            # Update existing config
            self.db.execute_query(
                "UPDATE server_config SET galactic_updates_channel_id = %s WHERE guild_id = %s",
                (channel.id, interaction.guild.id)
            )
        else:
            # Create new config entry with just the guild_id and updates channel
            self.db.execute_query(
                """INSERT INTO server_config 
                   (guild_id, galactic_updates_channel_id) 
                   VALUES (%s, %s)""",
                (interaction.guild.id, channel.id)
            )
        
        embed = discord.Embed(
            title="📰 Galactic Updates Channel Set",
            description=f"Galactic news updates will be posted to {channel.mention}",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📡 News Types",
            value="• Corridor shifts and infrastructure changes\n• Major galactic events\n• Character obituaries\n• Economic and trade news\n• Discovery reports",
            inline=False
        )
        
        embed.add_field(
            name="⏰ News Delays",
            value="News will include realistic delays based on distance from galactic center, simulating information transmission time across space.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Send a test news message
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            await news_cog.queue_news(
                interaction.guild.id,
                'fluff_news',
                'Galactic News Network Online',
                f'Galactic News Network has established a relay connection to {channel.mention}. All major galactic events will now be reported with appropriate transmission delays based on interstellar distances.',
                None  # No location for this administrative message
            )
    @admin_group.command(name="npc_debug", description="Debug information about NPCs")
    @app_commands.describe(
        npc_type="Type of NPCs to view",
        location_id="Specific location ID to check (optional)"
    )
    @app_commands.choices(npc_type=[
        app_commands.Choice(name="Static NPCs", value="static"),
        app_commands.Choice(name="Dynamic NPCs", value="dynamic"),
        app_commands.Choice(name="All NPCs", value="all")
    ])
    async def npc_debug(self, interaction: discord.Interaction, npc_type: str, location_id: int = None):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🤖 NPC Debug Information", color=0x9b59b6)
        
        if npc_type in ["static", "all"]:
            if location_id:
                static_npcs = self.db.execute_query(
                    """SELECT s.name, s.age, s.occupation, l.name as location_name
                       FROM static_npcs s
                       JOIN locations l ON s.location_id = l.location_id
                       WHERE s.location_id = %s
                       ORDER BY s.name""",
                    (location_id,),
                    fetch='all'
                )
                embed.add_field(
                    name=f"📍 Static NPCs at Location {location_id}",
                    value="\n".join([f"• {name} ({age}y) - {occupation} at {loc}" 
                                   for name, age, occupation, loc in static_npcs]) or "None",
                    inline=False
                )
            else:
                static_count = self.db.execute_query(
                    "SELECT COUNT(*) FROM static_npcs",
                    fetch='one'
                )[0]
                
                static_by_location = self.db.execute_query(
                    """SELECT l.name, COUNT(s.npc_id) as npc_count
                       FROM locations l
                       LEFT JOIN static_npcs s ON l.location_id = s.location_id
                       WHERE s.npc_id IS NOT NULL
                       GROUP BY l.location_id, l.name
                       ORDER BY npc_count DESC
                       LIMIT 10""",
                    fetch='all'
                )
                
                embed.add_field(
                    name=f"📊 Static NPCs (Total: {static_count})",
                    value="\n".join([f"• {loc}: {count} NPCs" for loc, count in static_by_location]) or "None",
                    inline=False
                )
        
        if npc_type in ["dynamic", "all"]:
            if location_id:
                dynamic_npcs = self.db.execute_query(
                    """SELECT n.name, n.callsign, n.ship_name, n.is_alive,
                              CASE WHEN n.travel_start_time IS NOT NULL THEN 'Traveling' ELSE 'Docked' END as status
                       FROM dynamic_npcs n
                       WHERE n.current_location = %s OR n.destination_location = %s
                       ORDER BY n.name""",
                    (location_id, location_id),
                    fetch='all'
                )
                embed.add_field(
                    name=f"🚀 Dynamic NPCs at Location {location_id}",
                    value="\n".join([f"• {name} ({callsign}) - {ship} [{status}]{'💀' if not alive else ''}" 
                                   for name, callsign, ship, alive, status in dynamic_npcs]) or "None",
                    inline=False
                )
            else:
                dynamic_stats = self.db.execute_query(
                    """SELECT
                       COALESCE(COUNT(*), 0),
                       COALESCE(SUM(CASE WHEN is_alive = true THEN 1 ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN travel_start_time IS NOT NULL AND is_alive = true THEN 1 ELSE 0 END), 0)
                       FROM dynamic_npcs""",
                    fetch='one'
                )
                total, alive, traveling = dynamic_stats
                docked = alive - traveling
                dead = total - alive
                
                embed.add_field(
                    name="🚀 Dynamic NPC Statistics",
                    value=f"**Total:** {total}\n**Alive:** {alive}\n**Docked:** {docked}\n**Traveling:** {traveling}\n**Dead:** {dead}",
                    inline=True
                )
                
                # Top locations by dynamic NPC presence
                top_locations = self.db.execute_query(
                    """SELECT l.name, COUNT(n.npc_id) as npc_count
                       FROM locations l
                       JOIN dynamic_npcs n ON l.location_id = n.current_location
                       WHERE n.is_alive = true AND n.travel_start_time IS NULL
                       GROUP BY l.location_id, l.name
                       ORDER BY npc_count DESC
                       LIMIT 5""",
                    fetch='all'
                )
                
                if top_locations:
                    embed.add_field(
                        name="📍 Top NPC Locations",
                        value="\n".join([f"• {loc}: {count}" for loc, count in top_locations]),
                        inline=True
                    )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @admin_group.command(name="kill_npc", description="Kill a dynamic NPC")
    @app_commands.describe(callsign="Callsign of the NPC to kill")
    async def kill_npc(self, interaction: discord.Interaction, callsign: str):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Find the NPC
        npc_info = self.db.execute_query(
            "SELECT npc_id, name, is_alive, current_location, destination_location FROM dynamic_npcs WHERE callsign = %s",
            (callsign.upper(),),
            fetch='one'
        )
        
        if not npc_info:
            await interaction.response.send_message(f"❌ No NPC found with callsign {callsign}", ephemeral=True)
            return
        
        npc_id, name, is_alive, current_location, destination_location = npc_info
        
        if not is_alive:
            await interaction.response.send_message(f"❌ {name} ({callsign}) is already dead!", ephemeral=True)
            return
        
        # Kill the NPC
        self.db.execute_query(
            "UPDATE dynamic_npcs SET is_alive = false WHERE npc_id = %s",
            (npc_id,)
        )
        
        # Post obituary to galactic news with random death cause
        death_causes = [
            "system malfunction", "corridor instability", "reactor overload",
            "life support failure", "navigation error", "power core breach", 
            "hull breach", "unknown circumstances", "mechanical failure",
            "hypoxia incident", "radiation exposure", "debris impact",
            "equipment failure", "structural collapse", "communications blackout", 
            "fuel system explosion", "gravity generator malfunction",
            "pressure seal failure", "electronic systems failure",
            "asteroid collision", "solar radiation storm", "magnetic field anomaly"
        ]
        
        cause = random.choice(death_causes)
        
        # Get galactic news cog and post obituary
        galactic_news_cog = self.bot.get_cog('GalacticNews')
        # Use destination_location if current_location is None (NPC is traveling)
        obituary_location = current_location or destination_location
        if galactic_news_cog and obituary_location:
            await galactic_news_cog.post_character_obituary(name, obituary_location, cause)
        
        await interaction.response.send_message(
            f"💀 Killed dynamic NPC: **{name}** ({callsign})",
            ephemeral=True
        )

# Add this to your admin.py file in the AdminCog class

    @admin_group.command(name="ship_diagnostic", description="Diagnose ship/fuel issues for a player")
    @app_commands.describe(player="The player to diagnose")
    async def ship_diagnostic(self, interaction: discord.Interaction, player: discord.Member = None):
        """Diagnose ship and fuel issues"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        target = player or interaction.user
        
        # Get character data
        char_data = self.db.execute_query(
            "SELECT name, ship_id, active_ship_id FROM characters WHERE user_id = %s",
            (target.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(f"{target.mention} doesn't have a character!", ephemeral=True)
            return
        
        char_name, old_ship_id, active_ship_id = char_data
        
        # Get active ship from player_ships
        player_ship = self.db.execute_query(
            '''SELECT ps.ship_id, s.name, s.current_fuel, s.fuel_capacity
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = %s AND ps.is_active = true''',
            (target.id,),
            fetch='one'
        )
        
        # Check fuel using old ship_id
        old_fuel_check = self.db.execute_query(
            '''SELECT s.current_fuel, s.fuel_capacity, s.name
               FROM characters c
               JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.user_id = %s''',
            (target.id,),
            fetch='one'
        )
        
        # Check fuel using active_ship_id
        active_fuel_check = self.db.execute_query(
            '''SELECT s.current_fuel, s.fuel_capacity, s.name
               FROM characters c
               JOIN ships s ON c.active_ship_id = s.ship_id
               WHERE c.user_id = %s''',
            (target.id,),
            fetch='one'
        )
        
        embed = discord.Embed(
            title="🔍 Ship Diagnostic Report",
            description=f"Diagnosing ship issues for **{char_name}**",
            color=0xffff00
        )
        
        embed.add_field(name="Player", value=target.mention, inline=True)
        embed.add_field(name="Character", value=char_name, inline=True)
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        # Database fields
        embed.add_field(
            name="📊 Database Fields",
            value=f"ship_id: **{old_ship_id}**\nactive_ship_id: **{active_ship_id}**",
            inline=False
        )
        
        # Active ship from player_ships
        if player_ship:
            embed.add_field(
                name="✅ Active Ship (player_ships)",
                value=f"ID: **{player_ship[0]}** - {player_ship[1]}\nFuel: {player_ship[2]}/{player_ship[3]}",
                inline=False
            )
        else:
            embed.add_field(name="❌ No Active Ship", value="No active ship in player_ships!", inline=False)
        
        # Fuel check using ship_id
        if old_fuel_check:
            embed.add_field(
                name="🔴 Fuel Check (using ship_id)",
                value=f"Ship: {old_fuel_check[2]}\nFuel: {old_fuel_check[0]}/{old_fuel_check[1]}",
                inline=True
            )
        else:
            embed.add_field(name="🔴 Fuel Check (ship_id)", value="No ship found!", inline=True)
        
        # Fuel check using active_ship_id
        if active_fuel_check:
            embed.add_field(
                name="🟢 Fuel Check (using active_ship_id)",
                value=f"Ship: {active_fuel_check[2]}\nFuel: {active_fuel_check[0]}/{active_fuel_check[1]}",
                inline=True
            )
        else:
            embed.add_field(name="🟢 Fuel Check (active_ship_id)", value="No ship found!", inline=True)
        
        # Diagnosis
        problems = []
        if old_ship_id != active_ship_id:
            problems.append("⚠️ ship_id and active_ship_id don't match!")
        if player_ship and player_ship[0] != active_ship_id:
            problems.append("⚠️ active_ship_id doesn't match player_ships!")
        if player_ship and player_ship[0] != old_ship_id:
            problems.append("⚠️ ship_id doesn't match player_ships!")
        
        if problems:
            embed.add_field(
                name="⚠️ Issues Found",
                value="\n".join(problems),
                inline=False
            )
            embed.add_field(
                name="💡 Solution",
                value="Run `/admin fix_player_ship_id` to fix this player's ship_id field",
                inline=False
            )
        else:
            embed.add_field(name="✅ No Issues", value="All ship IDs are properly synchronized!", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="news_status", description="Check galactic news system status")
    async def galactic_news_status(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Get configuration
        config = self.db.execute_query(
            "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = %s",
            (interaction.guild.id,),
            fetch='one'
        )
        
        embed = discord.Embed(
            title="📰 Galactic News System Status",
            color=0x4169E1
        )
        
        if config and config[0]:
            channel = interaction.guild.get_channel(config[0])
            if channel:
                embed.add_field(
                    name="📡 Updates Channel",
                    value=f"✅ {channel.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📡 Updates Channel",
                    value="❌ Channel not found (may have been deleted)",
                    inline=False
                )
        else:
            embed.add_field(
                name="📡 Updates Channel",
                value="❌ Not configured",
                inline=False
            )
        
        # Get pending news count
        pending_count = self.db.execute_query(
            "SELECT COUNT(*) FROM news_queue WHERE guild_id = %s AND is_delivered = false",
            (interaction.guild.id,),
            fetch='one'
        )[0]
        
        embed.add_field(
            name="📰 Pending News",
            value=f"{pending_count} item{'s' if pending_count != 1 else ''} awaiting delivery",
            inline=True
        )
        
        # Get recent news count
        recent_count = self.db.execute_query(
            "SELECT COUNT(*) FROM news_queue WHERE guild_id = %s AND created_at > NOW() - INTERVAL '24 hours'",
            (interaction.guild.id,),
            fetch='one'
        )[0]
        
        embed.add_field(
            name="📊 Last 24 Hours",
            value=f"{recent_count} news item{'s' if recent_count != 1 else ''} generated",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)




    @admin_group.command(name="fix_all_ships", description="Fix all ship issues for all players")
    async def fix_all_ships(self, interaction: discord.Interaction):
        """Fix all ship-related issues for all players"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        fixed_count = 0
        
        # Step 1: Find all characters and their ships
        all_characters = self.db.execute_query(
            '''SELECT c.user_id, c.name, c.ship_id, c.active_ship_id,
                      s.ship_id as owned_ship_id, s.name as ship_name
               FROM characters c
               LEFT JOIN ships s ON s.owner_id = c.user_id
               WHERE c.ship_id IS NOT NULL OR s.ship_id IS NOT NULL''',
            fetch='all'
        )
        
        for user_id, char_name, char_ship_id, active_ship_id, owned_ship_id, ship_name in all_characters:
            # Determine which ship ID to use (prefer owned_ship_id from ships table)
            ship_id = owned_ship_id or char_ship_id or active_ship_id
            
            if not ship_id:
                continue
                
            # Check if this ship exists in player_ships
            exists_in_player_ships = self.db.execute_query(
                "SELECT 1 FROM player_ships WHERE owner_id = %s AND ship_id = %s",
                (user_id, ship_id),
                fetch='one'
            )
            
            if not exists_in_player_ships:
                # Add to player_ships
                self.db.execute_query(
                    "INSERT INTO player_ships (owner_id, ship_id, is_active) VALUES (%s, %s, true)",
                    (user_id, ship_id)
                )
                fixed_count += 1
            else:
                # Make sure it's active
                self.db.execute_query(
                    "UPDATE player_ships SET is_active = true WHERE owner_id = %s AND ship_id = %s",
                    (user_id, ship_id)
                )
            
            # Deactivate any other ships for this player
            self.db.execute_query(
                "UPDATE player_ships SET is_active = false WHERE owner_id = %s AND ship_id != %s",
                (user_id, ship_id)
            )
            
            # Update character's ship_id and active_ship_id
            self.db.execute_query(
                "UPDATE characters SET ship_id = %s, active_ship_id = %s WHERE user_id = %s",
                (ship_id, ship_id, user_id)
            )
        
        # Step 2: Clean up orphaned entries in player_ships (ships that don't exist)
        self.db.execute_query(
            '''DELETE FROM player_ships 
               WHERE ship_id NOT IN (SELECT ship_id FROM ships)'''
        )
        
        # Step 3: Ensure fuel is initialized for all ships
        self.db.execute_query(
            '''UPDATE ships 
               SET current_fuel = fuel_capacity 
               WHERE current_fuel IS NULL OR current_fuel = 0'''
        )
        
        # Count total fixed
        total_chars = len(all_characters)
        
        await interaction.followup.send(
            f"✅ Checked {total_chars} characters and fixed {fixed_count} ship issues.\n"
            f"All ships now have fuel and are properly linked to their owners.",
            ephemeral=True
        )
        

    
    @admin_group.command(name="cleanup_channels", description="Manually trigger cleanup of unused location channels")
    @app_commands.describe(force="Force cleanup even for recently used channels")
    async def cleanup_channels(self, interaction: discord.Interaction, force: bool = False):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from utils.channel_manager import ChannelManager
            channel_manager = ChannelManager(self.bot)
            
            # Get stats before cleanup
            stats_before = await channel_manager.get_location_statistics(interaction.guild)
            
            # Run cleanup
            if force:
                await channel_manager._cleanup_old_channels(interaction.guild, force=True)
            else:
                await channel_manager.cleanup_channels_task(interaction.guild)
            
            # Get stats after cleanup
            stats_after = await channel_manager.get_location_statistics(interaction.guild)
            
            channels_cleaned = stats_before['active_channels'] - stats_after['active_channels']
            
            embed = discord.Embed(
                title="🧹 Channel Cleanup Complete",
                color=0x00ff00 if channels_cleaned > 0 else 0x4169E1
            )
            
            embed.add_field(name="Channels Cleaned", value=str(channels_cleaned), inline=True)
            embed.add_field(name="Active Before", value=str(stats_before['active_channels']), inline=True)
            embed.add_field(name="Active After", value=str(stats_after['active_channels']), inline=True)
            
            if channels_cleaned == 0:
                embed.add_field(
                    name="ℹ️ No Cleanup Needed",
                    value="All active channels are still being used",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"Error during cleanup: {str(e)}", ephemeral=True)
    
    @admin_group.command(name="cleanup_ship_exchange", description="Clean up expired ship exchange listings and offers")
    async def cleanup_ship_exchange(self, interaction: discord.Interaction):
        """Clean up expired ship exchange listings and offers"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get counts before cleanup
            expired_listings = self.db.execute_query(
                "SELECT COUNT(*) FROM ship_exchange_listings WHERE expires_at < NOW() AND is_active = true",
                fetch='one'
            )[0]
            
            expired_offers = self.db.execute_query(
                "SELECT COUNT(*) FROM ship_exchange_offers WHERE offer_expires_at < NOW() AND status = 'pending'",
                fetch='one'
            )[0]
            
            # Perform cleanup
            self.db.cleanup_expired_ship_listings()
            
            # Get stats after cleanup
            stats = self.db.get_ship_exchange_stats()
            
            embed = discord.Embed(
                title="🧹 Ship Exchange Cleanup Complete",
                color=0x00ff00 if (expired_listings + expired_offers) > 0 else 0x4169E1
            )
            
            embed.add_field(name="Expired Listings Removed", value=str(expired_listings), inline=True)
            embed.add_field(name="Expired Offers Removed", value=str(expired_offers), inline=True)
            embed.add_field(name="Total Cleaned", value=str(expired_listings + expired_offers), inline=True)
            
            embed.add_field(name="Current Active Listings", value=str(stats['active_listings']), inline=True)
            embed.add_field(name="Current Pending Offers", value=str(stats['pending_offers']), inline=True)
            embed.add_field(name="Total Exchanges Completed", value=str(stats['completed_exchanges']), inline=True)
            
            if expired_listings == 0 and expired_offers == 0:
                embed.add_field(
                    name="ℹ️ No Cleanup Needed",
                    value="No expired ship exchange data found",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"Error during ship exchange cleanup: {str(e)}", ephemeral=True)
    
    @admin_group.command(name="fix_ship_activities", description="Generate activities for ships that don't have them")
    async def fix_ship_activities(self, interaction: discord.Interaction):
        """Generate ship activities for all ships missing them"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Import the activity manager
        from utils.ship_activities import ShipActivityManager
        activity_manager = ShipActivityManager(self.bot)
        
        # Find all ships without activities
        ships_without_activities = self.db.execute_query(
            '''SELECT s.ship_id, s.ship_type, s.name, c.name as owner_name
               FROM ships s
               LEFT JOIN ship_activities sa ON s.ship_id = sa.ship_id
               LEFT JOIN characters c ON s.owner_id = c.user_id
               WHERE sa.ship_id IS NULL
               GROUP BY s.ship_id''',
            fetch='all'
        )
        
        fixed_count = 0
        
        for ship_id, ship_type, ship_name, owner_name in ships_without_activities:
            # Generate activities for this ship
            activity_manager.generate_ship_activities(ship_id, ship_type)
            fixed_count += 1
        
        # Also fix any ships with zero activities
        ships_with_no_activities = self.db.execute_query(
            '''SELECT s.ship_id, s.ship_type, COUNT(sa.activity_id) as activity_count
               FROM ships s
               LEFT JOIN ship_activities sa ON s.ship_id = sa.ship_id
               GROUP BY s.ship_id
               HAVING activity_count = 0''',
            fetch='all'
        )
        
        for ship_id, ship_type, _ in ships_with_no_activities:
            activity_manager.generate_ship_activities(ship_id, ship_type)
            fixed_count += 1
        
        await interaction.followup.send(
            f"✅ Generated activities for {fixed_count} ships that were missing them!",
            ephemeral=True
        )
    
    
    @admin_group.command(name="location_info", description="Get detailed information about a location")
    @app_commands.describe(location_name="Name of the location to inspect")
    async def admin_location_info(self, interaction: discord.Interaction, location_name: str):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        location = self.db.execute_query(
            "SELECT * FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
            (f"%{location_name}%",),
            fetch='one'
        )
        
        if not location:
            await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
            return
        
        # Unpack location data
        (loc_id, channel_id, name, loc_type, description, wealth, population, x, y, system,
         has_jobs, has_shops, has_medical, has_repairs, has_fuel, has_upgrades, 
         is_generated, created_at) = location
        
        embed = discord.Embed(
            title=f"📍 {name} (Admin View)",
            description=description,
            color=0xff0000
        )
        
        # Basic info
        embed.add_field(name="ID", value=str(loc_id), inline=True)
        embed.add_field(name="Type", value=loc_type.replace('_', ' ').title(), inline=True)
        embed.add_field(name="Generated", value="Yes" if is_generated else "No", inline=True)
        
        # Channel info
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            channel_text = channel.mention if channel else f"Missing ({channel_id})"
        else:
            channel_text = "None"
        embed.add_field(name="Channel", value=channel_text, inline=True)
        
        # Stats
        embed.add_field(name="Wealth", value=f"{wealth}/10", inline=True)
        embed.add_field(name="Population", value=f"{population:,}", inline=True)
        embed.add_field(name="Coordinates", value=f"({x:.1f}, {y:.1f})", inline=True)
        embed.add_field(name="System", value=system, inline=True)
        
        # Services
        services = []
        if has_jobs: services.append("✅ Jobs")
        else: services.append("❌ Jobs")
        if has_shops: services.append("✅ Shopping")
        else: services.append("❌ Shopping")
        if has_medical: services.append("✅ Medical")
        else: services.append("❌ Medical")
        if has_repairs: services.append("✅ Repairs")
        else: services.append("❌ Repairs")
        if has_fuel: services.append("✅ Fuel")
        else: services.append("❌ Fuel")
        if has_upgrades: services.append("✅ Upgrades")
        else: services.append("❌ Upgrades")
        
        embed.add_field(name="Services", value="\n".join(services), inline=True)
        
        # Character count
        char_count = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_location = %s",
            (loc_id,),
            fetch='one'
        )[0]
        
        embed.add_field(name="Characters Present", value=str(char_count), inline=True)
        
        # Corridor connections
        corridors = self.db.execute_query(
            '''SELECT COUNT(*) FROM corridors 
               WHERE origin_location = %s AND is_active = true''',
            (loc_id,),
            fetch='one'
        )[0]
        
        embed.add_field(name="Active Corridors", value=str(corridors), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    

    @admin_group.command(name="reset", description="Reset various parts of the game data")
    @app_commands.describe(
        reset_type="What to reset",
        confirm="Type 'CONFIRM' to proceed with the reset"
    )
    @app_commands.choices(reset_type=[
        app_commands.Choice(name="Full Reset (Everything)", value="full"),
        app_commands.Choice(name="Galaxy Reset (Auto-Logout + Preserve Characters)", value="galaxy_with_logout"),
        app_commands.Choice(name="Galaxy Only (Locations & Corridors)", value="galaxy"),
        app_commands.Choice(name="Characters Only", value="characters"),
        app_commands.Choice(name="Economy (Jobs, Shop Items, Inventory)", value="economy"),
        app_commands.Choice(name="Travel Sessions", value="travel"),
    ])
    async def reset_data(self, interaction: discord.Interaction, reset_type: str, confirm: str = ""):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        if confirm.upper() != "CONFIRM":
            # Show warning and require confirmation
            embed = discord.Embed(
                title="⚠️ RESET WARNING",
                description=f"You are about to perform a **{reset_type.upper()} RESET**. This action is **IRREVERSIBLE**!",
                color=0xff0000
            )
            
            reset_details = self._get_reset_details(reset_type)
            embed.add_field(name="What will be deleted:", value=reset_details, inline=False)
            
            embed.add_field(
                name="🔒 To confirm this action:",
                value=f"Run the command again with: `confirm:CONFIRM`\n\n`/admin reset reset_type:{reset_type} confirm:CONFIRM`",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Important:",
                value="• Make sure all players are offline\n• This cannot be undone\n• Consider backing up your database first",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Confirmed reset - proceed
        await interaction.response.defer(ephemeral=True)
        
        try:
            reset_results = await self._perform_reset(interaction.guild, reset_type)
            
            embed = discord.Embed(
                title="✅ Reset Complete",
                description=f"**{reset_type.upper()} RESET** has been completed successfully.",
                color=0x00ff00
            )
            
            for category, count in reset_results.items():
                embed.add_field(name=category, value=f"{count} items", inline=True)
            
            embed.add_field(
                name="🔄 Next Steps",
                value=self._get_next_steps(reset_type),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log the reset action
            print(f"🔥 ADMIN RESET: {interaction.user.name} performed {reset_type} reset in {interaction.guild.name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Reset failed: {str(e)}", ephemeral=True)
    
    @admin_group.command(name="emergency_reset", description="EMERGENCY: Full reset with channel cleanup")
    async def emergency_reset(self, interaction: discord.Interaction):
        """Emergency reset with immediate confirmation dialog"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        view = EmergencyResetView(self.bot, interaction.user.id)
        
        embed = discord.Embed(
            title="🚨 EMERGENCY RESET",
            description="This will **COMPLETELY WIPE** all game data and channels.\n\n⚠️ **USE ONLY IN EMERGENCIES** ⚠️",
            color=0xff0000
        )
        
        embed.add_field(
            name="Will Delete:",
            value="• All characters and ships\n• All locations and corridors\n• All location channels\n• All jobs and inventory\n• All travel sessions\n• All shop data",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Confirmation Required",
            value="Click the button below to confirm this emergency reset.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _get_reset_details(self, reset_type: str) -> str:
        """Get detailed description of what each reset type will delete"""
        details = {
            "full": "• All player characters and ships\n• All locations and corridors\n• All location channels\n• All jobs and shop items\n• All player inventory\n• All travel sessions",
            "galaxy_with_logout": "• All locations (colonies, stations, outposts, gates)\n• All corridors between locations\n• All location channels\n• All jobs and economy data\n• All homes and properties (with credit refunds)\n• All NPCs and travel sessions\n• Auto-logout all users\n\n✅ **PRESERVES:** Characters, ships, inventory, XP, reputation",
            "galaxy": "• All locations (colonies, stations, outposts, gates)\n• All corridors between locations\n• All location channels\n• All jobs at locations\n• All shop items",
            "characters": "• All player characters\n• All player ships\n• All player inventory",
            "economy": "• All jobs at all locations\n• All shop items and stock\n• All player inventory items",
            "travel": "• All active travel sessions\n• All temporary transit channels",
        }
        return details.get(reset_type, "Unknown reset type")
    
    def _get_next_steps(self, reset_type: str) -> str:
        """Get recommended next steps after each reset type"""
        steps = {
            "full": "• Run `/admin setup` to reconfigure server\n• Run `/galaxy generate` to create new galaxy\n• Players can `/character create` to restart",
            "galaxy_with_logout": "• Run `/galaxy generate` to create new galaxy\n• Players can `/character login` to respawn at colonies\n• All character data, ships, and inventory preserved",
            "galaxy": "• Run `/galaxy generate` to create new galaxy\n• Existing characters will need to be moved to new locations",
            "characters": "• Players can `/character create` to make new characters\n• Galaxy and economy remain intact",
            "economy": "• Jobs and shop items will regenerate automatically\n• Players keep characters but lose inventory",
            "travel": "• All active journeys have been cancelled\n• Players may need to relocate manually",
        }
        return steps.get(reset_type, "Reset complete.")
    
    async def _perform_reset(self, guild: discord.Guild, reset_type: str) -> dict:
        """Perform the actual reset operation, including channel cleanup for full/galaxy resets"""
        reset_counts = {}

        if reset_type == "full":
            # For full reset, we need to clear EVERYTHING
            # Get counts of all tables before deletion
            all_tables = [
                # Character related
                "characters", "character_identity", "character_reputation", "character_experience",
                "character_inventory", "afk_warnings", "search_cooldowns",
                
                # Ship related
                "ships", "ship_upgrades", "ship_customizations", "ship_activities", "player_ships",
                
                # Location related
                "locations", "corridors", "location_items", "location_logs", "location_homes",
                "home_activities", "home_interiors", "home_market_listings", "home_invitations",
                "location_economy", "economic_events", "location_ownership", "location_upgrades",
                "location_access_control", "location_income_log", "location_storage", "sub_locations",
                
                # NPC related
                "static_npcs", "dynamic_npcs", "npc_respawn_queue", "npc_inventory", 
                "npc_trade_inventory", "npc_jobs", "npc_job_completions",
                
                # Economy related
                "jobs", "job_tracking", "shop_items", "inventory", "black_markets", "black_market_items",
                
                # Group related
                
                # Combat related
                "combat_states", "combat_encounters", "pvp_opt_outs", "pvp_combat_states", 
                "pvp_cooldowns", "pending_robberies",
                
                # Travel related
                "travel_sessions", "corridor_events", "active_beacons",
                
                # System related
                "repeaters", "user_location_panels", "logbook_entries", "news_queue", 
                "galactic_history", "game_panels", "galaxy_info", "galaxy_settings",
                "endgame_config", "endgame_evacuations"
            ]
            
            # Count rows in each table
            for table in all_tables:
                try:
                    count = self.db.execute_query(f"SELECT COUNT(*) FROM {table}", fetch='one')[0]
                    if count > 0:
                        reset_counts[table] = count
                except:
                    pass  # Table might not exist
            
            # Get location channels before deletion
            location_channels = self.db.execute_query(
                "SELECT channel_id FROM locations WHERE channel_id IS NOT NULL",
                fetch='all'
            )
            
            # Get temporary travel channels
            temp_channels = self.db.execute_query(
                "SELECT DISTINCT temp_channel_id FROM travel_sessions WHERE temp_channel_id IS NOT NULL",
                fetch='all'
            )
            
            # Clear all tables in reverse dependency order
            # This order is important to avoid foreign key constraint issues
            tables_to_clear_in_order = [
                # Clear dependent tables first
                "afk_warnings", "search_cooldowns", "user_location_panels", "active_beacons",
                "pvp_cooldowns", "pending_robberies", "pvp_combat_states", "pvp_opt_outs",
                "combat_encounters", "combat_states",
                "group_votes", "group_vote_sessions", "group_invites", "group_ships",
                "ship_activities", "ship_customizations", "ship_upgrades", "player_ships",
                "character_inventory", "character_experience", "character_reputation", "character_identity",
                "home_invitations", "home_market_listings", "home_interiors", "home_activities",
                "location_storage", "location_income_log", "location_access_control", 
                "location_upgrades", "location_ownership", "economic_events", "location_economy",
                "location_logs", "location_items", "location_homes",
                "npc_job_completions", "npc_jobs", "npc_trade_inventory", "npc_inventory",
                "npc_respawn_queue", "dynamic_npcs", "static_npcs",
                "black_market_items", "black_markets", "sub_locations",
                "job_tracking", "jobs", "shop_items", "inventory",
                "corridor_events", "travel_sessions", "repeaters",
                "logbook_entries", "ships", "characters",
                "galactic_history", "corridors", "locations",
                "news_queue", "game_panels",
                "endgame_evacuations", "endgame_config",
                "galaxy_settings", "galaxy_info"
            ]
            
            # PostgreSQL always enforces foreign key constraints
            # No need to disable/enable them like in SQLite
            
            # Delete all data using a transaction for atomicity
            try:
                # Use database transaction to ensure all-or-nothing behavior
                transaction_operations = []
                for table in tables_to_clear_in_order:
                    # Use TRUNCATE for better performance and foreign key handling
                    transaction_operations.append((f"TRUNCATE TABLE {table} CASCADE", None))
                
                # Execute all truncations in a single transaction
                self.db.execute_transaction(transaction_operations)
                print("🗑️ All tables cleared successfully")
                
            except Exception as e:
                print(f"⚠️ TRUNCATE failed, falling back to individual DELETE operations: {e}")
                # Fallback: delete tables one by one
                for table in tables_to_clear_in_order:
                    try:
                        self.db.execute_query(f"DELETE FROM {table}")
                        print(f"✅ Cleared {table}")
                    except Exception as e2:
                        print(f"❌ Could not clear table {table}: {e2}")
                        # Continue with other tables
            
            # PostgreSQL always enforces foreign key constraints
            # No need to disable/enable them like in SQLite
            
            # PostgreSQL doesn't use WAL checkpoints via PRAGMA
            # Database changes are automatically persisted
            
            # Delete Discord channels
            channels_deleted = 0
            for (channel_id,) in location_channels:
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.delete(reason="Full server reset")
                        channels_deleted += 1
                    except:
                        pass
            
            for (channel_id,) in temp_channels:
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.delete(reason="Full server reset")
                        channels_deleted += 1
                    except:
                        pass
            
            reset_counts["Discord Channels"] = channels_deleted
            
        else:
            # Handle other reset types (unchanged from original)
            
            # ————— Character data —————
            if reset_type in ["characters"]:
                reset_counts["Characters"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM characters", fetch='one'
                )[0]
                reset_counts["Ships"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM ships", fetch='one'
                )[0]
                reset_counts["Inventory Items"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM inventory", fetch='one'
                )[0]

                # Delete in proper order to avoid foreign key issues using transaction
                try:
                    character_tables = [
                        "logbook_entries", "character_identity", "character_reputation", 
                        "character_experience", "character_inventory", "characters", "ships", "inventory"
                    ]
                    transaction_operations = [(f"TRUNCATE TABLE {table} CASCADE", None) for table in character_tables]
                    self.db.execute_transaction(transaction_operations)
                    print("🗑️ Character data cleared successfully")
                except Exception as e:
                    print(f"⚠️ TRUNCATE failed for character data, using DELETE: {e}")
                    # Fallback to individual deletes
                    for table in character_tables:
                        try:
                            self.db.execute_query(f"DELETE FROM {table}")
                        except Exception as e2:
                            print(f"❌ Could not clear {table}: {e2}")

            # ————— Galaxy Reset with Character Preservation —————
            if reset_type in ["galaxy_with_logout"]:
                # Step 1: Force logout all logged in users
                logged_in_users = self.db.execute_query(
                    "SELECT user_id FROM characters WHERE is_logged_in = true", 
                    fetch='all'
                )
                
                reset_counts["Users Logged Out"] = len(logged_in_users)
                
                # Force logout all logged in users
                character_cog = self.bot.get_cog('Character')
                if character_cog:
                    for (user_id,) in logged_in_users:
                        try:
                            # Use the auto-logout method designed for system-initiated logouts
                            await character_cog._execute_auto_logout(user_id, "Galaxy reset")
                        except Exception as e:
                            print(f"Warning: Could not logout user {user_id}: {e}")
                
                # Step 2: Start transaction for database operations
                try:
                    conn = self.db.begin_transaction()
                    
                    # Calculate and refund home values
                    home_refunds = self.db.execute_in_transaction(conn, """
                        SELECT lh.owner_id, SUM(lh.price) as total_value
                        FROM location_homes lh 
                        WHERE lh.owner_id IS NOT NULL 
                        GROUP BY lh.owner_id
                    """, fetch='all')
                    
                    total_refunds = 0
                    for owner_id, home_value in home_refunds:
                        # Add credits to character account
                        self.db.execute_in_transaction(conn,
                            "UPDATE characters SET credits = credits + %s WHERE user_id = %s",
                            (home_value, owner_id)
                        )
                        total_refunds += home_value
                    
                    reset_counts["Home Refund Credits"] = total_refunds
                    reset_counts["Players Refunded"] = len(home_refunds)
                
                    # Step 3: Count what will be deleted
                    reset_counts["Locations"] = self.db.execute_in_transaction(conn,
                        "SELECT COUNT(*) FROM locations", fetch='one'
                    )[0]
                    reset_counts["Corridors"] = self.db.execute_in_transaction(conn,
                        "SELECT COUNT(*) FROM corridors", fetch='one'
                    )[0]
                    reset_counts["Homes"] = self.db.execute_in_transaction(conn,
                        "SELECT COUNT(*) FROM location_homes", fetch='one'
                    )[0]

                    # Get location channels before deletion
                    location_channels = self.db.execute_in_transaction(conn,
                        "SELECT channel_id FROM locations WHERE channel_id IS NOT NULL",
                        fetch='all'
                    )

                    # Get temporary travel channels
                    temp_channels = self.db.execute_in_transaction(conn,
                        "SELECT DISTINCT temp_channel_id FROM travel_sessions WHERE temp_channel_id IS NOT NULL",
                        fetch='all'
                    )

                    # Step 4: Clear galaxy data using comprehensive method
                    await self._clear_comprehensive_galaxy_data_in_transaction(conn)

                    # Step 5: Set character locations to NULL so they'll respawn at colonies
                    self.db.execute_in_transaction(conn, "UPDATE characters SET current_location = NULL")
                    
                    # Step 6: Clear ship docking locations since locations will be reset
                    self.db.execute_in_transaction(conn, "UPDATE ships SET docked_at_location = NULL")
                    
                    # Commit the transaction
                    self.db.commit_transaction(conn)
                    
                except Exception as e:
                    # Rollback on error (only if transaction is active)
                    try:
                        self.db.rollback_transaction(conn)
                    except:
                        # No active transaction to rollback
                        pass
                    print(f"Database transaction failed during galaxy reset: {e}")
                    raise e

                # Step 6: Delete Discord channels (outside transaction)
                channels_deleted = 0
                for (channel_id,) in location_channels:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Galaxy reset with character preservation")
                            channels_deleted += 1
                        except:
                            pass

                for (channel_id,) in temp_channels:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Galaxy reset with character preservation")
                            channels_deleted += 1
                        except:
                            pass

                reset_counts["Location Channels Deleted"] = channels_deleted

            # ————— Galaxy data —————
            if reset_type in ["galaxy"]:
                reset_counts["Locations"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM locations", fetch='one'
                )[0]
                reset_counts["Corridors"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM corridors", fetch='one'
                )[0]

                location_channels = self.db.execute_query(
                    "SELECT channel_id FROM locations WHERE channel_id IS NOT NULL",
                    fetch='all'
                )

                await self._clear_comprehensive_galaxy_data()

                channels_deleted = 0
                for (channel_id,) in location_channels:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Galaxy reset")
                            channels_deleted += 1
                        except:
                            pass

                reset_counts["Location Channels Deleted"] = channels_deleted

            # ————— Economy data —————
            if reset_type in ["economy"]:
                reset_counts["Jobs"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM jobs", fetch='one'
                )[0]
                reset_counts["Shop Items"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM shop_items", fetch='one'
                )[0]

                self.db.execute_query("DELETE FROM jobs")
                self.db.execute_query("DELETE FROM job_tracking")
                self.db.execute_query("DELETE FROM shop_items")
                self.db.execute_query("DELETE FROM inventory")

            # ————— Travel data —————
            if reset_type in ["travel"]:
                reset_counts["Travel Sessions"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM travel_sessions", fetch='one'
                )[0]

                temp_channels = self.db.execute_query(
                    "SELECT DISTINCT temp_channel_id FROM travel_sessions WHERE temp_channel_id IS NOT NULL",
                    fetch='all'
                )

                self.db.execute_query("DELETE FROM travel_sessions")
                self.db.execute_query("DELETE FROM corridor_events")

                temp_deleted = 0
                for (channel_id,) in temp_channels:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Travel reset")
                            temp_deleted += 1
                        except:
                            pass

                reset_counts["Temporary Channels Deleted"] = temp_deleted


        # Ensure all tables exist after reset
        print("🔧 Recreating database tables after reset...")
        self.db.init_database()
        print("✅ Database tables recreated successfully")

        return reset_counts

    async def _clear_comprehensive_galaxy_data(self):
        """Use the same comprehensive clearing logic as the galaxy generator"""
        print("🗑️ Performing comprehensive galaxy data clearing...")
        
        try:
            # Clear in reverse dependency order to avoid foreign key issues
            # This is the same order used in galaxy_generator.py _clear_existing_galaxy_data
            
            # First, clear tables that depend on locations
            tables_to_clear = [
                "home_activities", "home_interiors", "home_market_listings", 
                "home_invitations", "location_homes", "character_reputation",
                "location_items", "location_logs", "shop_items", "jobs", 
                "job_tracking", "location_storage", "location_income_log",
                "location_access_control", "location_upgrades", "location_ownership",
                "location_economy", "economic_events",
                
                # NPC related tables
                "npc_respawn_queue", "npc_inventory", "npc_trade_inventory",
                "npc_jobs", "npc_job_completions", "static_npcs", "dynamic_npcs",
                
                # Black market tables
                "black_market_items", "black_markets",
                
                # Sub-locations and repeaters
                "sub_locations", "repeaters",
                
                # Travel sessions that reference corridors/locations
                "travel_sessions", "corridor_events",
                
                # Clear history before locations due to foreign key constraints
                "galactic_history",
                
                # Finally clear corridors and locations
                "corridors", "locations",
                
                # Clear news
                "news_queue"
                
                # Skip endgame tables - not essential for galaxy reset
            ]
            
            # PostgreSQL always enforces foreign key constraints
            # No need to disable/enable them like in SQLite
            
            # Clear tables with timeout protection
            for i, table in enumerate(tables_to_clear):
                try:
                    # Add progress indicator for user feedback
                    if i % 5 == 0:
                        print(f"🗑️ Clearing table {i+1}/{len(tables_to_clear)}: {table}")
                    
                    self.db.execute_query(f"DELETE FROM {table}")
                    
                    # Brief yield every few tables to prevent blocking
                    if i % 3 == 0:
                        await asyncio.sleep(0.05)
                        
                except Exception as e:
                    # Some tables might not exist, which is fine
                    print(f"Note: Could not clear table {table}: {e}")
            
            # PostgreSQL always enforces foreign key constraints
            # No need to disable/enable them like in SQLite
            
            # Skip game panels deletion - they'll update automatically when new galaxy exists
            
            # PostgreSQL doesn't use WAL checkpoints via PRAGMA
            # Database changes are automatically persisted
            
            print("✅ Comprehensive galaxy data clearing complete")
            
        except Exception as e:
            print(f"❌ Error during comprehensive galaxy clearing: {e}")
            raise

    async def _clear_comprehensive_galaxy_data_in_transaction(self, conn):
        """Use the same comprehensive clearing logic as the galaxy generator, within a transaction"""
        print("🗑️ Performing comprehensive galaxy data clearing in transaction...")
        
        try:
            # Clear in reverse dependency order to avoid foreign key issues
            # This is the same order used in galaxy_generator.py _clear_existing_galaxy_data
            
            # First, clear tables that depend on locations
            tables_to_clear = [
                "home_activities", "home_interiors", "home_market_listings", 
                "home_invitations", "location_homes", "character_reputation",
                "location_items", "location_logs", "shop_items", "jobs", 
                "job_tracking", "location_storage", "location_income_log",
                "location_access_control", "location_upgrades", "location_ownership",
                "location_economy", "economic_events",
                
                # NPC related tables
                "npc_respawn_queue", "npc_inventory", "npc_trade_inventory",
                "npc_jobs", "npc_job_completions", "static_npcs", "dynamic_npcs",
                
                # Black market tables
                "black_market_items", "black_markets",
                
                # Sub-locations and repeaters
                "sub_locations", "repeaters",
                
                # Travel sessions that reference corridors/locations
                "travel_sessions", "corridor_events",
                
                # Clear history before locations due to foreign key constraints
                "galactic_history",
                
                # Finally clear corridors and locations
                "corridors", "locations",
                
                # Clear news
                "news_queue"
                
                # Skip endgame tables - not essential for galaxy reset
            ]
            
            for table in tables_to_clear:
                try:
                    self.db.execute_in_transaction(conn, f"DELETE FROM {table}")
                except Exception as e:
                    # Some tables might not exist, which is fine
                    print(f"Note: Could not clear table {table}: {e}")
            
            # Skip game panels deletion - they'll update automatically when new galaxy exists
            
            # PostgreSQL doesn't use WAL checkpoints via PRAGMA
            # Database changes are automatically persisted
            
            print("✅ Comprehensive galaxy data clearing in transaction complete")
            
        except Exception as e:
            print(f"❌ Error during comprehensive galaxy clearing in transaction: {e}")
            raise
    
    @app_commands.command(name="cleanup", description="Cleanup Unused Channels")
    @app_commands.describe(
        player="Player to log out"
    )
    async def afk_player(self, interaction: discord.Interaction, player: discord.Member):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Check if player has a character and is logged in
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in, current_location, current_ship_id, current_home_id FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
            return
        
        char_name, is_logged_in, current_location, current_ship_id, current_home_id = char_data
        
        if not is_logged_in:
            await interaction.response.send_message(f"**{char_name}** is not currently logged in.", ephemeral=True)
            return
        
        # Cancel any active jobs
        self.db.execute_query(
            "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = %s",
            (player.id,)
        )
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = %s",
            (player.id,)
        )
        
        # Clear nickname if auto-rename is enabled
        if interaction.guild.me.guild_permissions.manage_nicknames:
            auto_rename_setting = self.db.execute_query(
                "SELECT auto_rename FROM characters WHERE user_id = %s",
                (player.id,),
                fetch='one'
            )
            if auto_rename_setting and auto_rename_setting[0] == 1 and player.nick == char_name:
                try:
                    await player.edit(nick=None, reason="Admin AFK logout")
                except Exception as e:
                    print(f"Failed to clear nickname on AFK logout for {player}: {e}")
        
        # Log out the character
        self.db.execute_query(
            "UPDATE characters SET is_logged_in = false WHERE user_id = %s",
            (player.id,)
        )
        
        # Remove access and cleanup
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        if current_location:
            await channel_manager.remove_user_location_access(player, current_location)
            await channel_manager.immediate_logout_cleanup(interaction.guild, current_location, current_ship_id, current_home_id)
        elif current_ship_id:
            await channel_manager.remove_user_ship_access(player, current_ship_id)
            await channel_manager.immediate_logout_cleanup(interaction.guild, None, current_ship_id, current_home_id)
        elif current_home_id:
            await channel_manager.remove_user_home_access(player, current_home_id)
            await channel_manager.immediate_logout_cleanup(interaction.guild, None, None, current_home_id)
        
        # Clean up activity tracker
        if hasattr(self.bot, 'activity_tracker'):
            self.bot.activity_tracker.cleanup_user_tasks(player.id)
        
        # Send confirmation to admin
        embed = discord.Embed(
            title="✅ AFK Logout Complete",
            description=f"**{char_name}** ({player.mention}) has been silently logged out.",
            color=0x00ff00
        )
        embed.add_field(
            name="Actions Taken",
            value="• Character logged out\n• Active jobs cancelled\n• Channel access removed\n• Activity tracking cleared",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log the action
        print(f"🚪 Admin AFK logout: {char_name} (ID: {player.id}) by {interaction.user} ({interaction.user.id})")
    
    
    @app_commands.command(name="create_game_panel", description="Create a game panel in the current channel")
    @app_commands.describe(channel="Channel to create the game panel in (optional - uses current channel if not specified)")
    async def create_game_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Create a game panel in the current or specified channel"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Use specified channel or default to current channel
        target_channel = channel if channel else interaction.channel
        
        # Check if a panel already exists in the target channel
        existing_panel = self.db.execute_query(
            "SELECT message_id FROM game_panels WHERE guild_id = %s AND channel_id = %s",
            (interaction.guild.id, target_channel.id),
            fetch='one'
        )
        
        if existing_panel:
            await interaction.response.send_message(
                f"A game panel already exists in {target_channel.mention}!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get game panel cog and create panel
            panel_cog = self.bot.get_cog('GamePanelCog')
            if panel_cog:
                embed = await panel_cog.create_panel_embed(interaction.guild)
                view = await panel_cog.create_panel_view()
                
                # Send the panel message to the target channel
                message = await target_channel.send(embed=embed, view=view)
                
                # Store panel in database
                self.db.execute_query(
                    """INSERT INTO game_panels (guild_id, channel_id, message_id, created_by)
                       VALUES (%s, %s, %s, %s)""",
                    (interaction.guild.id, target_channel.id, message.id, interaction.user.id)
                )
                
                # Respond with success message
                success_message = f"✅ Game panel created successfully in {target_channel.mention}!"
                await interaction.followup.send(success_message, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Game panel system not available.",
                    ephemeral=True
                )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to create game panel: {str(e)}",
                ephemeral=True
            )
    @admin_group.command(name="backup", description="Create a backup of the current database")
    async def backup_database(self, interaction: discord.Interaction):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            import subprocess
            from datetime import datetime
            import os
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"rpg_game_backup_{timestamp}.sql"
            
            # Use pg_dump to create PostgreSQL backup
            # Extract connection details from database URL
            db_url = self.db.db_url
            env = os.environ.copy()
            if 'host=/tmp' in db_url:
                env['PGHOST'] = '/tmp'
            
            # Run pg_dump command
            result = subprocess.run([
                'pg_dump', 
                '-h', '/tmp',
                '-U', 'thequietend_user', 
                '-d', 'thequietend_db',
                '-f', backup_filename,
                '--no-password'
            ], env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"pg_dump failed: {result.stderr}")
            
            # Get database stats
            stats = {}
            tables = ["characters", "locations", "corridors", "jobs", "ships", "inventory"]
            for table in tables:
                try:
                    count = self.db.execute_query(f"SELECT COUNT(*) FROM {table}", fetch='one')[0]
                    stats[table] = count
                except:
                    stats[table] = 0
            
            embed = discord.Embed(
                title="💾 PostgreSQL Database Backup Created",
                description=f"Backup saved as: `{backup_filename}`",
                color=0x00ff00
            )
            
            stats_text = "\n".join([f"{table.title()}: {count}" for table, count in stats.items()])
            embed.add_field(name="Backed Up Data", value=stats_text, inline=True)
            
            embed.add_field(
                name="📁 File Details", 
                value=f"SQL dump file created with pg_dump\nFile: `{backup_filename}`\nFormat: Plain SQL",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Backup failed: {str(e)}", ephemeral=True)
    
    @admin_group.command(name="item", description="Delete items from player inventory")
    @app_commands.describe(player="Player to delete items from (optional - defaults to yourself)")
    async def delete_item(self, interaction: discord.Interaction, player: Optional[discord.Member] = None):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Use specified player or default to admin
        target_user = player if player else interaction.user
        
        # Check if target has a character
        char_info = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (target_user.id,),
            fetch='one'
        )
        
        if not char_info:
            target_name = player.display_name if player else "You"
            await interaction.response.send_message(f"{target_name} don't have a character.", ephemeral=True)
            return
        
        char_name = char_info[0]
        
        # Get player's inventory
        items = self.db.execute_query(
            '''SELECT i.item_name, i.item_type, i.quantity, i.description, i.value, 
                      i.item_id, CASE WHEN ce.equipment_id IS NOT NULL THEN 1 ELSE 0 END as is_equipped
               FROM inventory i
               LEFT JOIN character_equipment ce ON i.item_id = ce.item_id AND ce.user_id = i.owner_id
               WHERE i.owner_id = %s
               ORDER BY is_equipped DESC, i.item_type, i.item_name''',
            (target_user.id,),
            fetch='all'
        )
        
        if not items:
            target_possessive = f"{player.display_name}'s" if player else "Your"
            await interaction.response.send_message(f"{target_possessive} inventory is empty.", ephemeral=True)
            return
        
        # Create the deletion view
        from utils.views import AdminInventoryDeleteView
        view = AdminInventoryDeleteView(self.bot, target_user.id, items, char_name)
        
        target_text = f"**{char_name}**'s" if player else "your"
        embed = discord.Embed(
            title="🗑️ Admin Item Deletion",
            description=f"Select items to delete from {target_text} inventory.\n⚠️ **This action cannot be undone!**",
            color=0xff0000
        )
        embed.add_field(name="Target Character", value=char_name, inline=True)
        embed.add_field(name="Total Items", value=len(items), inline=True)
        embed.set_footer(text="Admin Tool • Items will be permanently deleted")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @admin_group.command(name="cleanup_dead_characters", description="Find and kill characters that should be dead (HP ≤ 0 or hull ≤ 0)")
    @app_commands.describe(
        dry_run="If True, only shows what would be killed without actually doing it"
    )
    async def cleanup_dead_characters(self, interaction: discord.Interaction, dry_run: bool = True):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Find characters with HP ≤ 0
            dead_hp_chars = self.db.execute_query("""
                SELECT c.user_id, c.name, c.hp 
                FROM characters c 
                WHERE c.hp <= 0 AND c.is_logged_in = true
            """, fetch='all')
            
            # Find characters with hull ≤ 0  
            dead_hull_chars = self.db.execute_query("""
                SELECT c.user_id, c.name, s.hull_integrity 
                FROM characters c 
                JOIN ships s ON c.user_id = s.owner_id 
                WHERE s.hull_integrity <= 0 AND c.is_logged_in = true
            """, fetch='all')
            
            total_found = len(dead_hp_chars) + len(dead_hull_chars)
            
            if total_found == 0:
                embed = discord.Embed(
                    title="✅ No Dead Characters Found",
                    description="All characters with HP ≤ 0 or hull ≤ 0 have already been properly killed.",
                    color=0x00ff00
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Create report embed
            embed = discord.Embed(
                title="☠️ Dead Characters Cleanup" + (" (DRY RUN)" if dry_run else ""),
                description=f"Found {total_found} characters that should be dead but aren't.",
                color=0xff0000 if not dry_run else 0xffaa00
            )
            
            if dead_hp_chars:
                hp_list = []
                for user_id, name, hp in dead_hp_chars:
                    member = interaction.guild.get_member(user_id)
                    member_name = member.display_name if member else f"Unknown ({user_id})"
                    hp_list.append(f"• **{name}** ({member_name}): {hp} HP")
                
                embed.add_field(
                    name=f"💔 Characters with HP ≤ 0 ({len(dead_hp_chars)})",
                    value="\n".join(hp_list[:10]) + (f"\n... and {len(hp_list)-10} more" if len(hp_list) > 10 else ""),
                    inline=False
                )
            
            if dead_hull_chars:
                hull_list = []
                for user_id, name, hull in dead_hull_chars:
                    member = interaction.guild.get_member(user_id)
                    member_name = member.display_name if member else f"Unknown ({user_id})"
                    hull_list.append(f"• **{name}** ({member_name}): {hull} Hull")
                
                embed.add_field(
                    name=f"🚢 Characters with Hull ≤ 0 ({len(dead_hull_chars)})",
                    value="\n".join(hull_list[:10]) + (f"\n... and {len(hull_list)-10} more" if len(hull_list) > 10 else ""),
                    inline=False
                )
            
            if dry_run:
                embed.add_field(
                    name="ℹ️ Dry Run Mode",
                    value="No characters were actually killed. Run with `dry_run: False` to execute the cleanup.",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Actually kill the characters
            char_cog = self.bot.get_cog('CharacterCog')
            if not char_cog:
                await interaction.followup.send("❌ Character system not available.", ephemeral=True)
                return
            
            killed_count = 0
            
            # Kill HP-dead characters
            for user_id, name, hp in dead_hp_chars:
                try:
                    await char_cog.update_character_hp(user_id, 0, interaction.guild, "Administrative cleanup - HP was already ≤ 0")
                    killed_count += 1
                except Exception as e:
                    print(f"Failed to kill character {name} ({user_id}) with HP {hp}: {e}")
            
            # Kill hull-dead characters  
            for user_id, name, hull in dead_hull_chars:
                try:
                    await char_cog.update_ship_hull(user_id, 0, interaction.guild, "Administrative cleanup - Hull was already ≤ 0")
                    killed_count += 1
                except Exception as e:
                    print(f"Failed to kill character {name} ({user_id}) with hull {hull}: {e}")
            
            embed.add_field(
                name="✅ Cleanup Complete",
                value=f"Successfully processed {killed_count}/{total_found} characters.",
                inline=False
            )
            
            embed.color = 0x00ff00
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            print(f"🧹 Dead character cleanup: {interaction.user.name} processed {killed_count} characters in {interaction.guild.name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Cleanup failed: {str(e)}", ephemeral=True)
    
    # ... (keep all your other existing admin commands)

class EmergencyResetView(discord.ui.View):
    def __init__(self, bot, admin_user_id: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.admin_user_id = admin_user_id
    
    @discord.ui.button(label="EMERGENCY RESET - DELETE EVERYTHING", 
                      style=discord.ButtonStyle.danger, 
                      emoji="🚨")
    async def emergency_reset_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user_id:
            await interaction.response.send_message("Only the admin who initiated this can confirm.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Perform full reset
            admin_cog = self.bot.get_cog('AdminCog')
            reset_results = await admin_cog._perform_reset(interaction.guild, "full")
            
            # Also clear server config (fresh start)
            admin_cog.db.execute_query(
                "DELETE FROM server_config WHERE guild_id = %s",
                (interaction.guild.id,)
            )
            
            # Clear galaxy settings
            admin_cog.db.execute_query("DELETE FROM galaxy_settings")
            
            embed = discord.Embed(
                title="🚨 EMERGENCY RESET COMPLETE",
                description="**ALL GAME DATA HAS BEEN WIPED**\n\nThe server is now in a fresh state.",
                color=0xff4444
            )
            
            total_deleted = sum(reset_results.values())
            embed.add_field(name="Total Items Deleted", value=str(total_deleted), inline=True)
            
            embed.add_field(
                name="🔄 To Restart:",
                value="1. `/admin setup` - Configure server\n2. `/galaxy generate` - Create new galaxy\n3. Players use `/character create`",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Notice",
                value="All players will need to create new characters. Previous game state is completely erased.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            print(f"🚨 EMERGENCY RESET: {interaction.user.name} wiped everything in {interaction.guild.name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Emergency reset failed: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user_id:
            await interaction.response.send_message("Only the admin who initiated this can cancel.", ephemeral=True)
            return
        
        await interaction.response.send_message("Emergency reset cancelled.", ephemeral=True)
class ServerResetConfirmView(discord.ui.View):
    def __init__(self, bot, admin_user_id: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.admin_user_id = admin_user_id
    
    @discord.ui.button(label="COMPLETE SERVER RESET - DELETE EVERYTHING", 
                      style=discord.ButtonStyle.danger, 
                      emoji="☠️")
    async def server_reset_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user_id:
            await interaction.response.send_message("Only the admin who initiated this can confirm.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            admin_cog = self.bot.get_cog('AdminCog')
            
            # Stop background tasks first
            await interaction.edit_original_response(
                content="🔄 **Server Reset in Progress**\n⏸️ Stopping background tasks...",
                embed=None, view=None
            )
            self.bot.stop_background_tasks()
            
            # Get server config before we delete it
            config = admin_cog.db.execute_query(
                """SELECT colony_category_id, station_category_id, outpost_category_id,
                          gate_category_id, transit_category_id, ship_interiors_category_id,
                          galactic_updates_channel_id, residences_category_id, status_voice_channel_id
                   FROM server_config WHERE guild_id = %s""",
                (interaction.guild.id,),
                fetch='one'
            )
            
            categories_to_delete = []
            channels_to_delete = []
            
            if config:
                # Collect category IDs
                category_ids = [config[0], config[1], config[2], config[3], config[4], config[5]]
                for cat_id in category_ids:
                    if cat_id:
                        category = interaction.guild.get_channel(cat_id)
                        if category and isinstance(category, discord.CategoryChannel):
                            categories_to_delete.append(category)
                
                # Collect special channels
                if config[6]:  # galactic_updates_channel_id
                    channel = interaction.guild.get_channel(config[6])
                    if channel:
                        channels_to_delete.append(channel)
                
                if config[7]:  # status_voice_channel_id
                    channel = interaction.guild.get_channel(config[7])
                    if channel:
                        channels_to_delete.append(channel)
            
            # Find the main galaxy category
            main_category_name = " ==== 🌌 GALAXY 🌌 ==== "
            for category in interaction.guild.categories:
                if category.name.strip() == main_category_name.strip() and category not in categories_to_delete:
                    categories_to_delete.append(category)
            
            # Update status
            await interaction.edit_original_response(
                content="🔄 **Server Reset in Progress**\n🗑️ Deleting channels and categories..."
            )
            
            # Delete all channels in categories first
            channels_deleted = 0
            for category in categories_to_delete:
                for channel in category.channels:
                    try:
                        await channel.delete(reason="Server reset - removing all bot channels")
                        channels_deleted += 1
                    except:
                        pass
            
            # Delete standalone channels
            for channel in channels_to_delete:
                try:
                    await channel.delete(reason="Server reset - removing bot channels")
                    channels_deleted += 1
                except:
                    pass
            
            # Delete categories
            categories_deleted = 0
            for category in categories_to_delete:
                try:
                    await category.delete(reason="Server reset - removing bot categories")
                    categories_deleted += 1
                except:
                    pass
            
            # Update status
            await interaction.edit_original_response(
                content=f"🔄 **Server Reset in Progress**\n"
                        f"✅ Deleted {channels_deleted} channels and {categories_deleted} categories\n"
                        f"💾 Resetting database..."
            )
            
            # Perform complete database reset
            reset_results = await admin_cog._perform_reset(interaction.guild, "full")
            
            # Also clear server config completely
            admin_cog.db.execute_query(
                "DELETE FROM server_config WHERE guild_id = %s",
                (interaction.guild.id,)
            )
            
            # Clear galaxy settings
            admin_cog.db.execute_query("DELETE FROM galaxy_settings")
            admin_cog.db.execute_query("DELETE FROM galaxy_info")
            
            # Clear any remaining tables that might not be in _perform_reset
            additional_tables_to_clear = [
                "game_panels", "news_queue", "galactic_history", 
                "endgame_config", "endgame_evacuations", "active_beacons",
                "afk_warnings", "search_cooldowns", "user_location_panels",
                "pvp_opt_outs", "pvp_combat_states", "pvp_cooldowns", 
                "pending_robberies", "character_inventory", "ship_activities",
                "player_ships", "repeaters", "corridor_events", "logbook_entries",
                "character_reputation", "character_experience", "character_identity",
                "home_invitations", "home_market_listings", "home_interiors", 
                "home_activities", "location_homes", "location_economy", 
                "economic_events", "location_ownership", "location_upgrades",
                "location_access_control", "location_income_log", "location_storage",
                "sub_locations", "black_markets", "black_market_items",
                "static_npcs", "dynamic_npcs", "npc_respawn_queue", "npc_inventory",
                "npc_trade_inventory", "npc_jobs", "npc_job_completions",
                "combat_states", "combat_encounters", "group_invites",
                "group_vote_sessions", "group_votes", "group_ships",
                "job_tracking", "ship_upgrades", "ship_customizations"
            ]

            for table in additional_tables_to_clear:
                try:
                    admin_cog.db.execute_query(f"DELETE FROM {table}")
                except:
                    pass  # Table might not exist
            
            # Final status update
            total_deleted = sum(reset_results.values())
            
            embed = discord.Embed(
                title="☠️ COMPLETE SERVER RESET SUCCESSFUL",
                description="The server has been returned to a fresh install state.",
                color=0x000000
            )
            
            embed.add_field(
                name="🗑️ Channels & Categories Deleted",
                value=f"• {channels_deleted} channels removed\n• {categories_deleted} categories removed",
                inline=True
            )
            
            embed.add_field(
                name="💾 Database Items Cleared",
                value=f"• {total_deleted} total database entries\n• All configurations reset",
                inline=True
            )
            
            embed.add_field(
                name="✅ Server Status",
                value="• Setup flag: Not configured\n• Galaxy: None\n• All data: Wiped",
                inline=False
            )
            
            embed.add_field(
                name="🔄 Next Steps",
                value="1. Run `/admin setup` to configure the server\n"
                      "2. Run `/galaxy generate` to create a new galaxy\n"
                      "3. Players can use `/character create` to start fresh",
                inline=False
            )
            
            await interaction.edit_original_response(content=None, embed=embed)
            
            # Resume background tasks
            await asyncio.sleep(1)
            self.bot.start_background_tasks()
            
            print(f"☠️ COMPLETE SERVER RESET: {interaction.user.name} reset {interaction.guild.name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Server reset failed: {str(e)}", ephemeral=True)
            # Make sure to restart background tasks even on error
            self.bot.start_background_tasks()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user_id:
            await interaction.response.send_message("Only the admin who initiated this can cancel.", ephemeral=True)
            return
        
        await interaction.response.send_message("Server reset cancelled. No changes were made.", ephemeral=True)

    @admin_group.command(name="migrate_npc_table", description="Create missing npc_job_completions table")
    async def migrate_npc_table(self, interaction: discord.Interaction):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Run the migration
            success = self.bot.db.migrate_npc_job_completions_table()
            
            if success:
                await interaction.followup.send("✅ Database migration completed successfully! The npc_job_completions table has been created.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Migration failed. Check console logs for details.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error during migration: {str(e)}", ephemeral=True)
            print(f"Migration command error: {e}")


        

async def setup(bot):
    await bot.add_cog(AdminCog(bot))