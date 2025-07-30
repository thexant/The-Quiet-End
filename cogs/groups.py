# cogs/groups.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List
import asyncio
import json
from datetime import datetime, timedelta, timezone


class GroupsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Start cleanup task for expired invites and votes
        self.cleanup_task = self.bot.loop.create_task(self._cleanup_expired_data())
    
    async def _cleanup_expired_data(self):
        """Background task to clean up expired invites and votes"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Clean up expired invites using Unix timestamp
                current_timestamp = int(datetime.now().timestamp())
                self.db.execute_query(
                    "DELETE FROM group_invites WHERE expires_at < ?",
                    (current_timestamp,)
                )
                
                # Clean up expired vote sessions
                expired_sessions = self.db.execute_query(
                    "SELECT session_id FROM group_vote_sessions WHERE expires_at < datetime('now')",
                    fetch='all'
                )
                
                for session_id, in expired_sessions:
                    self.db.execute_query(
                        "DELETE FROM group_votes WHERE session_id = ?",
                        (session_id,)
                    )
                    self.db.execute_query(
                        "DELETE FROM group_vote_sessions WHERE session_id = ?",
                        (session_id,)
                    )
                
            except Exception as e:
                print(f"Error in group cleanup: {e}")
                await asyncio.sleep(60)
    
    group_group = app_commands.Group(name="group", description="Group and crew management")
    
    @group_group.command(name="create", description="Create a new group")
    @app_commands.describe(name="Name for your group (optional)")
    async def create_group(self, interaction: discord.Interaction, name: str = None):
        # Check if user already in a group
        existing = self.db.execute_query(
            "SELECT group_id FROM characters WHERE user_id = ? AND group_id IS NOT NULL",
            (interaction.user.id,),
            fetch='one'
        )
        
        if existing:
            await interaction.response.send_message("You're already in a group! Leave your current group first.", ephemeral=True)
            return
        
        # Get current location and character name
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, char_name = char_info
        
        # Generate group name if not provided
        if not name:
            name = f"{char_name}'s Crew"
        
        # Create group
        self.db.execute_query(
            "INSERT INTO groups (name, leader_id, current_location) VALUES (?, ?, ?)",
            (name, interaction.user.id, current_location)
        )
        
        group_id = self.db.execute_query(
            "SELECT group_id FROM groups WHERE leader_id = ? ORDER BY group_id DESC LIMIT 1",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Add user to group
        self.db.execute_query(
            "UPDATE characters SET group_id = ? WHERE user_id = ?",
            (group_id, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="✅ Group Created",
            description=f"Successfully created group **{name}**!",
            color=0x9932cc
        )
        embed.add_field(name="Leader", value=char_name, inline=True)
        embed.add_field(name="Group ID", value=str(group_id), inline=True)
        embed.add_field(
            name="💡 Next Steps",
            value="• Use `/group invite @user` to invite specific players\n• Manage your group with `/group info`\n• Start votes with `/group travel_vote` or when accepting jobs",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @group_group.command(name="invite", description="Invite a user to your group (leader only)")
    @app_commands.describe(user="User to invite to the group")
    async def invite_user(self, interaction: discord.Interaction, user: discord.Member):
        # Check if user is group leader
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id, g.current_location
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group or not the leader.", ephemeral=True)
            return
        group_id, group_name, leader_id, current_location = group_info
        
        if leader_id != interaction.user.id:
            await interaction.response.send_message("Only the group leader can invite members.", ephemeral=True)
            return
        
        # Check if target user has a character
        target_char = self.db.execute_query(
            "SELECT name, group_id, current_location FROM characters WHERE user_id = ?",
            (user.id,),
            fetch='one'
        )
        
        if not target_char:
            await interaction.response.send_message(f"{user.mention} doesn't have a character.", ephemeral=True)
            return
        
        char_name, existing_group, user_location = target_char
        
        if existing_group:
            await interaction.response.send_message(f"{user.mention} is already in a group.", ephemeral=True)
            return
        
        if user_location != current_location:
            await interaction.response.send_message(f"{user.mention} is not at the same location as your group.", ephemeral=True)
            return
        
        # Check if already invited - using Unix timestamp
        current_timestamp = int(datetime.now().timestamp())
        existing_invite = self.db.execute_query(
            "SELECT invite_id FROM group_invites WHERE group_id = ? AND invitee_id = ? AND expires_at > ?",
            (group_id, user.id, current_timestamp),
            fetch='one'
        )
        
        if existing_invite:
            await interaction.response.send_message(f"{user.mention} already has a pending invite to your group.", ephemeral=True)
            return
        
        # Create invite (expires in 10 minutes) - store as Unix timestamp
        expire_datetime = datetime.now() + timedelta(minutes=10)
        expire_timestamp = int(expire_datetime.timestamp())
        self.db.execute_query(
            "INSERT INTO group_invites (group_id, inviter_id, invitee_id, expires_at) VALUES (?, ?, ?, ?)",
            (group_id, interaction.user.id, user.id, expire_timestamp)
        )
        
        # Notify both users
        embed = discord.Embed(
            title="📧 Group Invitation Sent",
            description=f"Invitation sent to **{char_name}** ({user.mention})",
            color=0x00ff00
        )
        embed.add_field(name="Group", value=group_name, inline=True)
        embed.add_field(name="Expires", value=f"<t:{expire_timestamp}:R>", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Send invite notification in location channel instead of DM
        location_info = self.db.execute_query(
            '''SELECT l.channel_id 
               FROM locations l 
               WHERE l.location_id = ?''',
            (current_location,),
            fetch='one'
        )
        
        if location_info and location_info[0]:
            location_channel = self.bot.get_channel(location_info[0])
            if location_channel:
                # Send public invitation notification
                invite_embed = discord.Embed(
                    title="📧 Group Invitation",
                    description=f"**{interaction.user.display_name}** has invited {user.mention} to join **{group_name}**",
                    color=0x4169E1
                )
                invite_embed.add_field(
                    name="How to Join",
                    value=f"{user.mention} can use `/group join {group_name}` to accept this invitation.",
                    inline=False
                )
                invite_embed.add_field(name="Expires", value=f"<t:{expire_timestamp}:R>", inline=True)
                
                await location_channel.send(embed=invite_embed)
    
    @group_group.command(name="join", description="Join a group (requires invitation)")
    @app_commands.describe(group_name="Name of the group to join")
    async def join_group(self, interaction: discord.Interaction, group_name: str):
        # Check if user already in a group
        existing = self.db.execute_query(
            "SELECT group_id FROM characters WHERE user_id = ? AND group_id IS NOT NULL",
            (interaction.user.id,),
            fetch='one'
        )
        
        if existing:
            await interaction.response.send_message("You're already in a group! Leave your current group first.", ephemeral=True)
            return
        
        # Check if user has a character
        char_check = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_check:
            await interaction.response.send_message("You need a character first! Use `/character create`.", ephemeral=True)
            return
        
        # Find group and check for valid invitation - using Unix timestamp comparison
        current_timestamp = int(datetime.now().timestamp())
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id, c.name as leader_name, gi.invite_id
               FROM groups g
               JOIN characters c ON g.leader_id = c.user_id
               JOIN group_invites gi ON g.group_id = gi.group_id
               WHERE LOWER(g.name) = LOWER(?) 
                     AND g.status = 'active' 
                     AND gi.invitee_id = ? 
                     AND gi.expires_at > ?''',
            (group_name, interaction.user.id, current_timestamp),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message(
                f"No valid invitation found for group '{group_name}' or group doesn't exist.\nMake sure you have a valid invitation that hasn't expired.", 
                ephemeral=True
            )
            return
        
        group_id, name, leader_id, leader_name, invite_id = group_info
        
        # Add to group
        self.db.execute_query(
            "UPDATE characters SET group_id = ? WHERE user_id = ?",
            (group_id, interaction.user.id)
        )
        
        # Remove the used invitation
        self.db.execute_query(
            "DELETE FROM group_invites WHERE invite_id = ?",
            (invite_id,)
        )
        
        embed = discord.Embed(
            title="✅ Joined Group",
            description=f"You have joined **{name}**!",
            color=0x00ff00
        )
        embed.add_field(name="Leader", value=leader_name, inline=True)
        embed.add_field(name="Group ID", value=str(group_id), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Get the group's current location to send notification in location channel
        location_info = self.db.execute_query(
            '''SELECT g.current_location, l.channel_id 
               FROM groups g 
               JOIN locations l ON g.current_location = l.location_id 
               WHERE g.group_id = ?''',
            (group_id,),
            fetch='one'
        )
        
        if location_info and location_info[1]:
            location_channel = self.bot.get_channel(location_info[1])
            if location_channel:
                # Send notification to location channel
                char_name = char_check[0]
                notification_embed = discord.Embed(
                    title="👥 Group Update",
                    description=f"**{char_name}** has joined the group **{name}**!",
                    color=0x00ff00
                )

                # ✅ Get how many members now
                member_count = self.db.execute_query(
                    "SELECT COUNT(*) FROM characters WHERE group_id = ?",
                    (group_id,),
                    fetch='one'
                )[0]

                notification_embed.set_footer(text=f"Group Size: {member_count} members")

                await location_channel.send(embed=notification_embed)    
    @group_group.command(name="leave", description="Leave your current group")
    async def leave_group(self, interaction: discord.Interaction):
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id, c.name as char_name
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group.", ephemeral=True)
            return
        
        group_id, group_name, leader_id, char_name = group_info
        
        if leader_id == interaction.user.id:
            await interaction.response.send_message("Leaders cannot leave their group. Use `/group disband` to dissolve the group.", ephemeral=True)
            return
        
        # Remove from group
        self.db.execute_query(
            "UPDATE characters SET group_id = NULL WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        embed = discord.Embed(
            title="👋 Left Group",
            description=f"You have left **{group_name}**.",
            color=0xffa500
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Get the group's current location to send notification
        location_info = self.db.execute_query(
            '''SELECT g.current_location, l.channel_id 
               FROM groups g 
               JOIN locations l ON g.current_location = l.location_id 
               WHERE g.group_id = ?''',
            (group_id,),
            fetch='one'
        )
        
        if location_info and location_info[1]:
            location_channel = self.bot.get_channel(location_info[1])
            if location_channel:
                # Get remaining members count
                remaining_members = self.db.execute_query(
                    "SELECT COUNT(*) FROM characters WHERE group_id = ?",
                    (group_id,),
                    fetch='one'
                )[0]
                
                # Send notification to location channel
                notification_embed = discord.Embed(
                    title="👥 Group Update",
                    description=f"**{char_name}** has left the group **{group_name}**.",
                    color=0xffa500
                )
                
                if remaining_members > 0:
                    notification_embed.set_footer(text=f"Group Size: {remaining_members} members remaining")
                else:
                    notification_embed.set_footer(text="Group has been automatically disbanded (no members remaining)")
                
                await location_channel.send(embed=notification_embed)
    
    @group_group.command(name="disband", description="Dissolve your group (leader only)")
    async def disband_group(self, interaction: discord.Interaction):
        # Check if user is group leader
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id, g.current_location
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group.", ephemeral=True)
            return
        
        group_id, group_name, leader_id, current_location = group_info
        
        if leader_id != interaction.user.id:
            await interaction.response.send_message("Only the group leader can disband the group.", ephemeral=True)
            return
        
        # Get all members to notify them
        members = self.db.execute_query(
            "SELECT user_id, name FROM characters WHERE group_id = ?",
            (group_id,),
            fetch='all'
        )
        
        # Remove all members from group
        self.db.execute_query(
            "UPDATE characters SET group_id = NULL WHERE group_id = ?",
            (group_id,)
        )
        
        # Mark group as dissolved
        self.db.execute_query(
            "UPDATE groups SET status = 'dissolved' WHERE group_id = ?",
            (group_id,)
        )
        
        # Clean up any active votes
        self.db.execute_query(
            "DELETE FROM group_votes WHERE session_id IN (SELECT session_id FROM group_vote_sessions WHERE group_id = ?)",
            (group_id,)
        )
        self.db.execute_query(
            "DELETE FROM group_vote_sessions WHERE group_id = ?",
            (group_id,)
        )
        
        embed = discord.Embed(
            title="💥 Group Disbanded",
            description=f"**{group_name}** has been dissolved.",
            color=0xff0000
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Get the group's location to send notification
        location_info = self.db.execute_query(
            '''SELECT l.channel_id 
               FROM locations l 
               WHERE l.location_id = ?''',
            (current_location,),
            fetch='one'
        )
        
        if location_info and location_info[0]:
            location_channel = self.bot.get_channel(location_info[0])
            if location_channel:
                # Send notification to location channel
                notification_embed = discord.Embed(
                    title="💥 Group Disbanded",
                    description=f"The group **{group_name}** has been disbanded by its leader.",
                    color=0xff0000
                )
                notification_embed.add_field(
                    name="Affected Members", 
                    value=", ".join([name for _, name in members]) if members else "None",
                    inline=False
                )
                
                await location_channel.send(embed=notification_embed)
    
    @group_group.command(name="info", description="View information about your group")
    async def group_info(self, interaction: discord.Interaction):
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id, g.current_location, g.status, g.created_at,
                      l.name as location_name, c.name as leader_name
               FROM characters ch
               JOIN groups g ON ch.group_id = g.group_id
               LEFT JOIN locations l ON g.current_location = l.location_id
               LEFT JOIN characters c ON g.leader_id = c.user_id
               WHERE ch.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group.", ephemeral=True)
            return
        
        group_id, name, leader_id, current_location, status, created_at, location_name, leader_name = group_info
        
        # Get group members
        members = self.db.execute_query(
            '''SELECT c.name, c.user_id, s.ship_type, s.current_fuel, s.fuel_capacity
               FROM characters c
               LEFT JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.group_id = ?
               ORDER BY c.user_id = ? DESC''',  # Leader first
            (group_id, leader_id),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"🎯 Group: {name}",
            description=f"Group information and member status",
            color=0x9932cc
        )
        
        embed.add_field(name="Leader", value=leader_name, inline=True)
        embed.add_field(name="Status", value=status.title(), inline=True)
        embed.add_field(name="Location", value=location_name or "Unknown", inline=True)
        
        # Member list with ship info and login status
        member_text = []
        total_fuel = 0
        low_fuel_members = 0
        online_members = 0

        for member_name, member_id, ship_type, fuel, fuel_cap in members:
            is_leader = "👑" if member_id == leader_id else "👤"
            
            # Check if member is logged in
            is_online = self.db.execute_query(
                "SELECT is_logged_in FROM characters WHERE user_id = ?",
                (member_id,),
                fetch='one'
            )[0]
            
            status_emoji = "🟢" if is_online else "⚫"
            
            if is_online:
                online_members += 1
                
                if fuel is not None and fuel_cap is not None:
                    fuel_percent = (fuel / fuel_cap) * 100 if fuel_cap > 0 else 0
                    fuel_emoji = "🟢" if fuel_percent > 70 else "🟡" if fuel_percent > 30 else "🔴"
                    if fuel_percent < 30:
                        low_fuel_members += 1
                    total_fuel += fuel
                    member_text.append(f"{is_leader} **{member_name}** {status_emoji} {fuel_emoji} ({ship_type})")
                else:
                    member_text.append(f"{is_leader} **{member_name}** {status_emoji} ❓ (No ship data)")
            else:
                member_text.append(f"{is_leader} **{member_name}** {status_emoji} (Offline)")

        embed.add_field(
            name=f"Members ({len(members)}) - {online_members} Online",
            value="\n".join(member_text) if member_text else "None",
            inline=False
        )

        # Group readiness status (only for online members)
        if online_members == 0:
            embed.add_field(
                name="💤 Group Status",
                value="No members currently online",
                inline=True
            )
        elif low_fuel_members > 0:
            embed.add_field(
                name="⚠️ Group Status",
                value=f"{low_fuel_members} online member(s) have low fuel",
                inline=True
            )
        else:
            embed.add_field(
                name="✅ Group Status",
                value="All online members ready for travel",
                inline=True
            )
        
        embed.add_field(name="Total Group Fuel", value=f"{total_fuel} units", inline=True)
        
        # Check for pending invites
        pending_invites = self.db.execute_query(
            '''SELECT COUNT(*) FROM group_invites gi
               WHERE gi.group_id = ? AND gi.expires_at > datetime('now')''',
            (group_id,),
            fetch='one'
        )[0]
        
        if pending_invites > 0:
            embed.add_field(
                name="📧 Pending Invitations",
                value=f"{pending_invites} invite(s) pending",
                inline=True
            )
        
        # Add group actions for leader
        if leader_id == interaction.user.id:
            embed.add_field(
                name="👑 Leader Commands",
                value="• `/group invite @user` - Invite member\n• `/group kick @user` - Remove member\n• `/group travel_vote` - Start travel vote\n• `/group disband` - Dissolve group",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @group_group.command(name="kick", description="Remove a member from your group (leader only)")
    @app_commands.describe(user="User to remove from the group")
    async def kick_member(self, interaction: discord.Interaction, user: discord.Member):
        # Check if user is group leader
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group.", ephemeral=True)
            return
        
        group_id, group_name, leader_id = group_info
        
        if leader_id != interaction.user.id:
            await interaction.response.send_message("Only the group leader can kick members.", ephemeral=True)
            return
        
        # Check if target user is in the group
        target_in_group = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ? AND group_id = ?",
            (user.id, group_id),
            fetch='one'
        )
        
        if not target_in_group:
            await interaction.response.send_message(f"{user.mention} is not in your group.", ephemeral=True)
            return
        
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot kick yourself. Use `/group disband` instead.", ephemeral=True)
            return
        
        # Remove from group
        self.db.execute_query(
            "UPDATE characters SET group_id = NULL WHERE user_id = ?",
            (user.id,)
        )
        
        char_name = target_in_group[0]
        
        embed = discord.Embed(
            title="👢 Member Removed",
            description=f"**{char_name}** has been removed from **{group_name}**.",
            color=0xff4444
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Get the group's location to send notification
        location_info = self.db.execute_query(
            '''SELECT l.channel_id 
               FROM locations l 
               WHERE l.location_id = ?''',
            (current_location,),
            fetch='one'
        )
        
        if location_info and location_info[0]:
            location_channel = self.bot.get_channel(location_info[0])
            if location_channel:
                # Get remaining members count
                remaining_members = self.db.execute_query(
                    "SELECT COUNT(*) FROM characters WHERE group_id = ?",
                    (group_id,),
                    fetch='one'
                )[0]
                
                # Send notification to location channel
                notification_embed = discord.Embed(
                    title="👥 Group Update",
                    description=f"**{char_name}** has been removed from the group **{group_name}**.",
                    color=0xff4444
                )
                notification_embed.set_footer(text=f"Group Size: {remaining_members} members remaining")
                
                await location_channel.send(embed=notification_embed)
    
    @group_group.command(name="travel_vote", description="Start a vote for group travel (leader only)")
    async def travel_vote(self, interaction: discord.Interaction):
        # Check if user is group leader
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id, g.current_location
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )

        if not group_info:
            await interaction.response.send_message("You're not in a group or not the leader.", ephemeral=True)
            return

        group_id, group_name, leader_id, _ = group_info

        # --- FIX: Sync group's location with leader's location before proceeding ---
        current_location = await self._sync_group_location(group_id, leader_id)
        if current_location is None:
            await interaction.response.send_message("Cannot start a vote because the group leader is currently in transit.", ephemeral=True)
            return
        # --- END FIX ---

        if leader_id != interaction.user.id:
            await interaction.response.send_message("Only the group leader can start travel votes.", ephemeral=True)
            return

        # Check for an existing active vote
        current_timestamp = int(datetime.now().timestamp())
        existing_vote = self.db.execute_query(
            "SELECT session_id FROM group_vote_sessions WHERE group_id = ? AND expires_at > ?",
            (group_id, current_timestamp),
            fetch='one'
        )

        if existing_vote:
            await interaction.response.send_message("There is already an active vote for this group.", ephemeral=True)
            return

        # Fetch all available corridors from the group's (now correct) current location
        corridors = self.db.execute_query(
            '''SELECT c.corridor_id, c.name, l.name AS dest_name, c.travel_time, c.fuel_cost, c.danger_level
               FROM corridors c
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1''',
            (current_location,),
            fetch='all'
        )

        if not corridors:
            location_name = self.db.execute_query("SELECT name FROM locations WHERE location_id = ?", (current_location,), fetch='one')[0]
            await interaction.response.send_message(f"There are no available travel routes from the group's current location: **{location_name}**.", ephemeral=True)
            return

        # (The rest of the function remains the same as the previous fix)
        # Build the dropdown for the leader to select a route
        options = []
        for cid, cname, dest_name, ttime, cost, danger in corridors[:25]:
            time_text = f"{ttime//60}m"
            danger_text = "⚠️" * danger if danger > 0 else "Safe"
            options.append(discord.SelectOption(
                label=f"To: {dest_name}",
                description=f"via {cname[:20]}.. | {time_text} | {cost} fuel | {danger_text}",
                value=str(cid)
            ))

        select = discord.ui.Select(placeholder="Choose a destination to start a vote...", options=options)

        async def select_callback(inter: discord.Interaction):
            if inter.user.id != leader_id:
                await inter.response.send_message("Only the group leader can make this selection.", ephemeral=True)
                return

            chosen_corridor_id = int(select.values[0])
            corridor = next((c for c in corridors if c[0] == chosen_corridor_id), None)

            if not corridor:
                await inter.response.edit_message(content="Error: Selected corridor not found.", view=None)
                return

            corridor_id, corridor_name, dest_name, travel_time, fuel_cost, danger = corridor

            members = self.db.execute_query(
                "SELECT user_id, name FROM characters WHERE group_id = ?",
                (group_id,),
                fetch='all'
            )

            if len(members) < 2:
                await inter.response.edit_message(content="You need at least 2 group members to start a vote.", view=None)
                return

            vote_data = {
                'type': 'travel', 'corridor_id': corridor_id, 'destination': dest_name,
                'corridor_name': corridor_name, 'travel_time': travel_time,
                'fuel_cost': fuel_cost, 'danger_level': danger
            }

            expire_datetime = datetime.now() + timedelta(minutes=10)

            self.db.execute_query(
                '''INSERT INTO group_vote_sessions (group_id, vote_type, vote_data, channel_id, expires_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (group_id, 'travel', json.dumps(vote_data), inter.channel.id, expire_datetime.isoformat())
            )

            session_id = self.db.execute_query(
                "SELECT session_id FROM group_vote_sessions WHERE group_id = ? ORDER BY session_id DESC LIMIT 1",
                (group_id,), fetch='one'
            )[0]

            embed = discord.Embed(
                title="🗳️ Group Travel Vote",
                description=f"**{group_name}** - Vote to travel to **{dest_name}**",
                color=0x4169E1
            )
            time_text_display = f"{travel_time//60}m {travel_time%60}s"
            danger_text_display = "⚠️" * danger if danger else "Safe"

            embed.add_field(name="Destination", value=dest_name, inline=True)
            embed.add_field(name="Via", value=corridor_name, inline=True)
            embed.add_field(name="Travel Time", value=time_text_display, inline=True)
            embed.add_field(name="Fuel Cost", value=f"{fuel_cost} per ship", inline=True)
            embed.add_field(name="Danger Level", value=danger_text_display, inline=True)
            embed.add_field(name="Vote Duration", value="10 minutes", inline=True)
            embed.add_field(
                name="📋 How to Vote",
                value=f"All group members must use `/group vote yes` or `/group vote no` in this channel.",
                inline=False
            )
            
            await inter.response.edit_message(content=f"✅ Travel vote for **{dest_name}** has been started in the channel.", embed=None, view=None)
            await inter.channel.send(embed=embed)

            asyncio.create_task(self._process_vote_timeout(session_id, 600))

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("Select a destination for the group travel vote:", view=view, ephemeral=True)
    async def _sync_group_location(self, group_id: int, leader_id: int) -> int | None:
        """
        Ensures the group's location is synced with the leader's current location.
        Returns the synchronized location ID or None if the leader is in transit.
        """
        # Get the leader's current location from the characters table
        leader_location_data = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (leader_id,),
            fetch='one'
        )

        if leader_location_data and leader_location_data[0] is not None:
            leader_location_id = leader_location_data[0]
            # Update the groups table with the correct location
            self.db.execute_query(
                "UPDATE groups SET current_location = ? WHERE group_id = ?",
                (leader_location_id, group_id)
            )
            return leader_location_id
        
        # Leader is in transit or has no location, so we can't sync
        return None
    @group_group.command(name="vote", description="Cast your vote in an active group vote")
    @app_commands.describe(choice="Your vote choice")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def cast_vote(self, interaction: discord.Interaction, choice: str):
        # Get user's group and check for active vote
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, c.name as char_name
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ? AND g.status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group.", ephemeral=True)
            return
        
        group_id, group_name, char_name = group_info
        
        current_timestamp = int(datetime.now().timestamp())

        vote_session = self.db.execute_query(
            '''SELECT session_id, vote_type, vote_data FROM group_vote_sessions
               WHERE group_id = ? AND channel_id = ? AND expires_at > ?''',
            (group_id, interaction.channel.id, current_timestamp),
            fetch='one'
        )
        
        if not vote_session:
            await interaction.response.send_message("No active vote found in this channel for your group.", ephemeral=True)
            return
        
        session_id, vote_type, vote_data_str = vote_session
        
        # Check if user already voted
        existing_vote = self.db.execute_query(
            "SELECT vote_id FROM group_votes WHERE session_id = ? AND user_id = ?",
            (session_id, interaction.user.id),
            fetch='one'
        )
        
        if existing_vote:
            # Update existing vote
            self.db.execute_query(
                "UPDATE group_votes SET vote_value = ?, voted_at = datetime('now') WHERE vote_id = ?",
                (choice, existing_vote[0])
            )
            action = "updated"
        else:
            # Create new vote
            self.db.execute_query(
                "INSERT INTO group_votes (session_id, user_id, vote_value) VALUES (?, ?, ?)",
                (session_id, interaction.user.id, choice)
            )
            action = "cast"
        
        # Get current vote counts
        votes = self.db.execute_query(
            "SELECT vote_value, COUNT(*) FROM group_votes WHERE session_id = ? GROUP BY vote_value",
            (session_id,),
            fetch='all'
        )
        
        vote_counts = {'yes': 0, 'no': 0}
        for vote_value, count in votes:
            vote_counts[vote_value] = count
        
        # Get total members
        total_members = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE group_id = ?",
            (group_id,),
            fetch='one'
        )[0]
        
        total_votes = vote_counts['yes'] + vote_counts['no']
        
        embed = discord.Embed(
            title="🗳️ Vote Recorded",
            description=f"**{char_name}** {action} vote: {'✅ Yes' if choice == 'yes' else '❌ No'}",
            color=0x00ff00 if choice == 'yes' else 0xff0000
        )
        
        embed.add_field(
            name="Current Results",
            value=f"✅ Yes: {vote_counts['yes']}\n❌ No: {vote_counts['no']}\n📊 Total: {total_votes}/{total_members}",
            inline=False
        )
        
        # Check if all members have voted
        if total_votes >= total_members:
            # Process vote result
            if vote_counts['yes'] > vote_counts['no']:
                embed.add_field(name="🎉 Vote Passed", value="Group will proceed with this action!", inline=False)
                await self._execute_vote_result(session_id, group_id, vote_type, vote_data_str, interaction)
            else:
                embed.add_field(name="❌ Vote Failed", value="Action was rejected by the group.", inline=False)
                
                # Notify the initiator
                initiator = self.db.execute_query(
                    '''SELECT c.user_id FROM group_votes gv
                       JOIN characters c ON gv.user_id = c.user_id
                       WHERE gv.session_id = ? ORDER BY gv.voted_at ASC LIMIT 1''',
                    (session_id,),
                    fetch='one'
                )
                
                if initiator:
                    initiator_user = self.bot.get_user(initiator[0])
                    if initiator_user:
                        try:
                            await initiator_user.send(
                                f"❌ Your {vote_type} vote in **{group_name}** failed.\n"
                                f"Consider discussing with your group members or leaving the group to continue solo."
                            )
                        except:
                            pass
            
            # Clean up vote
            self.db.execute_query("DELETE FROM group_votes WHERE session_id = ?", (session_id,))
            self.db.execute_query("DELETE FROM group_vote_sessions WHERE session_id = ?", (session_id,))
        
        await interaction.response.send_message(embed=embed)
    
    async def _execute_vote_result(self, session_id, group_id, vote_type, vote_data_str, interaction):
        """Execute the result of a successful vote"""
        vote_data = json.loads(vote_data_str)
        
        if vote_type == 'travel':
            # Initiate group travel
            await self._initiate_group_travel(group_id, vote_data['corridor_id'], vote_data, interaction)
            
        elif vote_type == 'job':
            # Handle group job acceptance
            await interaction.defer()
            
            job_id = vote_data['job_id']
            
            # Double-check job is still available
            job_available = self.db.execute_query(
                "SELECT is_taken FROM jobs WHERE job_id = ?",
                (job_id,),
                fetch='one'
            )
            
            if not job_available or job_available[0] == 1:
                embed = discord.Embed(
                    title="❌ Job No Longer Available",
                    description="This job has been taken by someone else.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Assign job to group leader (for tracking purposes)
            self.db.execute_query(
                "UPDATE jobs SET is_taken = 1, taken_by = ?, taken_at = datetime('now'), job_status = 'active' WHERE job_id = ?",
                (group_id, job_id)  # Store group_id in taken_by for group jobs
            )
            
            # Create job tracking for all members
            members = self.db.execute_query(
                "SELECT user_id, name FROM characters WHERE group_id = ?",
                (group_id,),
                fetch='all'
            )
            
            current_location = self.db.execute_query(
                "SELECT current_location FROM groups WHERE group_id = ?",
                (group_id,),
                fetch='one'
            )[0]
            
            for member_id, member_name in members:
                # Set job tracking for each member
                self.db.execute_query(
                    "INSERT OR REPLACE INTO job_tracking (job_id, user_id, start_location, required_duration) VALUES (?, ?, ?, ?)",
                    (job_id, member_id, current_location, vote_data['duration_minutes'])
                )
            
            embed = discord.Embed(
                title="✅ Group Job Accepted & Started",
                description=f"All **{len(members)}** group members have been assigned to:\n🔄 **Job is now active** - work in progress!",
                color=0x00ff00
            )
            embed.add_field(name="Job", value=vote_data['title'], inline=False)
            embed.add_field(name="Total Reward", value=f"{vote_data['reward_money']:,} credits", inline=True)
            embed.add_field(name="Per Member", value=f"{vote_data['reward_money']//len(members):,} credits", inline=True)
            embed.add_field(name="Duration", value=f"{vote_data['duration_minutes']} minutes", inline=True)
            
            await interaction.followup.send(embed=embed)

    async def _initiate_group_travel(self, group_id, corridor_id, vote_data, interaction):
        """Initiate group travel for all members"""
        from utils.channel_manager import ChannelManager
        import asyncio
        
        # Get all group members
        members = self.db.execute_query(
            "SELECT user_id, name FROM characters WHERE group_id = ?",
            (group_id,),
            fetch='all'
        )
        
        if not members:
            return
        
        # Get corridor information
        corridor_info = self.db.execute_query(
            '''SELECT c.corridor_id, c.name, c.origin_location, c.destination_location, 
                      c.travel_time, c.fuel_cost, c.danger_level,
                      ol.name as origin_name, dl.name as dest_name
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.corridor_id = ?''',
            (corridor_id,),
            fetch='one'
        )
        
        if not corridor_info:
            await interaction.followup.send("❌ Corridor information not found!", ephemeral=True)
            return
        
        corridor_id, corridor_name, origin_location, destination_location, travel_time, fuel_cost, danger_level, origin_name, dest_name = corridor_info
        
        # Check and deduct fuel for all members
        failed_members = []
        for member_id, member_name in members:
            # Check fuel
            fuel_info = self.db.execute_query(
                "SELECT s.current_fuel FROM characters c JOIN ships s ON c.ship_id = s.ship_id WHERE c.user_id = ?",
                (member_id,),
                fetch='one'
            )
            
            if not fuel_info or fuel_info[0] < fuel_cost:
                failed_members.append(member_name)
            else:
                # Deduct fuel
                self.db.execute_query(
                    "UPDATE ships SET current_fuel = current_fuel - ? WHERE owner_id = ?",
                    (fuel_cost, member_id)
                )
        
        if failed_members:
            embed = discord.Embed(
                title="❌ Group Travel Failed",
                description=f"The following members don't have enough fuel:\n{', '.join(failed_members)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create group transit channel
        channel_manager = ChannelManager(self.bot)
        member_users = [interaction.guild.get_member(member_id) for member_id, _ in members]
        member_users = [user for user in member_users if user]  # Filter out None values
        
        if not member_users:
            await interaction.followup.send("❌ Could not find group members in this server!", ephemeral=True)
            return
        
        transit_channel = await channel_manager.create_transit_channel(
            interaction.guild,
            member_users,
            corridor_name,
            dest_name
        )
        
        # Remove access from origin location for all members
        for member_id, member_name in members:
            member_user = interaction.guild.get_member(member_id)
            if member_user:
                await channel_manager.remove_user_location_access(member_user, origin_location)
                
                # Update character location to None (in transit)
                self.db.execute_query(
                    "UPDATE characters SET current_location = NULL WHERE user_id = ?",
                    (member_id,)
                )
        
        # Calculate travel time with ship efficiency (use leader's ship as base)
        leader_efficiency = self.db.execute_query(
            "SELECT s.fuel_efficiency FROM characters c JOIN ships s ON c.ship_id = s.ship_id WHERE c.user_id = ?",
            (members[0][0],),  # Use first member (leader) as base
            fetch='one'
        )
        
        ship_eff = leader_efficiency[0] if leader_efficiency else 5
        efficiency_modifier = 1.6 - (ship_eff * 0.08)
        actual_travel_time = max(int(travel_time * efficiency_modifier), 60)
        
        # Create travel sessions for all members
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(seconds=actual_travel_time)
        
        for member_id, member_name in members:
            self.db.execute_query(
                '''INSERT INTO travel_sessions 
                   (user_id, group_id, origin_location, destination_location, corridor_id, 
                    temp_channel_id, start_time, end_time, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'traveling')''',
                (member_id, group_id, origin_location, destination_location, 
                 corridor_id, transit_channel.id if transit_channel else None, 
                 start_time.isoformat(), end_time.isoformat())
            )
        
        # Send confirmation
        embed = discord.Embed(
            title="🚀 Group Travel Initiated",
            description=f"**{len(members)} members** are now traveling to **{dest_name}**",
            color=0x00ff00
        )
        
        mins, secs = divmod(actual_travel_time, 60)
        hours = mins // 60
        mins = mins % 60
        
        if hours > 0:
            time_display = f"{hours}h {mins}m {secs}s"
        else:
            time_display = f"{mins}m {secs}s"
        
        embed.add_field(name="Travel Time", value=time_display, inline=True)
        embed.add_field(name="Via", value=corridor_name, inline=True)
        embed.add_field(name="Fuel Cost", value=f"{fuel_cost} per ship", inline=True)
        
        if transit_channel:
            embed.add_field(name="Transit Channel", value=transit_channel.mention, inline=False)
        
        await interaction.followup.send(embed=embed)
        
        # Start progress tracking for the group
        if transit_channel:
            travel_cog = self.bot.get_cog('TravelCog')
            if travel_cog:
                # Pass group_id instead of a single user_id
                asyncio.create_task(travel_cog._start_travel_progress_tracking(
                    transit_channel, group_id, corridor_id, actual_travel_time, start_time, end_time, dest_name, is_group=True
                ))
        
        # Schedule completion
        asyncio.create_task(self._complete_group_travel(
            group_id, members, destination_location, dest_name, transit_channel, 
            interaction.guild, actual_travel_time
        ))

    async def _complete_group_travel(self, group_id, members, destination_location, dest_name, transit_channel, guild, travel_time):
        """Complete group travel after delay by handing off to the TravelCog arrival handler for each member."""
        await asyncio.sleep(travel_time)

        travel_cog = self.bot.get_cog('TravelCog')
        if not travel_cog:
            print("❌ CRITICAL: TravelCog not found during group travel completion.")
            if transit_channel:
                # Attempt to get channel manager for cleanup even if cog is missing
                from utils.channel_manager import ChannelManager
                channel_manager = ChannelManager(self.bot)
                await channel_manager.cleanup_transit_channel(transit_channel.id, delay_seconds=5)
            return

        try:
            arrival_statuses = []
            for member_id, member_name in members:
                # Get this member's session info to check status and get origin
                session_info = self.db.execute_query(
                    "SELECT origin_location, status FROM travel_sessions WHERE user_id=? AND group_id=? ORDER BY session_id DESC LIMIT 1",
                    (member_id, group_id), fetch='one'
                )

                # Skip if session is missing or already processed (e.g., by an event)
                if not session_info or session_info[1] != 'traveling':
                    continue

                origin_location_id, _ = session_info

                # Mark as 'arrived' to signal the arrival handler this session is ready for processing
                self.db.execute_query(
                    "UPDATE travel_sessions SET status='arrived' WHERE user_id=? AND group_id=? AND status='traveling'",
                    (member_id, group_id)
                )

                # Use the robust arrival handler from TravelCog for each member
                await travel_cog._handle_arrival_access(member_id, destination_location, origin_location_id, guild, transit_channel)

                # Check the final outcome for the summary message
                final_loc_id = self.db.execute_query("SELECT current_location FROM characters WHERE user_id = ?", (member_id,), fetch='one')[0]
                if final_loc_id == destination_location:
                    arrival_statuses.append(f"✅ **{member_name}** has arrived at {dest_name}.")
                else:
                    # This case handles retreats or diversions
                    final_loc_name = "an unknown location"
                    if final_loc_id:
                         final_loc_name_res = self.db.execute_query("SELECT name FROM locations WHERE location_id = ?", (final_loc_id,), fetch='one')
                         if final_loc_name_res:
                            final_loc_name = f"**{final_loc_name_res[0]}**"

                    arrival_statuses.append(f"❌ **{member_name}** was diverted and ended up at {final_loc_name}.")

            # Update group's location in DB if anyone made it
            if any("✅" in s for s in arrival_statuses):
                self.db.execute_query("UPDATE groups SET current_location=? WHERE group_id=?", (destination_location, group_id))

            # Post a final summary in the transit channel
            if transit_channel and arrival_statuses:
                summary_embed = discord.Embed(title="Group Arrival Complete", description=f"The group's journey to **{dest_name}** has concluded.", color=0x00ff00)
                summary_embed.add_field(name="Arrival Log", value="\n".join(arrival_statuses), inline=False)
                await transit_channel.send(embed=summary_embed)

        except Exception as e:
            print(f"❌ Error during group travel completion for group {group_id}: {e}")
        finally:
            # The manager of the travel session is responsible for the final cleanup
            if transit_channel:
                await travel_cog.channel_mgr.cleanup_transit_channel(transit_channel.id, delay_seconds=45)
              
    async def _process_vote_timeout(self, session_id: int, timeout_seconds: int):
        """Process vote timeout after specified duration"""
        await asyncio.sleep(timeout_seconds)
        
        current_timestamp = int(datetime.now().timestamp())

        vote_exists = self.db.execute_query(
            "SELECT group_id FROM group_vote_sessions WHERE session_id = ? AND expires_at > ?",
            (session_id, current_timestamp),
            fetch='one'
        )
        if vote_exists:
            # Vote timed out - clean up
            self.db.execute_query("DELETE FROM group_votes WHERE session_id = ?", (session_id,))
            self.db.execute_query("DELETE FROM group_vote_sessions WHERE session_id = ?", (session_id,))
            
            # Optionally notify in channel about timeout
            channel_id = self.db.execute_query(
                "SELECT channel_id FROM group_vote_sessions WHERE session_id = ?",
                (session_id,),
                fetch='one'
            )
            
            if channel_id and channel_id[0]:
                channel = self.bot.get_channel(channel_id[0])
                if channel:
                    embed = discord.Embed(
                        title="⏰ Vote Timed Out",
                        description="The group vote has expired without reaching a decision.",
                        color=0xff9900
                    )
                    await channel.send(embed=embed)

    # Create a job vote session (called by EconomyCog)
    async def create_job_vote_session(self, group_id, job_data, channel_id):
        """Create a job vote session (called by EconomyCog)"""
        # Check for existing active vote
        current_timestamp = int(datetime.now().timestamp())
        existing_vote = self.db.execute_query(
            "SELECT session_id FROM group_vote_sessions WHERE group_id = ? AND expires_at > ?",
            (group_id, current_timestamp),
            fetch='one'
        )
        
        if existing_vote:
            return None  # Vote already active
        
        # Create vote session
        expire_timestamp = datetime.now() + timedelta(minutes=10)
        self.db.execute_query(
            "INSERT INTO group_vote_sessions (group_id, vote_type, vote_data, channel_id, expires_at) VALUES (?, ?, ?, ?, ?)",
            (group_id, 'job', json.dumps(job_data), channel_id, expire_timestamp)
        )
        
        session_id = self.db.execute_query(
            "SELECT session_id FROM group_vote_sessions WHERE group_id = ? ORDER BY session_id DESC LIMIT 1",
            (group_id,),
            fetch='one'
        )[0]
        
        # Schedule cleanup
        asyncio.create_task(self._process_vote_timeout(session_id, 600))
        
        return session_id

async def setup(bot):
    await bot.add_cog(GroupsCog(bot))