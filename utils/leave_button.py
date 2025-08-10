# utils/leave_button.py
import discord
from discord.ext import commands
from typing import Optional
import asyncio

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
            # Check if this is a transit channel - Leave button should not work here
            if await self._is_transit_channel(interaction.channel):
                await interaction.followup.send("❌ You cannot use the leave button while in transit. Wait for your journey to complete.", ephemeral=True)
                return
            
            # Check if this is a home interior
            if await self._is_home_interior(interaction.channel):
                await self._handle_home_leave(interaction)
            # Check if this is a sub-location thread
            elif await self._is_sub_location(interaction.channel):
                await self._handle_area_leave(interaction)
            # Check if this is a ship interior
            elif await self._is_ship_interior(interaction.channel):
                await self._handle_ship_leave(interaction)
            else:
                await interaction.followup.send("❌ This leave button can only be used in home interiors, sub-locations, or ship interiors.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while trying to leave: {str(e)}", ephemeral=True)
    
    async def _is_home_interior(self, channel) -> bool:
        """Check if the channel is a home interior"""
        if not hasattr(channel, 'id'):
            return False
        
        # Check if the channel ID is registered as a home interior in the database
        home_check = self.db.execute_query(
            "SELECT home_id FROM home_interiors WHERE channel_id = %s",
            (channel.id,),
            fetch='one'
        )
        return home_check is not None
    
    async def _is_sub_location(self, channel) -> bool:
        """Check if the channel is a sub-location thread"""
        if not isinstance(channel, discord.Thread):
            return False
        
        # Check if this thread ID exists in the sub_locations table as an active sub-location
        sub_location_check = self.db.execute_query(
            "SELECT 1 FROM sub_locations WHERE thread_id = %s AND is_active = true",
            (channel.id,),
            fetch='one'
        )
        return sub_location_check is not None
    
    async def _is_ship_interior(self, channel) -> bool:
        """Check if the channel is a ship interior"""
        if not hasattr(channel, 'name'):
            return False
        
        # Ship channels are named with pattern 'ship-{name}'
        return channel.name.startswith('ship-')
    
    async def _is_transit_channel(self, channel) -> bool:
        """Check if the channel is a transit channel"""
        if not hasattr(channel, 'name'):
            return False
        
        # Transit channels are named with pattern 'transit-{user_id}' or 'transit-group-{group_id}'
        return channel.name.startswith('transit-')
    
    async def _handle_home_leave(self, interaction: discord.Interaction):
        """Handle leaving a home interior"""
        user_id = interaction.user.id
        
        # Get the user's current home and location data
        current_home_data = self.db.execute_query(
            '''SELECT c.current_home_id, h.location_id, h.home_name
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = %s''',
            (user_id,),
            fetch='one'
        )
        
        if not current_home_data:
            await interaction.followup.send("❌ You're not inside a home!", ephemeral=True)
            return
        
        home_id, location_id, home_name = current_home_data
        
        # Check if anyone else is in the home
        others_in_home = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_home_id = %s AND user_id != %s",
            (home_id, user_id),
            fetch='all'
        )
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_home_id = NULL WHERE user_id = %s",
            (user_id,)
        )
        
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        self.bot.dispatch('home_leave', user_id)
        
        # Send area movement embed to location channel
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )[0]
        
        # Send area movement announcement via cross-guild broadcast
        embed = discord.Embed(
            title="🚪 Area Movement",
            description=f"**{char_name}** has exited the **{home_name}**.",
            color=0xFF6600
        )
        cross_guild_channels = await channel_manager.get_cross_guild_location_channels(location_id)
        for guild_channel, channel in cross_guild_channels:
            try:
                await channel.send(embed=embed)
            except:
                pass  # Skip if can't send to this guild
        
        # Give user access back to location (suppress arrival notification for home departures)
        await channel_manager.give_user_location_access(interaction.user, location_id, send_arrival_notification=False)
        
        # Remove from home channel
        await channel_manager.remove_user_home_access(interaction.user, home_id)
        
        # If this was the owner and others are inside, move them out too
        owner_id = self.db.execute_query(
            "SELECT owner_id FROM location_homes WHERE home_id = %s",
            (home_id,),
            fetch='one'
        )[0]
        
        if user_id == owner_id and others_in_home:
            # Move all other users out
            for (other_user_id,) in others_in_home:
                member = interaction.guild.get_member(other_user_id)
                if member:
                    # Update their location
                    self.db.execute_query(
                        "UPDATE characters SET current_home_id = NULL WHERE user_id = %s",
                        (other_user_id,)
                    )
                    
                    # Give them location access (suppress arrival notification for home departures)
                    await channel_manager.give_user_location_access(member, location_id, send_arrival_notification=False)
                    
                    # Remove from home channel
                    await channel_manager.remove_user_home_access(member, home_id)
                    
                    # Send them a notification
                    try:
                        await member.send(f"The owner of {home_name} has left, so you've been moved back to the location.")
                    except:
                        pass
        
        # Check if home should be cleaned up (empty and not owned by anyone present)
        remaining_users = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_home_id = %s AND is_logged_in = true",
            (home_id,),
            fetch='all'
        )
        
        if not remaining_users:
            # Get home channel_id for cleanup
            home_channel_data = self.db.execute_query(
                "SELECT channel_id FROM home_interiors WHERE home_id = %s",
                (home_id,),
                fetch='one'
            )
            if home_channel_data and home_channel_data[0]:
                try:
                    await channel_manager.cleanup_home_channel(home_channel_data[0])
                except:
                    pass  # If cleanup fails, that's okay
        
        await interaction.followup.send("🚪 You have left the home interior.", ephemeral=True)
    
    async def _handle_area_leave(self, interaction: discord.Interaction):
        """Handle leaving a sub-location"""
        user_id = interaction.user.id
        thread = interaction.channel
        
        if not isinstance(thread, discord.Thread):
            await interaction.followup.send("❌ This is not a sub-location thread!", ephemeral=True)
            return
        
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("You need a character to leave areas!", ephemeral=True)
            return
        
        current_location, char_name = char_info
        
        # Look up this thread in the sub_locations table
        sub_location_info = self.db.execute_query(
            "SELECT parent_location_id, name, sub_type FROM sub_locations WHERE thread_id = %s AND is_active = true",
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
        
        # Get the main location channel for announcements using guild-specific system
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        location_info = channel_manager.get_channel_id_from_location(
            interaction.guild.id, 
            parent_location_id
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
            # Remove user from thread
            await thread.remove_user(interaction.user)
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
                        "UPDATE sub_locations SET thread_id = NULL WHERE thread_id = %s",
                        (thread.id,)
                    )
                    
                    print(f"🧹 Auto-cleaned empty sub-location thread: {sub_location_name}")
                    
                except Exception as e:
                    print(f"❌ Failed to clean up empty sub-location thread: {e}")
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to remove you from this thread.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Thread not found or you're not in it.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error leaving sub-location: {str(e)}", ephemeral=True)
    
    async def _handle_ship_leave(self, interaction: discord.Interaction):
        """Handle leaving a ship interior"""
        user_id = interaction.user.id
        
        # Check if in a ship
        current_ship_data = self.db.execute_query(
            '''SELECT c.current_ship_id, s.name, c.current_location
               FROM characters c
               LEFT JOIN ships s ON c.current_ship_id = s.ship_id
               WHERE c.user_id = %s''',
            (user_id,),
            fetch='one'
        )
        
        if not current_ship_data or not current_ship_data[0]:
            await interaction.followup.send("❌ You're not inside a ship!", ephemeral=True)
            return
        
        ship_id, ship_name, location_id = current_ship_data
        
        # Check if anyone else is in the ship
        others_in_ship = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_ship_id = %s AND user_id != %s",
            (ship_id, user_id),
            fetch='all'
        )
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_ship_id = NULL WHERE user_id = %s",
            (user_id,)
        )
        
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Give user access back to location (suppress arrival notification to avoid duplicate)
        await channel_manager.give_user_location_access(interaction.user, location_id, send_arrival_notification=False)
        
        # Remove from ship channel
        await channel_manager.remove_user_ship_access(interaction.user, ship_id)
        
        # Send area movement embed to location channel
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )[0]
        
        # Send area movement announcement via cross-guild broadcast
        embed = discord.Embed(
            title="🚪 Area Movement",
            description=f"**{char_name}** has exited the **{ship_name}**.",
            color=0xFF6600
        )
        cross_guild_channels = await channel_manager.get_cross_guild_location_channels(location_id)
        for guild_channel, channel in cross_guild_channels:
            try:
                await channel.send(embed=embed)
            except:
                pass  # Skip if can't send to this guild
        
        # Check if this was the owner and others are inside
        owner_id = self.db.execute_query(
            "SELECT owner_id FROM ships WHERE ship_id = %s",
            (ship_id,),
            fetch='one'
        )[0]
        
        if user_id == owner_id and others_in_ship:
            import asyncio
            # Move all other users out after 20-second warning
            for (other_user_id,) in others_in_ship:
                member = interaction.guild.get_member(other_user_id)
                if member:
                    try:
                        # Send warning with location link
                        location_info = self.db.execute_query(
                            "SELECT name, channel_id FROM locations WHERE location_id = %s",
                            (location_id,),
                            fetch='one'
                        )
                        
                        if location_info and location_info[1]:
                            location_channel = interaction.guild.get_channel(location_info[1])
                            location_link = location_channel.mention if location_channel else location_info[0]
                        else:
                            location_link = "the location"
                        
                        await member.send(f"⚠️ The owner of {ship_name} has left the ship. You will be moved back to {location_link} in 20 seconds.")
                    except:
                        pass  # DM failed, continue
            
            # Wait 20 seconds then move everyone out
            await asyncio.sleep(20)
            
            # Move all remaining users out
            remaining_users = self.db.execute_query(
                "SELECT user_id FROM characters WHERE current_ship_id = %s AND user_id != %s",
                (ship_id, user_id),
                fetch='all'
            )
            
            for (other_user_id,) in remaining_users:
                member = interaction.guild.get_member(other_user_id)
                if member:
                    # Update their location
                    self.db.execute_query(
                        "UPDATE characters SET current_ship_id = NULL WHERE user_id = %s",
                        (other_user_id,)
                    )
                    
                    # Give them location access (suppress arrival notification to avoid duplicate)
                    await channel_manager.give_user_location_access(member, location_id, send_arrival_notification=False)
                    
                    # Remove from ship channel
                    await channel_manager.remove_user_ship_access(member, ship_id)
                    
                    # Send area movement embed for forced exit
                    other_char_name = self.db.execute_query(
                        "SELECT name FROM characters WHERE user_id = %s",
                        (other_user_id,),
                        fetch='one'
                    )[0]
                    
                    # Send area movement announcement via cross-guild broadcast
                    embed = discord.Embed(
                        title="🚪 Area Movement",
                        description=f"**{other_char_name}** has exited the **{ship_name}**.",
                        color=0xFF6600
                    )
                    cross_guild_channels = await channel_manager.get_cross_guild_location_channels(location_id)
                    for guild_channel, channel in cross_guild_channels:
                        try:
                            await channel.send(embed=embed)
                        except:
                            pass  # Skip if can't send to this guild
        
        # Clean up ship channel if empty
        remaining_users = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_ship_id = %s",
            (ship_id,),
            fetch='one'
        )[0]
        
        if remaining_users == 0:
            # Get ship channel info and clean up
            ship_channel = self.db.execute_query(
                "SELECT channel_id FROM ships WHERE ship_id = %s",
                (ship_id,),
                fetch='one'
            )
            
            if ship_channel and ship_channel[0]:
                ship_channel_obj = interaction.guild.get_channel(ship_channel[0])
                if ship_channel_obj:
                    try:
                        await ship_channel_obj.delete(reason="Ship interior cleanup - no users aboard")
                        self.db.execute_query(
                            "UPDATE ships SET channel_id = NULL WHERE ship_id = %s",
                            (ship_id,)
                        )
                    except:
                        pass  # Failed to delete, continue
        
        await interaction.followup.send("🚪 You've left your ship.", ephemeral=True)