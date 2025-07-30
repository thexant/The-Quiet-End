
import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import asyncio
from utils.leave_button import UniversalLeaveView


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
        self.home_id = home['home_id']
        
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
            value="• Use `/tqe` to enter your home\n• Use `/tqe` to see all your properties",
            inline=False
        )
        await self.initialize_home_features(self.home['home_id'], self.home['home_type'])
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
    
    async def initialize_home_features(self, home_id: int, home_type: str):
        """Initialize storage and other features for newly purchased home"""
        # Set storage capacity based on home type
        storage_capacity = {
            'Luxury Suite': 150,
            'House': 100,
            'Apartment': 75,
            'Room': 50
        }.get(home_type, 50)
        
        self.db.execute_query(
            "UPDATE location_homes SET storage_capacity = ? WHERE home_id = ?",
            (storage_capacity, home_id)
        )
        
        # Initialize customization with defaults
        self.db.execute_query(
            '''INSERT INTO home_customizations 
               (home_id, wall_color, floor_type, lighting_style, furniture_style, ambiance)
               VALUES (?, 'Beige', 'Standard Tile', 'Standard', 'Basic', 'Cozy')''',
            (home_id,)
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
            thread = await self._get_or_create_home_interior(
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


class HomeStorageView(discord.ui.View):
    """View for managing home storage"""
    
    def __init__(self, bot, home_id: int, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.db = bot.db
        self.home_id = home_id
        self.user_id = user_id

class HomeUpgradeView(discord.ui.View):
    """View for purchasing home upgrades"""
    
    def __init__(self, bot, home_id: int, user_id: int, available_upgrades: List[Dict]):
        super().__init__(timeout=60)
        self.bot = bot
        self.db = bot.db
        self.home_id = home_id
        self.user_id = user_id
        
        # Create select menu
        options = []
        for upgrade in available_upgrades[:25]:
            options.append(discord.SelectOption(
                label=upgrade['name'],
                value=upgrade['type'],
                description=f"{upgrade['price']:,} credits | +{upgrade['income']}/day",
                emoji=upgrade['emoji']
            ))
        
        self.select = discord.ui.Select(
            placeholder="Select an upgrade to purchase",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your upgrade menu!", ephemeral=True)
            return
        
        upgrade_type = self.select.values[0]
        
        # Get upgrade details
        upgrade = next((u for u in self.available_upgrades if u['type'] == upgrade_type), None)
        if not upgrade:
            await interaction.response.send_message("Upgrade not found!", ephemeral=True)
            return
        
        # Check money
        money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )[0]
        
        if money < upgrade['price']:
            await interaction.response.send_message(
                f"You need {upgrade['price']:,} credits but only have {money:,}!",
                ephemeral=True
            )
            return
        
        # Purchase upgrade
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (upgrade['price'], self.user_id)
        )
        
        self.db.execute_query(
            '''INSERT INTO home_upgrades (home_id, upgrade_type, upgrade_name, daily_income, purchase_price)
               VALUES (?, ?, ?, ?, ?)''',
            (self.home_id, upgrade['type'], upgrade['name'], upgrade['income'], upgrade['price'])
        )
        
        # Initialize income tracking if needed
        self.db.execute_query(
            '''INSERT OR IGNORE INTO home_income (home_id, accumulated_income, last_collected, last_calculated)
               VALUES (?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
            (self.home_id,)
        )
        
        embed = discord.Embed(
            title="✅ Upgrade Purchased!",
            description=f"**{upgrade['name']}** has been installed in your home!",
            color=0x00ff00
        )
        embed.add_field(
            name="Daily Income",
            value=f"+{upgrade['income']} credits/day",
            inline=True
        )
        
        await interaction.response.edit_message(
            content="Upgrade purchased successfully!",
            embed=embed,
            view=None
        )

class HomesCog(commands.Cog):
    """Home ownership and management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.health_recovery_loop.start()
        
        

        
        
        # Define available upgrades
        self.home_upgrades = {
            'workshop': {
                'name': 'Mechanical Workshop',
                'type': 'workshop',
                'emoji': '🔧',
                'price': 5000,
                'income': 75,
                'description': 'Repair items for profit'
            },
            'garden': {
                'name': 'Hydroponics Garden',
                'type': 'garden',
                'emoji': '🌱',
                'price': 3000,
                'income': 50,
                'description': 'Grow and sell produce'
            },
            'rental': {
                'name': 'Rental Suite',
                'type': 'rental',
                'emoji': '🏨',
                'price': 10000,
                'income': 150,
                'description': 'Rent out a room for passive income'
            },
            'mining': {
                'name': 'Ore Mining Rig',
                'type': 'mining',
                'emoji': '⛏️',
                'price': 8000,
                'income': 100,
                'description': 'Mine planetary ore passively'
            },
            'market': {
                'name': 'Market Stall',
                'type': 'market',
                'emoji': '🏪',
                'price': 6000,
                'income': 85,
                'description': 'Automated trading post'
            }
        }
    
    def cog_unload(self):
        self.health_recovery_loop.cancel()
    
    @tasks.loop(minutes=5)
    async def health_recovery_loop(self):
        """Check for health recovery every 5 minutes"""
        try:
            # Get all users currently in homes
            users_in_homes = self.db.execute_query(
                '''SELECT c.user_id, c.current_home_id, c.hp, c.max_hp, h.entered_at, h.last_recovery
                   FROM characters c
                   JOIN home_recovery_tracking h ON c.user_id = h.user_id
                   WHERE c.current_home_id IS NOT NULL AND c.hp < c.max_hp''',
                fetch='all'
            )
            
            for user_id, home_id, hp, max_hp, entered_at, last_recovery in users_in_homes:
                # Check if 20 minutes have passed since last recovery
                last_recovery_time = datetime.fromisoformat(last_recovery)
                if datetime.now() - last_recovery_time >= timedelta(minutes=20):
                    # Heal 10 HP
                    new_hp = min(hp + 10, max_hp)
                    self.db.execute_query(
                        "UPDATE characters SET hp = ? WHERE user_id = ?",
                        (new_hp, user_id)
                    )
                    
                    # Update last recovery time
                    self.db.execute_query(
                        "UPDATE home_recovery_tracking SET last_recovery = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (user_id,)
                    )
        except Exception as e:
            print(f"Error in health recovery loop: {e}")
    
    @health_recovery_loop.before_loop
    async def before_health_recovery(self):
        await self.bot.wait_until_ready()
    
    homes_group = app_commands.Group(name="homes", description="View homes information")
    home_group = app_commands.Group(name="home", description="Home management commands")
    
    @home_group.command(name="enter", description="Enter your home at this location")
    async def enter_home(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if already in a home
        current_home = self.db.execute_query(
            "SELECT current_home_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if current_home and current_home[0]:
            await interaction.followup.send("You are already inside a home! Use `/tqe` to leave your home first.", ephemeral=True)
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
        self.bot.dispatch('home_enter', interaction.user.id, home_id)
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
            
            # Send area movement embed to location channel
            char_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            # Get location channel
            location_channel_id = self.db.execute_query(
                "SELECT channel_id FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )
            
            if location_channel_id:
                location_channel = self.bot.get_channel(location_channel_id[0])
                if location_channel:
                    embed = discord.Embed(
                        title="🚪 Area Movement",
                        description=f"**{char_name}** enters the **{home_name}**.",
                        color=0x7289DA
                    )
                    await location_channel.send(embed=embed)
            
            # Remove from location channel
            await channel_manager.remove_user_location_access(interaction.user, location_id)
            
            # Get customizations for the response
            customizations = self.db.execute_query(
                '''SELECT wall_color, floor_type, lighting_style, furniture_style, ambiance
                   FROM home_customizations WHERE home_id = ?''',
                (home_id,),
                fetch='one'
            )
            
            if customizations:
                wall_color, floor_type, lighting, furniture, ambiance = customizations
                custom_msg = f"\n🎨 *Current theme: {ambiance} atmosphere with {wall_color.lower()} walls*"
            else:
                custom_msg = ""
            
            await interaction.followup.send(
                f"You've entered your home. Head to {home_channel.mention}{custom_msg}",
                ephemeral=True
            )
        
    
    @home_group.command(name="accept", description="Accept a home invitation")
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
        
        # Send area movement embed to location channel
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Get location channel
        location_channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if location_channel_id:
            location_channel = self.bot.get_channel(location_channel_id[0])
            if location_channel:
                embed = discord.Embed(
                    title="🚪 Area Movement",
                    description=f"**{char_name}** enters the **{home_name}**.",
                    color=0x7289DA
                )
                await location_channel.send(embed=embed)
        
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
    
    
    
    @home_group.command(name="invite", description="Invite someone to your home")
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
            await player.send(f"{interaction.user.mention} has invited you to their home '{home_name}'. Use `/tqe` to enter.")
        except:
            pass

    @home_group.command(name="leave", description="Leave your home interior")
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
        self.bot.dispatch('home_leave', interaction.user.id)
        
        # Send area movement embed to location channel
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Get location channel
        location_channel_id = self.db.execute_query(
            "SELECT channel_id FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if location_channel_id:
            location_channel = self.bot.get_channel(location_channel_id[0])
            if location_channel:
                embed = discord.Embed(
                    title="🚪 Area Movement",
                    description=f"**{char_name}** has exited the **{home_name}**.",
                    color=0xFF6600
                )
                await location_channel.send(embed=embed)
        
        # Give user access back to location (suppress arrival notification for home departures)
        await channel_manager.give_user_location_access(interaction.user, location_id, send_arrival_notification=False)
        
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
        
        # Clean up home channel if empty (check only logged-in users)
        remaining_users = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE current_home_id = ? AND is_logged_in = 1",
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
    
    # Storage Commands
    storage_group = app_commands.Group(name="storage", description="Home storage management")
    
    @storage_group.command(name="store", description="Store items in your home")
    @app_commands.describe(
        item_name="Name of the item to store",
        quantity="How many to store (default: 1)"
    )
    async def store_item(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        await interaction.response.defer(ephemeral=True)
        
        if quantity < 1:
            await interaction.followup.send("You must store at least 1 item!", ephemeral=True)
            return
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name, h.storage_capacity
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to use storage!", ephemeral=True)
            return
        
        home_id, home_name, storage_capacity = home_data
        
        # Check current storage usage
        current_usage = self.db.execute_query(
            "SELECT COALESCE(SUM(quantity), 0) FROM home_storage WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )[0]
        
        if current_usage + quantity > storage_capacity:
            await interaction.followup.send(
                f"Not enough storage space! ({current_usage}/{storage_capacity} used, trying to add {quantity})",
                ephemeral=True
            )
            return
        
        # Find item in inventory
        inventory_item = self.db.execute_query(
            '''SELECT item_id, item_name, item_type, quantity, description, value
               FROM inventory 
               WHERE owner_id = ? AND LOWER(item_name) LIKE LOWER(?)
               ORDER BY item_name LIMIT 1''',
            (interaction.user.id, f"%{item_name}%"),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.followup.send(f"You don't have any '{item_name}' in your inventory!", ephemeral=True)
            return
        
        item_id, actual_name, item_type, inv_quantity, description, value = inventory_item
        
        if inv_quantity < quantity:
            await interaction.followup.send(
                f"You only have {inv_quantity} {actual_name}, can't store {quantity}!",
                ephemeral=True
            )
            return
        
        # Transfer items
        if inv_quantity == quantity:
            self.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (item_id,))
        else:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                (quantity, item_id)
            )
        
        # Add to home storage
        existing_storage = self.db.execute_query(
            "SELECT storage_id, quantity FROM home_storage WHERE home_id = ? AND item_name = ?",
            (home_id, actual_name),
            fetch='one'
        )
        
        if existing_storage:
            self.db.execute_query(
                "UPDATE home_storage SET quantity = quantity + ? WHERE storage_id = ?",
                (quantity, existing_storage[0])
            )
        else:
            self.db.execute_query(
                '''INSERT INTO home_storage 
                   (home_id, item_name, item_type, quantity, description, value, stored_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (home_id, actual_name, item_type, quantity, description, value, interaction.user.id)
            )
        
        embed = discord.Embed(
            title="📦 Items Stored",
            description=f"Stored {quantity}x **{actual_name}** in your home storage",
            color=0x00ff00
        )
        embed.add_field(
            name="Storage Usage",
            value=f"{current_usage + quantity}/{storage_capacity}",
            inline=True
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @storage_group.command(name="retrieve", description="Retrieve items from your home storage")
    @app_commands.describe(
        item_name="Name of the item to retrieve",
        quantity="How many to retrieve (default: 1)"
    )
    async def retrieve_item(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        await interaction.response.defer(ephemeral=True)
        
        if quantity < 1:
            await interaction.followup.send("You must retrieve at least 1 item!", ephemeral=True)
            return
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to access storage!", ephemeral=True)
            return
        
        home_id, home_name = home_data
        
        # Find item in storage
        storage_item = self.db.execute_query(
            '''SELECT storage_id, item_name, item_type, quantity, description, value
               FROM home_storage 
               WHERE home_id = ? AND LOWER(item_name) LIKE LOWER(?)
               ORDER BY item_name LIMIT 1''',
            (home_id, f"%{item_name}%"),
            fetch='one'
        )
        
        if not storage_item:
            await interaction.followup.send(f"No '{item_name}' found in your home storage!", ephemeral=True)
            return
        
        storage_id, actual_name, item_type, stored_quantity, description, value = storage_item
        
        if stored_quantity < quantity:
            await interaction.followup.send(
                f"You only have {stored_quantity} {actual_name} stored, can't retrieve {quantity}!",
                ephemeral=True
            )
            return
        
        # Transfer items
        if stored_quantity == quantity:
            self.db.execute_query("DELETE FROM home_storage WHERE storage_id = ?", (storage_id,))
        else:
            self.db.execute_query(
                "UPDATE home_storage SET quantity = quantity - ? WHERE storage_id = ?",
                (quantity, storage_id)
            )
        
        # Add to inventory
        existing_inv = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, actual_name),
            fetch='one'
        )
        
        if existing_inv:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
                (quantity, existing_inv[0])
            )
        else:
            self.db.execute_query(
                '''INSERT INTO inventory 
                   (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, actual_name, item_type, quantity, description, value)
            )
        
        embed = discord.Embed(
            title="📤 Items Retrieved",
            description=f"Retrieved {quantity}x **{actual_name}** from storage",
            color=0x00ff00
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @storage_group.command(name="view", description="View your home storage contents")
    async def view_storage(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name, h.storage_capacity
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to view storage!", ephemeral=True)
            return
        
        home_id, home_name, storage_capacity = home_data
        
        # Get storage contents
        items = self.db.execute_query(
            '''SELECT item_name, item_type, quantity, value
               FROM home_storage
               WHERE home_id = ?
               ORDER BY item_type, item_name''',
            (home_id,),
            fetch='all'
        )
        
        current_usage = sum(q for _, _, q, _ in items)
        
        embed = discord.Embed(
            title=f"📦 {home_name} Storage",
            description=f"Capacity: {current_usage}/{storage_capacity}",
            color=0x8B4513
        )
        
        if not items:
            embed.add_field(name="Empty", value="Your storage is empty.", inline=False)
        else:
            # Group by type
            item_types = {}
            total_value = 0
            
            for name, item_type, quantity, value in items:
                if item_type not in item_types:
                    item_types[item_type] = []
                item_types[item_type].append((name, quantity, value))
                total_value += value * quantity
            
            for item_type, type_items in item_types.items():
                items_text = []
                for name, quantity, value in type_items[:10]:
                    qty_text = f" x{quantity}" if quantity > 1 else ""
                    items_text.append(f"{name}{qty_text}")
                
                if len(type_items) > 10:
                    items_text.append(f"...and {len(type_items) - 10} more")
                
                embed.add_field(
                    name=item_type.replace('_', ' ').title(),
                    value="\n".join(items_text),
                    inline=True
                )
            
            embed.add_field(name="Total Value", value=f"{total_value:,} credits", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Income Commands
    income_group = app_commands.Group(name="income", description="Home income management")
    
    @income_group.command(name="upgrade", description="Purchase income-generating upgrades for your home")
    async def buy_upgrade(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name, c.money
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to purchase upgrades!", ephemeral=True)
            return
        
        home_id, home_name, money = home_data
        
        # Get existing upgrades
        existing = self.db.execute_query(
            "SELECT upgrade_type FROM home_upgrades WHERE home_id = ?",
            (home_id,),
            fetch='all'
        )
        existing_types = [e[0] for e in existing]
        
        if len(existing_types) >= 3:
            await interaction.followup.send("You already have the maximum of 3 upgrades!", ephemeral=True)
            return
        
        # Get available upgrades
        available = []
        for upgrade_type, upgrade_data in self.home_upgrades.items():
            if upgrade_type not in existing_types:
                available.append(upgrade_data)
        
        if not available:
            await interaction.followup.send("No more upgrades available!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🏗️ Home Upgrades - {home_name}",
            description=f"You have {money:,} credits\nSelect an upgrade to generate passive income:",
            color=0x2F4F4F
        )
        
        for upgrade in available:
            embed.add_field(
                name=f"{upgrade['emoji']} {upgrade['name']}",
                value=f"{upgrade['description']}\n**Cost:** {upgrade['price']:,} credits\n**Income:** {upgrade['income']}/day",
                inline=False
            )
        
        view = HomeUpgradeView(self.bot, home_id, interaction.user.id, available)
        view.available_upgrades = available  # Store for reference
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @income_group.command(name="collect", description="Collect accumulated income from your home")
    async def collect_income(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to collect income!", ephemeral=True)
            return
        
        home_id, home_name = home_data
        
        # Get total daily income from upgrades
        daily_income = self.db.execute_query(
            "SELECT COALESCE(SUM(daily_income), 0) FROM home_upgrades WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )[0]
        
        if daily_income == 0:
            await interaction.followup.send("Your home doesn't have any income-generating upgrades!", ephemeral=True)
            return
        
        # Get or create income record
        income_data = self.db.execute_query(
            '''SELECT accumulated_income, last_collected, last_calculated
               FROM home_income WHERE home_id = ?''',
            (home_id,),
            fetch='one'
        )
        
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        current_time = time_system.calculate_current_ingame_time()
        
        if not current_time:
            await interaction.followup.send("Error calculating time. Please try again later.", ephemeral=True)
            return
        
        if not income_data:
            # First time - initialize income tracking
            self.db.execute_query(
                '''INSERT INTO home_income (home_id, accumulated_income, last_collected, last_calculated)
                   VALUES (?, 0, ?, ?)''',
                (home_id, current_time.isoformat(), current_time.isoformat())
            )
            await interaction.followup.send("Income tracking initialized. Check back tomorrow!", ephemeral=True)
            return
        
        accumulated, last_collected_str, last_calculated_str = income_data
        
        # Calculate days since last calculation
        if last_calculated_str:
            last_calculated = datetime.fromisoformat(last_calculated_str)
            # Get in-game days passed
            days_passed = (current_time - last_calculated).total_seconds() / 86400
        else:
            days_passed = 0
        
        # Calculate new income
        new_income = int(daily_income * days_passed)
        total_available = accumulated + new_income
        
        # Cap at 7 days
        max_income = daily_income * 7
        if total_available > max_income:
            total_available = max_income
            days_capped = True
        else:
            days_capped = False
        
        if total_available <= 0:
            await interaction.followup.send("No income to collect yet. Check back later!", ephemeral=True)
            return
        
        # Update character money
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (total_available, interaction.user.id)
        )
        
        # Reset income tracking
        self.db.execute_query(
            '''UPDATE home_income 
               SET accumulated_income = 0, 
                   last_collected = ?,
                   last_calculated = ?
               WHERE home_id = ?''',
            (current_time.isoformat(), current_time.isoformat(), home_id)
        )
        
        # Create response embed
        embed = discord.Embed(
            title="💰 Income Collected!",
            description=f"Collected **{total_available:,} credits** from {home_name}",
            color=0x00ff00
        )
        
        embed.add_field(
            name="Daily Income Rate",
            value=f"{daily_income} credits/day",
            inline=True
        )
        
        embed.add_field(
            name="Time Period",
            value=f"{days_passed:.1f} in-game days",
            inline=True
        )
        
        if days_capped:
            embed.add_field(
                name="⚠️ Income Capped",
                value="Income was capped at 7 days. Collect more frequently!",
                inline=False
            )
        
        # Show upgrade details
        upgrades = self.db.execute_query(
            "SELECT upgrade_name, daily_income FROM home_upgrades WHERE home_id = ?",
            (home_id,),
            fetch='all'
        )
        
        if upgrades:
            upgrade_text = "\n".join([f"• {name}: {income}/day" for name, income in upgrades])
            embed.add_field(
                name="Active Upgrades",
                value=upgrade_text,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Customization Commands
    customize_group = app_commands.Group(name="home_customize", description="Home customization options")
    
    @customize_group.command(name="floor", description="Change your home's flooring")
    @app_commands.describe(floor="Choose a floor type")
    @app_commands.choices(floor=[
        app_commands.Choice(name="Standard Tile", value="Standard Tile"),
        app_commands.Choice(name="Hardwood", value="Hardwood"),
        app_commands.Choice(name="Plush Carpet", value="Carpet"),
        app_commands.Choice(name="Marble", value="Marble"),
        app_commands.Choice(name="Stone", value="Stone"),
        app_commands.Choice(name="Metal", value="Metal")
    ])
    async def customize_floor(self, interaction: discord.Interaction, floor: str):
        home_id = await self._check_home_ownership(interaction)
        if not home_id:
            return
        
        self.db.execute_query(
            "UPDATE home_customizations SET floor_type = ? WHERE home_id = ?",
            (floor, home_id)
        )
        
        await self._update_home_channel_topic(home_id, interaction)
        
        await interaction.response.send_message(
            f"✅ Floor type changed to **{floor}**!",
            ephemeral=True
        )

    @customize_group.command(name="lighting", description="Adjust your home's lighting")
    @app_commands.describe(lighting="Choose a lighting style")
    @app_commands.choices(lighting=[
        app_commands.Choice(name="Standard", value="Standard"),
        app_commands.Choice(name="Dim Mood Lighting", value="Dim"),
        app_commands.Choice(name="Bright", value="Bright"),
        app_commands.Choice(name="Neon Accents", value="Neon"),
        app_commands.Choice(name="Candlelit", value="Candlelit"),
        app_commands.Choice(name="Natural Sunlight", value="Natural")
    ])
    async def customize_lighting(self, interaction: discord.Interaction, lighting: str):
        home_id = await self._check_home_ownership(interaction)
        if not home_id:
            return
        
        self.db.execute_query(
            "UPDATE home_customizations SET lighting_style = ? WHERE home_id = ?",
            (lighting, home_id)
        )
        
        await self._update_home_channel_topic(home_id, interaction)
        
        await interaction.response.send_message(
            f"✅ Lighting changed to **{lighting}**!",
            ephemeral=True
        )

    @customize_group.command(name="furniture", description="Change your home's furniture style")
    @app_commands.describe(furniture="Choose a furniture style")
    @app_commands.choices(furniture=[
        app_commands.Choice(name="Basic", value="Basic"),
        app_commands.Choice(name="Modern", value="Modern"),
        app_commands.Choice(name="Luxury", value="Luxury"),
        app_commands.Choice(name="Industrial", value="Industrial"),
        app_commands.Choice(name="Earth Federation", value="Federation"),
        app_commands.Choice(name="Outlaw", value="Outlaw")
    ])
    async def customize_furniture(self, interaction: discord.Interaction, furniture: str):
        home_id = await self._check_home_ownership(interaction)
        if not home_id:
            return
        
        self.db.execute_query(
            "UPDATE home_customizations SET furniture_style = ? WHERE home_id = ?",
            (furniture, home_id)
        )
        
        await self._update_home_channel_topic(home_id, interaction)
        
        await interaction.response.send_message(
            f"✅ Furniture style changed to **{furniture}**!",
            ephemeral=True
        )

    @customize_group.command(name="ambiance", description="Set your home's overall ambiance")
    @app_commands.describe(ambiance="Choose an ambiance")
    @app_commands.choices(ambiance=[
        app_commands.Choice(name="Cozy", value="Cozy"),
        app_commands.Choice(name="Relaxing", value="Relaxing"),
        app_commands.Choice(name="Clean", value="Clean"),
        app_commands.Choice(name="Chaotic", value="Chaotic"),
        app_commands.Choice(name="Calm", value="Calm"),
        app_commands.Choice(name="Professional", value="Professional")
    ])
    async def customize_ambiance(self, interaction: discord.Interaction, ambiance: str):
        home_id = await self._check_home_ownership(interaction)
        if not home_id:
            return
        
        self.db.execute_query(
            "UPDATE home_customizations SET ambiance = ? WHERE home_id = ?",
            (ambiance, home_id)
        )
        
        await self._update_home_channel_topic(home_id, interaction)
        
        await interaction.response.send_message(
            f"✅ Ambiance changed to **{ambiance}**!",
            ephemeral=True
        )
    @customize_group.command(name="theme", description="Customize your home's appearance")
    async def customize_theme(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to customize it!", ephemeral=True)
            return
        
        home_id, home_name = home_data
        
        # Get current customization
        current = self.db.execute_query(
            '''SELECT wall_color, floor_type, lighting_style, furniture_style, ambiance
               FROM home_customizations WHERE home_id = ?''',
            (home_id,),
            fetch='one'
        )
        
        if not current:
            # Create default customization
            self.db.execute_query(
                "INSERT INTO home_customizations (home_id) VALUES (?)",
                (home_id,)
            )
            current = ('Beige', 'Standard Tile', 'Standard', 'Basic', 'Cozy')
        
        wall_color, floor_type, lighting, furniture, ambiance = current
        
        embed = discord.Embed(
            title=f"🎨 Customize {home_name}",
            description="Current theme settings:",
            color=0x9370DB
        )
        embed.add_field(name="🎨 Wall Color", value=wall_color, inline=True)
        embed.add_field(name="🏠 Floor Type", value=floor_type, inline=True)
        embed.add_field(name="💡 Lighting", value=lighting, inline=True)
        embed.add_field(name="🪑 Furniture", value=furniture, inline=True)
        embed.add_field(name="✨ Ambiance", value=ambiance, inline=True)
        
        embed.add_field(
            name="Available Commands",
            value=(
                "`/home_customize walls` - Change wall color\n"
                "`/home_customize floor` - Change flooring\n"
                "`/home_customize lighting` - Adjust lighting\n"
                "`/home_customize furniture` - Change furniture style\n"
                "`/home_customize ambiance` - Set overall ambiance"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @customize_group.command(name="walls", description="Change your home's wall color")
    @app_commands.describe(color="Choose a wall color")
    @app_commands.choices(color=[
        app_commands.Choice(name="Classic Beige", value="Beige"),
        app_commands.Choice(name="Modern Gray", value="Gray"),
        app_commands.Choice(name="Warm White", value="White"),
        app_commands.Choice(name="Navy Blue", value="Blue"),
        app_commands.Choice(name="Forest Green", value="Green"),
        app_commands.Choice(name="Charcoal Black", value="Black"),
        app_commands.Choice(name="Crimson Red", value="Red"),
        app_commands.Choice(name="Royal Purple", value="Purple")
    ])
    async def customize_walls(self, interaction: discord.Interaction, color: str):
        # Check ownership and update
        home_id = await self._check_home_ownership(interaction)
        if not home_id:
            return
        
        self.db.execute_query(
            "UPDATE home_customizations SET wall_color = ? WHERE home_id = ?",
            (color, home_id)
        )
        await self._update_home_channel_topic(home_id, interaction)
        await interaction.response.send_message(
            f"✅ Wall color changed to **{color}**!",
            ephemeral=True
        )
    
    async def _check_home_ownership(self, interaction: discord.Interaction) -> Optional[int]:
        """Helper method to check if user is in their own home"""
        home_data = self.db.execute_query(
            '''SELECT h.home_id
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.response.send_message(
                "You must be inside your own home to customize it!",
                ephemeral=True
            )
            return None
        
        # Ensure customization record exists
        self.db.execute_query(
            "INSERT OR IGNORE INTO home_customizations (home_id) VALUES (?)",
            (home_data[0],)
        )
        
        return home_data[0]
    
    async def _update_home_channel_topic(self, home_id: int, interaction: discord.Interaction):
        """Update home channel topic to reflect customizations"""
        channel_info = self.db.execute_query(
            "SELECT channel_id FROM home_interiors WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )
        
        if not channel_info or not channel_info[0]:
            return
        
        channel = interaction.guild.get_channel(channel_info[0])
        if not channel:
            return
        
        # Get home and customization info
        home_info = self.db.execute_query(
            "SELECT home_name, interior_description FROM location_homes WHERE home_id = ?",
            (home_id,),
            fetch='one'
        )
        
        custom = self.db.execute_query(
            '''SELECT wall_color, floor_type, lighting_style, furniture_style, ambiance
               FROM home_customizations WHERE home_id = ?''',
            (home_id,),
            fetch='one'
        )
        
        if home_info and custom:
            home_name, base_desc = home_info
            wall_color, floor_type, lighting, furniture, ambiance = custom
            
            topic = f"🏠 {home_name} | 🎨 {ambiance} theme with {wall_color} walls | {lighting} lighting"
            
            try:
                await channel.edit(topic=topic[:1024])  # Discord topic limit
            except:
                pass
    
    
    @home_group.command(name="preview", description="Preview the interior of your home")
    async def preview_home(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is in their own home
        home_data = self.db.execute_query(
            '''SELECT h.home_id, h.home_name, h.interior_description
               FROM characters c
               JOIN location_homes h ON c.current_home_id = h.home_id
               WHERE c.user_id = ? AND h.owner_id = ?''',
            (interaction.user.id, interaction.user.id),
            fetch='one'
        )
        
        if not home_data:
            await interaction.followup.send("You must be inside your own home to preview it!", ephemeral=True)
            return
        
        home_id, home_name, base_desc = home_data
        
        # Get customizations
        custom = self.db.execute_query(
            '''SELECT wall_color, floor_type, lighting_style, furniture_style, ambiance
               FROM home_customizations WHERE home_id = ?''',
            (home_id,),
            fetch='one'
        )
        
        if not custom:
            custom = ('Beige', 'Standard Tile', 'Standard', 'Basic', 'Cozy')
        
        wall_color, floor_type, lighting, furniture, ambiance = custom
        
        # Create detailed preview embed
        embed = discord.Embed(
            title=f"🏠 {home_name} - Interior Preview",
            color=self._get_embed_color(wall_color)
        )
        
        # Generate room descriptions based on customizations
        living_room = self._generate_room_description('living room', wall_color, floor_type, lighting, furniture, ambiance)
        bedroom = self._generate_room_description('bedroom', wall_color, floor_type, lighting, furniture, ambiance)
        
        embed.add_field(
            name="🛋️ Living Area",
            value=living_room,
            inline=False
        )
        
        embed.add_field(
            name="🛏️ Bedroom",
            value=bedroom,
            inline=False
        )
        
        embed.add_field(
            name="🎨 Current Theme Details",
            value=(
                f"**Wall Color:** {wall_color} {self._get_wall_emoji(wall_color)}\n"
                f"**Flooring:** {floor_type} {self._get_floor_emoji(floor_type)}\n"
                f"**Lighting:** {lighting} {self._get_lighting_emoji(lighting)}\n"
                f"**Furniture:** {furniture} {self._get_furniture_emoji(furniture)}\n"
                f"**Ambiance:** {ambiance} {self._get_ambiance_emoji(ambiance)}"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    def _generate_room_description(self, room_type, wall_color, floor_type, lighting, furniture, ambiance):
        """Generate room-specific descriptions based on customizations"""
        if room_type == 'living room':
            if furniture == 'Modern' and ambiance == 'Chaotic':
                return f"The {wall_color.lower()} walls frame sleek modern furniture. {lighting} lighting energizes the {floor_type.lower()} space."
            elif furniture == 'Luxury' and ambiance == 'Clean':
                return f"Luxurious furnishings rest on {floor_type.lower()}, while {lighting.lower()} lighting highlights the elegant {wall_color.lower()} walls."
            else:
                return f"A {ambiance.lower()} living space with {furniture.lower()} furniture and {wall_color.lower()} walls."
        
        elif room_type == 'bedroom':
            if ambiance == 'Relaxing':
                return f"A peaceful retreat with {lighting.lower()} lighting and {furniture.lower()} furnishings against {wall_color.lower()} walls."
            elif ambiance == 'Calm':
                return f"An enigmatic chamber where {lighting.lower()} lighting casts shadows on {wall_color.lower()} walls."
            else:
                return f"A {ambiance.lower()} bedroom featuring {furniture.lower()} furniture and {floor_type.lower()} floors."

    def _get_wall_emoji(self, wall_color):
        emojis = {
            'Beige': '🟫', 'Gray': '⬜', 'White': '⬜', 'Blue': '🟦',
            'Green': '🟩', 'Black': '⬛', 'Red': '🟥', 'Purple': '🟪'
        }
        return emojis.get(wall_color, '🎨')

    def _get_floor_emoji(self, floor_type):
        emojis = {
            'Standard Tile': '⬜', 'Hardwood': '🪵', 'Carpet': '🟦',
            'Marble': '⬜', 'Stone': '🪨', 'Metal': '⚙️'
        }
        return emojis.get(floor_type, '🏠')

    def _get_lighting_emoji(self, lighting):
        emojis = {
            'Standard': '💡', 'Dim': '🕯️', 'Bright': '☀️',
            'Neon': '🌈', 'Candlelit': '🕯️', 'Natural': '🌞'
        }
        return emojis.get(lighting, '💡')

    def _get_furniture_emoji(self, furniture):
        emojis = {
            'Basic': '🪑', 'Modern': '🛋️', 'Luxury': '👑',
            'Industrial': '⚙️', 'Federation': '🌐', 'Outlaw': '☠️'
        }
        return emojis.get(furniture, '🪑')

    def _get_ambiance_emoji(self, ambiance):
        emojis = {
            'Cozy': '🏡', 'Relaxing': '😌', 'Clean': '✨',
            'Chaotic': '⚡', 'Calm': '🌙', 'Professional': '💼'
        }
        return emojis.get(ambiance, '🏠')
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
            
            # Get customizations
            custom = self.db.execute_query(
                '''SELECT wall_color, floor_type, lighting_style, furniture_style, ambiance
                   FROM home_customizations WHERE home_id = ?''',
                (home_id,),
                fetch='one'
            )
            
            # Check if on market
            on_market = self.db.execute_query(
                "SELECT asking_price FROM home_market_listings WHERE home_id = ? AND is_active = 1",
                (home_id,),
                fetch='one'
            )
            
            market_status = f" 🏷️ Listed for {on_market[0]:,}" if on_market else ""
            
            # Add customization info
            theme_info = ""
            if custom:
                theme_info = f"\n🎨 {custom[4]} theme"  # Show ambiance
            
            embed.add_field(
                name=f"{name}",
                value=f"📍 {location}\n💰 Value: {current_value:,} credits{market_status}{theme_info}",
                inline=True
            )
        
        embed.add_field(
            name="📊 Total Portfolio Value",
            value=f"{total_value:,} credits",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    

    





    
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
                
                # Add universal leave button to the view
                leave_view = UniversalLeaveView(self.bot)
                # Transfer the leave button to the main view
                for item in leave_view.children:
                    view.add_item(item)
                
                activity_embed = discord.Embed(
                    title="🎯 Home Activities",
                    description="Choose an activity:",
                    color=0x00ff88
                )
                await thread.send(embed=activity_embed, view=view)
            else:
                # No activities, but still show the leave button
                leave_view = UniversalLeaveView(self.bot)
                activity_embed = discord.Embed(
                    title="🎯 Home Controls",
                    description="Use the button below to leave your home:",
                    color=0x00ff88
                )
                await thread.send(embed=activity_embed, view=leave_view)
            
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
    
    
    
    @commands.Cog.listener()
    async def on_home_enter(self, user_id: int, home_id: int):
        """Track when a user enters their home for health recovery"""
        # Initialize recovery tracking
        self.db.execute_query(
            '''INSERT OR REPLACE INTO home_recovery_tracking 
               (user_id, home_id, entered_at, last_recovery)
               VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
            (user_id, home_id)
        )
    
    @commands.Cog.listener()
    async def on_home_leave(self, user_id: int):
        """Clean up recovery tracking when user leaves home"""
        self.db.execute_query(
            "DELETE FROM home_recovery_tracking WHERE user_id = ?",
            (user_id,)
        )

async def setup(bot):
    await bot.add_cog(HomesCog(bot))