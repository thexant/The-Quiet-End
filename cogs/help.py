# cogs/help.py
import discord
from discord.ext import commands
from discord import app_commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    @app_commands.command(name="help", description="Get help information based on your current location and context")
    async def help_command(self, interaction: discord.Interaction):
        # Check if this is a location channel
        location_info = self.db.execute_query(
            "SELECT location_id, name, location_type, has_jobs, has_shops, has_medical, has_repairs, has_fuel, has_upgrades FROM locations WHERE channel_id = ?",
            (interaction.channel.id,),
            fetch='one'
        )
        
        if location_info:
            # This is a location channel - show contextual help
            await self._show_location_help(interaction, location_info)
        else:
            # Check if this is a transit channel
            if "transit" in interaction.channel.name.lower():
                await self._show_transit_help(interaction)
            else:
                # This is a general channel - show basic help
                await self._show_basic_help(interaction)
    
    async def _show_basic_help(self, interaction: discord.Interaction):
        """Show basic global help for non-location channels"""
        embed = discord.Embed(
            title="🌌 Command Guide",
            description="Your complete guide to navigating the galaxy",
            color=0x4169E1
        )
        
        # Character Management
        embed.add_field(
            name="👤 Character Management",
            value=(
                "`/here` - Open your location interaction panel\n"
                "`/status` - View your character, stats, ship and inventory\n"
                "`/character delete` - Permanently delete your character\n"
                "`/character login` - Log into the game world\n"
                "`/character logout` - Safely log out\n"
                "`/character name` - Toggle automatic nickname changing\n"
                "`/act <action>` - Perform a roleplay action\n"
                "`/character dock/undock` - Manage ship docking status\n"
                "`/character search` - Search location for items\n"
                "`/character train` - Train skills at certain locations\n"
                "`/character drop/pickup` - Manage items at locations\n"
                "`/use <item>` - Use an item from your inventory"
            ),
            inline=False
        )
        
        # Core Gameplay
        embed.add_field(
            name="🚀 Travel & Navigation",
            value=(
                "`/travel go` - Travel between locations\n"
                "`/travel status` - Check your current travel progress\n"
                "`/travel routes` - View available routes from current location\n"
                "`/travel plotroute <destination>` - Calculate best route to destination\n"
                "`/travel fuel_estimate` - Calculate fuel requirements for routes\n"
                "`/travel emergency_exit` - Emergency corridor exit (DANGEROUS)\n"
                "`/webmap_status` - View web-map and its status\n"
                "📍 Visit location channels to dock and access services"
            ),
            inline=False
        )
        embed.add_field(
            name="💰 Economy & Jobs",
            value=(
                "`/shop list` - Browse available items for purchase\n"
                "`/shop buy <item> [qty]` - Buy items from shop\n"
                "`/shop sell <item> [qty]` - Sell items from inventory\n"
                "`/job list` - View available jobs at location\n"
                "`/job accept <job>` - Accept a job by title or ID\n"
                "`/job status` - Check current job progress\n"
                "`/job complete` - Complete your current job\n"
                "`/job abandon` - Abandon current job\n"
                "`/federal_supply list` - Access Federal Supply depot\n"
                "`/npc` - Interact with NPCs at your location"
            ),
            inline=False
        )
        # Communication
        embed.add_field(
            name="📻 Communication",
            value=(
                "`/radio send <message>` - Send radio transmission\n"
                "📡 Range affected by distance & interference\n"
                "🔄 Messages may be relayed through repeaters"
            ),
            inline=False
        )
        # Time System - NEW
        embed.add_field(
            name="🕐 Time System",
            value=(
                "`/date` - View current Inter-Solar Standard Time (ISST)\n"
                "⏰ Galaxy operates on accelerated time scale"
            ),
            inline=False
        )
        embed.add_field(
            name="🏢 Area Access",
            value=(
                "`/area enter <type>` - Enter location sub-areas (bar, medbay, etc.)\n"
                "`/area leave` - Leave current sub-location area\n"
                "`/area list` - View available areas at your location\n"
                "🍺 Access specialized areas like bars, medical bays, and more"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ Combat Commands",
            value=(
                "`/attack npc` - Initiate combat with an NPC\n"
                "`/attack player` - Initiate PvP combat with player\n"
                "`/attack fight` - Continue an ongoing fight\n"
                "`/attack flee` - Attempt to escape from combat\n"
                "`/pvp_opt` - Manage your PvP opt-out status\n"
                "`/rob npc` - Attempt to rob an NPC\n"
                "`/rob player` - Attempt to rob another player"
            ),
            inline=False
        )
        embed.add_field(
            name="🚀 Ship Management",
            value=(
                "`/ship interior enter` - Enter your ship's interior\n"
                "`/ship interior leave` - Exit your ship\n"
                "`/ship interior board <player>` - Request to board another ship\n"
                "`/ship customize` - Customize ship appearance and upgrades\n"
                "`/ship upgrade` - Purchase ship component upgrades\n"
                "`/ship shipyard` - Access shipyard services\n"
                "`/ship group_ship` - Manage group ship settings"
            ),
            inline=False
        )
        # Group System
        embed.add_field(
            name="👥 Group System",
            value=(
                "`/group create [name]` - Start a group\n"
                "`/group invite <player>` - Invite someone to your group (leader only)\n"
                "`/group join <group_name>` - Join a group (requires invitation)\n"
                "`/group leave` - Leave your current group\n"
                "`/group disband` - Dissolve your group (leader only)\n"
                "`/group info` - View group information\n"
                "`/group kick <player>` - Remove member (leader only)\n"
                "`/group travel_vote` - Start group travel vote (leader only)\n"
                "`/group vote <yes/no>` - Cast your vote in group decisions"
            ),
            inline=False
        )
        embed.add_field(
            name="📍 Location Management",
            value=(
                "`/here` - View interactive location panel\n"
                "`/location_info` - View detailed location information\n"
                "`/purchase_location` - Purchase or claim current location\n"
                "`/upgrade_location` - Upgrade your owned locations\n"
                "`/logs view` - View location's log/guestbook\n"
                "`/logs add <message>` - Add entry to location log\n"
                "🏢 Own and develop locations across the galaxy"
            ),
            inline=False
        )

        # Quick Start
        embed.add_field(
            name="🎯 Quick Start Guide",
            value=(
                "1️⃣ Create character with `/character create`\n"
                "2️⃣ Login with `/character login`\n"
                "3️⃣ Use `/here` for local services\n"
                "4️⃣ Travel with `/travel go` to explore\n"
                "5️⃣ Use `/help` in location channels for specific options\n"
                "5️⃣ Use `/logout` when you're done to ensure your character is safe!"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Use /help in location channels for specific services and options!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _show_location_help(self, interaction: discord.Interaction, location_info):
        """Show contextual help for location channels"""
        location_id, name, location_type, has_jobs, has_shops, has_medical, has_repairs, has_fuel, has_upgrades = location_info
        
        # Get user's dock status to determine available actions
        user_data = self.db.execute_query(
            "SELECT location_status, current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        is_docked = user_data and user_data[0] == "docked" and user_data[1] == location_id
        
        # Create location-specific embed
        location_emojis = {
            "colony": "🏙️",
            "space_station": "🛰️",
            "outpost": "🏭",
            "gate": "🌌",
            "shipyard": "🚢",
            "mining_station": "⛏️",
            "research_facility": "🔬",
            "military_base": "⚔️"
        }
        
        emoji = location_emojis.get(location_type, "📍")
        
        embed = discord.Embed(
            title=f"{emoji} {name} - Command Guide",
            description=f"Available commands and services at this {location_type.replace('_', ' ')}",
            color=0x00ff7f if is_docked else 0xffa500
        )
        
        # Core Location Commands
        embed.add_field(
            name="🎮 Core Commands",
            value=(
                "`/here` - Open interactive location panel\n"
                "`/status` - Open interactive character panel\n"
            ),
            inline=False
        )
        # Area Access - NEW (add after Core Commands)
        embed.add_field(
            name="🏢 Area Access",
            value=(
                "`/area list` - View available sub-areas at this location\n"
                "`/area enter <type>` - Enter specialized areas\n"
                "`/area leave` - Exit current sub-area\n"
                "• Access bars, medical bays, engineering, security offices\n"
                "• Different locations offer different specialized areas"
            ),
            inline=False
        )
        # Location Management & Logs
        # NPC Interactions
        embed.add_field(
            name="👥 NPC Interactions",
            value=(
                "`/npc` - Interact with NPCs at this location\n"
                "• Browse NPC job offerings\n"
                "• Trade items with NPCs\n"
                "• General conversation and roleplay"
            ),
            inline=False
        )
        # Ship Commands - UPDATED
        embed.add_field(
            name="🚀 Ship Commands",
            value=(
                "`/ship interior enter` - Enter your ship\n"
                "`/ship interior leave` - Exit ship interior\n"
                "`/ship interior board <player>` - Board another ship\n"
                "`/ship customize` - Customize ship appearance\n"
                "`/ship upgrade` - Purchase ship upgrades\n"
                "`/ship shipyard` - Access shipyard services\n"
                "`/ship group_ship` - Manage group ship settings"
            ),
            inline=True
        )
         # Home Management (if applicable)
        if has_shops:  # Assuming homes are available where shops are
            embed.add_field(
                name="🏠 Home Services",
                value=(
                    "If this location has homes available, you may be able to purchase one\n"
                    "`/home buy` - Purchase available homes\n"
                    "`/homes view` - View your properties\n"
                    "`/home interior enter` - Enter your home\n"
                    "`/home market` - List home for sale"
                ),
                inline=False
            )
        # Location Logs and Ownership
        embed.add_field(
            name="📜 Location Services",
            value=(
                "`/location_info` - View detailed location information\n"
                "`/logs view` - Read location log/guestbook\n"
                "`/logs add <message>` - Add entry to location log\n"
                "`/purchase_location` - Purchase/claim location (if available)\n"
                "`/upgrade_location` - Upgrade owned locations\n"
                "• View ownership status and upgrade information\n"
                "• Read and contribute to location history"
            ),
            inline=False
        )
        # Services Available
        services = []
        if has_shops:
            services.extend([
                "🛒 **Shopping Available**",
                "`/shop list` - Browse available items",
                "`/shop buy <item> [quantity]` - Purchase items",
                "`/shop sell <item> [quantity]` - Sell your items",
                "`/federal_supply list` - Access Federal supplies (if available)"
            ])

        if has_jobs:
            services.extend([
                "💼 **Jobs Available**",
                "`/job list` - View available jobs",
                "`/job accept <job_id>` - Accept a job",
                "`/job status` - Check current job progress",
                "`/job complete` - Complete current job",
                "`/job abandon` - Abandon current job"
            ])
        
        if has_medical:
            services.extend([
                "🏥 **Medical Services**",
                "• Healing and medical treatment",
                "• Use location panel for medical services"
            ])
        
        if has_repairs:
            services.extend([
                "🔧 **Ship Repairs**",
                "• Hull repair and maintenance",
                "• System diagnostics and fixes"
            ])
        
        if has_fuel:
            services.extend([
                "⛽ **Fuel Services**",
                "• Refuel your ship",
                "• Fuel efficiency upgrades"
            ])
        
        if has_upgrades:
            services.extend([
                "⬆️ **Ship Upgrades**",
                "• Purchase better ships",
                "• Upgrade ship components",
                "• Performance enhancements"
            ])
        
        if services:
            embed.add_field(
                name="🏢 Available Services",
                value="\n".join(services),
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Services",
                value="No commercial services available at this location.",
                inline=False
            )
        
        # Communication
        embed.add_field(
            name="📻 Communication",
            value=(
                "`/radio send <message>` - Send radio transmission\n"
                "💡 Your transmission range depends on local infrastructure"
            ),
            inline=False
        )
        
        # Location-specific tips
        tips = []
        if location_type == "colony":
            tips.extend([
                "🏙️ Colonies are major population centers",
                "💼 Best source of diverse job opportunities",
                "🛒 Full shopping and services available",
                "📡 Excellent radio transmission range"
            ])
        elif location_type == "space_station":
            tips.extend([
                "🛰️ Major trading and transport hubs",
                "🚢 Often have shipyard facilities",
                "🌌 Strategic locations on trade routes",
                "👥 Great for finding crew members"
            ])
        elif location_type == "outpost":
            tips.extend([
                "🏭 Frontier settlements with basic services",
                "⛏️ Often near resource extraction sites",
                "🔧 Good for repairs and refueling",
                "💰 May have specialized local jobs"
            ])
        elif location_type == "gate":
            tips.extend([
                "🌌 Massive structures enabling long-distance travel",
                "⚡ Require significant power and coordination",
                "🚀 Can transport you across vast distances",
                "📡 Advanced communication relay capabilities"
            ])
        elif location_type == "shipyard":
            tips.extend([
                "🚢 Specialized ship construction and upgrade facilities",
                "⬆️ Best place to purchase new ships",
                "🔧 Advanced repair and modification services",
                "💰 Often expensive but high-quality services"
            ])
        if location_type in ["colony", "space_station", "outpost"]:
            tips.extend([
                "📜 Check the location log to read about recent events",
                "💰 Some distressed locations may be available for purchase",
                "⬆️ Owned locations can be upgraded to improve services"
            ])
        # Add ownership-specific tips
        if owner_id == interaction.user.id:
            tips.extend([
                "🏢 You own this location! Use `/upgrade_location` to improve it",
                "💰 Collect income regularly from your location",
                "📊 Monitor your location's performance and upgrade strategically"
            ])
        elif is_derelict or wealth_level <= 3:
            tips.extend([
                "💰 This location may be available for purchase",
                "🏗️ Purchasing allows you to upgrade and improve the location",
                "📈 Ownership can provide passive income over time"
            ])

        # Add log-specific tips for all locations
        tips.extend([
            "📜 Use `/logs view` to read about this location's history",
            "✍️ Add your own entry with `/logs add` to leave your mark"
        ])
        if tips:
            embed.add_field(
                name="💡 Location Tips",
                value="\n".join(tips),
                inline=False
            )
        
        # Status indicator
        status_text = "🛬 **Docked** - Full access to all services" if is_docked else "🚀 **In Orbit** - Limited service access (dock for full services)"
        embed.add_field(
            name="📊 Current Status",
            value=status_text,
            inline=False
        )
        
        embed.set_footer(text="💡 Use the location panel (/character location) for interactive service access!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _show_transit_help(self, interaction: discord.Interaction):
        """Show help for transit channels"""
        embed = discord.Embed(
            title="🚀 In Transit - Command Guide",
            description="You're currently traveling through space",
            color=0xff6600
        )
        
        embed.add_field(
            name="🎮 Available Commands",
            value=(
                "`/status` - Open your interactive character panel\n"
                "`/here` - Open your interactive location panel\n"
                "`/radio send <message>` - Send radio transmission\n"
                "`/travel status` - Check your travel progress\n"
                "`/travel emergency_exit` - Emergency exit (DANGEROUS)\n"
                "`/date` - View current galactic time"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Transit Limitations",
            value=(
                "• No shopping or job services\n"
                "• Limited character interactions\n"
                "• Cannot change destination mid-journey\n"
                "• Emergency exit available if needed"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🆘 Emergency Commands",
            value=(
                "If you encounter issues during travel:\n"
                "• Wait for automatic arrival\n"
                "• Contact admins if stuck\n"
                "• Emergency exit (dangerous, last resort)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📻 Radio Communication",
            value=(
                "• Radio range may be limited during travel\n"
                "• Corridor interference can affect signals\n"
                "• Other travelers may be in communication range"
            ),
            inline=False
        )
        
        embed.set_footer(text="Enjoy the journey! You'll arrive at your destination soon.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="commands", description="Show a complete list of all available commands")
    async def commands_list(self, interaction: discord.Interaction):
        """Show complete command reference"""
        embed = discord.Embed(
            title="📚 Complete Command Reference",
            description="All available commands organized by category",
            color=0x9932cc
        )
        
        # Character Commands
        embed.add_field(
            name="👤 Character Commands",
            value=(
                "`/status` - Open your interactive character panel\n"
                "`/here` - Open your interactive location panel\n"
                "`/character login` - Login to game\n"
                "`/character logout` - Logout safely\n"
                "`/character delete` - Permanently delete your current character"
            ),
            inline=True
        )
        # Time System Commands - NEW
        embed.add_field(
            name="🕐 Time Commands",
            value=(
                "`/date` - View current galactic time\n"
                "⏰ Inter-Solar Standard Time (ISST)"
            ),
            inline=True
        )

        # Area Commands - NEW
        embed.add_field(
            name="🏢 Area Commands",
            value=(
                "`/area enter <type>` - Enter sub-areas\n"
                "`/area leave` - Leave current area\n"
                "`/area list` - List available areas\n"
                "🍺 Bars, medbays, hangars, and more"
            ),
            inline=True
        )
        # Travel Commands - UPDATED
        embed.add_field(
            name="🚀 Travel Commands",
            value=(
                "`/travel go` - Travel between locations\n"
                "`/travel status` - Check travel progress\n"
                "`/travel routes` - View available routes\n"
                "`/travel plotroute <dest>` - Calculate route\n"
                "`/travel fuel_estimate` - Calculate fuel needs\n"
                "`/travel emergency_exit` - Emergency exit\n"
                "`/webmap status` - Get webmap status"
            ),
            inline=True
        )
        
        # Ship Commands - UPDATED
        embed.add_field(
            name="🚀 Ship Commands",
            value=(
                "`/ship interior enter` - Enter your ship\n"
                "`/ship interior leave` - Exit ship interior\n"
                "`/ship interior board <player>` - Board another ship\n"
                "`/ship customize` - Customize ship appearance\n"
                "`/ship upgrade` - Purchase ship upgrades\n"
                "`/ship shipyard` - Access shipyard services\n"
                "`/ship group_ship` - Manage group ship settings"
            ),
            inline=True
        )
        # Economy Commands
        embed.add_field(
            name="💰 Economy Commands",
            value=(
                "`/shop list` - Browse shop items\n"
                "`/shop buy <item> [qty]` - Buy items\n"
                "`/shop sell <item> [qty]` - Sell items\n"
                "`/federal_supply list` - Access Federal Supply\n"
                "`/job list` - View available jobs\n"
                "`/job accept <id>` - Accept job\n"
                "`/job status` - Check job progress\n"
                "`/job complete` - Complete job\n"
                "`/job abandon` - Abandon current job"
            ),
            inline=True
        )
        # Character Actions
        embed.add_field(
            name="🎭 Character Actions",
            value=(
                "`/act <action>` - Perform roleplay action\n"
                "`/character search` - Search location for items\n"
                "`/character train <skill>` - Train at locations\n"
                "`/character drop <item>` - Drop item at location\n"
                "`/character pickup <item>` - Pick up items\n"
                "`/character dock/undock` - Manage ship status\n"
                "`/character name` - Toggle nickname auto-change"
            ),
            inline=True
        )
        # Group Commands
        embed.add_field(
            name="👥 Group Commands",
            value=(
                "`/group create <name>` - Create crew\n"
                "`/group join <leader>` - Join crew\n"
                "`/group disband <group>` - Disband your group (leader only)\n"
                "`/group leave` - Leave crew\n"
                "`/group info` - View crew info\n"
                "`/group travel_vote` - Vote on travel\n"
                "`/group job_vote` - Vote on jobs\n"
                "`/group vote` - Cast your vote on group votes"
            ),
            inline=True
        )
        
        # Communication
        embed.add_field(
            name="📻 Communication & Reputation",
            value=(
                "`/radio send <message>` - Send radio transmission\n"
                "`/reputation` - View your regional reputation standings\n"
                "📡 Range affected by distance & interference\n"
                "🔄 Messages may be relayed through repeaters"
            ),
            inline=False
        )
        # Home Commands
        embed.add_field(
            name="🏠 Home Commands",
            value=(
                "`/home buy` - Purchase homes\n"
                "`/homes view [player]` - View properties\n"
                "`/home interior enter` - Enter your home\n"
                "`/home interior leave` - Exit home\n"
                "`/home interior invite <player>` - Invite to home\n"
                "`/home interior accept` - Accept invitation\n"
                "`/home market` - List home for sale\n"
                "`/home sell <player> <price>` - Sell directly"
            ),
            inline=True
        )
        embed.add_field(
            name="📍 Location Management",
            value=(
                "`/location_info` - View location details\n"
                "`/purchase_location` - Buy/claim location\n"
                "`/upgrade_location` - Upgrade owned locations\n"
                "`/logs view` - View location log/guestbook\n"
                "`/logs add <message>` - Add log entry\n"
                "🏢 Own, develop, and manage locations"
            ),
            inline=True
        )
        embed.add_field(
            name="🎯 Reputation & Bounty Commands",
            value=(
                "`/reputation` - View your regional reputation\n"
                "`/postbounty <player> <amount>` - Post bounty\n"
                "`/removebounty <player>` - Remove bounty\n"
                "`/removeallbounties` - Remove all bounties\n"
                "`/capture <player>` - Capture opposing player\n"
                "`/bounty <player>` - Capture bountied player\n"
                "`/bounties` - View active bounties nearby\n"
                "`/bounty_status` - Check bounty status\n"
                "`/paybounty <amount>` - Pay off bounties"
            ),
            inline=True
        )
        # Combat Commands
        embed.add_field(
            name="⚔️ Combat Commands",
            value=(
                "`/attack npc` - Initiate combat with an NPC\n"
                "`/attack player` - Initiate PvP combat with player\n"
                "`/attack fight` - Continue an ongoing fight\n"
                "`/attack flee` - Attempt to escape from combat\n"
                "`/pvp_opt` - Manage your PvP opt-out status\n"
                "`/rob npc` - Attempt to rob an NPC\n"
                "`/rob rob_player` - Attempt to rob another player"
            ),
            inline=False
        )
        # Admin Commands - UPDATED (add these lines to existing admin section)
        embed.add_field(
            name="⚙️ Admin Commands",
            value=(
                "`/admin setup` - Initial server setup\n"
                "`/admin config` - View/modify server configuration\n"
                "`/admin teleport` - Teleport players\n"
                "`/admin create_item` - Create items for shops/players\n"
                "`/admin create_job` - Create jobs at locations\n"
                "`/admin create_location` - Create new locations\n"
                "`/admin create_corridor` - Create travel corridors\n"
                "`/admin stats` - View server statistics\n"
                "`/admin backup` - Backup database\n"
                "`/admin reset` - Reset various game data\n"
                "`/setreputation <user> <location> <value>` - Set reputation\n"
                "`/galaxy generate` - Generate a galaxy\n"
                "`/web_map start/stop` - Manage webmap service\n"
                "`/export` - Export galaxy data\n"
                "`/time_admin pause/resume` - Control time flow\n"
                "`/time_admin set_time <time>` - Set galactic time\n"
                "`/time_admin set_speed <factor>` - Set time scale\n"
                "`/time_admin debug` - Time system diagnostics"
            ),
            inline=True
        )
        # Event System Admin Commands - NEW
        embed.add_field(
            name="🎲 Event System Admin",
            value=(
                "`/events trigger_corridor` - Manually trigger corridor check\n"
                "`/events generate_jobs [location]` - Generate jobs\n"
                "`/events status` - View event system status\n"
                "`/events force_collapse <corridor>` - Force corridor collapse\n"
                "`/events emergency_jobs [count]` - Generate emergency jobs\n"
                "⚙️ Manage dynamic events and systems"
            ),
            inline=True
        )
        
        embed.set_footer(text="💡 Use /help in specific locations for contextual assistance!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))