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
                "`/character create` - Create your character\n"
                "`/character delete` - Permanently delete your character\n"
                "`/character login` - Log into the game world\n"
                "`/character logout` - Safely log out\n"
                "`/here` - Open your location interaction panel\n"
                "`/status` - View your character, stats, ship and inventory"
            ),
            inline=False
        )
        
        # Core Gameplay
        embed.add_field(
            name="🚀 Travel & Navigation",
            value=(
                "`/travel go` - Travel between locations\n"
                "`/webmap_status` - View web-map and it's status\n"
                "📍 Visit location channels to dock and access services"
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
        
        # Group System
        embed.add_field(
            name="👥 Group System",
            value=(
                "`/group create <size>` - Start a crew (2-4 members)\n"
                "`/group join <leader>` - Join someone's crew\n"
                "`/group leave` - Leave your current crew\n"
                "`/group travel_vote` - Vote on group travel\n"
                "`/group job_vote` - Vote on group jobs\n"
                "`/group vote <Yes/No>` - Cast your vote on group votes"
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
        
        # Services Available
        services = []
        if has_shops:
            services.extend([
                "🛒 **Shopping Available**",
                "`/shop list` - Browse available items",
                "`/shop buy <item> [quantity]` - Purchase items",
                "`/shop sell <item> [quantity]` - Sell your items"
            ])
        
        if has_jobs:
            services.extend([
                "💼 **Jobs Available**",
                "`/job list` - View available jobs",
                "`/job accept <job_id>` - Accept a job",
                "`/job status` - Check current job progress",
                "`/job complete` - Complete current job"
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
                "`/galaxy visual_map` - View your route on the galaxy map"
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
                "`/character create` - Create new character\n"
                "`/status` - Open your interactive character panel\n"
                "`/here` - Open your interactive location panel\n"
                "`/character login` - Login to game\n"
                "`/character logout` - Logout safely\n"
                "`/character delete` - Permanently delete your current character"
            ),
            inline=True
        )
        
        # Travel Commands
        embed.add_field(
            name="🚀 Travel Commands",
            value=(
                "`/travel go` - Travel between locations\n"
                "`/galaxy visual_map` - Generate a galaxy map\n"
                "`/travel plotroute` - Plot a route to a destination\n"
                "`/travel routes` - View Available travel routes\n"
                "`/webmap status` - Get the webmap status"
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
                "`/job list` - View available jobs\n"
                "`/job accept <id>` - Accept job\n"
                "`/job status` - Check job progress\n"
                "`/job complete` - Complete job"
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
        
        # Communication Commands
        embed.add_field(
            name="📻 Communication Commands",
            value=(
                "`/radio send <message>` - Send radio\n"
            ),
            inline=True
        )
        embed.add_field(
            name="🎯 Reputation Bounty Commands",
            value=(
                "`/reputation` - View your regional reputation\n"
                "`/capture` - Attempt to capture a player of an opposing alignment for a reward\n"
                "`/bounty` - Attempt to capture a player with a bounty on their head\n"
                "`/bounties` - View active bounties nearby\n"
                "`/bounty_status` - Check your bounty capture status and active bounties\n"
                "`/postbounty <player>` - Post a bounty on another player\n"
                "`/removebounty <player>` - Remove your posted bounty from another player\n"
                "`/paybounty` - Pay off your bounties\n"
                "`/removeallbounties` - Remove *all* of your set bounties"
            ),
            inline=True
        )
        embed.add_field(
            name="⚔️ Combat Commands",
            value=(
                "`/attack npc` - Initiate combat with an NPC\n"
                "`/attack fight` - Make an attack while in combat\n"
                "`/attack flee` - Attempt to escape from combat\n"
                "`/rob` - Attempt to rob an NPC\n"
                "PvP and Player Robberies coming soon..."
            ),
            inline=True
        )
        # Admin Commands (if applicable)
        if interaction.user.guild_permissions.administrator:
            embed.add_field(
                name="⚙️ Admin Commands",
                value=(
                    "`/admin setup` - Initial server setup\n"
                    "`/galaxy generate` - Generate a galaxy for the game\n"
                    "`/web_map start` - Start the webmap service on port 8090\n"
                    "`/web_map stop` - Stop the webmap service\n"
                    "`/export` - Export the current galaxy state in a Wiki format, HTML or Markdown\n"
                    "`/admin teleport` - Teleport players\n"
                    "`/admin reset` - Reset galaxy\n"
                    "`/admin backup` - Backup data"
                ),
                inline=True
            )
        
        embed.set_footer(text="💡 Use /help in specific locations for contextual assistance!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))