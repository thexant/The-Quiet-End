# utils/leave_button.py
import discord
from discord.ext import commands
from typing import Optional

class UniversalLeaveView(discord.ui.View):
    """Universal Leave button that works in both home interiors and sub-locations"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.db = bot.db
    
    @discord.ui.button(label="Leave", emoji="🚪", style=discord.ButtonStyle.secondary, row=4)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle leave button press - detects context and performs appropriate action"""
        
        # Defer the response first
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if this is a home interior
            if await self._is_home_interior(interaction.channel):
                await self._handle_home_leave(interaction)
            # Check if this is a sub-location thread
            elif await self._is_sub_location(interaction.channel):
                await self._handle_area_leave(interaction)
            else:
                await interaction.followup.send("❌ This leave button can only be used in home interiors or sub-locations.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while trying to leave: {str(e)}", ephemeral=True)
    
    async def _is_home_interior(self, channel) -> bool:
        """Check if the channel is a home interior"""
        if not hasattr(channel, 'name'):
            return False
        
        # Check if it's a home interior based on channel name pattern
        return channel.name.endswith("-interior") or "interior" in channel.name.lower()
    
    async def _is_sub_location(self, channel) -> bool:
        """Check if the channel is a sub-location thread"""
        if not isinstance(channel, discord.Thread):
            return False
        
        # Check if it's a sub-location thread by checking the database or thread name patterns
        # Look for common sub-location patterns in thread names
        sub_location_keywords = ['bar', 'medbay', 'engineering', 'security', 'observatory', 'lounge', 'market', 'docks']
        channel_name_lower = channel.name.lower()
        
        return any(keyword in channel_name_lower for keyword in sub_location_keywords)
    
    async def _handle_home_leave(self, interaction: discord.Interaction):
        """Handle leaving a home interior"""
        user_id = interaction.user.id
        
        # Get the user's current location
        cursor = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?", 
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            await interaction.followup.send("❌ Character not found!", ephemeral=True)
            return
        
        current_location = result[0]
        
        # Update user's location to remove home interior
        self.db.execute_query(
            "UPDATE characters SET current_location = ? WHERE user_id = ?",
            (current_location.replace('-interior', ''), user_id)
        )
        
        await interaction.followup.send("🚪 You have left the home interior.", ephemeral=True)
        
        # Try to redirect to main location channel
        try:
            from cogs.travel import Travel
            travel_cog = self.bot.get_cog('Travel')
            if travel_cog:
                await travel_cog._show_location_info(interaction.channel, user_id, current_location.replace('-interior', ''))
        except:
            pass  # If we can't show location info, that's okay
    
    async def _handle_area_leave(self, interaction: discord.Interaction):
        """Handle leaving a sub-location"""
        user_id = interaction.user.id
        thread = interaction.channel
        
        if not isinstance(thread, discord.Thread):
            await interaction.followup.send("❌ This is not a sub-location thread!", ephemeral=True)
            return
        
        try:
            # Remove user from thread
            await thread.remove_user(interaction.user)
            await interaction.followup.send("🚪 You have left the sub-location.", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to remove you from this thread.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Thread not found or you're not in it.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error leaving sub-location: {str(e)}", ephemeral=True)