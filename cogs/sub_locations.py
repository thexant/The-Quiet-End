# cogs/sub_locations.py
import discord
from discord.ext import commands
from discord import app_commands
from utils.sub_locations import SubLocationManager
import random
import asyncio

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
            
    @sub_group.command(name="leave", description="Leave the current sub-location area")
    async def leave_area(self, interaction: discord.Interaction):
        """Leave a sub-location area"""
        
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("You need a character to leave areas!", ephemeral=True)
            return
        
        current_location, char_name = char_info
        
        # Check if we're in a thread (sub-location)
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("You can only use this command inside a sub-location area!", ephemeral=True)
            return
        
        thread = interaction.channel
        
        # Look up this thread in the sub_locations table
        sub_location_info = self.db.execute_query(
            "SELECT parent_location_id, name, sub_type FROM sub_locations WHERE thread_id = ? AND is_active = 1",
            (thread.id,),
            fetch='one'
        )
        
        if not sub_location_info:
            await interaction.followup.send("This doesn't appear to be a valid sub-location area!", ephemeral=True)
            return
        
        parent_location_id, sub_location_name, sub_type = sub_location_info
        
        # Verify user is at the correct location
        if current_location != parent_location_id:
            await interaction.followup.send("You can only leave sub-locations at your current location!", ephemeral=True)
            return
        
        # Get the main location channel for announcements
        location_info = self.db.execute_query(
            "SELECT channel_id, name FROM locations WHERE location_id = ?",
            (parent_location_id,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.followup.send("Main location channel not found!", ephemeral=True)
            return
        
        channel_id, location_name = location_info
        location_channel = interaction.guild.get_channel(channel_id)
        
        if not location_channel:
            await interaction.followup.send("Main location channel is not accessible!", ephemeral=True)
            return
        
        try:
            # Remove user from the thread
            await thread.remove_user(interaction.user)
            
            # Send confirmation to user
            await interaction.followup.send(f"✅ You have left {sub_location_name}.", ephemeral=True)
            
            # Send public announcement in main location channel
            announce_embed = discord.Embed(
                title="🚪 Area Movement",
                description=f"**{char_name}** has exited the **{sub_location_name}**.",
                color=0xFF6600  # Orange color for exit
            )
            await location_channel.send(embed=announce_embed)
            
            # Check if thread is now empty and clean it up if so
            await asyncio.sleep(1)  # Brief delay to ensure user removal is processed
            
            # Count remaining members (excluding bots)
            remaining_members = sum(1 for member in thread.members if not member.bot)
            
            if remaining_members == 0:
                # Thread is empty, clean it up
                try:
                    await thread.delete(reason="Sub-location empty - automatic cleanup")
                    
                    # Clear thread_id from database
                    self.db.execute_query(
                        "UPDATE sub_locations SET thread_id = NULL WHERE thread_id = ?",
                        (thread.id,)
                    )
                    
                    print(f"🧹 Auto-cleaned empty sub-location thread: {sub_location_name}")
                    
                except Exception as e:
                    print(f"❌ Failed to clean up empty sub-location thread: {e}")
            
        except discord.Forbidden:
            await interaction.followup.send("❌ Permission error: Cannot remove you from this area.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Thread or user not found.", ephemeral=True)
        except Exception as e:
            print(f"❌ Error in area leave: {e}")
            await interaction.followup.send("❌ An error occurred while leaving the area.", ephemeral=True)
            
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