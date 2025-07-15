# cogs/homes.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict
import math
import asyncio
from datetime import datetime

# Note: Import the home activities after creating the util file
try:
    from utils.home_activities import HomeActivityManager, HomeActivityView
except ImportError:
    print("Warning: home_activities.py not found in utils folder")
    HomeActivityManager = None
    HomeActivityView = None

class HomeBuyView(discord.ui.View):
    """View for home purchase confirmation"""
    
    def __init__(self, homes: List[Dict], buyer_id: int, bot):
        super().__init__(timeout=60)
        self.homes = homes
        self.buyer_id = buyer_id
        self.bot = bot
        self.db = bot.db
        
        # Create select menu
        options = []
        for home in homes[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=home['home_name'],
                value=str(home['home_id']),
                description=f"{home['price']:,} credits",
                emoji="🏠"
            ))
        
        self.select = discord.ui.Select(
            placeholder="Select a home to purchase",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("This isn't your purchase menu!", ephemeral=True)
            return
        
        home_id = int(self.select.values[0])
        home = next((h for h in self.homes if h['home_id'] == home_id), None)
        
        if not home:
            await interaction.response.send_message("Home not found!", ephemeral=True)
            return
        
        # Show confirmation
        embed = discord.Embed(
            title="🏠 Confirm Home Purchase",
            description=f"**{home['home_name']}**\n{home['interior_description']}",
            color=0x2F4F4F
        )
        embed.add_field(name="Price", value=f"{home['price']:,} credits", inline=True)
        embed.add_field(name="Location", value=home['location_name'], inline=True)
        
        confirm_view = ConfirmPurchaseView(home, self.buyer_id, self.bot)
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class ConfirmPurchaseView(discord.ui.View):
    """Confirmation view for home purchase"""
    
    def __init__(self, home: Dict, buyer_id: int, bot):
        super().__init__(timeout=30)
        self.home = home
        self.buyer_id = buyer_id
        self.bot = bot
        self.db = bot.db
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("This isn't your purchase!", ephemeral=True)
            return
        
        # Check money again
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.buyer_id,),
            fetch='one'
        )[0]
        
        if money < self.home['price']:
            await interaction.response.edit_message(
                content="Insufficient funds!",
                embed=None,
                view=None
            )
            return
        
        # Process purchase
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.home['price'], self.buyer_id)
        )
        
        self.db.execute_query(
            '''UPDATE location_homes 
               SET owner_id = ?, purchase_date = CURRENT_TIMESTAMP, is_available = 0
               WHERE home_id = ?''',
            (self.buyer_id, self.home['home_id'])
        )
        
        embed = discord.Embed(
            title="🏠 Home Purchased!",
            description=f"You are now the owner of **{self.home['home_name']}**!",
            color=0x00ff00
        )
        embed.add_field(
            name="Next Steps",
            value="• Use `/home interior enter` to enter your home\n• Use `/homes view` to see all your properties",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("This isn't your purchase!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Purchase cancelled.",
            embed=None,
            view=None
        )


class HomeWarpView(discord.ui.View):
    """View for warping to owned homes"""
    
    def __init__(self, homes: List[Dict], user_id: int, current_location: int, bot):
        super().__init__(timeout=60)
        self.homes = homes
        self.user_id = user_id
        self.current_location = current_location
        self.bot = bot
        self.db = bot.db
        
        # Create select menu
        options = []
        for home in homes[:25]:
            # Calculate distance-based fee
            distance = self._calculate_distance(current_location, home['location_id'])
            fee = min(100, int(distance * 5))
            
            options.append(discord.SelectOption(
                label=home['home_name'],
                value=f"{home['home_id']}|{fee}",
                description=f"{home['location_name']} - {fee} credits",
                emoji="🏠"
            ))
        
        self.select = discord.ui.Select(
            placeholder="Select a home to warp to",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    def _calculate_distance(self, loc1: int, loc2: int) -> int:
        """Simple distance calculation based on location IDs"""
        return abs(loc1 - loc2)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your warp menu!", ephemeral=True)
            return
        
        home_id, fee = self.select.values[0].split('|')
        home_id = int(home_id)
        fee = int(fee)
        
        # Check money
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )[0]
        
        if money < fee:
            await interaction.response.edit_message(
                content=f"Insufficient funds! You need {fee} credits for transit.",
                view=None
            )
            return
        
        # Process warp
        home = next((h for h in self.homes if h['home_id'] == home_id), None)
        
        # Deduct fee
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (fee, self.user_id)
        )
        
        # Update location
        self.db.execute_query(
            "UPDATE characters SET current_location = ?, location_status = 'docked' WHERE user_id = ?",
            (home['location_id'], self.user_id)
        )
        
        # Handle channel access
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Remove from current location
        if self.current_location:
            await channel_manager.remove_user_location_access(interaction.user, self.current_location)
        
        # Give access to home location
        await channel_manager.give_user_location_access(interaction.user, home['location_id'])
        
        # Auto-enter home
        await interaction.response.defer()
        
        # Create home interior thread
        location_channel = interaction.guild.get_channel(
            self.db.execute_query(
                "SELECT channel_id FROM locations WHERE location_id = ?",
                (home['location_id'],),
                fetch='one'
            )[0]
        )
        
        if location_channel:
            # Get home interior creation from the cog
            cog = self.bot.get_cog('HomesCog')
            if cog:
                thread = await cog._get_or_create_home_interior(
                    interaction.guild,
                    location_channel,
                    home_id,
                    home['home_name'],
                    self.db.execute_query(
                        "SELECT interior_description FROM location_homes WHERE home_id = ?",
                        (home_id,),
                        fetch='one'
                    )[0],
                    interaction.user
                )
            
            embed = discord.Embed(
                title="🏠 Warped Home!",
                description=f"You've been transported to **{home['home_name']}** in {home['location_name']}.",
                color=0x00ff00
            )
            embed.add_field(
                name="Transit Fee",
                value=f"{fee} credits",
                inline=True
            )
            
            if thread:
                embed.add_field(
                    name="Home Interior",
                    value=f"You've entered your home at {thread.mention}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)


class HomeSellView(discord.ui.View):
    """View for confirming direct home sale"""
    
    def __init__(self, seller_id: int, buyer: discord.Member, home: Dict, price: int, bot):
        super().__init__(timeout=300)  # 5 minutes
        self.seller_id = seller_id
        self.buyer = buyer
        self.home = home
        self.price = price
        self.bot = bot
        self.db = bot.db
        self.responded = False
    
    @discord.ui.button(label="Accept Purchase", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer.id:
            await interaction.response.send_message("This offer isn't for you!", ephemeral=True)
            return
        
        if self.responded:
            await interaction.response.send_message("This offer has already been responded to!", ephemeral=True)
            return
        
        # Check buyer's money
        buyer_money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.buyer.id,),
            fetch='one'
        )[0]
        
        if buyer_money < self.price:
            await interaction.response.edit_message(
                content="Purchase failed - insufficient funds!",
                view=None
            )
            self.responded = True
            return
        
        # Check buyer's home limit
        owned_homes = self.db.execute_query(
            "SELECT COUNT(*) FROM location_homes WHERE owner_id = ?",
            (self.buyer.id,),
            fetch='one'
        )[0]
        
        if owned_homes >= 5:
            await interaction.response.edit_message(
                content="Purchase failed - you already own 5 homes (maximum)!",
                view=None
            )
            self.responded = True
            return
        
        # Process transaction
        # Transfer money
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.price, self.buyer.id)
        )
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (self.price, self.seller_id)
        )
        
        # Transfer ownership
        self.db.execute_query(
            '''UPDATE location_homes 
               SET owner_id = ?, purchase_date = CURRENT_TIMESTAMP
               WHERE home_id = ?''',
            (self.buyer.id, self.home['home_id'])
        )
        
        # Remove from market if listed
        self.db.execute_query(
            "UPDATE home_market_listings SET is_active = 0 WHERE home_id = ?",
            (self.home['home_id'],)
        )
        
        self.responded = True
        
        embed = discord.Embed(
            title="🏠 Home Purchased!",
            description=f"You've successfully purchased **{self.home['home_name']}** for {self.price:,} credits!",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Notify seller
        try:
            seller = interaction.guild.get_member(self.seller_id)
            if seller:
                await seller.send(
                    f"Your home **{self.home['home_name']}** has been sold to {self.buyer.display_name} for {self.price:,} credits!"
                )
        except:
            pass
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer.id:
            await interaction.response.send_message("This offer isn't for you!", ephemeral=True)
            return
        
        if self.responded:
            await interaction.response.send_message("This offer has already been responded to!", ephemeral=True)
            return
        
        self.responded = True
        await interaction.response.edit_message(
            content="Purchase offer declined.",
            view=None
        )
        
        # Notify seller
        try:
            seller = interaction.guild.get_member(self.seller_id)
            if seller:
                await seller.send(
                    f"{self.buyer.display_name} has declined your offer to sell **{self.home['home_name']}**."
                )
        except:
            pass


class HomesCog(commands.Cog):
    """Home ownership and management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    home_group = app_commands.Group(name="home", description="Home management commands")
    homes_group = app_commands.Group(name="homes", description="View homes information")
    
    @home_group.command(name="buy", description="Browse and purchase available homes at your location")
    async def buy_home(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get character info
        char_info = self.db.execute_query(
            '''SELECT c.current_location, c.money, c.name, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("You need a character to buy a home!", ephemeral=True)
            return
        
        location_id, money, char_name, location_name = char_info
        
        # Check home ownership limit
        owned_homes = self.db.execute_query(
            "SELECT COUNT(*) FROM location_homes WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if owned_homes >= 5:
            await interaction.followup.send("You already own 5 homes (maximum limit)!", ephemeral=True)
            return
        
        # Get available homes at location
        homes = self.db.execute_query(
            '''SELECT home_id, home_type, home_name, price, interior_description
               FROM location_homes
               WHERE location_id = ? AND is_available = 1
               ORDER BY price ASC''',
            (location_id,),
            fetch='all'
        )
        
        if not homes:
            await interaction.followup.send(f"No homes are available for purchase at {location_name}.", ephemeral=True)
            return
        
        # Convert to dict format
        homes_data = []
        for home in homes:
            homes_data.append({
                'home_id': home[0],
                'home_type': home[1],
                'home_name': home[2],
                'price': home[3],
                'interior_description': home[4],
                'location_name': location_name
            })
        
        embed = discord.Embed(
            title=f"🏠 Available Homes in {location_name}",
            description=f"You have {money:,} credits\nSelect a home to view details and purchase:",
            color=0x2F4F4F
        )
        
        view = HomeBuyView(homes_data, interaction.user.id, self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @homes_group.command(name="view", description="View your owned homes or another player's homes")
    @app_commands.describe(player="The player whose homes to view (leave empty for your own)")
    async def view_homes(self, interaction: discord.Interaction, player: Optional[discord.Member] = None):
        target_user = player or interaction.user
        
        # Get homes
        homes = self.db.execute_query(
            '''SELECT h.home_id, h.home_name, h.home_type, l.name as location_name,
                      h.price, h.purchase_date, h.value_modifier
               FROM location_homes h
               JOIN locations l ON h.location_id = l.location_id
               WHERE h.owner_id = ?
               ORDER BY h.purchase_date DESC''',
            (target_user.id,),
            fetch='all'
        )
        
        if not homes:
            if target_user == interaction.user:
                await interaction.response.send_message("You don't own any homes.", ephemeral=True)
            else:
                await interaction.response.send_message(f"{target_user.display_name} doesn't own any homes.", ephemeral=True)
            return
        
        # Get character name
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (target_user.id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title=f"🏠 {char_name}'s Properties",
            description=f"Total Properties: {len(homes)}/5",
            color=0x2F4F4F
        )
        
        total_value = 0
        for home in homes:
            home_id, name, home_type, location, price, purchase_date, value_mod = home
            current_value = int(price * value_mod)
            total_value += current_value
            
            # Check if on market
            on_market = self.db.execute_query(
                "SELECT asking_price FROM home_market_listings WHERE home_id = ? AND is_active = 1",
                (home_id,),
                fetch='one'
            )
            
            market_status = f" 🏷️ Listed for {on_market[0]:,}" if on_market else ""
            
            embed.add_field(
                name=f"{name}",
                value=f"📍 {location}\n💰 Value: {current_value:,} credits{market_status}",
                inline=True
            )
        
        embed.add_field(
            name="📊 Total Portfolio Value",
            value=f"{total_value:,} credits",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Create interior subgroup
    interior_group = app_commands.Group(name="interior", description="Manage home interior access", parent=home_group)
    
    @interior_group.command(name="enter", description="Enter your home at this location")
    async def enter_home(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if already in a home
        current_home = self.db.execute_query(
            "SELECT current_home_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if current_home and current_home[0]:
            await interaction.followup.send("You are already inside a home! Use `/home interior leave` first.", ephemeral=True)
            return
        
        # Get character location
        char_info = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or char_info[1] != 'docked':
            await interaction.followup.send("You must be docked at a location to enter your home!", ephemeral=True)
            return
        
        location_id = char_info[0]
        
        # Get owned home at this location
        home = self.db.execute_query(
            '''SELECT home_id, home_name, interior_description
               FROM location_homes
               WHERE owner_id = ? AND location_id = ?''',
            (interaction.user.id, location_id),
            fetch='one'
        )
        
        if not home:
            await interaction.followup.send("You don't own a home at this location!", ephemeral=True)
            return
        
        home_id, home_name, interior_desc = home
        
        # Get or create home channel
        home_channel_info = self.db.execute_query(
            "SELECT channel_id FROM home_interiors WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )
        
        channel_id = home_channel_info[0] if home_channel_info else None
        home_info = (home_id, home_name, location_id, interior_desc, channel_id)
        
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        home_channel = await channel_manager.get_or_create_home_channel(
            interaction.guild,
            home_info,
            interaction.user
        )
        
        if home_channel:
            # Update character to be inside home
            self.db.execute_query(
                "UPDATE characters SET current_home_id = ? WHERE user_id = ?",
                (home_id, interaction.user.id)
            )
            
            # Remove from location channel
            await channel_manager.remove_user_location_access(interaction.user, location_id)
            
            await interaction.followup.send(
                f"You've entered your home. Head to {home_channel.mention}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("Failed to create home interior!", ephemeral=True)
    
    @interior_group.command(name="leave", description="Leave your home interior")
    async def leave_home(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if in a home
        current_home_data = self.db.execute_query(
            '''SELECT c.current_home_id, h.location_id, h.home_name
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not current_home_data:
            await interaction.followup.send("You're not inside a home!", ephemeral=True)
            return
        
        home_id, location_id, home_name = current_home_data
        
        # Check if anyone else is in the home
        others_in_home = self.db.execute_query(
            "SELECT user_id FROM characters WHERE current_home_id = ? AND user_id != ?",
            (home_id, interaction.user.id),
            fetch='all'
        )
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_home_id = NULL WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Give user access back to location
        await channel_manager.give_user_location_access(interaction.user, location_id)
        
        # Remove from home channel
        await channel_manager.remove_user_home_access(interaction.user, home_id)
        
        # If this was the owner and others are inside, move them out too
        owner_id = self.db.execute_query(
            "SELECT owner_id FROM location_homes WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )[0]
        
        if interaction.user.id == owner_id and others_in_home:
            # Move all other users out
            for (other_user_id,) in others_in_home:
                member = interaction.guild.get_member(other_user_id)
                if member:
                    # Update their location
                    self.db.execute_query(
                        "UPDATE characters SET current_home_id = NULL WHERE user_id = ?",
                        (other_user_id,)
                    )
                    
                    # Give them location access
                    await channel_manager.give_user_location_access(member, location_id)
                    
                    # Remove from home channel
                    await channel_manager.remove_user_home_access(member, home_id)
                    
                    # Notify them
                    try:
                        await member.send(f"The owner of {home_name} has left, and you've been moved back to the location.")
                    except:
                        pass
        
        # Clean up home channel if empty
        remaining_users = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_home_id = ?",
            (home_id,),
            fetch='one'
        )[0]
        
        if remaining_users == 0:
            # Get channel ID and clean up
            home_channel = self.db.execute_query(
                "SELECT channel_id FROM home_interiors WHERE home_id = ?",
                (home_id,),
                fetch='one'
            )
            
            if home_channel and home_channel[0]:
                await channel_manager.cleanup_home_channel(home_channel[0])
        
        await interaction.followup.send("You've left your home.", ephemeral=True)
    @interior_group.command(name="invite", description="Invite someone to your home")
    @app_commands.describe(player="The player to invite to your home")
    async def invite_to_home(self, interaction: discord.Interaction, player: discord.Member):
        if player.id == interaction.user.id:
            await interaction.response.send_message("You can't invite yourself!", ephemeral=True)
            return
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name, h.location_id
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.response.send_message("You must be inside your own home to invite someone!", ephemeral=True)
            return
        
        home_id, home_name, location_id = home_data
        
        # Check if target player is at the same location
        target_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ? AND location_status = 'docked'",
            (player.id,),
            fetch='one'
        )
        
        if not target_location or target_location[0] != location_id:
            await interaction.response.send_message(f"{player.mention} must be at the same location as your home!", ephemeral=True)
            return
        
        # Create invitation
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(minutes=5)
        
        self.db.execute_query(
            '''INSERT INTO home_invitations (home_id, inviter_id, invitee_id, location_id, expires_at)
               VALUES (?, ?, ?, ?, ?)''',
            (home_id, interaction.user.id, player.id, location_id, expires_at)
        )
        
        await interaction.response.send_message(
            f"Invited {player.mention} to your home. They have 5 minutes to accept with `/home interior accept`.",
            ephemeral=False
        )
        
        # Notify the invitee
        try:
            await player.send(f"{interaction.user.mention} has invited you to their home '{home_name}'. Use `/home interior accept` to enter.")
        except:
            pass

    @interior_group.command(name="accept", description="Accept a home invitation")
    async def accept_home_invitation(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Find valid invitation
        invitation = self.db.execute_query(
            '''SELECT i.invitation_id, i.home_id, i.inviter_id, h.home_name, h.interior_description
               FROM home_invitations i
               JOIN location_homes h ON i.home_id = h.home_id
               WHERE i.invitee_id = ? AND i.expires_at > datetime('now')
               ORDER BY i.created_at DESC
               LIMIT 1''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not invitation:
            await interaction.followup.send("You don't have any active home invitations.", ephemeral=True)
            return
        
        invitation_id, home_id, inviter_id, home_name, interior_desc = invitation
        
        # Check if already in a home
        current_home = self.db.execute_query(
            "SELECT current_home_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if current_home and current_home[0]:
            await interaction.followup.send("You must leave your current location before accepting an invitation!", ephemeral=True)
            return
        
        # Get home channel
        home_channel_id = self.db.execute_query(
            "SELECT channel_id FROM home_interiors WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )
        
        if not home_channel_id or not home_channel_id[0]:
            await interaction.followup.send("The home channel no longer exists.", ephemeral=True)
            return
        
        home_channel = interaction.guild.get_channel(home_channel_id[0])
        if not home_channel:
            await interaction.followup.send("The home channel no longer exists.", ephemeral=True)
            return
        
        # Accept invitation
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        # Update character location
        self.db.execute_query(
            "UPDATE characters SET current_home_id = ? WHERE user_id = ?",
            (home_id, interaction.user.id)
        )
        
        # Get current location to remove access
        current_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Remove from location channel
        await channel_manager.remove_user_location_access(interaction.user, current_location)
        
        # Give access to home channel
        success = await channel_manager.give_user_home_access(interaction.user, home_id)
        
        if success:
            # Delete the invitation
            self.db.execute_query(
                "DELETE FROM home_invitations WHERE invitation_id = ?",
                (invitation_id,)
            )
            
            await interaction.followup.send(
                f"You've entered {home_name}. Head to {home_channel.mention}",
                ephemeral=True
            )
            
            # Notify the inviter
            try:
                inviter = interaction.guild.get_member(inviter_id)
                if inviter:
                    await home_channel.send(f"{interaction.user.mention} has entered the home.")
            except:
                pass
        else:
            await interaction.followup.send("Failed to enter the home.", ephemeral=True)
    @home_group.command(name="market", description="List your home on the market")
    async def market_home(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get homes at current location
        location_id = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        homes = self.db.execute_query(
            '''SELECT home_id, home_name, price, value_modifier
               FROM location_homes
               WHERE owner_id = ? AND location_id = ?''',
            (interaction.user.id, location_id),
            fetch='all'
        )
        
        if not homes:
            await interaction.followup.send("You don't own any homes at this location!", ephemeral=True)
            return
        
        # For simplicity, if only one home, list it directly
        if len(homes) == 1:
            home_id, home_name, original_price, value_mod = homes[0]
            
            # Calculate market price based on economy
            wealth_level = self.db.execute_query(
                "SELECT wealth_level FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )[0]
            
            if wealth_level >= 6:
                economy_modifier = 1.1  # Good economy
            elif wealth_level <= 2:
                economy_modifier = 0.9  # Poor economy
            else:
                economy_modifier = 1.0
            
            market_price = int(original_price * value_mod * economy_modifier)
            
            # List on market
            self.db.execute_query(
                '''INSERT INTO home_market_listings 
                   (home_id, seller_id, asking_price, original_price)
                   VALUES (?, ?, ?, ?)''',
                (home_id, interaction.user.id, market_price, original_price)
            )
            
            embed = discord.Embed(
                title="🏠 Home Listed!",
                description=f"**{home_name}** is now on the market for {market_price:,} credits.",
                color=0x00ff00
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @home_group.command(name="sell", description="Offer to sell your home directly to another player")
    @app_commands.describe(
        player="The player to sell to",
        price="Your asking price"
    )
    async def sell_home(self, interaction: discord.Interaction, player: discord.Member, price: int):
        if player.id == interaction.user.id:
            await interaction.response.send_message("You can't sell to yourself!", ephemeral=True)
            return
        
        if price < 1:
            await interaction.response.send_message("Price must be positive!", ephemeral=True)
            return
        
        # Get homes at current location
        location_id = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Check if buyer is at same location
        buyer_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (player.id,),
            fetch='one'
        )
        
        if not buyer_location or buyer_location[0] != location_id:
            await interaction.response.send_message("The buyer must be at the same location!", ephemeral=True)
            return
        
        homes = self.db.execute_query(
            '''SELECT home_id, home_name
               FROM location_homes
               WHERE owner_id = ? AND location_id = ?''',
            (interaction.user.id, location_id),
            fetch='all'
        )
        
        if not homes:
            await interaction.response.send_message("You don't own any homes at this location!", ephemeral=True)
            return
        
        # For simplicity, use first home if only one
        if len(homes) == 1:
            home_data = {
                'home_id': homes[0][0],
                'home_name': homes[0][1]
            }
            
            # Send offer to buyer
            view = HomeSellView(interaction.user.id, player, home_data, price, self.bot)
            
            embed = discord.Embed(
                title="🏠 Home Purchase Offer",
                description=f"{interaction.user.display_name} is offering to sell you their home:",
                color=0x2F4F4F
            )
            embed.add_field(name="Property", value=home_data['home_name'], inline=True)
            embed.add_field(name="Price", value=f"{price:,} credits", inline=True)
            
            try:
                await player.send(embed=embed, view=view)
                await interaction.response.send_message(
                    f"Offer sent to {player.display_name}. They have 5 minutes to respond.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"Couldn't send offer to {player.display_name}. They may have DMs disabled.",
                    ephemeral=True
                )
    
    async def _get_or_create_home_interior(self, guild, location_channel, home_id, home_name, interior_desc, user):
        """Create or get home interior thread"""
        # Check for existing thread
        thread_name = f"🏠 {home_name}"
        
        for thread in location_channel.threads:
            if thread.name == thread_name and not thread.archived:
                await thread.add_user(user)
                return thread
        
        # Create new thread
        try:
            thread = await location_channel.create_thread(
                name=thread_name,
                auto_archive_duration=1440,  # 24 hours
                reason=f"Home interior for {user.name}"
            )
            
            # Send welcome message
            char_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (user.id,),
                fetch='one'
            )[0]
            
            embed = discord.Embed(
                title=f"🏠 Welcome Home, {char_name}",
                description=interior_desc,
                color=0x2F4F4F
            )
            
            # Get home activities
            if HomeActivityManager:
                manager = HomeActivityManager(self.bot)
                activities = manager.get_home_activities(home_id)
            else:
                activities = []
            
            if activities:
                activity_list = []
                for activity in activities[:8]:
                    activity_list.append(f"{activity['icon']} {activity['name']}")
                
                embed.add_field(
                    name="🎮 Home Facilities",
                    value="\n".join(activity_list),
                    inline=False
                )
            
            embed.add_field(
                name="🎮 Available Actions",
                value="• Use the activity buttons below\n• `/home interior leave` - Exit your home\n• Invite others to visit",
                inline=False
            )
            
            await thread.send(embed=embed)
            
            # Send activity buttons
            if activities and HomeActivityView:
                view = HomeActivityView(self.bot, home_id, home_name, char_name)
                activity_embed = discord.Embed(
                    title="🎯 Home Activities",
                    description="Choose an activity:",
                    color=0x00ff88
                )
                await thread.send(embed=activity_embed, view=view)
            
            # Update database
            self.db.execute_query(
                '''INSERT OR REPLACE INTO home_interiors (home_id, channel_id)
                   VALUES (?, ?)''',
                (home_id, thread.id)
            )
            
            return thread
            
        except Exception as e:
            print(f"Failed to create home interior: {e}")
            return None
    
    @commands.Cog.listener()
    async def on_character_delete(self, user_id: int):
        """Release homes when character is deleted"""
        # Make all owned homes available again
        self.db.execute_query(
            '''UPDATE location_homes 
               SET owner_id = NULL, is_available = 1, purchase_date = NULL
               WHERE owner_id = ?''',
            (user_id,)
        )
        
        # Remove from market
        self.db.execute_query(
            '''UPDATE home_market_listings 
               SET is_active = 0
               WHERE seller_id = ?''',
            (user_id,)
        )


async def setup(bot):
    await bot.add_cog(HomesCog(bot))