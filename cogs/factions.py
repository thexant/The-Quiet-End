import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from typing import Optional

class PayoutConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, faction_id: int, amount_per_member: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.faction_id = faction_id
        self.amount_per_member = amount_per_member
    
    @discord.ui.button(label="Distribute Funds", style=discord.ButtonStyle.success, emoji="💸")
    async def confirm_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        
        # Get all members
        members = self.bot.db.execute_query(
            "SELECT user_id FROM faction_members WHERE faction_id = ?",
            (self.faction_id,),
            fetch='all'
        )
        
        # Create payouts for each member
        for (member_id,) in members:
            self.bot.db.execute_query(
                "INSERT INTO faction_payouts (faction_id, user_id, amount) VALUES (?, ?, ?)",
                (self.faction_id, member_id, self.amount_per_member)
            )
        
        # Clear faction bank
        total_payout = self.amount_per_member * len(members)
        self.bot.db.execute_query(
            "UPDATE factions SET bank_balance = bank_balance - ? WHERE faction_id = ?",
            (total_payout, self.faction_id)
        )
        
        embed = discord.Embed(
            title="💸 Payout Complete!",
            description=f"Distributed {self.amount_per_member:,} credits to each of {len(members)} members",
            color=0x00ff00
        )
        embed.add_field(name="Total Distributed", value=f"{total_payout:,} credits", inline=True)
        embed.set_footer(text="Members will receive their payout when they next log in")
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        
        await interaction.response.edit_message(content="Payout cancelled.", embed=None, view=None)
        self.stop()



