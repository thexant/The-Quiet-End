import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List


class FactionPurchaseConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, faction_id: int, price: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.faction_id = faction_id
        self.price = price
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success, emoji="💰")
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        
        # Get current funds
        funds = self.bot.db.execute_query(
            '''SELECT c.money, f.bank_balance
               FROM characters c
               JOIN faction_members fm ON c.user_id = fm.user_id
               JOIN factions f ON fm.faction_id = f.faction_id
               WHERE c.user_id = ? AND f.faction_id = ?''',
            (self.user_id, self.faction_id),
            fetch='one'
        )
        
        if not funds:
            return await interaction.response.send_message("Error: Faction data not found!", ephemeral=True)
        
        personal_money, faction_bank = funds
        
        # Deduct from faction bank first, then personal
        remaining_cost = self.price
        faction_deduct = min(faction_bank or 0, remaining_cost)
        remaining_cost -= faction_deduct
        personal_deduct = remaining_cost
        
        if personal_money < personal_deduct:
            return await interaction.response.send_message("Insufficient funds!", ephemeral=True)
        
        # Process purchase
        if faction_deduct > 0:
            self.bot.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance - ? WHERE faction_id = ?",
                (faction_deduct, self.faction_id)
            )
        
        if personal_deduct > 0:
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (personal_deduct, self.user_id)
            )
        
        # Set ownership
        self.bot.db.execute_query(
            '''INSERT INTO location_ownership (location_id, faction_id, purchase_price, ownership_type)
               VALUES (?, ?, ?, 'faction')''',
            (self.location_id, self.faction_id, self.price)
        )
        
        # Get location name
        location_name = self.bot.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (self.location_id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="✅ Location Purchased!",
            description=f"Your faction now owns **{location_name}**!",
            color=0x00ff00
        )
        embed.add_field(name="Total Cost", value=f"{self.price:,} credits", inline=True)
        embed.add_field(name="From Faction Bank", value=f"{faction_deduct:,} credits", inline=True)
        embed.add_field(name="From Personal", value=f"{personal_deduct:,} credits", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        
        await interaction.response.edit_message(content="Purchase cancelled.", embed=None, view=None)
        self.stop()



class LocationOwnershipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        
        # Upgrade costs and effects
        self.upgrade_types = {
            'wealth': {
                'name': 'Economic Development',
                'description': 'Improves location wealth and income generation',
                'max_level': 10,
                'base_cost': 10000
            },
            'population': {
                'name': 'Population Growth',
                'description': 'Increases population and service capacity',
                'max_level': 10,
                'base_cost': 8000
            },
            'security': {
                'name': 'Security Systems',
                'description': 'Reduces raid chance and improves defenses',
                'max_level': 5,
                'base_cost': 15000
            },
            'storage': {
                'name': 'Storage Facility',
                'description': 'Increases private storage capacity',
                'max_level': 8,
                'base_cost': 12000
            },
            'services': {
                'name': 'Service Expansion',
                'description': 'Unlocks and improves location services',
                'max_level': 6,
                'base_cost': 20000
            }
        }
        
    location_group = app_commands.Group(name="location", description="Location management commands")
    
    def calculate_purchase_price(self, location_data: tuple) -> Optional[int]:
        """Calculate the purchase price for a location"""
        location_id, name, location_type, wealth_level, population, is_derelict = location_data
        
        # Exclude loyalist and black market/outlaw locations
        if location_type in ['loyalist', 'outlaw']:
            return None
        
        # New pricing structure:
        # Derelict = 90,000
        # Wealth 1 = 100,000, scaling up with wealth
        if is_derelict:
            return 90000
        else:
            # Base price of 100,000 for wealth 1, +10,000 per wealth level
            return 100000 + ((wealth_level - 1) * 10000)

    def calculate_upkeep_cost(self, location_id: int) -> int:
        """Calculate monthly upkeep cost based on upgrades"""
        upgrades = self.db.execute_query(
            "SELECT upgrade_type, upgrade_level FROM location_upgrades WHERE location_id = ?",
            (location_id,),
            fetch='all'
        )
        
        base_upkeep = 1000
        for upgrade_type, level in upgrades:
            base_upkeep += level * 500
        
        return base_upkeep

    @location_group.command(name="ownership_info", description="View detailed information about current location")
    async def location_info(self, interaction: discord.Interaction):
        # Get character's current location
        char_data = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        
        location_id = char_data[0]
        
        # Get location details
        location_data = self.db.execute_query(
            '''SELECT l.name, l.location_type, l.wealth_level, l.population, l.is_derelict, 
                      l.description, lo.owner_id, lo.custom_name, lo.custom_description,
                      c.name as owner_name, f.faction_id, f.name as faction_name, f.emoji as faction_emoji
               FROM locations l
               LEFT JOIN location_ownership lo ON l.location_id = lo.location_id
               LEFT JOIN characters c ON lo.owner_id = c.user_id
               LEFT JOIN factions f ON lo.faction_id = f.faction_id
               WHERE l.location_id = ?''',
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            return await interaction.response.send_message("Location not found!", ephemeral=True)
        
        (name, location_type, wealth_level, population, is_derelict, description, 
        owner_id, custom_name, custom_description, owner_name, faction_id, 
        faction_name, faction_emoji) = location_data
        
        # Create embed
        display_name = custom_name or name
        embed = discord.Embed(
            title=f"📍 {display_name}",
            description=custom_description or description,
            color=0x00ff00 if owner_id else (0xff6b6b if is_derelict else 0x4169E1)
        )
        
        # Basic info
        embed.add_field(name="Type", value=location_type.replace('_', ' ').title(), inline=True)
        embed.add_field(name="Wealth Level", value=f"{wealth_level}/10", inline=True)
        embed.add_field(name="Population", value=f"{population:,}", inline=True)
        
        # Ownership info
        if faction_id:
            ownership_text = f"{faction_emoji} **{faction_name}**"
            if owner_id and owner_id == interaction.user.id:
                ownership_text += " (Your faction owns this!)"
            embed.add_field(name="Controlled By", value=ownership_text, inline=False)
            
            # Show upgrades if owned
            upgrades = self.db.execute_query(
                "SELECT upgrade_type, upgrade_level FROM location_upgrades WHERE location_id = ?",
                (location_id,),
                fetch='all'
            )
            
            if upgrades:
                upgrade_text = []
                for upgrade_type, level in upgrades:
                    upgrade_info = self.upgrade_types.get(upgrade_type, {})
                    upgrade_name = upgrade_info.get('name', upgrade_type.title())
                    upgrade_text.append(f"• {upgrade_name}: Level {level}")
                
                embed.add_field(name="Upgrades", value="\n".join(upgrade_text), inline=False)
        
        else:  # All non-owned locations can be purchased (except loyalist/outlaw)
            # Show purchase option
            purchase_price = self.calculate_purchase_price((location_id, name, location_type, wealth_level, population, is_derelict))
            if purchase_price:
                status = "Derelict - Available for Claiming" if is_derelict else "Available for Purchase"
                embed.add_field(
                    name="Availability", 
                    value=f"**{status}**\nPrice: {purchase_price:,} credits", 
                    inline=False
                )
            # Show purchase option
            purchase_price = self.calculate_purchase_price((location_id, name, location_type, wealth_level, population, is_derelict))
            if purchase_price:
                status = "Derelict - Available for Claiming" if is_derelict else "Economically Distressed - Available for Purchase"
                embed.add_field(
                    name="Availability", 
                    value=f"**{status}**\nPrice: {purchase_price:,} credits", 
                    inline=False
                )
        
        # Add view with action buttons if applicable
        view = LocationOwnershipView(self.bot, interaction.user.id, location_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @location_group.command(name="set_docking_fee", description="Set docking fee for non-members at faction locations")
    @app_commands.describe(fee="Docking fee amount (0-10000)")
    async def set_docking_fee(self, interaction: discord.Interaction, fee: int):
        if fee < 0 or fee > 10000:
            return await interaction.response.send_message("Fee must be between 0-10,000 credits!", ephemeral=True)
        
        # Get user's faction and current location
        data = self.db.execute_query(
            '''SELECT c.current_location, fm.faction_id, f.leader_id, f.name, lo.ownership_id
               FROM characters c
               LEFT JOIN faction_members fm ON c.user_id = fm.user_id
               LEFT JOIN factions f ON fm.faction_id = f.faction_id
               LEFT JOIN location_ownership lo ON c.current_location = lo.location_id AND lo.faction_id = f.faction_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not data:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        
        location_id, faction_id, leader_id, faction_name, ownership_id = data
        
        if not faction_id:
            return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
        
        if leader_id != interaction.user.id:
            return await interaction.response.send_message("Only faction leaders can set docking fees!", ephemeral=True)
        
        if not ownership_id:
            return await interaction.response.send_message("Your faction doesn't own this location!", ephemeral=True)
        
        # Update or insert docking fee
        self.db.execute_query(
            "UPDATE location_ownership SET docking_fee = ? WHERE ownership_id = ?",
            (fee, ownership_id)
        )
        
        embed = discord.Embed(
            title="💰 Docking Fee Updated",
            description=f"Non-members will now pay **{fee:,} credits** to dock at this location",
            color=0x00ff00
        )
        if fee > 0:
            embed.add_field(
                name="Effect",
                value=f"All non-faction members arriving here must pay the fee, with profits going to {faction_name}'s bank",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @location_group.command(name="purchase", description="Purchase or claim the current location")
    async def purchase_location(self, interaction: discord.Interaction):
        # Get character data
        char_data = self.db.execute_query(
            '''SELECT c.current_location, c.money, fm.faction_id, f.name as faction_name, 
                      f.emoji, f.leader_id, f.bank_balance
               FROM characters c
               LEFT JOIN faction_members fm ON c.user_id = fm.user_id
               LEFT JOIN factions f ON fm.faction_id = f.faction_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        
        location_id, money, faction_id, faction_name, faction_emoji, leader_id, faction_bank = char_data
        
        # Check faction membership
        if not faction_id:
            # Show faction creation prompt
            embed = discord.Embed(
                title="🏛️ Faction Required",
                description="You must create or join a faction before purchasing locations!",
                color=0xff6b6b
            )
            embed.add_field(
                name="Create a Faction",
                value="Use `/faction create` to establish your own faction",
                inline=False
            )
            embed.add_field(
                name="Join a Faction", 
                value="Use `/faction join` if you have an invitation or there are public factions nearby",
                inline=False
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Check if user is faction leader
        if leader_id != interaction.user.id:
            return await interaction.response.send_message(
                f"Only the faction leader can purchase locations! Ask your leader to buy this location for {faction_name}.",
                ephemeral=True
            )
        
        # Get location data
        location_data = self.db.execute_query(
            '''SELECT l.location_type, l.name, l.wealth_level, l.population, l.is_derelict
               FROM locations l
               WHERE l.location_id = ?''',
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            return await interaction.response.send_message("Location not found!", ephemeral=True)
        
        location_type, name, wealth_level, population, is_derelict = location_data
        
        # Check if already owned
        existing_owner = self.db.execute_query(
            "SELECT faction_id, owner_id FROM location_ownership WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if existing_owner:
            return await interaction.response.send_message("This location is already owned!", ephemeral=True)
        
        # Check if location is purchasable (exclude loyalist/outlaw)
        if location_type in ['loyalist', 'outlaw']:
            return await interaction.response.send_message("This location type cannot be purchased!", ephemeral=True)
        
        # Calculate purchase price
        purchase_price = self.calculate_purchase_price((location_id, name, location_type, wealth_level, population, is_derelict))
        if not purchase_price:
            return await interaction.response.send_message("This location is not available for purchase.", ephemeral=True)
        
        # Check if can afford (personal + faction bank)
        total_available = money + (faction_bank or 0)
        if total_available < purchase_price:
            return await interaction.response.send_message(
                f"Insufficient funds! Need {purchase_price:,} credits.\n"
                f"Personal: {money:,} | Faction Bank: {faction_bank or 0:,} | Total: {total_available:,}",
                ephemeral=True
            )
        
        # Show purchase confirmation
        embed = discord.Embed(
            title=f"{faction_emoji} Purchase Location: {name}",
            description=f"Buy this location for **{faction_name}**?",
            color=0x00ff00
        )
        embed.add_field(name="Location Type", value=location_type.replace('_', ' ').title(), inline=True)
        embed.add_field(name="Wealth Level", value=f"{wealth_level}/10", inline=True)
        embed.add_field(name="Population", value=f"{population:,}", inline=True)
        embed.add_field(name="Purchase Price", value=f"{purchase_price:,} credits", inline=True)
        embed.add_field(name="Your Balance", value=f"{money:,} credits", inline=True)
        embed.add_field(name="Faction Bank", value=f"{faction_bank or 0:,} credits", inline=True)
        
        view = FactionPurchaseConfirmView(self.bot, interaction.user.id, location_id, faction_id, purchase_price)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    #@location_group.command(name="rename", description="Rename a location owned by your faction")
    #@app_commands.describe(new_name="New name for the location")
    #async def rename_location(self, interaction: discord.Interaction, new_name: str):
    #    if len(new_name) < 3 or len(new_name) > 50:
    #        return await interaction.response.send_message("Name must be 3-50 characters!", ephemeral=True)
    #    
    #    # Get user's faction and current location
    #    data = self.db.execute_query(
    #        '''SELECT c.current_location, fm.faction_id, f.leader_id, lo.ownership_id
    #           FROM characters c
    #           LEFT JOIN faction_members fm ON c.user_id = fm.user_id
    #           LEFT JOIN factions f ON fm.faction_id = f.faction_id
    #           LEFT JOIN location_ownership lo ON c.current_location = lo.location_id AND lo.faction_id = f.faction_id
    #           WHERE c.user_id = ?''',
    #        (interaction.user.id,),
    #        fetch='one'
     #   )
    #    
    #    if not data:
    #        return await interaction.response.send_message("Character not found!", ephemeral=True)
    #    
    #    location_id, faction_id, leader_id, ownership_id = data
   #     
    #    if not faction_id:
    #        return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
    #    
     #   if leader_id != interaction.user.id:
    #        return await interaction.response.send_message("Only faction leaders can rename locations!", ephemeral=True)
    #    
    #    if not ownership_id:
    #        return await interaction.response.send_message("Your faction doesn't own this location!", ephemeral=True)
    #    
    #    # Update the custom name
    #    self.db.execute_query(
    #        "UPDATE location_ownership SET custom_name = ? WHERE ownership_id = ?",
    #        (new_name, ownership_id)
    #    )
    #    
    #    await interaction.response.send_message(f"Location renamed to **{new_name}**!", ephemeral=True)
    
    @location_group.command(name="set_sales_tax", description="Set sales tax for shops at faction locations")
    @app_commands.describe(percentage="Tax percentage (0-25)")
    async def set_sales_tax(self, interaction: discord.Interaction, percentage: int):
        if percentage < 0 or percentage > 25:
            return await interaction.response.send_message("Tax must be between 0-25%!", ephemeral=True)
        
        # Get user's faction and current location
        data = self.db.execute_query(
            '''SELECT c.current_location, fm.faction_id, f.leader_id, f.name, lo.ownership_id
               FROM characters c
               LEFT JOIN faction_members fm ON c.user_id = fm.user_id
               LEFT JOIN factions f ON fm.faction_id = f.faction_id
               LEFT JOIN location_ownership lo ON c.current_location = lo.location_id AND lo.faction_id = f.faction_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not data:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        
        location_id, faction_id, leader_id, faction_name, ownership_id = data
        
        if not faction_id:
            return await interaction.response.send_message("You're not in a faction!", ephemeral=True)
        
        if leader_id != interaction.user.id:
            return await interaction.response.send_message("Only faction leaders can set sales tax!", ephemeral=True)
        
        if not ownership_id:
            return await interaction.response.send_message("Your faction doesn't own this location!", ephemeral=True)
        
        # Update or insert tax rate
        existing = self.db.execute_query(
            "SELECT tax_id FROM faction_sales_tax WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if existing:
            self.db.execute_query(
                "UPDATE faction_sales_tax SET tax_percentage = ? WHERE location_id = ?",
                (percentage, location_id)
            )
        else:
            self.db.execute_query(
                "INSERT INTO faction_sales_tax (faction_id, location_id, tax_percentage) VALUES (?, ?, ?)",
                (faction_id, location_id, percentage)
            )
        
        embed = discord.Embed(
            title="💰 Sales Tax Updated",
            description=f"Sales tax at this location is now **{percentage}%**",
            color=0x00ff00
        )
        if percentage > 0:
            embed.add_field(
                name="Effect",
                value=f"All shop items will cost {percentage}% more, with profits going to {faction_name}'s bank",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    
    
    @location_group.command(name="upgrade", description="Upgrade one of your owned locations")
    async def upgrade_location(self, interaction: discord.Interaction):
        # Get user's owned locations
        owned_locations = self.db.execute_query(
            '''SELECT lo.location_id, l.name, l.location_type
               FROM location_ownership lo
               JOIN locations l ON lo.location_id = l.location_id
               WHERE lo.owner_id = ?''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not owned_locations:
            return await interaction.response.send_message("You don't own any locations!", ephemeral=True)
        
        # If user owns only one location, go directly to upgrades
        if len(owned_locations) == 1:
            location_id = owned_locations[0][0]
            await self._show_upgrade_options(interaction, location_id)
        else:
            # Show location selection
            view = LocationSelectionView(self.bot, interaction.user.id, owned_locations, "upgrade")
            embed = discord.Embed(
                title="Select Location to Upgrade",
                description="Choose which location you want to upgrade:",
                color=0x4169E1
            )
            
            for location_id, name, location_type in owned_locations:
                embed.add_field(
                    name=f"{name} ({location_type.replace('_', ' ').title()})",
                    value=f"ID: {location_id}",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_upgrade_options(self, interaction: discord.Interaction, location_id: int):
        """Show available upgrades for a location"""
        # Get current upgrades
        current_upgrades = {}
        upgrades = self.db.execute_query(
            "SELECT upgrade_type, upgrade_level FROM location_upgrades WHERE location_id = ?",
            (location_id,),
            fetch='all'
        )
        
        for upgrade_type, level in upgrades:
            current_upgrades[upgrade_type] = level
        
        # Get location info
        location_info = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        location_name = location_info[0] if location_info else "Unknown"
        
        embed = discord.Embed(
            title=f"Upgrade Options: {location_name}",
            description="Select an upgrade type:",
            color=0x00ff00
        )
        
        # Show available upgrades
        for upgrade_type, upgrade_info in self.upgrade_types.items():
            current_level = current_upgrades.get(upgrade_type, 0)
            max_level = upgrade_info['max_level']
            
            if current_level < max_level:
                next_level = current_level + 1
                cost = upgrade_info['base_cost'] * next_level
                
                embed.add_field(
                    name=f"{upgrade_info['name']} (Level {current_level} → {next_level})",
                    value=f"{upgrade_info['description']}\nCost: {cost:,} credits",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"{upgrade_info['name']} (MAX LEVEL)",
                    value=f"{upgrade_info['description']}\nMaxed out at level {max_level}",
                    inline=False
                )
        
        view = UpgradeSelectionView(self.bot, interaction.user.id, location_id, current_upgrades)
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class LocationOwnershipView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        # Check if user owns this location
        ownership = self.bot.db.execute_query(
            "SELECT owner_id FROM location_ownership WHERE location_id = ? AND owner_id = ?",
            (location_id, user_id),
            fetch='one'
        )
        
        # Check if location is purchasable
        location_data = self.bot.db.execute_query(
            "SELECT location_type, wealth_level, is_derelict FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        is_owned_by_user = bool(ownership)
        is_purchasable = False
        
        if location_data and not ownership:
            location_type, wealth_level, is_derelict = location_data
            is_purchasable = is_derelict or wealth_level <= 3
        
        # Add appropriate buttons
        if is_owned_by_user:
            self.add_item(UpgradeLocationButton())
            self.add_item(ManageLocationButton())
            self.add_item(CollectIncomeButton())
        elif is_purchasable:
            self.add_item(PurchaseLocationButton())

class PurchaseLocationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Purchase/Claim", style=discord.ButtonStyle.green, emoji="💰")
    
    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog('LocationOwnershipCog')
        if cog:
            await cog.purchase_location.callback(cog, interaction)

class UpgradeLocationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Upgrade", style=discord.ButtonStyle.primary, emoji="⬆️")
    
    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog('LocationOwnershipCog')
        if cog:
            await cog._show_upgrade_options(interaction, self.view.location_id)

class ManageLocationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Manage", style=discord.ButtonStyle.secondary, emoji="⚙️")
    
    async def callback(self, interaction: discord.Interaction):
        # Implementation for location management (access control, fees, etc.)
        await interaction.response.send_message("Location management coming soon!", ephemeral=True)

class CollectIncomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Collect Income", style=discord.ButtonStyle.success, emoji="💵")
    
    async def callback(self, interaction: discord.Interaction):
        # Check for uncollected income
        uncollected = self.view.bot.db.execute_query(
            "SELECT SUM(amount) FROM location_income_log WHERE location_id = ? AND collected = 0",
            (self.view.location_id,),
            fetch='one'
        )
        
        total_income = uncollected[0] if uncollected and uncollected[0] else 0
        
        if total_income <= 0:
            await interaction.response.send_message("No income to collect.", ephemeral=True)
            return
        
        # Collect income
        self.view.bot.db.execute_query(
            "UPDATE location_income_log SET collected = 1 WHERE location_id = ? AND collected = 0",
            (self.view.location_id,)
        )
        
        # Add money to player
        self.view.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (total_income, self.view.user_id)
        )
        
        await interaction.response.send_message(f"💰 Collected {total_income:,} credits in income!", ephemeral=True)

class PurchaseConfirmationView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, price: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.price = price
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your transaction!", ephemeral=True)
        
        # Double-check funds
        money = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.user_id,),
            fetch='one'
        )
        
        if not money or money[0] < self.price:
            return await interaction.response.send_message("Insufficient funds!", ephemeral=True)
        
        # Complete purchase
        try:
            # Deduct money
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (self.price, self.user_id)
            )
            
            # Create ownership record
            upkeep_due = datetime.now() + timedelta(days=30)
            self.bot.db.execute_query(
                '''INSERT INTO location_ownership 
                   (location_id, owner_id, purchase_price, upkeep_due_date, total_invested)
                   VALUES (?, ?, ?, ?, ?)''',
                (self.location_id, self.user_id, self.price, upkeep_due, self.price)
            )
            
            # Update location status
            self.bot.db.execute_query(
                "UPDATE locations SET is_derelict = 0 WHERE location_id = ?",
                (self.location_id,)
            )
            
            location_name = self.bot.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (self.location_id,),
                fetch='one'
            )[0]
            
            embed = discord.Embed(
                title="🎉 Purchase Successful!",
                description=f"You now own **{location_name}**!",
                color=0x00ff00
            )
            embed.add_field(name="Amount Paid", value=f"{self.price:,} credits", inline=True)
            embed.add_field(name="Next Upkeep Due", value=upkeep_due.strftime("%Y-%m-%d"), inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Purchase failed: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your transaction!", ephemeral=True)
        
        await interaction.response.send_message("Purchase cancelled.", ephemeral=True)

class LocationSelectionView(discord.ui.View):
    def __init__(self, bot, user_id: int, locations: List, action: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.action = action
        
        # Add buttons for each location
        for i, (location_id, name, location_type) in enumerate(locations[:5]):  # Limit to 5
            button = LocationSelectButton(location_id, name, i)
            self.add_item(button)

class LocationSelectButton(discord.ui.Button):
    def __init__(self, location_id: int, name: str, row: int):
        super().__init__(label=name[:80], style=discord.ButtonStyle.primary, row=row)
        self.location_id = location_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            return await interaction.response.send_message("This is not your panel!", ephemeral=True)
        
        cog = interaction.client.get_cog('LocationOwnershipCog')
        if cog and self.view.action == "upgrade":
            await cog._show_upgrade_options(interaction, self.location_id)

class UpgradeSelectionView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, current_upgrades: Dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.current_upgrades = current_upgrades
        
        # Add upgrade buttons
        cog = bot.get_cog('LocationOwnershipCog')
        if cog:
            for upgrade_type, upgrade_info in cog.upgrade_types.items():
                current_level = current_upgrades.get(upgrade_type, 0)
                if current_level < upgrade_info['max_level']:
                    button = UpgradeButton(upgrade_type, upgrade_info, current_level)
                    self.add_item(button)

class UpgradeButton(discord.ui.Button):
    def __init__(self, upgrade_type: str, upgrade_info: Dict, current_level: int):
        next_level = current_level + 1
        cost = upgrade_info['base_cost'] * next_level
        
        super().__init__(
            label=f"{upgrade_info['name']} (Lv{next_level}) - {cost:,}",
            style=discord.ButtonStyle.secondary
        )
        
        self.upgrade_type = upgrade_type
        self.upgrade_info = upgrade_info
        self.current_level = current_level
        self.cost = cost
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            return await interaction.response.send_message("This is not your panel!", ephemeral=True)
        
        # Check if user can afford upgrade
        money = self.view.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (self.view.user_id,),
            fetch='one'
        )
        
        if not money or money[0] < self.cost:
            return await interaction.response.send_message(f"Insufficient funds! You need {self.cost:,} credits.", ephemeral=True)
        
        # Perform upgrade
        try:
            # Deduct money
            self.view.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
                (self.cost, self.view.user_id)
            )
            
            # Add or update upgrade
            existing = self.view.bot.db.execute_query(
                "SELECT upgrade_level FROM location_upgrades WHERE location_id = ? AND upgrade_type = ?",
                (self.view.location_id, self.upgrade_type),
                fetch='one'
            )
            
            new_level = self.current_level + 1
            
            if existing:
                self.view.bot.db.execute_query(
                    "UPDATE location_upgrades SET upgrade_level = ?, cost = cost + ? WHERE location_id = ? AND upgrade_type = ?",
                    (new_level, self.cost, self.view.location_id, self.upgrade_type)
                )
            else:
                self.view.bot.db.execute_query(
                    '''INSERT INTO location_upgrades (location_id, upgrade_type, upgrade_level, cost, description)
                       VALUES (?, ?, ?, ?, ?)''',
                    (self.view.location_id, self.upgrade_type, new_level, self.cost, self.upgrade_info['description'])
                )
            
            # Update total invested
            self.view.bot.db.execute_query(
                "UPDATE location_ownership SET total_invested = total_invested + ? WHERE location_id = ?",
                (self.cost, self.view.location_id)
            )
            
            # Apply upgrade effects
            await self._apply_upgrade_effects(interaction, new_level)
            
            embed = discord.Embed(
                title="✅ Upgrade Complete!",
                description=f"**{self.upgrade_info['name']}** upgraded to level {new_level}",
                color=0x00ff00
            )
            embed.add_field(name="Cost", value=f"{self.cost:,} credits", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Upgrade failed: {str(e)}", ephemeral=True)
    
    async def _apply_upgrade_effects(self, interaction: discord.Interaction, new_level: int):
        """Apply the effects of the upgrade to the location"""
        if self.upgrade_type == 'wealth':
            # Increase wealth level
            self.view.bot.db.execute_query(
                "UPDATE locations SET wealth_level = LEAST(wealth_level + 1, 10) WHERE location_id = ?",
                (self.view.location_id,)
            )
        
        elif self.upgrade_type == 'population':
            # Increase population
            increase = new_level * 50
            self.view.bot.db.execute_query(
                "UPDATE locations SET population = population + ? WHERE location_id = ?",
                (increase, self.view.location_id)
            )
        
        elif self.upgrade_type == 'services':
            # Enable services based on level
            if new_level >= 2:
                self.view.bot.db.execute_query(
                    "UPDATE locations SET has_medical = 1 WHERE location_id = ?",
                    (self.view.location_id,)
                )
            if new_level >= 3:
                self.view.bot.db.execute_query(
                    "UPDATE locations SET has_repairs = 1, has_upgrades = 1 WHERE location_id = ?",
                    (self.view.location_id,)
                )

async def setup(bot):
    await bot.add_cog(LocationOwnershipCog(bot))
    
    
    