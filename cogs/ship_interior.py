# cogs/ship_interior.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta
import asyncio


class ShipInteriorCog(commands.Cog):
    """Ship interior access and management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.cleanup_task = None
    
    async def cog_load(self):
        """Start cleanup task when cog loads"""
        if not self.cleanup_task:
            self.cleanup_task = self.bot.loop.create_task(self.cleanup_expired_invitations())
    
    async def cog_unload(self):
        """Stop cleanup task when cog unloads"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
    
    async def cleanup_expired_invitations(self):
        """Remove expired ship invitations every 10 minutes"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                # Remove expired invitations
                deleted = self.db.execute_query(
                    "DELETE FROM ship_invitations WHERE expires_at <= NOW()",
                    fetch='rowcount'
                )
                
                if deleted and deleted > 0:
                    print(f"🧹 Cleaned up {deleted} expired ship invitations")
                
                # Wait 10 minutes before next cleanup
                await asyncio.sleep(600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error cleaning up ship invitations: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    ship_group = app_commands.Group(name="shipinterior", description="Ship interior management commands")
    ship_interior_group = app_commands.Group(name="interior", description="Ship interior management", parent=ship_group)
    
    @ship_interior_group.command(name="enter", description="Enter your ship interior")
    async def enter_ship(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if already in a ship
        current_ship = self.db.execute_query(
            "SELECT current_ship_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if current_ship and current_ship[0]:
            await interaction.followup.send("You are already inside a ship! Use `/tqe` to leave your ship first.", ephemeral=True)
            return
        
        # Get character location and status
        char_info = self.db.execute_query(
            "SELECT current_location, location_status, active_ship_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or char_info[1] != 'docked':
            await interaction.followup.send("You must be docked at a location to enter your ship!", ephemeral=True)
            return
        
        location_id, location_status, active_ship_id = char_info
        
        if not active_ship_id:
            await interaction.followup.send("You don't have an active ship!", ephemeral=True)
            return
        
        # Get ship info
        ship_info = self.db.execute_query(
            '''SELECT ship_id, name, ship_type, interior_description, channel_id
               FROM ships WHERE ship_id = %s''',
            (active_ship_id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.followup.send("Ship not found!", ephemeral=True)
            return
        
        # Create ship interior channel and give access
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        ship_channel = await channel_manager.get_or_create_ship_channel(
            interaction.guild,
            ship_info,
            interaction.user
        )
        
        if ship_channel:
            # Send area movement embed to location channel BEFORE removing access
            char_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            # Ensure location channel exists and get it
            location_channel = await channel_manager.get_or_create_location_channel(
                interaction.guild, location_id
            )
            
            if location_channel:
                embed = discord.Embed(
                    title="🚪 Area Movement",
                    description=f"**{char_name}** enters the **{ship_info[1]}**.",
                    color=0x7289DA
                )
                try:
                    await self.bot.send_with_cross_guild_broadcast(location_channel, embed=embed)
                except Exception as e:
                    print(f"❌ Failed to send ship entry embed: {e}")
            
            # Update character to be inside ship
            self.db.execute_query(
                "UPDATE characters SET current_ship_id = %s WHERE user_id = %s",
                (active_ship_id, interaction.user.id)
            )
            
            # Keep location channel access - users should retain access to both ship and location channels
            
            # Trigger cleanup check after successful operations - add small delay to ensure database consistency
            async def delayed_cleanup():
                await asyncio.sleep(2)  # Allow database updates to complete
                await channel_manager._immediate_cleanup_check(interaction.guild, location_id)
            
            asyncio.create_task(delayed_cleanup())
            
            await interaction.followup.send(
                f"You've entered your ship. Head to {ship_channel.mention}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("Failed to create ship interior.", ephemeral=True)
    
    @ship_interior_group.command(name="leave", description="Leave your ship interior")
    async def leave_ship(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if in a ship
        current_ship_data = self.db.execute_query(
            '''SELECT c.current_ship_id, s.name, c.current_location
               FROM characters c
               LEFT JOIN ships s ON c.current_ship_id = s.ship_id
               WHERE c.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not current_ship_data or not current_ship_data[0]:
            await interaction.followup.send("You're not inside a ship!", ephemeral=True)
            return
        
        ship_id, ship_name, location_id = current_ship_data
        
        # Check if anyone else is in the ship
        others_in_ship = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_ship_id = %s AND user_id != %s",
            (ship_id, interaction.user.id),
            fetch='all'
        )
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_ship_id = NULL WHERE user_id = %s",
            (interaction.user.id,)
        )
        
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Location access is already preserved - no need to restore it
        
        # Remove from ship channel
        await channel_manager.remove_user_ship_access(interaction.user, ship_id)
        
        # Send area movement embed to location channel
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Ensure location channel exists and send exit embed
        location_channel = await channel_manager.get_or_create_location_channel(
            interaction.guild, location_id
        )
        
        if location_channel:
            embed = discord.Embed(
                title="🚪 Area Movement",
                description=f"**{char_name}** has exited the **{ship_name}**.",
                color=0xFF6600
            )
            try:
                await self.bot.send_with_cross_guild_broadcast(location_channel, embed=embed)
            except Exception as e:
                print(f"❌ Failed to send ship exit embed: {e}")
        
        # Check if this was the owner and others are inside
        owner_id = self.db.execute_query(
            "SELECT owner_id FROM ships WHERE ship_id = %s",
            (ship_id,),
            fetch='one'
        )[0]
        
        if interaction.user.id == owner_id and others_in_ship:
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
                (ship_id, interaction.user.id),
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
                    
                    # Ensure location channel exists for forced exit embed
                    location_channel = await channel_manager.get_or_create_location_channel(
                        interaction.guild, location_id
                    )
                    
                    if location_channel:
                        embed = discord.Embed(
                            title="🚪 Area Movement",
                            description=f"**{other_char_name}** has exited the **{ship_name}**.",
                            color=0xFF6600
                        )
                        try:
                            await self.bot.send_with_cross_guild_broadcast(location_channel, embed=embed)
                        except Exception as e:
                            print(f"❌ Failed to send forced exit embed: {e}")
        
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
        
        await interaction.followup.send("You've left your ship.", ephemeral=True)
    
    @ship_interior_group.command(name="invite", description="Invite someone to your ship")
    @app_commands.describe(player="The player to invite to your ship")
    async def invite_to_ship(self, interaction: discord.Interaction, player: discord.Member):
        if player.id == interaction.user.id:
            await interaction.response.send_message("You can't invite yourself!", ephemeral=True)
            return
        
        # Check if user is in their own ship
        ship_data = self.db.execute_query(
            '''SELECT s.ship_id, s.name, c.current_location
               FROM characters c
               JOIN ships s ON c.current_ship_id = s.ship_id
               WHERE c.user_id = %s AND s.owner_id = %s''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not ship_data:
            await interaction.response.send_message("You must be inside your own ship to invite someone!", ephemeral=True)
            return
        
        ship_id, ship_name, location_id = ship_data
        
        # Check if target player is at the same location and docked
        target_info = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not target_info or target_info[0] != location_id or target_info[1] != 'docked':
            await interaction.response.send_message(f"{player.mention} must be docked at the same location as your ship!", ephemeral=True)
            return
        
        # Create invitation
        expires_at = datetime.now() + timedelta(minutes=5)
        
        self.db.execute_query(
            '''INSERT INTO ship_invitations (ship_id, inviter_id, invitee_id, location_id, expires_at)
               VALUES (%s, %s, %s, %s, %s)''',
            (ship_id, interaction.user.id, player.id, location_id, expires_at)
        )
        
        await interaction.response.send_message(
            f"Invited {player.mention} to your ship. They have 5 minutes to accept with `/shipinterior interior accept`.",
            ephemeral=False
        )
        
        # Notify the invitee
        try:
            await player.send(f"{interaction.user.mention} has invited you aboard their ship '{ship_name}'. Use `/shipinterior interior accept` to enter.")
        except:
            pass  # DM failed
    
    @ship_interior_group.command(name="accept", description="Accept a ship invitation")
    async def accept_ship_invitation(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Find valid invitation
        invitation = self.db.execute_query(
            '''SELECT i.invitation_id, i.ship_id, i.inviter_id, s.name, s.interior_description
               FROM ship_invitations i
               JOIN ships s ON i.ship_id = s.ship_id
               WHERE i.invitee_id = %s AND i.expires_at > NOW()
               ORDER BY i.created_at DESC
               LIMIT 1''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not invitation:
            await interaction.followup.send("You don't have any active ship invitations.", ephemeral=True)
            return
        
        invitation_id, ship_id, inviter_id, ship_name, interior_desc = invitation
        
        # Check if already in a ship
        current_ship = self.db.execute_query(
            "SELECT current_ship_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if current_ship and current_ship[0]:
            await interaction.followup.send("You must leave your current location before accepting an invitation!", ephemeral=True)
            return
        
        # Get ship channel
        ship_channel_id = self.db.execute_query(
            "SELECT channel_id FROM ships WHERE ship_id = %s",
            (ship_id,),
            fetch='one'
        )
        
        if not ship_channel_id or not ship_channel_id[0]:
            await interaction.followup.send("The ship interior no longer exists.", ephemeral=True)
            return
        
        ship_channel = interaction.guild.get_channel(ship_channel_id[0])
        if not ship_channel:
            await interaction.followup.send("The ship interior channel no longer exists.", ephemeral=True)
            return
        
        # Accept invitation
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Send area movement embed to location channel BEFORE updating character location
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Get current location to send embed
        current_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if current_location:
            # Ensure location channel exists and get it
            location_channel = await channel_manager.get_or_create_location_channel(
                interaction.guild, current_location
            )
            
            if location_channel:
                embed = discord.Embed(
                    title="🚪 Area Movement",
                    description=f"**{char_name}** boards the **{ship_name}**.",
                    color=0x7289DA
                )
                try:
                    await self.bot.send_with_cross_guild_broadcast(location_channel, embed=embed)
                except Exception as e:
                    print(f"❌ Failed to send ship boarding embed: {e}")
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_ship_id = %s WHERE user_id = %s",
            (ship_id, interaction.user.id)
        )
        
        # Keep location channel access - users should retain access to both ship and location channels
        
        # Give access to ship channel
        success = await channel_manager.give_user_ship_access(interaction.user, ship_id)
        
        if success:
            # Delete the invitation
            self.db.execute_query(
                "DELETE FROM ship_invitations WHERE invitation_id = %s",
                (invitation_id,)
            )
            
            await interaction.followup.send(
                f"You've boarded {ship_name}. Head to {ship_channel.mention}",
                ephemeral=True
            )
            
            # Send area movement embed to location channel
            char_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            # Ensure location channel exists for invitation acceptance embed
            location_channel = await channel_manager.get_or_create_location_channel(
                interaction.guild, current_location
            )
            
            if location_channel:
                embed = discord.Embed(
                    title="🚪 Area Movement",
                    description=f"**{char_name}** enters the **{ship_name}**.",
                    color=0x7289DA
                )
                try:
                    await self.bot.send_with_cross_guild_broadcast(location_channel, embed=embed)
                except Exception as e:
                    print(f"❌ Failed to send invitation acceptance embed: {e}")
            
            # Notify the inviter
            try:
                inviter = interaction.guild.get_member(inviter_id)
                if inviter:
                    await ship_channel.send(f"{interaction.user.mention} has boarded the ship.")
            except:
                pass
        else:
            await interaction.followup.send("Failed to board the ship.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShipInteriorCog(bot))