class FactionCreateModal(discord.ui.Modal, title="Create New Faction"):
    faction_name = discord.ui.TextInput(
        label="Faction Name",
        placeholder="Enter faction name (3-32 characters)",
        min_length=3,
        max_length=32,
        required=True
    )
    
    faction_emoji = discord.ui.TextInput(
        label="Faction Emoji", 
        placeholder="Enter :emoji_name: or paste an emoji",
        min_length=1,
        max_length=100,  # Increased to handle custom emoji format
        required=True
    )
    
    faction_description = discord.ui.TextInput(
        label="Faction Description",
        placeholder="Describe your faction's goals and values",
        min_length=10,
        max_length=500,
        required=True,
        style=discord.TextStyle.paragraph
    )
    
    is_public = discord.ui.TextInput(
        label="Public Faction? (yes/no)",
        placeholder="Type 'yes' for public, 'no' for invite-only",
        min_length=2,
        max_length=3,
        required=True
    )
    
    def __init__(self, cog, user_id: int):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has enough credits
        user_money = self.cog.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if not user_money or user_money[0] < 2500:
            return await interaction.followup.send(
                f"Creating a faction costs 2,500 credits! You only have {user_money[0] if user_money else 0:,} credits.",
                ephemeral=True
            )
        
        # Just store whatever emoji they enter - Discord will handle it
        emoji = self.faction_emoji.value.strip()
        
        # Check if name is unique
        existing = self.cog.db.execute_query(
            "SELECT faction_id FROM factions WHERE name = ?",
            (self.faction_name.value,),
            fetch='one'
        )
        
        if existing:
            return await interaction.followup.send("A faction with that name already exists!", ephemeral=True)
        
        # Parse public setting
        is_public = 1 if self.is_public.value.lower() == 'yes' else 0
        
        # Create faction with initial bank balance of 2500
        self.cog.db.execute_query(
            '''INSERT INTO factions (name, emoji, description, leader_id, is_public, bank_balance) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (self.faction_name.value, emoji, self.faction_description.value, self.user_id, is_public, 2500)
        )
        
        # Deduct credits from player
        self.cog.db.execute_query(
            "UPDATE characters SET money = money - 2500 WHERE user_id = ?",
            (self.user_id,)
        )
        
        faction_id = self.cog.db.execute_query(
            "SELECT faction_id FROM factions WHERE leader_id = ? ORDER BY created_at DESC LIMIT 1",
            (self.user_id,),
            fetch='one'
        )[0]
        
        # Add leader as member
        self.cog.db.execute_query(
            "INSERT INTO faction_members (faction_id, user_id) VALUES (?, ?)",
            (faction_id, self.user_id)
        )
        
        embed = discord.Embed(
            title=f"{emoji} Faction Created!",
            description=f"**{self.faction_name.value}** has been established!",
            color=0x00ff00
        )
        embed.add_field(name="Description", value=self.faction_description.value, inline=False)
        embed.add_field(name="Type", value="Public" if is_public else "Invite-Only", inline=True)
        embed.add_field(name="Leader", value=interaction.user.mention, inline=True)
        embed.add_field(name="Bank Balance", value="2,500 credits", inline=True)
        embed.add_field(name="Creation Cost", value="2,500 credits (added to faction bank)", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class FactionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    faction_group = app_commands.Group(name="faction", description="Faction management commands")
    
    @faction_group.command(name="create", description="Create a new faction")
    async def faction_create(self, interaction: discord.Interaction):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            return await interaction.response.send_message("You need a character first!", ephemeral=True)
        
        # Check if already in a faction
        existing_faction = self.db.execute_query(
            "SELECT f.name FROM faction_members fm JOIN factions f ON fm.faction_id = f.faction_id WHERE fm.user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if existing_faction:
            return await interaction.response.send_message(f"You're already in the faction **{existing_faction[0]}**!", ephemeral=True)
        
        modal = FactionCreateModal(self, interaction.user.id)
        await interaction.response.send_modal(modal)
    
    @faction_group.command(name="info", description="View faction information")
    async def faction_info(self, interaction: discord.Interaction):
        # Get user's faction
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.emoji, f.description, f.leader_id, f.is_public, 
                      f.bank_balance, c.name as leader_name
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               LEFT JOIN characters c ON f.leader_id = c.user_id
               WHERE fm.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not faction_data:
            return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
        
        faction_id, name, emoji, description, leader_id, is_public, bank_balance, leader_name = faction_data
        
        # Get member count
        member_count = self.db.execute_query(
            "SELECT COUNT(*) FROM faction_members WHERE faction_id = ?",
            (faction_id,),
            fetch='one'
        )[0]
        
        # Get owned locations
        locations = self.db.execute_query(
            '''SELECT l.name, l.location_type FROM locations l
               JOIN location_ownership lo ON l.location_id = lo.location_id
               WHERE lo.faction_id = ?''',
            (faction_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"{emoji} {name}",
            description=description,
            color=0x00ff00 if leader_id == interaction.user.id else 0x4169E1
        )
        
        embed.add_field(name="Leader", value=leader_name or "Unknown", inline=True)
        embed.add_field(name="Type", value="Public" if is_public else "Invite-Only", inline=True)
        embed.add_field(name="Members", value=str(member_count), inline=True)
        embed.add_field(name="Bank Balance", value=f"{bank_balance:,} credits", inline=True)
        
        if locations:
            location_list = "\n".join([f"• {loc[0]} ({loc[1].replace('_', ' ').title()})" for loc in locations[:10]])
            if len(locations) > 10:
                location_list += f"\n...and {len(locations) - 10} more"
            embed.add_field(name="Owned Locations", value=location_list, inline=False)
        
        if leader_id == interaction.user.id:
            embed.set_footer(text="You are the faction leader!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @faction_group.command(name="invite", description="Invite a player to your faction")
    @app_commands.describe(member="The player to invite")
    async def faction_invite(self, interaction: discord.Interaction, member: discord.Member):
        # Check if user is faction leader
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.emoji, f.is_public
               FROM factions f
               WHERE f.leader_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not faction_data:
            return await interaction.response.send_message("Only faction leaders can invite members!", ephemeral=True)
        
        faction_id, faction_name, emoji, is_public = faction_data
        
        # Check if target has a character
        target_char = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (member.id,),
            fetch='one'
        )
        
        if not target_char:
            return await interaction.response.send_message("That player doesn't have a character!", ephemeral=True)
        
        # Check if in same location
        user_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if target_char[0] != user_location:
            return await interaction.response.send_message("You must be in the same location to invite someone!", ephemeral=True)
        
        # Check if already in a faction
        existing_faction = self.db.execute_query(
            "SELECT faction_id FROM faction_members WHERE user_id = ?",
            (member.id,),
            fetch='one'
        )
        
        if existing_faction:
            return await interaction.response.send_message("That player is already in a faction!", ephemeral=True)
        
        # Check for existing invite
        existing_invite = self.db.execute_query(
            "SELECT invite_id FROM faction_invites WHERE faction_id = ? AND invitee_id = ? AND expires_at > datetime('now')",
            (faction_id, member.id),
            fetch='one'
        )
        
        if existing_invite:
            return await interaction.response.send_message("You already have a pending invite to this player!", ephemeral=True)
        
        # Create invite
        expires_at = datetime.utcnow() + timedelta(hours=24)
        self.db.execute_query(
            '''INSERT INTO faction_invites (faction_id, inviter_id, invitee_id, expires_at)
               VALUES (?, ?, ?, ?)''',
            (faction_id, interaction.user.id, member.id, expires_at)
        )
        
        # Send notification to invitee
        embed = discord.Embed(
            title=f"{emoji} Faction Invitation",
            description=f"You've been invited to join **{faction_name}**!",
            color=0x00ff00
        )
        embed.add_field(name="Invited by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Type", value="Public" if is_public else "Invite-Only", inline=True)
        embed.add_field(name="Expires", value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
        embed.set_footer(text="Use /faction join to accept this invitation")
        
        try:
            await member.send(embed=embed)
        except:
            pass  # DMs might be disabled
        
        await interaction.response.send_message(f"Invitation sent to {member.mention}!", ephemeral=True)
    
    @faction_group.command(name="join", description="Join a faction you've been invited to")
    async def faction_join(self, interaction: discord.Interaction):
        # Get all pending invites
        invites = self.db.execute_query(
            '''SELECT fi.faction_id, f.name, f.emoji, c.name as inviter_name
               FROM faction_invites fi
               JOIN factions f ON fi.faction_id = f.faction_id
               LEFT JOIN characters c ON fi.inviter_id = c.user_id
               WHERE fi.invitee_id = ? AND fi.expires_at > datetime('now')''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not invites:
            # Check for public factions in same location
            user_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not user_location:
                return await interaction.response.send_message("No pending invitations!", ephemeral=True)
            
            public_factions = self.db.execute_query(
                '''SELECT DISTINCT f.faction_id, f.name, f.emoji
                   FROM factions f
                   JOIN faction_members fm ON f.faction_id = fm.faction_id
                   JOIN characters c ON fm.user_id = c.user_id
                   WHERE f.is_public = 1 AND c.current_location = ?''',
                (user_location[0],),
                fetch='all'
            )
            
            if not public_factions:
                return await interaction.response.send_message("No factions available to join!", ephemeral=True)
            
            # Show public faction selection
            view = PublicFactionSelectView(self, interaction.user.id, public_factions)
            embed = discord.Embed(
                title="Public Factions Available",
                description="Select a public faction to join:",
                color=0x4169E1
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        if len(invites) == 1:
            # Auto-accept single invite
            faction_id = invites[0][0]
            await self._join_faction(interaction, faction_id)
        else:
            # Show selection menu
            view = FactionInviteSelectView(self, interaction.user.id, invites)
            embed = discord.Embed(
                title="Pending Faction Invitations",
                description="Select which faction to join:",
                color=0x4169E1
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _join_faction(self, interaction: discord.Interaction, faction_id: int):
        # Add to faction
        self.db.execute_query(
            "INSERT INTO faction_members (faction_id, user_id) VALUES (?, ?)",
            (faction_id, interaction.user.id)
        )
        
        # Remove all invites for this user
        self.db.execute_query(
            "DELETE FROM faction_invites WHERE invitee_id = ?",
            (interaction.user.id,)
        )
        
        # Get faction info
        faction_info = self.db.execute_query(
            "SELECT name, emoji FROM factions WHERE faction_id = ?",
            (faction_id,),
            fetch='one'
        )
        
        embed = discord.Embed(
            title=f"{faction_info[1]} Welcome to {faction_info[0]}!",
            description="You've successfully joined the faction!",
            color=0x00ff00
        )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @faction_group.command(name="leave", description="Leave your current faction")
    async def faction_leave(self, interaction: discord.Interaction):
        # Get faction info
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.leader_id
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               WHERE fm.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not faction_data:
            return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
        
        faction_id, faction_name, leader_id = faction_data
        
        if leader_id == interaction.user.id:
            # Check if there are other members
            member_count = self.db.execute_query(
                "SELECT COUNT(*) FROM faction_members WHERE faction_id = ?",
                (faction_id,),
                fetch='one'
            )[0]
            
            if member_count > 1:
                return await interaction.response.send_message(
                    "You can't leave as the faction leader! Transfer leadership first with `/faction transfer_leadership`.",
                    ephemeral=True
                )
        
        # Remove from faction
        self.db.execute_query(
            "DELETE FROM faction_members WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        await interaction.response.send_message(f"You've left **{faction_name}**.", ephemeral=True)
        
        # If last member, dissolve faction
        remaining = self.db.execute_query(
            "SELECT COUNT(*) FROM faction_members WHERE faction_id = ?",
            (faction_id,),
            fetch='one'
        )[0]
        
        if remaining == 0:
            await self._dissolve_faction(faction_id)
    
    @faction_group.command(name="donate", description="Donate credits to your faction bank")
    @app_commands.describe(amount="Amount to donate")
    async def faction_donate(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Amount must be positive!", ephemeral=True)
        
        # Get user's money and faction
        user_data = self.db.execute_query(
            '''SELECT c.money, fm.faction_id, f.name, f.emoji
               FROM characters c
               JOIN faction_members fm ON c.user_id = fm.user_id
               JOIN factions f ON fm.faction_id = f.faction_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not user_data:
            return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
        
        money, faction_id, faction_name, emoji = user_data
        
        if money < amount:
            return await interaction.response.send_message(f"Insufficient funds! You have {money:,} credits.", ephemeral=True)
        
        # Transfer money
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (amount, interaction.user.id)
        )
        
        self.db.execute_query(
            "UPDATE factions SET bank_balance = bank_balance + ? WHERE faction_id = ?",
            (amount, faction_id)
        )
        
        # Get new balance
        new_balance = self.db.execute_query(
            "SELECT bank_balance FROM factions WHERE faction_id = ?",
            (faction_id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title=f"{emoji} Donation Successful",
            description=f"You donated **{amount:,} credits** to {faction_name}",
            color=0x00ff00
        )
        embed.add_field(name="New Bank Balance", value=f"{new_balance:,} credits", inline=True)
        embed.add_field(name="Your Balance", value=f"{money - amount:,} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @faction_group.command(name="payout", description="Distribute faction bank funds equally to all members")
    async def faction_payout(self, interaction: discord.Interaction):
        # Check if user is faction leader
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.emoji, f.bank_balance
               FROM factions f
               WHERE f.leader_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not faction_data:
            return await interaction.response.send_message("Only faction leaders can initiate payouts!", ephemeral=True)
        
        faction_id, faction_name, emoji, bank_balance = faction_data
        
        if bank_balance <= 0:
            return await interaction.response.send_message("No funds in faction bank to distribute!", ephemeral=True)
        
        # Get member count
        member_count = self.db.execute_query(
            "SELECT COUNT(*) FROM faction_members WHERE faction_id = ?",
            (faction_id,),
            fetch='one'
        )[0]
        
        if member_count == 0:
            return await interaction.response.send_message("No members to pay out to!", ephemeral=True)
        
        payout_per_member = bank_balance // member_count
        if payout_per_member == 0:
            return await interaction.response.send_message("Not enough funds to distribute (less than 1 credit per member)!", ephemeral=True)
        
        # Show confirmation
        embed = discord.Embed(
            title=f"{emoji} Faction Payout",
            description=f"Distribute faction bank funds to all members?",
            color=0x00ff00
        )
        embed.add_field(name="Total Funds", value=f"{bank_balance:,} credits", inline=True)
        embed.add_field(name="Members", value=str(member_count), inline=True)
        embed.add_field(name="Per Member", value=f"{payout_per_member:,} credits", inline=True)
        
        view = PayoutConfirmView(self.bot, interaction.user.id, faction_id, payout_per_member)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @faction_group.command(name="members", description="View faction members")
    async def faction_members(self, interaction: discord.Interaction):
        # Get user's faction
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.emoji, f.leader_id
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               WHERE fm.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not faction_data:
            return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
        
        faction_id, faction_name, emoji, leader_id = faction_data
        
        # Get all members
        members = self.db.execute_query(
            '''SELECT c.user_id, c.name, c.level, c.current_location, l.name as location_name
               FROM faction_members fm
               JOIN characters c ON fm.user_id = c.user_id
               LEFT JOIN locations l ON c.current_location = l.location_id
               WHERE fm.faction_id = ?
               ORDER BY c.level DESC''',
            (faction_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"{emoji} {faction_name} Members",
            description=f"Total Members: {len(members)}",
            color=0x4169E1
        )
        
        member_list = []
        for user_id, name, level, current_location, location_name in members[:25]:  # Discord field limit
            leader_mark = "👑 " if user_id == leader_id else ""
            member_list.append(f"{leader_mark}**{name}** (Lvl {level}) - {location_name or 'Unknown'}")
        
        if member_list:
            embed.add_field(name="Members", value="\n".join(member_list), inline=False)
        
        if len(members) > 25:
            embed.set_footer(text=f"...and {len(members) - 25} more members")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _dissolve_faction(self, faction_id: int):
        """Dissolve a faction and make its locations neutral"""
        # Make all faction locations neutral
        self.db.execute_query(
            "UPDATE location_ownership SET faction_id = NULL, owner_id = NULL WHERE faction_id = ?",
            (faction_id,)
        )
        
        # Delete faction data
        self.db.execute_query("DELETE FROM faction_invites WHERE faction_id = ?", (faction_id,))
        self.db.execute_query("DELETE FROM faction_sales_tax WHERE faction_id = ?", (faction_id,))
        self.db.execute_query("DELETE FROM faction_payouts WHERE faction_id = ?", (faction_id,))
        self.db.execute_query("DELETE FROM factions WHERE faction_id = ?", (faction_id,))
    
    async def check_faction_dissolution(self):
        """Check if any factions have all members dead and dissolve them"""
        # Get factions with all members dead
        dead_factions = self.db.execute_query(
            '''SELECT DISTINCT f.faction_id, f.name
               FROM factions f
               WHERE NOT EXISTS (
                   SELECT 1 FROM faction_members fm
                   JOIN characters c ON fm.user_id = c.user_id
                   WHERE fm.faction_id = f.faction_id AND c.is_alive = 1
               )''',
            fetch='all'
        )
        
        for faction_id, faction_name in dead_factions:
            await self._dissolve_faction(faction_id)
            print(f"Dissolved faction {faction_name} - all members dead")

class PublicFactionSelectView(discord.ui.View):
    def __init__(self, cog, user_id: int, factions: list):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        
        # Create select menu
        options = []
        for faction_id, name, emoji in factions[:25]:  # Discord limit
            options.append(discord.SelectOption(label=name, value=str(faction_id), emoji=emoji))
        
        self.select = discord.ui.Select(placeholder="Choose a faction...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        
        faction_id = int(self.select.values[0])
        await self.cog._join_faction(interaction, faction_id)
        self.stop()

class FactionInviteSelectView(discord.ui.View):
    def __init__(self, cog, user_id: int, invites: list):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        
        # Create select menu
        options = []
        for faction_id, name, emoji, inviter_name in invites[:25]:
            options.append(discord.SelectOption(
                label=name, 
                value=str(faction_id), 
                emoji=emoji,
                description=f"Invited by {inviter_name or 'Unknown'}"
            ))
        
        self.select = discord.ui.Select(placeholder="Choose a faction...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        
        faction_id = int(self.select.values[0])
        await self.cog._join_faction(interaction, faction_id)
        self.stop()

async def setup(bot):
    await bot.add_cog(FactionsCog(bot))