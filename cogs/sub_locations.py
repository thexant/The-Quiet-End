# cogs/sub_locations.py
import discord
from discord.ext import commands
from discord import app_commands
from utils.sub_locations import SubLocationManager
import random
class SubLocationCog(commands.Cog):
    """Commands for sub-location interactions"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.sub_manager = SubLocationManager(bot)
    
    sub_group = app_commands.Group(name="area", description="Sub-location area commands")
    
    @sub_group.command(name="enter", description="Enter a sub-location area")
    @app_commands.describe(area_type="Type of area to enter")
    @app_commands.choices(area_type=[
        app_commands.Choice(name="🍺 Bar", value="bar"),
        app_commands.Choice(name="⚕️ Medical Bay", value="medbay"),
        app_commands.Choice(name="🔧 Engineering", value="engineering"),
        app_commands.Choice(name="🛡️ Security Office", value="security"),
        app_commands.Choice(name="🚁 Hangar Bay", value="hangar"),
        app_commands.Choice(name="🛋️ Lounge", value="lounge"),
        app_commands.Choice(name="🛒 Market", value="market"),
        app_commands.Choice(name="📋 Administration", value="admin")
    ])
    async def enter_area(self, interaction: discord.Interaction, area_type: str):
        """Enter a sub-location area"""
        
        await interaction.response.defer(ephemeral=True)

        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("You need a character to enter areas!", ephemeral=True)
            return
        
        current_location, char_name = char_info
        
        if not current_location:
            await interaction.followup.send("You need to be at a location to enter its areas!", ephemeral=True)
            return
        
        # Get location channel
        location_info = self.db.execute_query(
            "SELECT channel_id, name FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.followup.send("Location channel not found!", ephemeral=True)
            return
        
        channel_id, location_name = location_info
        location_channel = interaction.guild.get_channel(channel_id)
        
        if not location_channel:
            await interaction.followup.send("Location channel is not accessible!", ephemeral=True)
            return
        
        # Check if this sub-location exists for this location
        available_subs = await self.sub_manager.get_available_sub_locations(current_location)
        area_exists = any(sub['type'] == area_type for sub in available_subs)
        
        if not area_exists:
            sub_location_details = self.sub_manager.sub_location_types.get(area_type)
            area_name = sub_location_details['name'] if sub_location_details else area_type.replace('_', ' ')
            await interaction.followup.send(f"This location doesn't have a {area_name}!", ephemeral=True)
            return
        
        # Create or get the sub-location thread
        thread = await self.sub_manager.create_sub_location(
            interaction.guild, location_channel, current_location, area_type, interaction.user
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
            await interaction.followup.send("Failed to access that area. Try again later.", ephemeral=True)
    
    @sub_group.command(name="list", description="List available areas at your current location")
    async def list_areas(self, interaction: discord.Interaction):
        """List available sub-location areas"""
        
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("You need a character to check areas!", ephemeral=True)
            return
        
        current_location, char_name = char_info
        
        if not current_location:
            await interaction.response.send_message("You need to be at a location to check its areas!", ephemeral=True)
            return
        
        # Get available sub-locations
        available_subs = await self.sub_manager.get_available_sub_locations(current_location)
        
        # Get location name
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )[0]
        
        if not available_subs:
            await interaction.response.send_message(f"No special areas are available at {location_name}.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏢 Available Areas",
            description=f"Areas accessible at **{location_name}**:",
            color=0x4169e1
        )
        
        area_list = []
        for sub in available_subs:
            status = "🟢 Active" if sub['exists'] else "⚪ Available"
            area_list.append(f"{sub['icon']} **{sub['name']}** - {status}")
            area_list.append(f"   *{sub['description']}*")
        
        embed.add_field(
            name="📍 Areas",
            value="\n".join(area_list),
            inline=False
        )
        
        embed.add_field(
            name="🎮 Usage",
            value="Use `/area enter <area_type>` to access any of these areas.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SubLocationCog(bot))