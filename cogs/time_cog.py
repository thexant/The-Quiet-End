# cogs/time_cog.py
import discord
from discord.ext import commands
from discord import app_commands
from utils.time_system import TimeSystem
from datetime import datetime, timedelta

class TimeCog(commands.Cog, name="Time"):
    def __init__(self, bot):
        self.bot = bot
        self.time_system = TimeSystem(bot)
    
    @app_commands.command(name="date", description="Show current Inter-Solar Standard Time (ISST)")
    async def current_date(self, interaction: discord.Interaction):
        """Display current in-game date and time"""
        
        # Get galaxy info
        galaxy_info = self.time_system.get_galaxy_info()
        if not galaxy_info:
            await interaction.response.send_message(
                "❌ No galaxy found! Generate a galaxy first with `/galaxy generate`.",
                ephemeral=True
            )
            return
        
        galaxy_name, start_date_str, time_scale, time_started_at, created_at, is_paused, paused_at, current_ingame = galaxy_info
        
        # Calculate current time
        current_datetime = self.time_system.calculate_current_ingame_time()
        if not current_datetime:
            await interaction.response.send_message(
                "❌ Error calculating current time. Please contact an administrator.",
                ephemeral=True
            )
            return
        
        formatted_time = self.time_system.format_ingame_datetime(current_datetime)
        
        # Get days elapsed
        days_elapsed = self.time_system.get_days_elapsed()
        
        # Create embed
        embed = discord.Embed(
            title="🕐 Inter-Solar Standard Time",
            description=f"**{galaxy_name}**",
            color=0x4169E1 if not is_paused else 0xff9900
        )
        
        embed.add_field(
            name="📅 Current Date & Time",
            value=formatted_time,
            inline=False
        )
        
        if days_elapsed is not None:
            embed.add_field(
                name="📊 Temporal Statistics",
                value=f"**Days Since Genesis:** {days_elapsed:,}\n**Time Scale:** {time_scale}x speed\n**Status:** {'⏸️ PAUSED' if is_paused else '▶️ Running'}",
                inline=False
            )
        
        # Add current time period description
        hour = current_datetime.hour
        if 5 <= hour < 11:
            period = "🌅 Morning Shift"
            description = "Colony work shifts are beginning across human space."
        elif 11 <= hour < 17:
            period = "☀️ Day Shift"
            description = "Peak operational hours - maximum traffic on all corridors."
        elif 17 <= hour < 23:
            period = "🌆 Evening Shift"
            description = "Systems transitioning to night operations."
        else:
            period = "🌙 Night Shift"
            description = "Minimal activity - most colonies on standby operations."
        
        embed.add_field(
            name="🌌 Current Period",
            value=f"**{period}**\n{description}",
            inline=False
        )
        
        # Add genesis information
        start_date = self.time_system.parse_date_string(start_date_str)
        if start_date:
            embed.add_field(
                name="🏁 Genesis Point",
                value=f"**{start_date.strftime('%d-%m-%Y')} 00:00 ISST**\nThe beginning of this galactic era",
                inline=True
            )
        
        if is_paused:
            embed.set_footer(text="⚠️ Time system is currently paused by administrators")
        else:
            embed.set_footer(text="Time flows at 4x speed (6 hours real = 1 day in-game)")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    time_admin_group = app_commands.Group(name="time_admin", description="Administrative time controls")
    
    @time_admin_group.command(name="pause", description="Pause the galactic time system")
    async def pause_time(self, interaction: discord.Interaction):
        """Pause the time system"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if self.time_system.is_paused():
            await interaction.response.send_message("⏸️ Time system is already paused.", ephemeral=True)
            return
        
        success = self.time_system.pause_time()
        if success:
            current_time = self.time_system.calculate_current_ingame_time()
            formatted_time = self.time_system.format_ingame_datetime(current_time)
            
            embed = discord.Embed(
                title="⏸️ Time System Paused",
                description="Galactic time flow has been suspended.",
                color=0xff9900
            )
            embed.add_field(
                name="Time Frozen At",
                value=formatted_time,
                inline=False
            )
            embed.add_field(
                name="ℹ️ Note",
                value="Time will remain frozen until resumed by an administrator.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to pause time system.", ephemeral=True)
    
    @time_admin_group.command(name="resume", description="Resume the galactic time system")
    async def resume_time(self, interaction: discord.Interaction):
        """Resume the time system"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not self.time_system.is_paused():
            await interaction.response.send_message("▶️ Time system is already running.", ephemeral=True)
            return
        
        success = self.time_system.resume_time()
        if success:
            current_time = self.time_system.calculate_current_ingame_time()
            formatted_time = self.time_system.format_ingame_datetime(current_time)
            
            embed = discord.Embed(
                title="▶️ Time System Resumed",
                description="Galactic time flow has been restored.",
                color=0x00ff00
            )
            embed.add_field(
                name="Resuming From",
                value=formatted_time,
                inline=False
            )
            embed.add_field(
                name="ℹ️ Note",
                value="Time will now continue flowing at 4x speed.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to resume time system.", ephemeral=True)
    
    @time_admin_group.command(name="set_time", description="Set the current galactic time")
    @app_commands.describe(
        new_time="New time in DD-MM-YYYY HH:MM format (must be after galaxy genesis)"
    )
    async def set_time(self, interaction: discord.Interaction, new_time: str):
        """Set the current in-game time"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Parse the new time
        new_datetime = self.time_system.parse_datetime_string(new_time)
        if not new_datetime:
            await interaction.response.send_message(
                "❌ Invalid time format. Use DD-MM-YYYY HH:MM (e.g., 15-03-2751 14:30)",
                ephemeral=True
            )
            return
        
        # Get galaxy start date for validation
        galaxy_info = self.time_system.get_galaxy_info()
        if not galaxy_info:
            await interaction.response.send_message("❌ No galaxy found.", ephemeral=True)
            return
        
        start_date_str = galaxy_info[1]
        start_date = self.time_system.parse_date_string(start_date_str)
        
        if new_datetime < start_date:
            await interaction.response.send_message(
                f"❌ Cannot set time before galaxy genesis ({start_date.strftime('%d-%m-%Y')} 00:00 ISST).",
                ephemeral=True
            )
            return
        
        success = self.time_system.set_current_time(new_datetime)
        if success:
            formatted_time = self.time_system.format_ingame_datetime(new_datetime)
            
            embed = discord.Embed(
                title="🕐 Time Set Successfully",
                description="Galactic time has been adjusted.",
                color=0x00ff00
            )
            embed.add_field(
                name="New Current Time",
                value=formatted_time,
                inline=False
            )
            embed.add_field(
                name="ℹ️ Note",
                value="Time will now continue flowing from this point at 4x speed.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to set time.", ephemeral=True)
    
    @time_admin_group.command(name="set_speed", description="Set the time scale factor")
    @app_commands.describe(
        speed="Time scale factor (e.g., 4.0 = 6 hours real = 1 day in-game)"
    )
    async def set_speed(self, interaction: discord.Interaction, speed: float):
        """Set the time scale factor"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if speed <= 0:
            await interaction.response.send_message("❌ Time scale must be positive.", ephemeral=True)
            return
        
        # Use the new method that properly rebases the calculation
        success = self.time_system.set_time_scale(speed)
        if not success:
            await interaction.response.send_message("❌ Failed to set time scale.", ephemeral=True)
            return
        
        # Calculate real time to game time ratio
        hours_real_per_game_day = 24 / speed
        
        embed = discord.Embed(
            title="⚡ Time Scale Updated",
            description=f"Galactic time flow rate has been changed.",
            color=0x00ff00
        )
        embed.add_field(
            name="New Time Scale",
            value=f"**{speed}x speed**",
            inline=True
        )
        embed.add_field(
            name="Real Time Ratio",
            value=f"{hours_real_per_game_day:.1f} hours real = 1 day in-game",
            inline=True
        )
        embed.add_field(
            name="⚠️ Note",
            value="Time calculation has been rebased to current moment to prevent time jumps.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @time_admin_group.command(name="debug", description="Show detailed time system information")
    async def debug_time(self, interaction: discord.Interaction):
        """Show debug information about the time system"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        galaxy_info = self.time_system.get_galaxy_info()
        if not galaxy_info:
            await interaction.response.send_message("❌ No galaxy found.", ephemeral=True)
            return
        
        name, start_date, time_scale, time_started_at, created_at, is_paused, paused_at, current_ingame = galaxy_info
        
        embed = discord.Embed(title="🔧 Time System Debug", color=0xff9900)
        embed.add_field(name="Galaxy Name", value=name, inline=True)
        embed.add_field(name="Genesis Date", value=start_date, inline=True)
        embed.add_field(name="Time Scale", value=f"{time_scale}x", inline=True)
        embed.add_field(name="Started At (Real)", value=time_started_at, inline=False)
        embed.add_field(name="Galaxy Created At", value=created_at, inline=False)
        embed.add_field(name="Is Paused", value="Yes" if is_paused else "No", inline=True)
        embed.add_field(name="Paused At", value=paused_at or "N/A", inline=True)
        embed.add_field(name="Current In-Game", value=current_ingame or "N/A", inline=True)
        
        # Calculate current time
        current_time = self.time_system.calculate_current_ingame_time()
        if current_time:
            embed.add_field(
                name="Calculated Current Time",
                value=self.time_system.format_ingame_datetime(current_time),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TimeCog(bot))