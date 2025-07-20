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


class LocationCreationModal(discord.ui.Modal):
    """Modal for additional location configuration"""
    def __init__(self, cog, location_data: dict):
        super().__init__(title="Configure Location Details")
        self.cog = cog
        self.location_data = location_data
        
        # Description field
        self.description = discord.ui.TextInput(
            label="Location Description",
            placeholder="Describe the location's atmosphere and features...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.description)
        
        # Population field
        self.population = discord.ui.TextInput(
            label="Population Size",
            placeholder="Number of inhabitants (e.g., 50000)",
            default=str(self._get_default_population()),
            required=True,
            max_length=10
        )
        self.add_item(self.population)
        
        # Number of Static NPCs
        self.npc_count = discord.ui.TextInput(
            label="Number of Static NPCs",
            placeholder="How many notable NPCs (e.g., 5-20)",
            default=str(self._get_default_npc_count()),
            required=True,
            max_length=3
        )
        self.add_item(self.npc_count)
    
    def _get_default_population(self) -> int:
        """Get default population based on location type and wealth"""
        base_pop = {
            'colony': 50000,
            'space_station': 10000,
            'outpost': 1000,
            'gate': 500
        }
        pop = base_pop.get(self.location_data['type'], 5000)
        # Adjust for wealth
        pop = int(pop * (self.location_data['wealth'] / 5))
        return pop
    
    def _get_default_npc_count(self) -> int:
        """Get default NPC count based on location type"""
        return {
            'colony': 15,
            'space_station': 12,
            'outpost': 8,
            'gate': 5
        }.get(self.location_data['type'], 10)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate and store additional data
            pop = int(self.population.value)
            if pop < 1 or pop > 10000000:
                await interaction.response.send_message("Population must be between 1 and 10,000,000", ephemeral=True)
                return
            
            npc_count = int(self.npc_count.value)
            if npc_count < 0 or npc_count > 100:
                await interaction.response.send_message("NPC count must be between 0 and 100", ephemeral=True)
                return
            
            self.location_data['description'] = self.description.value or ""
            self.location_data['population'] = pop
            self.location_data['npc_count'] = npc_count
            
            # Continue with location creation
            await self.cog._finalize_location_creation(interaction, self.location_data)
            
        except ValueError:
            await interaction.response.send_message("Invalid number format. Please enter valid numbers.", ephemeral=True)

class ServiceSelectionView(discord.ui.View):
    """View for selecting location services"""
    def __init__(self, cog, location_data: dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.location_data = location_data
        self.selected_services = set()
        self.sub_locations = []
        
        # Add service toggle buttons
        services = [
            ("💼 Jobs", "jobs"),
            ("🛒 Shops", "shops"),
            ("⚕️ Medical", "medical"),
            ("🔨 Repairs", "repairs"),
            ("⛽ Fuel", "fuel"),
            ("⬆️ Upgrades", "upgrades"),
            ("🚢 Shipyard", "shipyard")
        ]
        
        for label, service_id in services:
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=service_id,
                row=0 if services.index((label, service_id)) < 4 else 1
            )
            button.callback = self.create_service_callback(service_id)
            self.add_item(button)
        
        # Add sub-location selection dropdown
        self.add_sub_location_dropdown()
        
        # Add continue button
        continue_btn = discord.ui.Button(
            label="Continue",
            style=discord.ButtonStyle.primary,
            emoji="➡️",
            row=3
        )
        continue_btn.callback = self.continue_setup
        self.add_item(continue_btn)
    
    def add_sub_location_dropdown(self):
        """Add dropdown for sub-location selection"""
        # Get available sub-location types based on location type
        sub_location_options = self._get_sub_location_options()
        
        if sub_location_options:
            select = discord.ui.Select(
                placeholder="Select sub-locations (optional)",
                min_values=0,
                max_values=len(sub_location_options),
                options=sub_location_options,
                row=2
            )
            select.callback = self.sub_location_callback
            self.add_item(select)
    
    def _get_sub_location_options(self) -> List[discord.SelectOption]:
        """Get available sub-location options based on location type"""
        loc_type = self.location_data['type']
        wealth = self.location_data['wealth']
        
        # Sub-location types by location type
        options_map = {
            'colony': [
                ("🏛️ Administration", "administration"),
                ("🏪 Market District", "market_district"),
                ("🏨 Entertainment District", "entertainment_district"),
                ("🏭 Industrial Zone", "industrial_zone"),
                ("🏥 Medical District", "medical_district"),
                ("📚 Historical Archive", "historical_archive")
            ],
            'space_station': [
                ("🎯 Command Center", "command_center"),
                ("🔬 Research Lab", "research_lab"),
                ("🏪 Promenade", "promenade"),
                ("🛠️ Engineering Bay", "engineering_bay"),
                ("🏥 Med Bay", "med_bay")
            ],
            'outpost': [
                ("📡 Communications", "communications"),
                ("🏪 Trading Post", "trading_post"),
                ("🛡️ Security Office", "security_office"),
                ("🔧 Maintenance Bay", "maintenance_bay")
            ],
            'gate': [
                ("🎛️ Control Room", "control_room"),
                ("🚨 Security Checkpoint", "security_checkpoint"),
                ("🏪 Duty Free Shop", "duty_free_shop")
            ]
        }
        
        options = []
        for label, value in options_map.get(loc_type, []):
            # Filter by wealth requirements
            if value in ["entertainment_district", "research_lab"] and wealth < 6:
                continue
            if value in ["historical_archive", "command_center"] and wealth < 7:
                continue
            
            options.append(discord.SelectOption(label=label, value=value))
        
        return options
    
    def create_service_callback(self, service_id: str):
        async def callback(interaction: discord.Interaction):
            # Toggle service selection
            button = discord.utils.get(self.children, custom_id=service_id)
            if service_id in self.selected_services:
                self.selected_services.remove(service_id)
                button.style = discord.ButtonStyle.secondary
            else:
                self.selected_services.add(service_id)
                button.style = discord.ButtonStyle.success
            
            await interaction.response.edit_message(view=self)
        return callback
    
    async def sub_location_callback(self, interaction: discord.Interaction):
        self.sub_locations = interaction.data['values']
        await interaction.response.edit_message(view=self)
    
    async def continue_setup(self, interaction: discord.Interaction):
        # Store selected services
        self.location_data['services'] = {
            'has_jobs': 'jobs' in self.selected_services,
            'has_shops': 'shops' in self.selected_services,
            'has_medical': 'medical' in self.selected_services,
            'has_repairs': 'repairs' in self.selected_services,
            'has_fuel': 'fuel' in self.selected_services,
            'has_upgrades': 'upgrades' in self.selected_services,
            'has_shipyard': 'shipyard' in self.selected_services
        }
        self.location_data['sub_locations'] = self.sub_locations
        
        # Show the configuration modal
        modal = LocationCreationModal(self.cog, self.location_data)
        await interaction.response.send_modal(modal)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    admin_group = app_commands.Group(name="admin", description="Administrative commands")
    
    
    @admin_group.command(name="afk", description="Trigger AFK warning for a player")
    @app_commands.describe(player="Player to send AFK warning to")
    async def admin_afk_warning(self, interaction: discord.Interaction, player: discord.Member):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if player has a character and is logged in
        char_info = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = ?",
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
            "SELECT warning_id FROM afk_warnings WHERE user_id = ? AND is_active = 1",
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.send_message("🔧 Starting server setup...", ephemeral=True)
        
        # Check if setup already completed
        existing_config = self.db.execute_query(
            "SELECT setup_completed FROM server_config WHERE guild_id = ?",
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
                "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = ?",
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
                            "UPDATE server_config SET galactic_updates_channel_id = ? WHERE guild_id = ?",
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
                "SELECT status_voice_channel_id FROM server_config WHERE guild_id = ?",
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
                    "SELECT guild_id FROM server_config WHERE guild_id = ?",
                    (interaction.guild.id,),
                    fetch='one'
                )
                
                if existing_config:
                    self.db.execute_query(
                        "UPDATE server_config SET galactic_updates_channel_id = ? WHERE guild_id = ?",
                        (news_channel.id, interaction.guild.id)
                    )
                else:
                    self.db.execute_query(
                        "INSERT INTO server_config (guild_id, galactic_updates_channel_id) VALUES (?, ?)",
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
                '''INSERT OR REPLACE INTO server_config 
                   (guild_id, colony_category_id, station_category_id, outpost_category_id, 
                    gate_category_id, transit_category_id, ship_interiors_category_id, residences_category_id, galactic_updates_channel_id, 
                    status_voice_channel_id, setup_completed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
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
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Show warning with confirmation view
        view = ServerResetConfirmView(self.bot, interaction.user.id)
        
        embed = discord.Embed(
            title="🚨 COMPLETE SERVER RESET",
            description="This will **PERMANENTLY DELETE**:\n\n"
                        "• ALL bot-created channels and categories\n"
                        "• ALL player characters and ships\n"
                        "• ALL locations and corridors\n"
                        "• ALL jobs, inventory, and groups\n"
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
               FROM server_config WHERE guild_id = ?''',
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
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
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
                "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)",
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

    @admin_group.command(name="create_item", description="Create a new item and add to location shop or player inventory")
    @app_commands.describe(
        item_name="Name of the item",
        item_type="Type of item",
        description="Item description", 
        value="Base value of the item",
        location_name="Location to add item shop (ignored if giving to player)",
        player="Player to give item to (ignored if adding to shop)",
        price="Price in shop (ignored if giving to player)",
        stock="Stock amount for shop (ignored if giving to player)",
        quantity="Quantity to give to player (ignored if adding to shop)",
        usage_type="How the item can be used",
        effect_value="Effect value (healing amount, fuel amount, etc)",
        uses_remaining="Number of uses for multi-use items",
        rarity="Item rarity level"
    )
    @app_commands.choices(
        item_type=[
            app_commands.Choice(name="Consumable", value="consumable"),
            app_commands.Choice(name="Equipment", value="equipment"), 
            app_commands.Choice(name="Medical", value="medical"),
            app_commands.Choice(name="Fuel", value="fuel"),
            app_commands.Choice(name="Trade", value="trade"),
            app_commands.Choice(name="Upgrade", value="upgrade")
        ],
        usage_type=[
            app_commands.Choice(name="Heal HP", value="heal_hp"),
            app_commands.Choice(name="Restore Fuel", value="restore_fuel"),
            app_commands.Choice(name="Repair Hull", value="repair_hull"),
            app_commands.Choice(name="Restore Energy", value="restore_energy"),
            app_commands.Choice(name="Temporary Boost", value="temp_boost"),
            app_commands.Choice(name="Ship Upgrade", value="upgrade_ship"),
            app_commands.Choice(name="Emergency Signal", value="emergency_signal"),
            app_commands.Choice(name="Narrative Only", value="narrative"),
            app_commands.Choice(name="No Usage", value="none")
        ],
        rarity=[
            app_commands.Choice(name="Common", value="common"),
            app_commands.Choice(name="Uncommon", value="uncommon"),
            app_commands.Choice(name="Rare", value="rare"),
            app_commands.Choice(name="Legendary", value="legendary")
        ]
    )
    async def create_item(self, interaction: discord.Interaction, item_name: str, item_type: str,
                         description: str, value: int, location_name: str = None,
                         player: discord.Member = None, price: int = None, stock: int = None,
                         quantity: int = 1, usage_type: str = "none", effect_value: str = None,
                         uses_remaining: int = None, rarity: str = "common"):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not location_name and not player:
            await interaction.response.send_message("Must specify either a location or a player.", ephemeral=True)
            return
        
        if location_name and player:
            await interaction.response.send_message("Cannot specify both location and player.", ephemeral=True)
            return
        
        # Create metadata
        import json
        metadata = {
            "usage_type": usage_type if usage_type != "none" else None,
            "effect_value": effect_value,
            "single_use": True if usage_type and usage_type != "narrative" and not uses_remaining else False,
            "uses_remaining": uses_remaining,
            "rarity": rarity
        }
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        metadata_str = json.dumps(metadata)
        
        if player:
            # Give item to player
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = ?",
                (player.id,),
                fetch='one'
            )
            
            if not char_check:
                await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
                return
            
            # Add to player inventory
            existing_item = self.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                (player.id, item_name),
                fetch='one'
            )
            
            if existing_item:
                self.db.execute_query(
                    "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
                    (quantity, existing_item[0])
                )
            else:
                self.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (player.id, item_name, item_type, quantity, description, value, metadata_str)
                )
            
            embed = discord.Embed(
                title="✅ Item Created",
                description=f"Gave {quantity}x **{item_name}** to {player.mention}",
                color=0x00ff00
            )
            embed.add_field(name="Type", value=item_type.title(), inline=True)
            embed.add_field(name="Value", value=f"{value} credits each", inline=True)
            embed.add_field(name="Usage", value=usage_type.replace('_', ' ').title() if usage_type != "none" else "No usage", inline=True)
            
        else:
            # Add to location shop
            location = self.db.execute_query(
                "SELECT location_id FROM locations WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{location_name}%",),
                fetch='one'
            )
            
            if not location:
                await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
                return
            
            location_id = location[0]
            
            # Set default price and stock if not provided
            if price is None:
                price = int(value * 1.5)  # 50% markup
            if stock is None:
                stock = 5
            
            # Check if item already exists in shop
            existing_item = self.db.execute_query(
                "SELECT item_id, stock FROM shop_items WHERE location_id = ? AND LOWER(item_name) = LOWER(?)",
                (location_id, item_name),
                fetch='one'
            )
            
            if existing_item:
                shop_item_id, current_stock = existing_item
                new_stock = current_stock + stock if current_stock != -1 else -1
                self.db.execute_query(
                    "UPDATE shop_items SET stock = ?, metadata = ? WHERE item_id = ?",
                    (new_stock, metadata_str, shop_item_id)
                )
            else:
                self.db.execute_query(
                    '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (location_id, item_name, item_type, price, stock, description, metadata_str)
                )
            
            embed = discord.Embed(
                title="✅ Item Created",
                description=f"Added **{item_name}** to shop at {location_name}",
                color=0x00ff00
            )
            embed.add_field(name="Price", value=f"{price} credits", inline=True)
            embed.add_field(name="Stock", value=str(stock), inline=True)
            embed.add_field(name="Usage", value=usage_type.replace('_', ' ').title() if usage_type != "none" else "No usage", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    debug_group = app_commands.Group(name="debug", description="Additional administrative debug commands")
    
    @debug_group.command(name="setmoney", description="Set a player's money to a specific amount")
    @app_commands.describe(
        player="The player whose money to set",
        amount="The amount of money to set"
    )
    async def set_money(self, interaction: discord.Interaction, player: discord.Member, amount: int):
        """Set a player's money to a specific amount"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if player has a character
        char_data = self.db.execute_query(
            "SELECT name, money FROM characters WHERE user_id = ?",
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
            "UPDATE characters SET money = ? WHERE user_id = ?",
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if player has a character
        char_data = self.db.execute_query(
            "SELECT name, experience, level, skill_points FROM characters WHERE user_id = ?",
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
               SET experience = ?, level = ?, skill_points = ?, 
                   max_hp = max_hp + ?, hp = CASE 
                       WHEN hp + ? > max_hp + ? THEN max_hp + ?
                       WHEN hp + ? < 1 THEN 1
                       ELSE hp + ?
                   END
               WHERE user_id = ?""",
            (amount, new_level, new_skill_points, 
             hp_difference, hp_difference, hp_difference, hp_difference, 
             hp_difference, hp_difference, player.id)
        )
        
        # Get updated HP for display
        updated_hp_data = self.db.execute_query(
            "SELECT hp, max_hp FROM characters WHERE user_id = ?",
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
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
                        "UPDATE shop_items SET metadata = ? WHERE item_id = ?",
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
                        "UPDATE inventory SET metadata = ? WHERE item_id = ?",
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
    
    async def create_job(self, interaction: discord.Interaction, location_name: str, title: str, 
                        description: str, reward: int, duration: int, danger_level: int,
                        required_skill: str = None, min_skill_level: int = 0, expires_hours: int = 8):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{location_name}%",),
            fetch='one'
        )
        
        if not location:
            await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
            return
        
        location_id, actual_name = location
        
        # Determine job type based on title/description
        is_travel_job = any(word in title.lower() for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger']) or any(word in description.lower() for word in ['transport', 'deliver', 'take to', 'bring to'])
        job_type = 'travel' if is_travel_job else 'stationary'
        
        from datetime import datetime, timedelta
        expire_time = datetime.now() + timedelta(hours=expires_hours)
        
        self.db.execute_query(
            '''INSERT INTO jobs
               (location_id, title, description, reward_money, required_skill,
                min_skill_level, danger_level, duration_minutes, expires_at, is_taken)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)''',
            (
                location_id,
                title,
                description,
                reward,
                required_skill,
                min_skill_level,
                danger_level,
                duration,
                expire_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        
        embed = discord.Embed(
            title="✅ Job Created",
            description=f"Created job at **{actual_name}**",
            color=0x00ff00
        )
        embed.add_field(name="Title", value=title, inline=False)
        embed.add_field(name="Type", value=job_type.title(), inline=True)
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger_level, inline=True)
        embed.add_field(name="Expires", value=f"<t:{int(expire_time.timestamp())}:R>", inline=True)
        
        if required_skill:
            embed.add_field(name="Skill Requirement", value=f"{required_skill.title()} Level {min_skill_level}+", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @admin_group.command(name="teleport", description="Teleport a character to a different location")
    @app_commands.describe(
        player="Player to teleport",
        destination="Destination location name"
    )
    async def teleport_character(self, interaction: discord.Interaction, player: discord.Member, destination: str):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if player has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (player.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
            return
        
        current_location_id, char_name = char_info
        
        # Find destination location
        dest_location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)",
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
            "SELECT name FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )[0] if current_location_id else "Unknown"
        
        # Cancel any active travel
        self.db.execute_query(
            "UPDATE travel_sessions SET status = 'admin_teleport' WHERE user_id = ? AND status = 'traveling'",
            (player.id,)
        )
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_location = ? WHERE user_id = ?",
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if server config exists, create if not
        existing_config = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE guild_id = ?",
            (interaction.guild.id,),
            fetch='one'
        )
        
        if existing_config:
            # Update existing config
            self.db.execute_query(
                "UPDATE server_config SET galactic_updates_channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild.id)
            )
        else:
            # Create new config entry with just the guild_id and updates channel
            self.db.execute_query(
                """INSERT INTO server_config 
                   (guild_id, galactic_updates_channel_id) 
                   VALUES (?, ?)""",
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🤖 NPC Debug Information", color=0x9b59b6)
        
        if npc_type in ["static", "all"]:
            if location_id:
                static_npcs = self.db.execute_query(
                    """SELECT s.name, s.age, s.occupation, l.name as location_name
                       FROM static_npcs s
                       JOIN locations l ON s.location_id = l.location_id
                       WHERE s.location_id = ?
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
                       WHERE n.current_location = ? OR n.destination_location = ?
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
                       COALESCE(SUM(CASE WHEN is_alive = 1 THEN 1 ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN travel_start_time IS NOT NULL AND is_alive = 1 THEN 1 ELSE 0 END), 0)
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
                       WHERE n.is_alive = 1 AND n.travel_start_time IS NULL
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

    @admin_group.command(name="spawn_dynamic_npc", description="Manually spawn a dynamic NPC")
    async def spawn_dynamic_npc(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            await interaction.response.send_message("NPC system not available!", ephemeral=True)
            return
        
        npc_id = await npc_cog.create_dynamic_npc()
        if npc_id:
            npc_info = self.db.execute_query(
                "SELECT name, callsign, ship_name FROM dynamic_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            name, callsign, ship_name = npc_info
            await interaction.response.send_message(
                f"✅ Spawned dynamic NPC: **{name}** ({callsign}) aboard *{ship_name}*",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Failed to spawn dynamic NPC", ephemeral=True)

    @admin_group.command(name="kill_npc", description="Kill a dynamic NPC")
    @app_commands.describe(callsign="Callsign of the NPC to kill")
    async def kill_npc(self, interaction: discord.Interaction, callsign: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Find the NPC
        npc_info = self.db.execute_query(
            "SELECT npc_id, name, is_alive FROM dynamic_npcs WHERE callsign = ?",
            (callsign.upper(),),
            fetch='one'
        )
        
        if not npc_info:
            await interaction.response.send_message(f"❌ No NPC found with callsign {callsign}", ephemeral=True)
            return
        
        npc_id, name, is_alive = npc_info
        
        if not is_alive:
            await interaction.response.send_message(f"❌ {name} ({callsign}) is already dead!", ephemeral=True)
            return
        
        # Kill the NPC
        self.db.execute_query(
            "UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?",
            (npc_id,)
        )
        
        await interaction.response.send_message(
            f"💀 Killed dynamic NPC: **{name}** ({callsign})",
            ephemeral=True
        )

# Add this to your admin.py file in the AdminCog class

    @admin_group.command(name="ship_diagnostic", description="Diagnose ship/fuel issues for a player")
    @app_commands.describe(player="The player to diagnose")
    async def ship_diagnostic(self, interaction: discord.Interaction, player: discord.Member = None):
        """Diagnose ship and fuel issues"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        target = player or interaction.user
        
        # Get character data
        char_data = self.db.execute_query(
            "SELECT name, ship_id, active_ship_id FROM characters WHERE user_id = ?",
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
               WHERE ps.owner_id = ? AND ps.is_active = 1''',
            (target.id,),
            fetch='one'
        )
        
        # Check fuel using old ship_id
        old_fuel_check = self.db.execute_query(
            '''SELECT s.current_fuel, s.fuel_capacity, s.name
               FROM characters c
               JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.user_id = ?''',
            (target.id,),
            fetch='one'
        )
        
        # Check fuel using active_ship_id
        active_fuel_check = self.db.execute_query(
            '''SELECT s.current_fuel, s.fuel_capacity, s.name
               FROM characters c
               JOIN ships s ON c.active_ship_id = s.ship_id
               WHERE c.user_id = ?''',
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Get configuration
        config = self.db.execute_query(
            "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = ?",
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
            "SELECT COUNT(*) FROM news_queue WHERE guild_id = ? AND is_delivered = 0",
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
            "SELECT COUNT(*) FROM news_queue WHERE guild_id = ? AND created_at > datetime('now', '-24 hours')",
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
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
                "SELECT 1 FROM player_ships WHERE owner_id = ? AND ship_id = ?",
                (user_id, ship_id),
                fetch='one'
            )
            
            if not exists_in_player_ships:
                # Add to player_ships
                self.db.execute_query(
                    "INSERT INTO player_ships (owner_id, ship_id, is_active) VALUES (?, ?, 1)",
                    (user_id, ship_id)
                )
                fixed_count += 1
            else:
                # Make sure it's active
                self.db.execute_query(
                    "UPDATE player_ships SET is_active = 1 WHERE owner_id = ? AND ship_id = ?",
                    (user_id, ship_id)
                )
            
            # Deactivate any other ships for this player
            self.db.execute_query(
                "UPDATE player_ships SET is_active = 0 WHERE owner_id = ? AND ship_id != ?",
                (user_id, ship_id)
            )
            
            # Update character's ship_id and active_ship_id
            self.db.execute_query(
                "UPDATE characters SET ship_id = ?, active_ship_id = ? WHERE user_id = ?",
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
        
    @admin_group.command(name="create_location", description="Create a custom location with full configuration")
    @app_commands.describe(
        name="Name of the location",
        location_type="Type of location",
        wealth="Wealth level 1-10",
        faction="Faction alignment",
        connect_to="Location to connect this to"
    )
    @app_commands.choices(
        location_type=[
            Choice(name="Colony", value="colony"),
            Choice(name="Space Station", value="space_station"),
            Choice(name="Outpost", value="outpost"),
            Choice(name="Gate", value="gate")
        ],
        faction=[
            Choice(name="Loyalist (Federal)", value="loyalist"),
            Choice(name="Outlaw (Bandit)", value="outlaw"),
            Choice(name="Independent", value="independent")
        ]
    )
    async def create_location(self, interaction: discord.Interaction, 
                             name: str, 
                             location_type: str,
                             wealth: app_commands.Range[int, 1, 10],
                             faction: str,
                             connect_to: str):
        """Create a fully configured custom location"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Find the connection location
        connection = self.db.execute_query(
            """SELECT location_id, name, x_coord, y_coord, location_type 
               FROM locations 
               WHERE LOWER(name) LIKE LOWER(?)""",
            (f"%{connect_to}%",),
            fetch='one'
        )
        
        if not connection:
            await interaction.response.send_message(
                f"Connection location '{connect_to}' not found.",
                ephemeral=True
            )
            return
        
        connect_id, connect_name, connect_x, connect_y, connect_type = connection
        
        # Generate coordinates near the connection
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(5, 15)
        x_coord = connect_x + distance * math.cos(angle)
        y_coord = connect_y + distance * math.sin(angle)
        
        # Prepare location data
        location_data = {
            'name': name,
            'type': location_type,
            'wealth': wealth,
            'faction': faction,
            'x_coord': x_coord,
            'y_coord': y_coord,
            'connect_to_id': connect_id,
            'connect_to_name': connect_name,
            'guild': interaction.guild,
            'user': interaction.user
        }
        
        # Show service selection view
        view = ServiceSelectionView(self, location_data)
        embed = discord.Embed(
            title="🏗️ Configure Location Services",
            description=f"Setting up **{name}** ({location_type})\n"
                        f"Wealth Level: {wealth}/10\n"
                        f"Faction: {faction.title()}\n"
                        f"Connecting to: {connect_name}",
            color=0x00ff00
        )
        embed.add_field(
            name="📋 Instructions",
            value="1. Click buttons to toggle services\n"
                  "2. Select sub-locations from dropdown\n"
                  "3. Click Continue when ready",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _finalize_location_creation(self, interaction: discord.Interaction, location_data: dict):
        """Finalize the location creation process"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Start transaction for safety
            conn = self.db.get_connection()
            
            # Create the location
            location_id = self.db.execute_in_transaction(
                conn,
                """INSERT INTO locations 
                   (name, location_type, description, wealth_level, population,
                    x_coord, y_coord,
                    has_jobs, has_shops, has_medical, has_repairs, has_fuel, 
                    has_upgrades, has_shipyard,
                    has_federal_supplies, has_black_market,
                    created_at, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 0)""",
                (
                    location_data['name'],
                    location_data['type'],
                    location_data.get('description', ''),
                    location_data['wealth'],
                    location_data.get('population', 10000),
                    location_data['x_coord'],
                    location_data['y_coord'],
                    location_data['services']['has_jobs'],
                    location_data['services']['has_shops'],
                    location_data['services']['has_medical'],
                    location_data['services']['has_repairs'],
                    location_data['services']['has_fuel'],
                    location_data['services']['has_upgrades'],
                    location_data['services']['has_shipyard'],
                    location_data['faction'] == 'loyalist',
                    location_data['faction'] == 'outlaw'
                ),
                return_last_id=True
            )
            
            # Create sub-locations
            for sub_type in location_data.get('sub_locations', []):
                sub_name = self._get_sub_location_name(sub_type)
                sub_desc = self._get_sub_location_description(sub_type)
                
                self.db.execute_in_transaction(
                    conn,
                    """INSERT INTO sub_locations 
                       (parent_location_id, name, sub_type, description, is_active)
                       VALUES (?, ?, ?, ?, 1)""",
                    (location_id, sub_name, sub_type, sub_desc)
                )
            
            # Create static NPCs
            npc_count = location_data.get('npc_count', 10)
            if npc_count > 0:
                npc_cog = self.bot.get_cog('NPCCog')
                if npc_cog:
                    # Generate NPC data
                    npc_data_list = npc_cog.generate_static_npc_batch_data(
                        location_id,
                        location_data.get('population', 10000),
                        location_data['type'],
                        location_data['wealth'],
                        location_data['faction'] == 'outlaw'
                    )
                    
                    # Limit to requested count
                    npc_data_list = npc_data_list[:npc_count]
                    
                    # Insert NPCs
                    self.db.executemany_in_transaction(
                        conn,
                        """INSERT INTO static_npcs 
                           (location_id, name, age, occupation, personality, alignment, 
                            hp, max_hp, combat_rating, credits)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        npc_data_list
                    )
            
            # Create the gate if it's a gate location
            if location_data['type'] == 'gate':
                # Gates connect to themselves for the main corridor
                pass  # Gate handling is done in corridor creation
            
            # Commit the location creation
            self.db.commit_transaction(conn)
            
            # Now create corridors (outside transaction to avoid locks)
            await self._create_location_corridors(
                location_id, 
                location_data['name'],
                location_data['type'],
                location_data['connect_to_id'],
                location_data['connect_to_name'],
                location_data['x_coord'],
                location_data['y_coord']
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Location Created Successfully",
                description=f"**{location_data['name']}** has been created and integrated into the galaxy!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📍 Location Details",
                value=f"Type: {location_data['type'].replace('_', ' ').title()}\n"
                      f"Wealth: {location_data['wealth']}/10\n"
                      f"Population: {location_data.get('population', 10000):,}\n"
                      f"Faction: {location_data['faction'].title()}",
                inline=True
            )
            
            embed.add_field(
                name="🛠️ Services",
                value=self._format_services(location_data['services']),
                inline=True
            )
            
            if location_data.get('sub_locations'):
                embed.add_field(
                    name="🏢 Sub-Locations",
                    value="\n".join([f"• {self._get_sub_location_name(s)}" 
                                   for s in location_data['sub_locations']]),
                    inline=False
                )
            
            embed.add_field(
                name="🤖 NPCs",
                value=f"{location_data.get('npc_count', 0)} static NPCs created",
                inline=True
            )
            
            embed.add_field(
                name="🗺️ Connections",
                value=f"Connected to {location_data['connect_to_name']} and 2-5 other locations",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if 'conn' in locals():
                self.db.rollback_transaction(conn)
            
            await interaction.followup.send(
                f"❌ Error creating location: {str(e)}",
                ephemeral=True
            )

    async def _create_location_corridors(self, location_id: int, location_name: str, 
                                       location_type: str, connect_to_id: int, 
                                       connect_to_name: str, x: float, y: float):
        """Create corridors connecting the new location to the galaxy"""
        
        # Get connection location details
        connect_info = self.db.execute_query(
            "SELECT x_coord, y_coord, location_type FROM locations WHERE location_id = ?",
            (connect_to_id,),
            fetch='one'
        )
        
        if not connect_info:
            return
        
        cx, cy, connect_type = connect_info
        distance = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        # Create primary connection
        if location_type == 'gate' or connect_type == 'gate':
            # Create gated corridor segments
            await self._create_gated_corridor(
                location_id, location_name, location_type,
                connect_to_id, connect_to_name, connect_type,
                distance
            )
        else:
            # Create ungated corridor
            travel_time = int(distance * 60) + random.randint(300, 600)
            fuel_cost = int(distance * 2) + random.randint(10, 30)
            danger_level = min(5, max(1, int(distance / 10) + 2))
            
            # Create bidirectional corridors
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time,
                    fuel_cost, danger_level, is_active, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                (f"{location_name} - {connect_to_name} Route (Ungated)",
                 location_id, connect_to_id, travel_time, fuel_cost, danger_level)
            )
            
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time,
                    fuel_cost, danger_level, is_active, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                (f"{connect_to_name} - {location_name} Route (Ungated)",
                 connect_to_id, location_id, travel_time, fuel_cost, danger_level)
            )
        
        # Add 2-5 random connections to existing locations
        await self._add_random_connections(location_id, location_name, x, y, location_type)

    async def _create_gated_corridor(self, loc1_id: int, loc1_name: str, loc1_type: str,
                                   loc2_id: int, loc2_name: str, loc2_type: str,
                                   distance: float):
        """Create a gated corridor with all segments"""
        
        # Determine which location is the gate
        if loc1_type == 'gate':
            gate_id, gate_name = loc1_id, loc1_name
            other_id, other_name = loc2_id, loc2_name
        elif loc2_type == 'gate':
            gate_id, gate_name = loc2_id, loc2_name
            other_id, other_name = loc1_id, loc1_name
        else:
            # Neither is a gate, create a route through nearest gate
            nearest_gate = self._find_nearest_gate(loc1_id, loc2_id)
            if nearest_gate:
                gate_id, gate_name = nearest_gate
                # Create routes from both locations to the gate
                await self._create_gated_corridor(loc1_id, loc1_name, loc1_type,
                                                gate_id, gate_name, 'gate', distance/2)
                await self._create_gated_corridor(loc2_id, loc2_name, loc2_type,
                                                gate_id, gate_name, 'gate', distance/2)
                return
            else:
                # No gates available, fall back to ungated
                return
        
        # Calculate times
        approach_time = int(distance * 20) + random.randint(180, 300)
        arrival_time = approach_time
        
        # Create approach corridor
        self.db.execute_query(
            """INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time,
                fuel_cost, danger_level, is_active, is_generated)
               VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
            (f"{gate_name} Approach", other_id, gate_id, approach_time, 
             int(distance * 0.5) + 5, 1)
        )
        
        # Create arrival corridor
        self.db.execute_query(
            """INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time,
                fuel_cost, danger_level, is_active, is_generated)
               VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
            (f"{gate_name} Arrival", gate_id, other_id, arrival_time,
             int(distance * 0.5) + 5, 1)
        )
        
        # If connecting two non-gate locations through a gate, create gate-to-gate corridor
        if loc1_type != 'gate' and loc2_type != 'gate':
            # This would be handled by the recursive calls above
            pass

    async def _add_random_connections(self, location_id: int, location_name: str,
                                    x: float, y: float, location_type: str):
        """Add 2-5 random connections to nearby locations"""
        
        # Find nearby locations
        nearby = self.db.execute_query(
            """SELECT location_id, name, x_coord, y_coord, location_type
               FROM locations
               WHERE location_id != ?
               AND ABS(x_coord - ?) < 30
               AND ABS(y_coord - ?) < 30
               ORDER BY RANDOM()
               LIMIT 10""",
            (location_id, x, y),
            fetch='all'
        )
        
        if not nearby:
            return
        
        # Create 2-5 connections
        num_connections = random.randint(2, min(5, len(nearby)))
        for i in range(num_connections):
            other_id, other_name, ox, oy, other_type = nearby[i]
            
            # Check if corridor already exists
            existing = self.db.execute_query(
                """SELECT corridor_id FROM corridors
                   WHERE (origin_location = ? AND destination_location = ?)
                   OR (origin_location = ? AND destination_location = ?)""",
                (location_id, other_id, other_id, location_id),
                fetch='one'
            )
            
            if existing:
                continue
            
            distance = math.sqrt((x - ox)**2 + (y - oy)**2)
            
            # Decide corridor type
            if location_type == 'gate' or other_type == 'gate':
                await self._create_gated_corridor(
                    location_id, location_name, location_type,
                    other_id, other_name, other_type,
                    distance
                )
            else:
                # Create ungated corridor with higher danger
                travel_time = int(distance * 80) + random.randint(400, 800)
                fuel_cost = int(distance * 3) + random.randint(20, 50)
                danger_level = min(5, max(3, int(distance / 8) + 2))
                
                corridor_name = f"{location_name} - {other_name} Route"
                
                # Bidirectional
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, is_active, is_generated)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                    (f"{corridor_name} (Ungated)", location_id, other_id,
                     travel_time, fuel_cost, danger_level)
                )
                
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, is_active, is_generated)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                    (f"{other_name} - {location_name} Route (Ungated)", 
                     other_id, location_id, travel_time, fuel_cost, danger_level)
                )

    def _find_nearest_gate(self, loc1_id: int, loc2_id: int) -> Optional[tuple]:
        """Find the nearest gate to route through"""
        result = self.db.execute_query(
            """SELECT g.location_id, g.name
               FROM locations g
               JOIN locations l1 ON l1.location_id = ?
               JOIN locations l2 ON l2.location_id = ?
               WHERE g.location_type = 'gate'
               ORDER BY (ABS(g.x_coord - l1.x_coord) + ABS(g.y_coord - l1.y_coord) +
                        ABS(g.x_coord - l2.x_coord) + ABS(g.y_coord - l2.y_coord))
               LIMIT 1""",
            (loc1_id, loc2_id),
            fetch='one'
        )
        return result if result else None

    def _get_sub_location_name(self, sub_type: str) -> str:
        """Get the display name for a sub-location type"""
        names = {
            'administration': 'Administration',
            'market_district': 'Market District',
            'entertainment_district': 'Entertainment District',
            'industrial_zone': 'Industrial Zone',
            'medical_district': 'Medical District',
            'historical_archive': 'Historical Archive',
            'command_center': 'Command Center',
            'research_lab': 'Research Lab',
            'promenade': 'Promenade',
            'engineering_bay': 'Engineering Bay',
            'med_bay': 'Med Bay',
            'communications': 'Communications',
            'trading_post': 'Trading Post',
            'security_office': 'Security Office',
            'maintenance_bay': 'Maintenance Bay',
            'control_room': 'Control Room',
            'security_checkpoint': 'Security Checkpoint',
            'duty_free_shop': 'Duty Free Shop'
        }
        return names.get(sub_type, sub_type.replace('_', ' ').title())

    def _get_sub_location_description(self, sub_type: str) -> str:
        """Get the description for a sub-location type"""
        descriptions = {
            'administration': 'The bureaucratic heart of the location, handling permits and documentation.',
            'market_district': 'A bustling commercial area with shops and traders.',
            'entertainment_district': 'Bars, clubs, and entertainment venues for off-duty personnel.',
            'industrial_zone': 'Manufacturing and industrial facilities.',
            'medical_district': 'Advanced medical facilities and research centers.',
            'historical_archive': 'A repository of historical records and cultural artifacts.',
            'command_center': 'The strategic command hub for station operations.',
            'research_lab': 'Cutting-edge research facilities and laboratories.',
            'promenade': 'A central hub with shops, restaurants, and social spaces.',
            'engineering_bay': 'Technical workshops and engineering facilities.',
            'med_bay': 'Medical treatment and emergency care facilities.',
            'communications': 'Communication arrays and message relay systems.',
            'trading_post': 'A hub for traders and merchants.',
            'security_office': 'Local security and law enforcement headquarters.',
            'maintenance_bay': 'Repair and maintenance facilities.',
            'control_room': 'Gate operations and navigation control.',
            'security_checkpoint': 'Security screening and customs.',
            'duty_free_shop': 'Tax-free shopping for travelers.'
        }
        return descriptions.get(sub_type, f"A {sub_type.replace('_', ' ')} area.")

    def _format_services(self, services: dict) -> str:
        """Format services dictionary into a readable string"""
        active_services = []
        service_names = {
            'has_jobs': '💼 Jobs',
            'has_shops': '🛒 Shops',
            'has_medical': '⚕️ Medical',
            'has_repairs': '🔨 Repairs',
            'has_fuel': '⛽ Fuel',
            'has_upgrades': '⬆️ Upgrades',
            'has_shipyard': '🚢 Shipyard'
        }
        
        for key, name in service_names.items():
            if services.get(key, False):
                active_services.append(name)
        
        return '\n'.join(active_services) if active_services else "No services"
    
    @admin_group.command(name="cleanup_channels", description="Manually trigger cleanup of unused location channels")
    @app_commands.describe(force="Force cleanup even for recently used channels")
    async def cleanup_channels(self, interaction: discord.Interaction, force: bool = False):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
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
    
# Add this to admin.py

    @admin_group.command(name="fix_ship_activities", description="Generate activities for ships that don't have them")
    async def fix_ship_activities(self, interaction: discord.Interaction):
        """Generate ship activities for all ships missing them"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
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
    
    @admin_group.command(name="create_corridor", description="Create a corridor between locations")
    @app_commands.describe(
        origin="Origin location name",
        destination="Destination location name", 
        corridor_name="Name of the corridor",
        travel_time="Travel time in seconds",
        fuel_cost="Fuel cost for travel",
        danger_level="Danger level 1-5"
    )
    async def create_corridor(self, interaction: discord.Interaction, origin: str, destination: str,
                             corridor_name: str, travel_time: int = 300, fuel_cost: int = 20, 
                             danger_level: int = 3):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Find locations by name (case insensitive)
        origin_loc = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)", 
            (f"%{origin}%",), 
            fetch='one'
        )
        dest_loc = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)", 
            (f"%{destination}%",), 
            fetch='one'
        )
        
        if not origin_loc:
            await interaction.response.send_message(f"Origin location '{origin}' not found.", ephemeral=True)
            return
        
        if not dest_loc:
            await interaction.response.send_message(f"Destination location '{destination}' not found.", ephemeral=True)
            return
        
        if origin_loc[0] == dest_loc[0]:
            await interaction.response.send_message("Origin and destination cannot be the same.", ephemeral=True)
            return
        
        # Check if corridor already exists
        existing = self.db.execute_query(
            '''SELECT corridor_id FROM corridors 
               WHERE origin_location = ? AND destination_location = ?''',
            (origin_loc[0], dest_loc[0]),
            fetch='one'
        )
        
        if existing:
            await interaction.response.send_message(
                f"Corridor from {origin_loc[1]} to {dest_loc[1]} already exists.",
                ephemeral=True
            )
            return
        
        # Validate parameters
        if travel_time < 60 or travel_time > 3600:
            await interaction.response.send_message("Travel time must be between 60 and 3600 seconds.", ephemeral=True)
            return
        
        if danger_level < 1 or danger_level > 5:
            await interaction.response.send_message("Danger level must be between 1 and 5.", ephemeral=True)
            return
        
        # Create corridor in both directions
        for origin_id, dest_id, orig_name, dest_name in [(origin_loc[0], dest_loc[0], origin_loc[1], dest_loc[1]),
                                                         (dest_loc[0], origin_loc[0], dest_loc[1], origin_loc[1])]:
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 0)''',
                (corridor_name, origin_id, dest_id, travel_time, fuel_cost, danger_level)
            )
        
        embed = discord.Embed(
            title="Corridor Created",
            description=f"Successfully created corridor '{corridor_name}'",
            color=0x00ff00
        )
        embed.add_field(name="Route", value=f"{origin_loc[1]} ↔ {dest_loc[1]}", inline=False)
        embed.add_field(name="Travel Time", value=f"{travel_time//60}m {travel_time%60}s", inline=True)
        embed.add_field(name="Fuel Cost", value=f"{fuel_cost} units", inline=True)
        embed.add_field(name="Danger Level", value="⚠️" * danger_level, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    @admin_group.command(name="location_info", description="Get detailed information about a location")
    @app_commands.describe(location_name="Name of the location to inspect")
    async def admin_location_info(self, interaction: discord.Interaction, location_name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        location = self.db.execute_query(
            "SELECT * FROM locations WHERE LOWER(name) LIKE LOWER(?)",
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
            "SELECT COUNT(*) FROM characters WHERE current_location = ?",
            (loc_id,),
            fetch='one'
        )[0]
        
        embed.add_field(name="Characters Present", value=str(char_count), inline=True)
        
        # Corridor connections
        corridors = self.db.execute_query(
            '''SELECT COUNT(*) FROM corridors 
               WHERE origin_location = ? AND is_active = 1''',
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
        app_commands.Choice(name="Galaxy Only (Locations & Corridors)", value="galaxy"),
        app_commands.Choice(name="Characters Only", value="characters"),
        app_commands.Choice(name="Economy (Jobs, Shop Items, Inventory)", value="economy"),
        app_commands.Choice(name="Travel Sessions", value="travel"),
        app_commands.Choice(name="Groups", value="groups")
    ])
    async def reset_data(self, interaction: discord.Interaction, reset_type: str, confirm: str = ""):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
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
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        view = EmergencyResetView(self.bot, interaction.user.id)
        
        embed = discord.Embed(
            title="🚨 EMERGENCY RESET",
            description="This will **COMPLETELY WIPE** all game data and channels.\n\n⚠️ **USE ONLY IN EMERGENCIES** ⚠️",
            color=0xff0000
        )
        
        embed.add_field(
            name="Will Delete:",
            value="• All characters and ships\n• All locations and corridors\n• All location channels\n• All jobs, inventory, groups\n• All travel sessions\n• All shop data",
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
            "full": "• All player characters and ships\n• All locations and corridors\n• All location channels\n• All jobs and shop items\n• All player inventory\n• All groups and travel sessions",
            "galaxy": "• All locations (colonies, stations, outposts, gates)\n• All corridors between locations\n• All location channels\n• All jobs at locations\n• All shop items",
            "characters": "• All player characters\n• All player ships\n• All player inventory\n• All groups (crews)",
            "economy": "• All jobs at all locations\n• All shop items and stock\n• All player inventory items",
            "travel": "• All active travel sessions\n• All temporary transit channels",
            "groups": "• All player groups/crews\n• Group leadership data"
        }
        return details.get(reset_type, "Unknown reset type")
    
    def _get_next_steps(self, reset_type: str) -> str:
        """Get recommended next steps after each reset type"""
        steps = {
            "full": "• Run `/admin setup` to reconfigure server\n• Run `/galaxy generate` to create new galaxy\n• Players can `/character create` to restart",
            "galaxy": "• Run `/galaxy generate` to create new galaxy\n• Existing characters will need to be moved to new locations",
            "characters": "• Players can `/character create` to make new characters\n• Galaxy and economy remain intact",
            "economy": "• Jobs and shop items will regenerate automatically\n• Players keep characters but lose inventory",
            "travel": "• All active journeys have been cancelled\n• Players may need to relocate manually",
            "groups": "• Players can create new groups with `/group create`"
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
                "groups", "group_invites", "group_vote_sessions", "group_votes", "group_ships",
                
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
                "logbook_entries", "groups", "ships", "characters",
                "corridors", "locations",
                "news_queue", "galactic_history", "game_panels",
                "endgame_evacuations", "endgame_config",
                "galaxy_settings", "galaxy_info"
            ]
            
            # Delete all data
            for table in tables_to_clear_in_order:
                try:
                    self.db.execute_query(f"DELETE FROM {table}")
                except Exception as e:
                    # Some tables might not exist, which is fine
                    print(f"Note: Could not clear table {table}: {e}")
            
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

                # Delete in proper order to avoid foreign key issues
                self.db.execute_query("DELETE FROM logbook_entries")
                self.db.execute_query("DELETE FROM character_identity")
                self.db.execute_query("DELETE FROM character_reputation")
                self.db.execute_query("DELETE FROM character_experience")
                self.db.execute_query("DELETE FROM character_inventory")
                self.db.execute_query("DELETE FROM characters")
                self.db.execute_query("DELETE FROM ships")
                self.db.execute_query("DELETE FROM inventory")

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

            # ————— Group data —————
            if reset_type in ["groups"]:
                reset_counts["Groups"] = self.db.execute_query(
                    "SELECT COUNT(*) FROM groups", fetch='one'
                )[0]
                
                self.db.execute_query("DELETE FROM group_votes")
                self.db.execute_query("DELETE FROM group_vote_sessions")
                self.db.execute_query("DELETE FROM group_invites")
                self.db.execute_query("DELETE FROM group_ships")
                self.db.execute_query("DELETE FROM groups")
                self.db.execute_query("UPDATE characters SET group_id = NULL")

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
                
                # Finally clear corridors and locations
                "corridors", "locations",
                
                # Clear history and news
                "galactic_history", "news_queue",
                
                # Clear endgame config if exists
                "endgame_config", "endgame_evacuations"
            ]
            
            for table in tables_to_clear:
                try:
                    self.db.execute_query(f"DELETE FROM {table}")
                except Exception as e:
                    # Some tables might not exist, which is fine
                    print(f"Note: Could not clear table {table}: {e}")
            
            # Clear game panels for this guild
            self.db.execute_query("DELETE FROM game_panels")
            
            print("✅ Comprehensive galaxy data clearing complete")
            
        except Exception as e:
            print(f"❌ Error during comprehensive galaxy clearing: {e}")
            raise
    
    @app_commands.command(name="cleanup", description="Cleanup Unused Channels")
    @app_commands.describe(
        player="Player to log out"
    )
    async def afk_player(self, interaction: discord.Interaction, player: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if player has a character and is logged in
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in, current_location, current_ship_id, group_id FROM characters WHERE user_id = ?",
            (player.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
            return
        
        char_name, is_logged_in, current_location, current_ship_id, group_id = char_data
        
        if not is_logged_in:
            await interaction.response.send_message(f"**{char_name}** is not currently logged in.", ephemeral=True)
            return
        
        # Cancel any active jobs
        self.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = ?",
            (player.id,)
        )
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = ?",
            (player.id,)
        )
        
        # Clear nickname if auto-rename is enabled
        if interaction.guild.me.guild_permissions.manage_nicknames:
            auto_rename_setting = self.db.execute_query(
                "SELECT auto_rename FROM characters WHERE user_id = ?",
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
            "UPDATE characters SET is_logged_in = 0 WHERE user_id = ?",
            (player.id,)
        )
        
        # Remove access and cleanup
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        if current_location:
            await channel_manager.remove_user_location_access(player, current_location)
            await channel_manager.immediate_logout_cleanup(interaction.guild, current_location)
        elif current_ship_id:
            await channel_manager.remove_user_ship_access(player, current_ship_id)
            await channel_manager.immediate_logout_cleanup(interaction.guild, None, current_ship_id)
        
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Use specified channel or default to current channel
        target_channel = channel if channel else interaction.channel
        
        # Check if a panel already exists in the target channel
        existing_panel = self.db.execute_query(
            "SELECT message_id FROM game_panels WHERE guild_id = ? AND channel_id = ?",
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
                       VALUES (?, ?, ?, ?)""",
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
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            import shutil
            from datetime import datetime
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"rpg_game_backup_{timestamp}.db"
            
            # Copy the database file
            shutil.copy2(self.db.db_path, backup_filename)
            
            # Get database stats
            stats = {}
            tables = ["characters", "locations", "corridors", "jobs", "groups", "ships", "inventory"]
            for table in tables:
                try:
                    count = self.db.execute_query(f"SELECT COUNT(*) FROM {table}", fetch='one')[0]
                    stats[table] = count
                except:
                    stats[table] = 0
            
            embed = discord.Embed(
                title="💾 Database Backup Created",
                description=f"Backup saved as: `{backup_filename}`",
                color=0x00ff00
            )
            
            stats_text = "\n".join([f"{table.title()}: {count}" for table, count in stats.items()])
            embed.add_field(name="Backed Up Data", value=stats_text, inline=True)
            
            embed.add_field(
                name="📁 File Location", 
                value=f"Same directory as bot files\nFile: `{backup_filename}`",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Backup failed: {str(e)}", ephemeral=True)
    
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
                "DELETE FROM server_config WHERE guild_id = ?",
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
                   FROM server_config WHERE guild_id = ?""",
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
                "DELETE FROM server_config WHERE guild_id = ?",
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
        
async def setup(bot):
    await bot.add_cog(AdminCog(bot))