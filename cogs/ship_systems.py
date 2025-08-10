# cogs/ship_systems.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from datetime import datetime, timedelta

class ShipSystemsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
    ship_group = app_commands.Group(name="ship", description="Ship management commands")
    
    @ship_group.command(name="purchase", description="Open the ship purchase interface")
    async def ship_purchase(self, interaction: discord.Interaction):
        """Enhanced ship purchase system with categories and detailed specs"""
        # Get character location and wealth info
        char_info = self.db.execute_query(
            '''SELECT c.current_location, c.money, l.has_shipyard, l.wealth_level, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, money, has_shipyard, wealth_level, location_name = char_info
        
        if not has_shipyard:
            await interaction.response.send_message(f"{location_name} doesn't have a shipyard.", ephemeral=True)
            return
        
        # Get current ship count for fleet management
        ship_count = self.db.execute_query(
            "SELECT COUNT(*) FROM player_ships WHERE owner_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Get active ship for trade-in options
        active_ship = self.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.condition_rating, s.market_value
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = %s AND ps.is_active = true''',
            (interaction.user.id,),
            fetch='one'
        )
        
        # Create ship browser view
        view = ShipBrowserView(self.bot, interaction.user.id, money, wealth_level, location_name, active_ship, ship_count, current_location)
        
        embed = discord.Embed(
            title=f"🚢 {location_name} Shipyard",
            description="Browse available ships by category or view special offers",
            color=0x2F4F4F
        )
        
        embed.add_field(name="💰 Your Credits", value=f"{money:,}", inline=True)
        embed.add_field(name="🏭 Shipyard Tier", value=f"Level {min(wealth_level//2 + 1, 5)}", inline=True)
        embed.add_field(name="📦 Fleet Size", value=f"{ship_count}/5 ships", inline=True)
        
        if active_ship:
            embed.add_field(
                name="🔄 Trade-in Available", 
                value=f"**{active_ship[1]}** - Est. value: {active_ship[4]:,} credits",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @ship_group.command(name="refresh_inventory", description="[Admin] Manually refresh shipyard inventory")
    async def refresh_shipyard_inventory(self, interaction: discord.Interaction, location_id: int = None):
        """Admin command to manually refresh shipyard inventory"""
        # Basic admin check - you might want to implement proper admin checking
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("This command requires administrator permissions.", ephemeral=True)
            return
        
        if location_id is None:
            # Get current location if not specified
            char_info = self.bot.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            if not char_info:
                await interaction.response.send_message("Character not found or location_id not specified!", ephemeral=True)
                return
            location_id = char_info[0]
        
        # Check if location has shipyard
        location_info = self.bot.db.execute_query(
            "SELECT name, has_shipyard, wealth_level FROM locations WHERE location_id = %s",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message(f"Location {location_id} not found!", ephemeral=True)
            return
            
        location_name, has_shipyard, wealth_level = location_info
        
        if not has_shipyard:
            await interaction.response.send_message(f"{location_name} doesn't have a shipyard!", ephemeral=True)
            return
        
        # Create a temporary browser view to access the refresh method
        temp_view = ShipBrowserView(self.bot, interaction.user.id, 0, wealth_level, location_name, None, 0, location_id)
        temp_view._refresh_shipyard_inventory()
        
        await interaction.response.send_message(
            f"✅ Shipyard inventory refreshed for {location_name}!",
            ephemeral=True
        )
    
    @ship_group.command(name="upgrade", description="Access comprehensive ship upgrade systems")
    async def ship_upgrade(self, interaction: discord.Interaction):
        """Enhanced upgrade system with components and modifications"""
        # Get character and ship info
        char_info = self.db.execute_query(
            '''SELECT c.current_location, c.money, l.has_upgrades, l.wealth_level, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, money, has_upgrades, wealth_level, location_name = char_info
        
        if not has_upgrades:
            await interaction.response.send_message(f"{location_name} doesn't offer upgrade services.", ephemeral=True)
            return
        
        # Get active ship with detailed specs
        ship_info = self.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.tier, s.condition_rating,
                      s.engine_level, s.hull_level, s.systems_level, s.special_mods,
                      s.max_upgrade_slots, s.used_upgrade_slots
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = %s AND ps.is_active = true''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("You need an active ship to upgrade!", ephemeral=True)
            return
        
        # Create upgrade workshop view
        view = UpgradeWorkshopView(self.bot, interaction.user.id, ship_info, money, wealth_level)
        
        embed = discord.Embed(
            title=f"🔧 {location_name} Upgrade Workshop",
            description=f"Enhance your **{ship_info[1]}** ({ship_info[2]})",
            color=0x4169e1
        )
        
        # Ship condition affects upgrade prices
        condition_modifier = ship_info[4] / 100  # 0.0 to 1.0
        
        embed.add_field(name="⚡ Engine", value=f"Level {ship_info[5]}/5", inline=True)
        embed.add_field(name="🛡️ Hull", value=f"Level {ship_info[6]}/5", inline=True)
        embed.add_field(name="💻 Systems", value=f"Level {ship_info[7]}/5", inline=True)
        
        embed.add_field(name="🔧 Condition", value=f"{ship_info[4]}%", inline=True)
        embed.add_field(name="📦 Mod Slots", value=f"{ship_info[10]}/{ship_info[9]}", inline=True)
        embed.add_field(name="💰 Credits", value=f"{money:,}", inline=True)
        
        if ship_info[8]:  # Special mods
            mods = json.loads(ship_info[8])
            embed.add_field(
                name="✨ Special Modifications",
                value="\n".join([f"• {mod}" for mod in mods[:5]]),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @ship_group.command(name="shipyard", description="Access the complete shipyard management interface")
    async def shipyard(self, interaction: discord.Interaction):
        """Main shipyard hub for all ship-related activities"""
        # Get location and character info
        location_info = self.db.execute_query(
            '''SELECT l.location_id, l.name, l.has_shipyard, l.has_upgrades, l.wealth_level, c.money
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message("Location not found!", ephemeral=True)
            return
        
        location_id, location_name, has_shipyard, has_upgrades, wealth_level, money = location_info
        
        if not has_shipyard:
            await interaction.response.send_message(f"{location_name} doesn't have a shipyard.", ephemeral=True)
            return
        
        # Get fleet overview
        fleet = self.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.tier, s.condition_rating, 
                      ps.is_active, s.market_value
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = %s
               ORDER BY ps.is_active DESC, ps.acquired_date DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        view = ShipyardHubView(self.bot, interaction.user.id, wealth_level, money, fleet, has_upgrades)
        
        embed = discord.Embed(
            title=f"🏗️ {location_name} Shipyard Hub",
            description="Complete ship management and services",
            color=0x2F4F4F
        )
        
        # Fleet summary
        if fleet:
            active_ship = next((s for s in fleet if s[5]), None)
            if active_ship:
                embed.add_field(
                    name="🚀 Active Ship",
                    value=f"**{active_ship[1]}** - {active_ship[2]} (Tier {active_ship[3]})\nCondition: {active_ship[4]}%",
                    inline=False
                )
            
            embed.add_field(name="📦 Fleet Size", value=f"{len(fleet)}/5 ships", inline=True)
            total_value = sum(s[6] for s in fleet)
            embed.add_field(name="💎 Fleet Value", value=f"{total_value:,} credits", inline=True)
        else:
            embed.add_field(name="⚠️ No Ships", value="Visit the shop to purchase your first ship!", inline=False)
        
        embed.add_field(name="💰 Credits", value=f"{money:,}", inline=True)
        
        # Available services based on wealth level
        services = ["🛒 Ship Shop", "🔧 Upgrades", "🎨 Customization"]
        if wealth_level >= 5:
            services.append("🔄 Ship Exchange")
        if wealth_level >= 7:
            services.append("⚡ Advanced Mods")
        
        embed.add_field(
            name="📋 Available Services",
            value="\n".join(services),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ShipBrowserView(discord.ui.View):
    """Enhanced ship browsing with categories and filters"""
    def __init__(self, bot, user_id: int, money: int, wealth_level: int, location_name: str, active_ship, ship_count: int, location_id: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.money = money
        self.wealth_level = wealth_level
        self.location_name = location_name
        self.active_ship = active_ship
        self.ship_count = ship_count
        self.location_id = location_id
        self.current_category = "all"
        self.show_affordable_only = False
        
    @discord.ui.select(
        placeholder="Select ship category...",
        options=[
            discord.SelectOption(label="All Ships", value="all", emoji="🚢"),
            discord.SelectOption(label="Cargo Vessels", value="cargo", emoji="📦"),
            discord.SelectOption(label="Fast Ships", value="speed", emoji="💨"),
            discord.SelectOption(label="Combat Ready", value="combat", emoji="⚔️"),
            discord.SelectOption(label="Exploration", value="explore", emoji="🔭"),
            discord.SelectOption(label="Luxury", value="luxury", emoji="💎"),
            discord.SelectOption(label="Special Offers", value="special", emoji="⭐")
        ]
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_category = select.values[0]
        await self.show_ships(interaction)
    
    @discord.ui.button(label="Affordable Only", style=discord.ButtonStyle.secondary, emoji="💰")
    async def toggle_affordable(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.show_affordable_only = not self.show_affordable_only
        button.style = discord.ButtonStyle.primary if self.show_affordable_only else discord.ButtonStyle.secondary
        await self.show_ships(interaction)
    
    @discord.ui.button(label="Trade-In Calculator", style=discord.ButtonStyle.success, emoji="🔄", row=2)
    async def trade_in_calc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active_ship:
            await interaction.response.send_message("You don't have an active ship to trade in!", ephemeral=True)
            return
        
        # Calculate trade-in value with condition modifier
        base_value = self.active_ship[4]  # market_value
        condition_modifier = self.active_ship[3] / 100  # condition_rating
        trade_value = int(base_value * condition_modifier * 0.7)  # 70% of adjusted value
        
        embed = discord.Embed(
            title="🔄 Trade-In Calculator",
            description=f"Trade in your **{self.active_ship[1]}** when purchasing a new ship",
            color=0x00ff00
        )
        
        embed.add_field(name="Ship Value", value=f"{base_value:,} credits", inline=True)
        embed.add_field(name="Condition", value=f"{self.active_ship[3]}%", inline=True)
        embed.add_field(name="Trade-In Value", value=f"{trade_value:,} credits", inline=True)
        
        embed.add_field(
            name="💡 Tip",
            value="Ships in better condition get higher trade-in values. Consider repairs before trading!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def show_ships(self, interaction: discord.Interaction):
        """Display ships based on current filters"""
        # Generate available ships
        ships = self._generate_filtered_ships()
        
        if self.show_affordable_only:
            # Include trade-in value if available
            trade_value = 0
            if self.active_ship:
                condition_modifier = self.active_ship[3] / 100
                trade_value = int(self.active_ship[4] * condition_modifier * 0.7)
            
            ships = [s for s in ships if s['price'] <= self.money + trade_value]
        
        embed = discord.Embed(
            title=f"🛒 Available Ships - {self.current_category.title()}",
            description=f"Ships available at {self.location_name}",
            color=0x00ff00
        )
        
        if not ships:
            embed.add_field(
                name="No Ships Available",
                value="No ships match your current filters. Try a different category!",
                inline=False
            )
        else:
            # Show up to 5 ships
            for ship in ships[:5]:
                value_parts = [
                    f"**Price:** {ship['price']:,} credits",
                    f"**Tier:** {ship['tier']} | **Class:** {ship['class']}"
                ]
                
                # Add key stats
                stats = []
                if ship['cargo_capacity'] > 100:
                    stats.append(f"📦 Cargo: {ship['cargo_capacity']}")
                if ship['speed_rating'] > 7:
                    stats.append(f"💨 Speed: {ship['speed_rating']}/10")
                if ship['combat_rating'] > 15:
                    stats.append(f"⚔️ Combat: {ship['combat_rating']}")
                
                if stats:
                    value_parts.append(" | ".join(stats))
                
                if ship.get('special_features'):
                    value_parts.append(f"✨ *{ship['special_features']}*")
                
                embed.add_field(
                    name=f"{ship['name']}",
                    value="\n".join(value_parts),
                    inline=False
                )
        
        # Add purchase instructions
        if ships:
            view = ShipPurchaseView(self.bot, self.user_id, ships, self.money, self.active_ship)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    def _generate_filtered_ships(self):
        """Get ships from persistent inventory, refreshing if needed"""
        import random
        from utils.ship_data import generate_random_ship_name
        
        # Check if inventory needs refreshing (random between 12-24 hours)
        refresh_hours = random.randint(12, 24)
        if self.bot.db.check_inventory_refresh_needed(self.location_id, refresh_hours):
            self._refresh_shipyard_inventory()
        
        # Get ships from inventory
        inventory_ships = self.bot.db.get_shipyard_inventory(self.location_id)
        
        # Convert to expected format and filter by category
        ships = []
        for inv_ship in inventory_ships:
            # Filter by category
            if self.current_category != "all":
                # Check if ship matches category
                categories = self._get_ship_categories(inv_ship['type'], inv_ship)
                if self.current_category not in categories:
                    continue
            
            # Convert to display format
            ship = {
                'inventory_id': inv_ship['inventory_id'],
                'name': inv_ship['name'],
                'type': inv_ship['type'],
                'class': inv_ship['class'],
                'tier': inv_ship['tier'],
                'price': inv_ship['price'],
                'cargo_capacity': inv_ship['cargo_capacity'],
                'speed_rating': inv_ship['speed_rating'],
                'combat_rating': inv_ship['combat_rating'],
                'fuel_efficiency': inv_ship['fuel_efficiency'],
                'special_features': inv_ship['special_features'],
                'is_player_sold': inv_ship['is_player_sold'],
                'condition_rating': inv_ship['condition_rating']
            }
            ships.append(ship)
        
        # Sort by player-sold first, then tier, then price
        ships.sort(key=lambda x: (not x['is_player_sold'], x['tier'], x['price']))
        
        return ships
    
    def _refresh_shipyard_inventory(self):
        """Refresh the shipyard inventory with new ships"""
        from utils.ship_data import generate_random_ship_name
        import random
        
        # Define ship templates by category
        templates = self._get_ship_templates()
        
        # Filter by shipyard tier
        tier_limit = min(self.wealth_level // 2 + 1, 5)
        available_templates = [t for t in templates if t['tier'] <= tier_limit]
        
        # Generate new ships from templates
        new_ships = []
        for template in available_templates:
            # Add some variation
            price_variance = random.randint(-15, 15) / 100
            ship = {
                'name': generate_random_ship_name(),
                'type': template['type'],
                'class': template['class'],
                'tier': template['tier'],
                'price': int(template['base_price'] * (1 + price_variance)),
                'cargo_capacity': template['cargo_capacity'] + random.randint(-10, 10),
                'speed_rating': template['speed_rating'],
                'combat_rating': template['combat_rating'],
                'fuel_efficiency': template['fuel_efficiency'],
                'special_features': template.get('special_features')
            }
            new_ships.append(ship)
        
        # Add special offers for high-tier shipyards
        if self.wealth_level >= 6:
            new_ships.extend(self._generate_special_offers())
        
        # Refresh inventory in database
        self.bot.db.refresh_shipyard_inventory(self.location_id, new_ships)
    
    def _get_ship_categories(self, ship_type: str, ship_data: dict) -> list:
        """Get categories that a ship belongs to"""
        categories = ['all']
        
        # Categorize by type
        cargo_types = ['Hauler', 'Heavy Hauler', 'Bulk Carrier', 'Mining Barge']
        speed_types = ['Scout', 'Fast Courier', 'Interceptor', 'Racing Ship']
        combat_types = ['Armed Trader', 'Frigate', 'Destroyer', 'Battleship']
        explore_types = ['Explorer', 'Research Vessel', 'Deep Space Scout']
        luxury_types = ['Luxury Yacht', 'Executive Transport', 'Ambassador']
        
        if ship_type in cargo_types or ship_data.get('cargo_capacity', 0) > 200:
            categories.append('cargo')
        if ship_type in speed_types or ship_data.get('speed_rating', 0) > 7:
            categories.append('speed')
        if ship_type in combat_types or ship_data.get('combat_rating', 0) > 15:
            categories.append('combat')
        if ship_type in explore_types:
            categories.append('explore')
        if ship_type in luxury_types or ship_data.get('tier', 1) >= 4:
            categories.append('luxury')
        if ship_data.get('is_player_sold', False):
            categories.append('special')
            
        return categories
    
    def _get_ship_templates(self):
        """Define ship templates with categories"""
        return [
            # Tier 1 - Basic Ships
            {
                'type': 'Hauler', 'class': 'Cargo', 'tier': 1,
                'base_price': 2500, 'cargo_capacity': 150, 'speed_rating': 4,
                'combat_rating': 5, 'fuel_efficiency': 7,
                'categories': ['all', 'cargo']
            },
            {
                'type': 'Scout', 'class': 'Recon', 'tier': 1,
                'base_price': 3000, 'cargo_capacity': 50, 'speed_rating': 8,
                'combat_rating': 8, 'fuel_efficiency': 9,
                'categories': ['all', 'speed', 'explore']
            },
            {
                'type': 'Shuttle', 'class': 'Transport', 'tier': 1,
                'base_price': 2000, 'cargo_capacity': 80, 'speed_rating': 6,
                'combat_rating': 3, 'fuel_efficiency': 8,
                'categories': ['all']
            },
            
            # Tier 2 - Improved Ships
            {
                'type': 'Heavy Hauler', 'class': 'Bulk Cargo', 'tier': 2,
                'base_price': 5500, 'cargo_capacity': 300, 'speed_rating': 3,
                'combat_rating': 10, 'fuel_efficiency': 5,
                'categories': ['all', 'cargo']
            },
            {
                'type': 'Fast Courier', 'class': 'Express', 'tier': 2,
                'base_price': 6000, 'cargo_capacity': 100, 'speed_rating': 9,
                'combat_rating': 12, 'fuel_efficiency': 7,
                'categories': ['all', 'speed']
            },
            
            # Tier 3 - Specialized Ships
            {
                'type': 'Armed Trader', 'class': 'Combat Merchant', 'tier': 3,
                'base_price': 8500, 'cargo_capacity': 200, 'speed_rating': 6,
                'combat_rating': 20, 'fuel_efficiency': 6,
                'categories': ['all', 'combat', 'cargo'],
                'special_features': 'Reinforced hull, weapon mounts'
            },
            {
                'type': 'Explorer', 'class': 'Long Range', 'tier': 3,
                'base_price': 9000, 'cargo_capacity': 120, 'speed_rating': 7,
                'combat_rating': 15, 'fuel_efficiency': 10,
                'categories': ['all', 'explore'],
                'special_features': 'Extended fuel tanks, advanced sensors'
            },
            
            # Tier 4 - Advanced Ships
            {
                'type': 'Blockade Runner', 'class': 'Stealth Cargo', 'tier': 4,
                'base_price': 15000, 'cargo_capacity': 180, 'speed_rating': 10,
                'combat_rating': 18, 'fuel_efficiency': 8,
                'categories': ['all', 'speed', 'cargo'],
                'special_features': 'Stealth coating, smuggler holds'
            },
            {
                'type': 'Corvette', 'class': 'Light Warship', 'tier': 4,
                'base_price': 18000, 'cargo_capacity': 100, 'speed_rating': 8,
                'combat_rating': 30, 'fuel_efficiency': 5,
                'categories': ['all', 'combat'],
                'special_features': 'Military-grade armor, advanced targeting'
            },
            
            # Tier 5 - Premium Ships
            {
                'type': 'Luxury Yacht', 'class': 'Executive', 'tier': 5,
                'base_price': 25000, 'cargo_capacity': 150, 'speed_rating': 7,
                'combat_rating': 12, 'fuel_efficiency': 6,
                'categories': ['all', 'luxury'],
                'special_features': 'Luxury accommodations, prestige bonus'
            },
            {
                'type': 'Research Vessel', 'class': 'Science', 'tier': 5,
                'base_price': 22000, 'cargo_capacity': 200, 'speed_rating': 5,
                'combat_rating': 10, 'fuel_efficiency': 8,
                'categories': ['all', 'explore'],
                'special_features': 'Laboratory, specialized scanners'
            }
        ]
    
    def _generate_special_offers(self):
        """Generate limited-time special offers"""
        from utils.ship_data import generate_random_ship_name
        
        specials = []
        
        # Refurbished military vessel
        if random.random() > 0.5:
            specials.append({
                'name': f"Ex-Military {generate_random_ship_name()}",
                'type': 'Patrol Craft',
                'class': 'Refurbished Military',
                'tier': 4,
                'price': 12000,  # Discounted
                'cargo_capacity': 120,
                'speed_rating': 8,
                'combat_rating': 25,
                'fuel_efficiency': 6,
                'special_features': '⚠️ Decommissioned weapons, military-grade hull'
            })
        
        # Salvaged alien tech
        if self.wealth_level >= 8 and random.random() > 0.7:
            specials.append({
                'name': f"Modified {generate_random_ship_name()}",
                'type': 'Hybrid Craft',
                'class': 'Experimental',
                'tier': 5,
                'price': 30000,
                'cargo_capacity': 180,
                'speed_rating': 9,
                'combat_rating': 22,
                'fuel_efficiency': 12,
                'special_features': '🛸 Alien drive system, unknown capabilities'
            })
        
        return specials


class ShipPurchaseView(discord.ui.View):
    """Handle ship purchase with options"""
    def __init__(self, bot, user_id: int, ships: list, money: int, active_ship):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ships = ships
        self.money = money
        self.active_ship = active_ship
        
        # Add ship selection dropdown
        options = []
        for i, ship in enumerate(ships[:25]):
            label = f"{ship['name']} - {ship['price']:,} cr"
            description = f"T{ship['tier']} {ship['class']}"
            if ship.get('special_features'):
                description = description[:40] + "..."
            
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(i)
                )
            )
        
        select = discord.ui.Select(placeholder="Choose a ship to purchase...", options=options)
        select.callback = self.ship_selected
        self.add_item(select)
    
    async def ship_selected(self, interaction: discord.Interaction):
        """Handle ship selection and show purchase options"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your purchase interface!", ephemeral=True)
            return
        
        ship_index = int(interaction.data['values'][0])
        selected_ship = self.ships[ship_index]
        
        # Show purchase confirmation with options
        embed = discord.Embed(
            title="🛒 Confirm Purchase",
            description=f"**{selected_ship['name']}**",
            color=0x00ff00
        )
        
        embed.add_field(name="Type", value=selected_ship['type'], inline=True)
        embed.add_field(name="Class", value=selected_ship['class'], inline=True)
        embed.add_field(name="Tier", value=selected_ship['tier'], inline=True)
        
        # Ship stats
        embed.add_field(name="📦 Cargo", value=selected_ship['cargo_capacity'], inline=True)
        embed.add_field(name="💨 Speed", value=f"{selected_ship['speed_rating']}/10", inline=True)
        embed.add_field(name="⚔️ Combat", value=selected_ship['combat_rating'], inline=True)
        
        if selected_ship.get('special_features'):
            embed.add_field(
                name="✨ Special Features",
                value=selected_ship['special_features'],
                inline=False
            )
        
        # Price breakdown
        base_price = selected_ship['price']
        trade_value = 0
        
        if self.active_ship:
            condition_modifier = self.active_ship[3] / 100
            trade_value = int(self.active_ship[4] * condition_modifier * 0.7)
        
        final_price = base_price - trade_value
        
        embed.add_field(name="Base Price", value=f"{base_price:,} credits", inline=True)
        if trade_value > 0:
            embed.add_field(name="Trade-In", value=f"-{trade_value:,} credits", inline=True)
        embed.add_field(name="Final Price", value=f"{final_price:,} credits", inline=True)
        
        # Check affordability
        can_afford = self.money >= final_price
        
        if not can_afford:
            embed.add_field(
                name="❌ Insufficient Funds",
                value=f"You need {final_price - self.money:,} more credits",
                inline=False
            )
        
        # Create confirmation view
        confirm_view = PurchaseConfirmView(
            self.bot, self.user_id, selected_ship, final_price, 
            trade_value > 0, can_afford
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class PurchaseConfirmView(discord.ui.View):
    """Confirm or cancel ship purchase"""
    def __init__(self, bot, user_id: int, ship_data: dict, final_price: int, has_trade: bool, can_afford: bool):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.ship_data = ship_data
        self.final_price = final_price
        self.has_trade = has_trade
        
        # Disable confirm if can't afford
        self.confirm_button.disabled = not can_afford
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your purchase!", ephemeral=True)
            return
        
        # Process the purchase
        await self._process_purchase(interaction)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your purchase!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Purchase cancelled.",
            embed=None,
            view=None
        )
    
    async def _process_purchase(self, interaction: discord.Interaction):
        """Process the ship purchase transaction"""
        from utils.ship_data import SHIP_DESCRIPTIONS
        from utils.ship_activities import ShipActivityManager
        import json
        
        # Start transaction
        conn = None
        try:
            # Begin database transaction
            conn = self.bot.db.begin_transaction()
            
            # Remove ship from shipyard inventory if it has inventory_id
            if 'inventory_id' in self.ship_data:
                self.bot.db.execute_in_transaction(
                    conn,
                    "DELETE FROM shipyard_inventory WHERE inventory_id = %s",
                    (self.ship_data['inventory_id'],)
                )
            
            # Deduct credits
            self.bot.db.execute_in_transaction(
                conn,
                "UPDATE characters SET money = money - %s WHERE user_id = %s",
                (self.final_price, self.user_id)
            )
            
            # Get descriptions
            ship_type = self.ship_data['type']
            if ship_type in SHIP_DESCRIPTIONS:
                exterior = random.choice(SHIP_DESCRIPTIONS[ship_type]["exterior"])
                interior = random.choice(SHIP_DESCRIPTIONS[ship_type]["interior"])
            else:
                exterior = f"A well-maintained {ship_type} with standard configuration"
                interior = f"The interior is equipped for {self.ship_data['class']} operations"
            
            # Calculate fuel capacity for the new ship
            fuel_capacity = 100 + (self.ship_data['tier'] * 20)
            
            # Create the ship with current_fuel initialized to fuel_capacity (full tank)
            new_ship_id = self.bot.db.execute_in_transaction(
                conn,
                '''INSERT INTO ships 
                   (owner_id, name, ship_type, tier, condition_rating,
                    fuel_capacity, cargo_capacity, combat_rating, fuel_efficiency,
                    exterior_description, interior_description,
                    engine_level, hull_level, systems_level,
                    max_upgrade_slots, market_value, special_mods, current_fuel)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING ship_id''',
                (self.user_id, self.ship_data['name'], ship_type, self.ship_data['tier'], 100,
                 fuel_capacity, self.ship_data['cargo_capacity'],
                 self.ship_data['combat_rating'], self.ship_data['fuel_efficiency'],
                 exterior, interior, 1, 1, 1, 3 + self.ship_data['tier'],
                 self.ship_data['price'], json.dumps([]), fuel_capacity),  # Initialize current_fuel to fuel_capacity
                fetch='one'
            )[0]
            
            # Add to player_ships
            self.bot.db.execute_in_transaction(
                conn,
                '''INSERT INTO player_ships (owner_id, ship_id, is_active)
                   VALUES (%s, %s, %s)''',
                (self.user_id, new_ship_id, 1 if not self.has_trade else 1)
            )
            
            # Update BOTH ship_id and active_ship_id to the new ship
            self.bot.db.execute_in_transaction(
                conn,
                "UPDATE characters SET ship_id = %s, active_ship_id = %s WHERE user_id = %s",
                (new_ship_id, new_ship_id, self.user_id)
            )
            
            # Handle trade-in if applicable
            if self.has_trade:
                # Get the old active ship ID BEFORE deactivating it
                old_active_ship = self.bot.db.execute_in_transaction(
                    conn,
                    "SELECT ship_id FROM player_ships WHERE owner_id = %s AND is_active = true AND ship_id != %s",
                    (self.user_id, new_ship_id),
                    fetch='one'
                )
                
                # Deactivate old ship
                self.bot.db.execute_in_transaction(
                    conn,
                    "UPDATE player_ships SET is_active = false WHERE owner_id = %s AND is_active = true AND ship_id != %s",
                    (self.user_id, new_ship_id)
                )
                
                # Remove old ship from player_ships and ships table (sold in trade)
                if old_active_ship:
                    self.bot.db.execute_in_transaction(
                        conn,
                        "DELETE FROM player_ships WHERE ship_id = %s",
                        (old_active_ship[0],)
                    )
                    self.bot.db.execute_in_transaction(
                        conn,
                        "DELETE FROM ships WHERE ship_id = %s",
                        (old_active_ship[0],)
                    )
            
            # Commit all changes
            self.bot.db.commit_transaction(conn)
            
            # Generate ship activities AFTER committing the transaction
            activity_manager = ShipActivityManager(self.bot)
            activity_manager.generate_ship_activities(new_ship_id, ship_type)
            
            # Success message
            embed = discord.Embed(
                title="✅ Purchase Complete!",
                description=f"Congratulations on your new ship!",
                color=0x00ff00
            )
            
            embed.add_field(name="Ship", value=self.ship_data['name'], inline=True)
            embed.add_field(name="Type", value=f"{self.ship_data['type']} ({self.ship_data['class']})", inline=True)
            embed.add_field(name="Credits Spent", value=f"{self.final_price:,}", inline=True)
            
            embed.add_field(
                name="🎉 Next Steps",
                value="• Use `/tqe` to view your new ship\n• Visit the upgrade workshop to enhance it\n• Check ship activities in your interior",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            # Rollback transaction if something went wrong
            if conn:
                try:
                    self.bot.db.rollback_transaction(conn)
                except:
                    pass  # Connection might already be closed
            
            await interaction.response.send_message(
                f"Error processing purchase: {str(e)}",
                ephemeral=True
            )

class UpgradeWorkshopView(discord.ui.View):
    """Comprehensive upgrade interface"""
    def __init__(self, bot, user_id: int, ship_info, money: int, wealth_level: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.ship_info = ship_info
        self.money = money
        self.wealth_level = wealth_level
    
    @discord.ui.button(label="Component Upgrades", style=discord.ButtonStyle.primary, emoji="⚡", row=0)
    async def component_upgrades(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Upgrade core ship components"""
        embed = discord.Embed(
            title="⚡ Component Upgrades",
            description="Upgrade your ship's core systems",
            color=0x4169e1
        )
        
        ship_id, name, ship_type, tier, condition, engine, hull, systems = self.ship_info[:8]
        
        # Calculate upgrade costs with condition modifier
        condition_mod = 1 + (1 - condition/100) * 0.5  # Poor condition = higher cost
        
        components = [
            {
                'name': 'Engine',
                'emoji': '⚡',
                'current': engine,
                'stat': 'Speed & Fuel Efficiency',
                'base_cost': 1000 * (engine + 1),
                'bonus': f"+{10 * (engine + 1)}% performance"
            },
            {
                'name': 'Hull',
                'emoji': '🛡️',
                'current': hull,
                'stat': 'Durability & Cargo',
                'base_cost': 1200 * (hull + 1),
                'bonus': f"+{15 * (hull + 1)} HP, +{5 * (hull + 1)}% cargo"
            },
            {
                'name': 'Systems',
                'emoji': '💻',
                'current': systems,
                'stat': 'Sensors & Navigation',
                'base_cost': 800 * (systems + 1),
                'bonus': f"+{(systems + 1) * 2} scan range, +{5 * (systems + 1)}% jump accuracy"
            }
        ]
        
        for comp in components:
            if comp['current'] < 5:
                cost = int(comp['base_cost'] * condition_mod)
                embed.add_field(
                    name=f"{comp['emoji']} {comp['name']} (Level {comp['current']}/5)",
                    value=f"**Upgrade to Level {comp['current'] + 1}:** {cost:,} credits\n"
                          f"*{comp['stat']}*\n"
                          f"Effect: {comp['bonus']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"{comp['emoji']} {comp['name']} (MAX)",
                    value="Fully upgraded!",
                    inline=False
                )
        
        view = ComponentUpgradeView(self.bot, self.user_id, self.ship_info, self.money, condition_mod)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Special Modifications", style=discord.ButtonStyle.secondary, emoji="✨", row=0)
    async def special_mods(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Install special modifications"""
        if self.wealth_level < 5:
            await interaction.response.send_message(
                "Special modifications require a Tier 3+ shipyard!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="✨ Special Modifications",
            description="Install unique upgrades to customize your ship",
            color=0xffd700
        )
        
        # Generate available mods based on ship type and tier
        available_mods = self._generate_special_mods()
        
        # Check current mods
        current_mods = json.loads(self.ship_info[8]) if self.ship_info[8] else []
        available_slots = self.ship_info[9] - self.ship_info[10]
        
        embed.add_field(
            name="📦 Modification Slots",
            value=f"{self.ship_info[10]}/{self.ship_info[9]} used",
            inline=False
        )
        
        if current_mods:
            embed.add_field(
                name="🔧 Installed Mods",
                value="\n".join([f"• {mod}" for mod in current_mods]),
                inline=False
            )
        
        if available_slots > 0:
            for mod in available_mods[:5]:
                if mod['name'] not in current_mods:
                    embed.add_field(
                        name=f"{mod['icon']} {mod['name']}",
                        value=f"**Cost:** {mod['cost']:,} credits\n"
                              f"*{mod['description']}*\n"
                              f"Effect: {mod['effect']}",
                        inline=False
                    )
        else:
            embed.add_field(
                name="❌ No Slots Available",
                value="Remove existing mods or upgrade your ship tier for more slots",
                inline=False
            )
        
        view = SpecialModView(self.bot, self.user_id, self.ship_info, available_mods, self.money, available_slots)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Maintenance & Repairs", style=discord.ButtonStyle.success, emoji="🔧", row=0)
    async def maintenance(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Ship maintenance and condition management"""
        condition = self.ship_info[4]
        
        embed = discord.Embed(
            title="🔧 Ship Maintenance",
            description=f"Keep your **{self.ship_info[1]}** in top condition",
            color=0x00ff00
        )
        
        embed.add_field(name="Current Condition", value=f"{condition}%", inline=True)
        
        # Condition affects everything
        status = "Excellent" if condition >= 90 else "Good" if condition >= 70 else "Fair" if condition >= 50 else "Poor"
        embed.add_field(name="Status", value=status, inline=True)
        
        # Repair costs
        if condition < 100:
            repair_cost = int((100 - condition) * 20 * (self.ship_info[3] + 1))  # Tier affects cost
            embed.add_field(
                name="🔧 Full Repair",
                value=f"Cost: {repair_cost:,} credits\nRestores condition to 100%",
                inline=False
            )
            
            # Partial repair options
            partial_amounts = [10, 25, 50]
            for amount in partial_amounts:
                if condition + amount <= 100:
                    cost = int(amount * 20 * (self.ship_info[3] + 1))
                    embed.add_field(
                        name=f"Repair +{amount}%",
                        value=f"{cost:,} credits",
                        inline=True
                    )
        
        # Maintenance tips
        embed.add_field(
            name="💡 Maintenance Tips",
            value="• Ships lose condition during combat and long journeys\n"
                  "• Poor condition increases upgrade costs\n"
                  "• Well-maintained ships have better trade-in value",
            inline=False
        )
        
        view = MaintenanceView(self.bot, self.user_id, self.ship_info[0], condition, self.money, self.ship_info[3])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Cosmetic Customization", style=discord.ButtonStyle.secondary, emoji="🎨", row=1)
    async def cosmetics(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Visual customization options"""
        embed = discord.Embed(
            title="🎨 Ship Customization",
            description="Personalize your ship's appearance",
            color=0xff69b4
        )
        
        # Current customizations
        current_custom = self.bot.db.execute_query(
            '''SELECT paint_job, decals, interior_style, name_plate
               FROM ship_customization
               WHERE ship_id = %s''',
            (self.ship_info[0],),
            fetch='one'
        )
        
        if current_custom:
            embed.add_field(
                name="Current Style",
                value=f"Paint: {current_custom[0] or 'Default'}\n"
                      f"Decals: {current_custom[1] or 'None'}\n"
                      f"Interior: {current_custom[2] or 'Standard'}",
                inline=False
            )
        
        # Available options
        options = [
            {
                'category': 'Paint Jobs',
                'icon': '🎨',
                'items': [
                    ('Midnight Black', 500),
                    ('Arctic White', 500),
                    ('Military Green', 750),
                    ('Racing Red', 1000),
                    ('Deep Space Blue', 1000),
                    ('Chrome Finish', 2000)
                ]
            },
            {
                'category': 'Decals',
                'icon': '🏷️',
                'items': [
                    ('Racing Stripes', 300),
                    ('Skull & Crossbones', 500),
                    ('Corporate Logo', 400),
                    ('Flame Pattern', 600),
                    ('Star Map', 800)
                ]
            },
            {
                'category': 'Interior Themes',
                'icon': '🛋️',
                'items': [
                    ('Minimalist', 1000),
                    ('Luxury', 2000),
                    ('Military Spec', 1500),
                    ('Retro-Future', 1800),
                    ('Alien-Inspired', 2500)
                ]
            }
        ]
        
        for opt in options:
            items_text = "\n".join([f"• {name}: {cost:,} cr" for name, cost in opt['items'][:3]])
            embed.add_field(
                name=f"{opt['icon']} {opt['category']}",
                value=items_text,
                inline=True
            )
        
        view = CosmeticView(self.bot, self.user_id, self.ship_info[0], self.money)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Apply Inventory Items", style=discord.ButtonStyle.primary, emoji="📦", row=1)
    async def apply_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Apply upgrade items from inventory"""
        # Get upgrade items from inventory
        items = self.bot.db.execute_query(
            '''SELECT i.item_id, i.item_name, i.quantity, i.metadata
               FROM inventory i
               WHERE i.owner_id = %s AND i.item_type = 'ship_upgrade'
               ORDER BY i.item_name''',
            (self.user_id,),
            fetch='all'
        )
        
        if not items:
            await interaction.response.send_message(
                "You don't have any ship upgrade items in your inventory!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📦 Apply Upgrade Items",
            description="Use items from your inventory to upgrade your ship",
            color=0x4169e1
        )
        
        for item_id, name, quantity, metadata in items[:10]:
            try:
                meta = json.loads(metadata) if metadata else {}
                upgrade_type = meta.get('upgrade_type', 'general')
                bonus = meta.get('bonus', 5)
                
                embed.add_field(
                    name=f"{name} (x{quantity})",
                    value=f"Type: {upgrade_type}\nBonus: +{bonus}",
                    inline=True
                )
            except:
                continue
        
        view = ItemApplicationView(self.bot, self.user_id, self.ship_info[0], items)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _generate_special_mods(self):
        """Generate available special modifications"""
        ship_type = self.ship_info[2]
        tier = self.ship_info[3]
        
        # Base mods available to all
        mods = [
            {
                'name': 'Smuggler Compartment',
                'icon': '📦',
                'cost': 5000,
                'description': 'Hidden cargo space undetectable by standard scans',
                'effect': '+20 stealth cargo capacity'
            },
            {
                'name': 'Emergency Booster',
                'icon': '🚀',
                'cost': 3000,
                'description': 'One-use speed boost for emergencies',
                'effect': '+50% speed for one jump'
            },
            {
                'name': 'Shield Generator',
                'icon': '🛡️',
                'cost': 8000,
                'description': 'Basic energy shielding system',
                'effect': '+20% damage reduction'
            }
        ]
        
        # Type-specific mods
        if 'Cargo' in ship_type or 'Hauler' in ship_type:
            mods.append({
                'name': 'Magnetic Clamps',
                'icon': '🧲',
                'cost': 4000,
                'description': 'External cargo attachment system',
                'effect': '+30% cargo capacity'
            })
        
        if 'Combat' in ship_type or 'Military' in ship_type:
            mods.append({
                'name': 'Targeting Computer',
                'icon': '🎯',
                'cost': 6000,
                'description': 'Advanced weapon targeting system',
                'effect': '+25% weapon accuracy'
            })
        
        if 'Fast' in ship_type or 'Scout' in ship_type:
            mods.append({
                'name': 'Afterburner Kit',
                'icon': '💨',
                'cost': 5500,
                'description': 'High-performance engine modification',
                'effect': '+2 speed rating'
            })
        
        # High-tier exclusive mods
        if tier >= 4:
            mods.append({
                'name': 'Cloaking Device',
                'icon': '🌑',
                'cost': 15000,
                'description': 'Basic stealth technology',
                'effect': 'Avoid 30% of random encounters'
            })
        
        return mods
    
    def _validate_ship_name(self, name: str) -> dict:
        """Validate ship name with various criteria"""
        # Basic length check
        if len(name) < 2:
            return {'valid': False, 'reason': 'Name must be at least 2 characters long'}
        
        if len(name) > 50:
            return {'valid': False, 'reason': 'Name cannot exceed 50 characters'}
        
        # Character validation - allow letters, numbers, spaces, and basic punctuation
        import re
        if not re.match(r'^[a-zA-Z0-9\s\'\-\.\_\(\)\[\]]+$', name):
            return {'valid': False, 'reason': 'Name contains invalid characters'}
        
        # Basic profanity filter (simple word list - in production would use a proper filter)
        profanity_words = ['fuck', 'shit', 'damn', 'hell', 'ass', 'bitch', 'bastard']  # Basic list
        name_lower = name.lower()
        for word in profanity_words:
            if word in name_lower:
                return {'valid': False, 'reason': 'Name contains inappropriate content'}
        
        # Prevent all caps (except for acronyms)
        if name.isupper() and len(name) > 5:
            return {'valid': False, 'reason': 'Name cannot be all capital letters'}
        
        # Prevent excessive whitespace
        if '  ' in name or name.startswith(' ') or name.endswith(' '):
            return {'valid': False, 'reason': 'Name has excessive whitespace'}
        
        return {'valid': True, 'reason': 'Valid name'}


class ComponentUpgradeView(discord.ui.View):
    """Handle component upgrade purchases"""
    def __init__(self, bot, user_id: int, ship_info, money: int, condition_mod: float):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_info = ship_info
        self.money = money
        self.condition_mod = condition_mod
        
        # Add upgrade buttons
        components = [
            ('Engine', '⚡', 5, 1000),
            ('Hull', '🛡️', 6, 1200),
            ('Systems', '💻', 7, 800)
        ]
        
        for name, emoji, index, base_cost in components:
            current_level = ship_info[index]
            if current_level < 5:
                cost = int(base_cost * (current_level + 1) * condition_mod)
                button = discord.ui.Button(
                    label=f"Upgrade {name} ({cost:,} cr)",
                    emoji=emoji,
                    style=discord.ButtonStyle.primary,
                    disabled=money < cost
                )
                button.callback = self._create_upgrade_callback(name.lower(), index, cost)
                self.add_item(button)
    
    def _create_upgrade_callback(self, component: str, index: int, cost: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your upgrade panel!", ephemeral=True)
                return
            
            # Process upgrade
            self.bot.db.execute_query(
                f"UPDATE ships SET {component}_level = {component}_level + 1 WHERE ship_id = %s",
                (self.ship_info[0],)
            )
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - %s WHERE user_id = %s",
                (cost, self.user_id)
            )
            
            await interaction.response.send_message(
                f"✅ {component.title()} upgraded to level {self.ship_info[index] + 1}!",
                ephemeral=True
            )
        
        return callback


class SpecialModView(discord.ui.View):
    """Handle special modification installation"""
    def __init__(self, bot, user_id: int, ship_info, mods: list, money: int, available_slots: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_info = ship_info
        self.mods = mods
        self.money = money
        
        if available_slots > 0:
            # Add mod selection
            current_mods = json.loads(ship_info[8]) if ship_info[8] else []
            
            options = []
            for mod in mods[:25]:
                if mod['name'] not in current_mods:
                    options.append(
                        discord.SelectOption(
                            label=f"{mod['name']} - {mod['cost']:,} cr",
                            description=mod['effect'][:50],
                            value=mod['name'],
                            emoji=mod['icon']
                        )
                    )
            
            if options:
                select = discord.ui.Select(
                    placeholder="Choose a modification to install...",
                    options=options
                )
                select.callback = self.mod_selected
                self.add_item(select)
    
    async def mod_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your panel!", ephemeral=True)
            return
        
        mod_name = interaction.data['values'][0]
        mod = next(m for m in self.mods if m['name'] == mod_name)
        
        if self.money < mod['cost']:
            await interaction.response.send_message("Insufficient credits!", ephemeral=True)
            return
        
        # Install mod
        current_mods = json.loads(self.ship_info[8]) if self.ship_info[8] else []
        current_mods.append(mod['name'])
        
        self.bot.db.execute_query(
            "UPDATE ships SET special_mods = %s, used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = %s",
            (json.dumps(current_mods), self.ship_info[0])
        )
        
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (mod['cost'], self.user_id)
        )
        
        await interaction.response.send_message(
            f"✅ {mod['icon']} **{mod['name']}** installed successfully!",
            ephemeral=True
        )


class MaintenanceView(discord.ui.View):
    """Handle ship repairs and maintenance"""
    def __init__(self, bot, user_id: int, ship_id: int, condition: int, money: int, tier: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.condition = condition
        self.money = money
        self.tier = tier
        
        # Add repair buttons
        if condition < 100:
            # Full repair
            full_cost = int((100 - condition) * 20 * (tier + 1))
            full_btn = discord.ui.Button(
                label=f"Full Repair ({full_cost:,} cr)",
                style=discord.ButtonStyle.success,
                emoji="🔧",
                disabled=money < full_cost
            )
            full_btn.callback = self._create_repair_callback(100 - condition, full_cost)
            self.add_item(full_btn)
            
            # Partial repairs
            for amount in [10, 25, 50]:
                if condition + amount <= 100:
                    cost = int(amount * 20 * (tier + 1))
                    btn = discord.ui.Button(
                        label=f"+{amount}% ({cost:,} cr)",
                        style=discord.ButtonStyle.primary,
                        disabled=money < cost
                    )
                    btn.callback = self._create_repair_callback(amount, cost)
                    self.add_item(btn)
    
    def _create_repair_callback(self, amount: int, cost: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your ship!", ephemeral=True)
                return
            
            # Process repair
            self.bot.db.execute_query(
                "UPDATE ships SET condition_rating = LEAST(condition_rating + %s, 100) WHERE ship_id = %s",
                (amount, self.ship_id)
            )
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - %s WHERE user_id = %s",
                (cost, self.user_id)
            )
            
            new_condition = min(self.condition + amount, 100)
            await interaction.response.send_message(
                f"✅ Ship repaired! Condition: {new_condition}%",
                ephemeral=True
            )
        
        return callback


class CosmeticView(discord.ui.View):
    """Handle cosmetic customization"""
    def __init__(self, bot, user_id: int, ship_id: int, money: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.money = money
        
        # Add category buttons
        categories = [
            ('Rename Ship', '✏️', 'rename_ship'),
            ('Paint Job', '🎨', 'paint_job'),
            ('Decals', '🏷️', 'decals'),
            ('Interior', '🛋️', 'interior_style')
        ]
        
        for label, emoji, category in categories:
            btn = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.primary
            )
            btn.callback = self._create_category_callback(category)
            self.add_item(btn)
    
    def _create_category_callback(self, category: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your customization panel!", ephemeral=True)
                return
            
            if category == 'rename_ship':
                await self._show_ship_rename(interaction)
            elif category == 'paint_job':
                await self._show_paint_jobs(interaction)
            elif category == 'decals':
                await self._show_decals(interaction)
            elif category == 'interior_style':
                await self._show_interior_themes(interaction)
        
        return callback
    
    async def _show_ship_rename(self, interaction: discord.Interaction):
        """Show ship renaming interface"""
        # Get current ship name
        ship_info = self.bot.db.execute_query(
            "SELECT name, ship_type FROM ships WHERE ship_id = %s",
            (self.ship_id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("Ship not found!", ephemeral=True)
            return
        
        current_name, ship_type = ship_info
        
        embed = discord.Embed(
            title="✏️ Rename Your Ship",
            description=f"Current name: **{current_name}**",
            color=0x4169e1
        )
        
        embed.add_field(name="Ship Type", value=ship_type, inline=True)
        embed.add_field(name="Cost", value="1,000 credits", inline=True)
        embed.add_field(name="Your Credits", value=f"{self.money:,}", inline=True)
        
        embed.add_field(
            name="📝 Naming Rules",
            value="• 2-50 characters long\n"
                  "• Letters, numbers, spaces, and basic punctuation\n"
                  "• No inappropriate content\n"
                  "• Cannot duplicate your existing ship names",
            inline=False
        )
        
        # Create rename modal
        view = ShipRenameView(self.bot, self.user_id, self.ship_id, self.money, current_name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _show_paint_jobs(self, interaction: discord.Interaction):
        """Show available paint job options"""
        from utils.ship_data import COSMETIC_OPTIONS
        
        # Get current paint job
        current_custom = self.bot.db.execute_query(
            "SELECT paint_job FROM ship_customization WHERE ship_id = %s",
            (self.ship_id,),
            fetch='one'
        )
        
        current_paint = current_custom[0] if current_custom else "Default"
        
        embed = discord.Embed(
            title="🎨 Ship Paint Jobs",
            description=f"Current paint: **{current_paint}**",
            color=0xff69b4
        )
        
        paint_jobs = COSMETIC_OPTIONS['paint_jobs']
        
        # Show available paint jobs with stat effects
        for paint in paint_jobs[:10]:  # Show first 10
            embed.add_field(
                name=paint['name'],
                value=f"{paint['description']}\n**Cost:** {paint['cost']:,} credits",
                inline=True
            )
        
        embed.add_field(
            name="🎨 Cosmetic Options",
            value="Paint jobs are purely cosmetic and allow you to personalize your ship's appearance. "
                  "Choose from a variety of colors and finishes to make your vessel unique in the galaxy.",
            inline=False
        )
        
        view = PaintJobSelectionView(self.bot, self.user_id, self.ship_id, paint_jobs, self.money)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _show_decals(self, interaction: discord.Interaction):
        """Show available decal options"""
        from utils.ship_data import COSMETIC_OPTIONS
        
        current_custom = self.bot.db.execute_query(
            "SELECT decals FROM ship_customization WHERE ship_id = %s",
            (self.ship_id,),
            fetch='one'
        )
        
        current_decals = current_custom[0] if current_custom else "None"
        
        embed = discord.Embed(
            title="🏷️ Ship Decals",
            description=f"Current decals: **{current_decals}**",
            color=0x4169e1
        )
        
        decals = COSMETIC_OPTIONS['decals']
        
        for decal in decals[:12]:  # Show first 12
            embed.add_field(
                name=decal['name'],
                value=f"{decal['description']}\n**Cost:** {decal['cost']:,} credits",
                inline=True
            )
        
        view = DecalSelectionView(self.bot, self.user_id, self.ship_id, decals, self.money)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _show_interior_themes(self, interaction: discord.Interaction):
        """Show available interior theme options"""
        from utils.ship_data import COSMETIC_OPTIONS
        
        current_custom = self.bot.db.execute_query(
            "SELECT interior_style FROM ship_customization WHERE ship_id = %s",
            (self.ship_id,),
            fetch='one'
        )
        
        current_interior = current_custom[0] if current_custom else "Standard"
        
        embed = discord.Embed(
            title="🛋️ Interior Themes",
            description=f"Current theme: **{current_interior}**",
            color=0x8B4513
        )
        
        themes = COSMETIC_OPTIONS['interior_themes']
        
        for theme in themes:
            effect_text = self._get_interior_effect(theme['name'])
            embed.add_field(
                name=theme['name'],
                value=f"{theme['description']}\n{effect_text}\n**Cost:** {theme['cost']:,} credits",
                inline=True
            )
        
        view = InteriorThemeView(self.bot, self.user_id, self.ship_id, themes, self.money)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    
    def _get_interior_effect(self, theme_name: str) -> str:
        """Get effect description for interior theme"""
        effects = {
            'Luxury': '+10% crew morale, +5% passenger comfort',
            'Military Spec': '+15% durability, +5% repair speed',
            'Minimalist': '+5% fuel efficiency, +3% system reliability',
            'Retro-Future': '+5% charm factor, +3% negotiation bonus',
            'Alien-Inspired': '+10% curiosity factor, +5% research speed'
        }
        return effects.get(theme_name, 'Aesthetic enhancement only')


class ItemApplicationView(discord.ui.View):
    """Apply upgrade items from inventory"""
    def __init__(self, bot, user_id: int, ship_id: int, items: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        
        # Create item selection
        options = []
        for item_id, name, quantity, metadata in items[:25]:
            options.append(
                discord.SelectOption(
                    label=f"{name} (x{quantity})",
                    value=str(item_id)
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an item to apply...",
                options=options
            )
            select.callback = self.item_selected
            self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your inventory!", ephemeral=True)
            return
        
        item_id = int(interaction.data['values'][0])
        
        # Get item details
        item = self.bot.db.execute_query(
            "SELECT item_name, metadata FROM inventory WHERE item_id = %s",
            (item_id,),
            fetch='one'
        )
        
        if not item:
            await interaction.response.send_message("Item not found!", ephemeral=True)
            return
        
        # Apply item effect
        try:
            metadata = json.loads(item[1]) if item[1] else {}
            upgrade_type = metadata.get('upgrade_type', 'general')
            bonus = metadata.get('bonus', 5)
            
            # Apply based on type
            if upgrade_type == 'fuel_efficiency':
                self.bot.db.execute_query(
                    "UPDATE ships SET fuel_efficiency = fuel_efficiency + %s WHERE ship_id = %s",
                    (bonus, self.ship_id)
                )
            elif upgrade_type == 'cargo_capacity':
                self.bot.db.execute_query(
                    "UPDATE ships SET cargo_capacity = cargo_capacity + %s WHERE ship_id = %s",
                    (bonus, self.ship_id)
                )
            elif upgrade_type == 'combat_rating':
                self.bot.db.execute_query(
                    "UPDATE ships SET combat_rating = combat_rating + %s WHERE ship_id = %s",
                    (bonus, self.ship_id)
                )
            
            # Remove item from inventory
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = %s",
                (item_id,)
            )
            
            self.bot.db.execute_query(
                "DELETE FROM inventory WHERE item_id = %s AND quantity <= 0",
                (item_id,)
            )
            
            await interaction.response.send_message(
                f"✅ Applied **{item[0]}** to your ship! (+{bonus} {upgrade_type})",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"Error applying item: {str(e)}",
                ephemeral=True
            )


class ShipyardHubView(discord.ui.View):
    """Main shipyard hub navigation"""
    def __init__(self, bot, user_id: int, wealth_level: int, money: int, fleet: list, has_upgrades: bool = False):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.wealth_level = wealth_level
        self.money = money
        self.fleet = fleet
        self.has_upgrades = has_upgrades
        
        # Conditionally add upgrade workshop button
        if has_upgrades:
            upgrade_button = discord.ui.Button(
                label="Upgrade Workshop", 
                style=discord.ButtonStyle.primary, 
                emoji="🔧", 
                row=0
            )
            upgrade_button.callback = self.upgrade_workshop
            self.add_item(upgrade_button)
        
    @discord.ui.button(label="Browse Ships", style=discord.ButtonStyle.primary, emoji="🛒", row=0)
    async def browse_ships(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Redirect to ship purchase command
        await self.bot.get_cog('ShipSystemsCog').ship_purchase.callback(
            self.bot.get_cog('ShipSystemsCog'), interaction
        )
    
    async def upgrade_workshop(self, interaction: discord.Interaction):
        if not any(s[5] for s in self.fleet):  # No active ship
            await interaction.response.send_message("You need an active ship first!", ephemeral=True)
            return
        
        await self.bot.get_cog('ShipSystemsCog').ship_upgrade.callback(
            self.bot.get_cog('ShipSystemsCog'), interaction
        )
    
    @discord.ui.button(label="Fleet Management", style=discord.ButtonStyle.secondary, emoji="📦", row=0)
    async def fleet_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage your ship collection"""
        embed = discord.Embed(
            title="📦 Fleet Management",
            description="Manage your ship collection",
            color=0x4169e1
        )
        
        if not self.fleet:
            embed.add_field(
                name="No Ships",
                value="You don't own any ships yet!",
                inline=False
            )
        else:
            for ship in self.fleet[:10]:
                ship_id, name, ship_type, tier, condition, is_active, value = ship
                
                status = "🟢 **ACTIVE**" if is_active else "🔵 Stored"
                embed.add_field(
                    name=f"{name}",
                    value=f"{status}\n"
                          f"Type: {ship_type} (Tier {tier})\n"
                          f"Condition: {condition}%\n"
                          f"Value: {value:,} credits",
                    inline=True
                )
        
        # Create fleet action buttons
        view = FleetManagementView(self.bot, self.user_id, self.fleet)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Ship Exchange", style=discord.ButtonStyle.success, emoji="🔄", row=1)
    async def ship_exchange(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.wealth_level < 5:
            await interaction.response.send_message(
                "Ship Exchange requires a Tier 3+ shipyard!",
                ephemeral=True
            )
            return
        
        # Get user's current location for the exchange
        char_info = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location = char_info[0]
        
        # Create and show the ship exchange view
        view = ShipExchangeView(self.bot, interaction.user.id, current_location, self.money)
        await view.create_exchange_embed(interaction)
    
    @discord.ui.button(label="Sell Ship", style=discord.ButtonStyle.danger, emoji="💰", row=1)
    async def sell_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.fleet:
            await interaction.response.send_message("You don't have any ships to sell!", ephemeral=True)
            return
        
        # Show ship selling interface
        embed = discord.Embed(
            title="💰 Sell Ship",
            description="Select a ship to sell",
            color=0xff0000
        )
        
        view = ShipSellView(self.bot, self.user_id, self.fleet)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class FleetManagementView(discord.ui.View):
    """Manage fleet operations"""
    def __init__(self, bot, user_id: int, fleet: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.fleet = fleet
        
        # Add ship switching if multiple ships
        if len(fleet) > 1:
            options = []
            for ship in fleet:
                ship_id, name, ship_type, tier, condition, is_active, value = ship
                if not is_active:
                    options.append(
                        discord.SelectOption(
                            label=f"{name} ({ship_type})",
                            description=f"Tier {tier}, Condition: {condition}%",
                            value=str(ship_id)
                        )
                    )
            
            if options:
                select = discord.ui.Select(
                    placeholder="Make ship active...",
                    options=options
                )
                select.callback = self.switch_ship
                self.add_item(select)
    
    async def switch_ship(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your fleet!", ephemeral=True)
            return
        
        new_ship_id = int(interaction.data['values'][0])
        
        # Deactivate all ships first
        self.bot.db.execute_query(
            "UPDATE player_ships SET is_active = false WHERE owner_id = %s",
            (self.user_id,)
        )
        
        # Activate the selected ship
        self.bot.db.execute_query(
            "UPDATE player_ships SET is_active = true WHERE owner_id = %s AND ship_id = %s",
            (self.user_id, new_ship_id)
        )
        
        # UPDATE BOTH ship_id AND active_ship_id
        self.bot.db.execute_query(
            "UPDATE characters SET ship_id = %s, active_ship_id = %s WHERE user_id = %s",
            (new_ship_id, new_ship_id, self.user_id)
        )
        
        ship_name = next(s[1] for s in self.fleet if s[0] == new_ship_id)
        await interaction.response.send_message(
            f"✅ **{ship_name}** is now your active ship!",
            ephemeral=True
        )

class ShipSellView(discord.ui.View):
    """Handle ship selling"""
    def __init__(self, bot, user_id: int, fleet: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.fleet = fleet
        
        # Create ship selection for selling
        options = []
        for ship in fleet:
            ship_id, name, ship_type, tier, condition, is_active, value = ship
            if not is_active or len(fleet) > 1:  # Can't sell only ship if it's active
                sell_value = int(value * (condition / 100) * 0.6)  # 60% of adjusted value
                options.append(
                    discord.SelectOption(
                        label=f"{name} - {sell_value:,} cr",
                        description=f"{ship_type}, Condition: {condition}%",
                        value=f"{ship_id}|{sell_value}"
                    )
                )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose a ship to sell...",
                options=options
            )
            select.callback = self.confirm_sale
            self.add_item(select)
        else:
            btn = discord.ui.Button(
                label="Cannot sell your only active ship!",
                disabled=True
            )
            self.add_item(btn)
    
    async def confirm_sale(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your transaction!", ephemeral=True)
            return
        
        ship_id, sell_value = interaction.data['values'][0].split('|')
        ship_id = int(ship_id)
        sell_value = int(sell_value)
        
        # Get ship details
        ship = next(s for s in self.fleet if s[0] == ship_id)
        
        # Confirm sale
        embed = discord.Embed(
            title="💰 Confirm Ship Sale",
            description=f"Are you sure you want to sell **{ship[1]}**%s",
            color=0xff0000
        )
        
        embed.add_field(name="Type", value=ship[2], inline=True)
        embed.add_field(name="Condition", value=f"{ship[4]}%", inline=True)
        embed.add_field(name="Sale Price", value=f"{sell_value:,} credits", inline=True)
        
        confirm_view = SaleConfirmView(self.bot, self.user_id, ship_id, sell_value)
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class SaleConfirmView(discord.ui.View):
    """Confirm ship sale"""
    def __init__(self, bot, user_id: int, ship_id: int, sell_value: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.sell_value = sell_value
    
    @discord.ui.button(label="Confirm Sale", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your sale!", ephemeral=True)
            return
        
        # Process sale
        # Get player's current location
        location_info = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (self.user_id,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message("Error: Character not found!", ephemeral=True)
            return
            
        current_location = location_info[0]
        
        # Get ship details for adding to inventory
        ship_details = self.bot.db.execute_query(
            """SELECT s.name, s.ship_type, s.ship_class, s.tier, s.condition_rating, 
                      s.market_value, s.cargo_capacity, s.speed_rating, s.combat_rating, 
                      s.fuel_efficiency, s.special_mods
               FROM ships s WHERE s.ship_id = %s""",
            (self.ship_id,),
            fetch='one'
        )
        
        if ship_details:
            # Prepare ship data for inventory
            ship_data = {
                'name': ship_details[0],
                'type': ship_details[1],
                'class': ship_details[2],
                'tier': ship_details[3],
                'cargo_capacity': ship_details[6],
                'speed_rating': ship_details[7],
                'combat_rating': ship_details[8],
                'fuel_efficiency': ship_details[9],
                'special_features': ship_details[10],
                'condition_rating': ship_details[4],
                'market_value': ship_details[5],
                'price': self.sell_value * 2  # Shipyard sells for roughly 2x what they buy for
            }
            
            # Add ship to shipyard inventory
            self.bot.db.add_ship_to_inventory(
                current_location, 
                ship_data, 
                is_player_sold=True, 
                original_owner_id=self.user_id
            )
        
        # Remove from player_ships
        self.bot.db.execute_query(
            "DELETE FROM player_ships WHERE ship_id = %s AND owner_id = %s",
            (self.ship_id, self.user_id)
        )
        
        # Delete ship from ships table
        self.bot.db.execute_query(
            "DELETE FROM ships WHERE ship_id = %s",
            (self.ship_id,)
        )
        
        # Add credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (self.sell_value, self.user_id)
        )
        
        await interaction.response.edit_message(
            content=f"✅ Ship sold for {self.sell_value:,} credits!",
            embed=None,
            view=None
        )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your sale!", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="Sale cancelled.",
            embed=None,
            view=None
        )


class PaintJobSelectionView(discord.ui.View):
    """Handle paint job selection and purchase"""
    def __init__(self, bot, user_id: int, ship_id: int, paint_jobs: list, money: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.money = money
        
        # Create selection dropdown
        options = []
        for paint in paint_jobs[:25]:  # Discord limit is 25 options
            options.append(
                discord.SelectOption(
                    label=f"{paint['name']} - {paint['cost']:,} cr",
                    description=paint['description'][:50],  # Truncate if too long
                    value=paint['name']
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose a paint job...",
                options=options
            )
            select.callback = self.paint_selected
            self.add_item(select)
    
    async def paint_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your customization panel!", ephemeral=True)
            return
        
        from utils.ship_data import COSMETIC_OPTIONS
        paint_name = interaction.data['values'][0]
        paint_data = next(p for p in COSMETIC_OPTIONS['paint_jobs'] if p['name'] == paint_name)
        
        if self.money < paint_data['cost']:
            await interaction.response.send_message("❌ Insufficient credits!", ephemeral=True)
            return
        
        # Apply paint job
        await self._apply_paint_job(paint_name, paint_data['cost'])
        
        await interaction.response.send_message(
            f"✅ Applied **{paint_name}** paint job to your ship! (-{paint_data['cost']:,} credits)",
            ephemeral=True
        )
    
    async def _apply_paint_job(self, paint_name: str, cost: int):
        """Apply the paint job and deduct credits"""
        # Ensure customization record exists
        self.bot.db.execute_query(
            '''INSERT INTO ship_customization (ship_id, paint_job, decals, interior_style)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (ship_id) DO NOTHING''',
            (self.ship_id, 'Default', 'None', 'Standard')
        )
        
        # Update paint job
        self.bot.db.execute_query(
            "UPDATE ship_customization SET paint_job = %s WHERE ship_id = %s",
            (paint_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (cost, self.user_id)
        )


class DecalSelectionView(discord.ui.View):
    """Handle decal selection and purchase"""
    def __init__(self, bot, user_id: int, ship_id: int, decals: list, money: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.money = money
        
        # Create selection dropdown
        options = []
        for decal in decals[:25]:  # Discord limit is 25 options
            options.append(
                discord.SelectOption(
                    label=f"{decal['name']} - {decal['cost']:,} cr",
                    description=decal['description'][:50],
                    value=decal['name']
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose decals...",
                options=options
            )
            select.callback = self.decal_selected
            self.add_item(select)
    
    async def decal_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your customization panel!", ephemeral=True)
            return
        
        from utils.ship_data import COSMETIC_OPTIONS
        decal_name = interaction.data['values'][0]
        decal_data = next(d for d in COSMETIC_OPTIONS['decals'] if d['name'] == decal_name)
        
        if self.money < decal_data['cost']:
            await interaction.response.send_message("❌ Insufficient credits!", ephemeral=True)
            return
        
        # Apply decals
        await self._apply_decals(decal_name, decal_data['cost'])
        
        await interaction.response.send_message(
            f"✅ Applied **{decal_name}** decals to your ship! (-{decal_data['cost']:,} credits)",
            ephemeral=True
        )
    
    async def _apply_decals(self, decal_name: str, cost: int):
        """Apply the decals and deduct credits"""
        # Ensure customization record exists
        self.bot.db.execute_query(
            '''INSERT INTO ship_customization (ship_id, paint_job, decals, interior_style)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (ship_id) DO NOTHING''',
            (self.ship_id, 'Default', 'None', 'Standard')
        )
        
        # Update decals
        self.bot.db.execute_query(
            "UPDATE ship_customization SET decals = %s WHERE ship_id = %s",
            (decal_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (cost, self.user_id)
        )


class InteriorThemeView(discord.ui.View):
    """Handle interior theme selection and purchase"""
    def __init__(self, bot, user_id: int, ship_id: int, themes: list, money: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.money = money
        
        # Create selection dropdown
        options = []
        for theme in themes:
            options.append(
                discord.SelectOption(
                    label=f"{theme['name']} - {theme['cost']:,} cr",
                    description=theme['description'][:50],
                    value=theme['name']
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose interior theme...",
                options=options
            )
            select.callback = self.theme_selected
            self.add_item(select)
    
    async def theme_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your customization panel!", ephemeral=True)
            return
        
        from utils.ship_data import COSMETIC_OPTIONS
        theme_name = interaction.data['values'][0]
        theme_data = next(t for t in COSMETIC_OPTIONS['interior_themes'] if t['name'] == theme_name)
        
        if self.money < theme_data['cost']:
            await interaction.response.send_message("❌ Insufficient credits!", ephemeral=True)
            return
        
        # Apply interior theme
        await self._apply_theme(theme_name, theme_data['cost'])
        
        await interaction.response.send_message(
            f"✅ Applied **{theme_name}** interior theme to your ship! (-{theme_data['cost']:,} credits)",
            ephemeral=True
        )
    
    async def _apply_theme(self, theme_name: str, cost: int):
        """Apply the interior theme and deduct credits"""
        # Ensure customization record exists
        self.bot.db.execute_query(
            '''INSERT INTO ship_customization (ship_id, paint_job, decals, interior_style)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (ship_id) DO NOTHING''',
            (self.ship_id, 'Default', 'None', 'Standard')
        )
        
        # Update interior theme
        self.bot.db.execute_query(
            "UPDATE ship_customization SET interior_style = %s WHERE ship_id = %s",
            (theme_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (cost, self.user_id)
        )


class ShipRenameView(discord.ui.View):
    """Handle ship renaming with modal input"""
    def __init__(self, bot, user_id: int, ship_id: int, money: int, current_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.money = money
        self.current_name = current_name
    
    @discord.ui.button(label="Enter New Name", style=discord.ButtonStyle.primary, emoji="✏️")
    async def enter_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your ship!", ephemeral=True)
            return
        
        # Show modal for name input
        modal = ShipRenameModal(self.bot, self.user_id, self.ship_id, self.money, self.current_name)
        await interaction.response.send_modal(modal)


class ShipRenameModal(discord.ui.Modal, title="Rename Your Ship"):
    """Modal for entering new ship name"""
    def __init__(self, bot, user_id: int, ship_id: int, money: int, current_name: str):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.money = money
        self.current_name = current_name
    
    new_name = discord.ui.TextInput(
        label="New Ship Name",
        placeholder="Enter your ship's new name...",
        max_length=50,
        min_length=2
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.new_name.value.strip()
        
        # Validation
        validation_result = self._validate_ship_name(new_name)
        if not validation_result['valid']:
            await interaction.response.send_message(
                f"❌ Invalid name: {validation_result['reason']}",
                ephemeral=True
            )
            return
        
        # Check if name is already in use by this player
        existing = self.bot.db.execute_query(
            '''SELECT COUNT(*) FROM ships s
               JOIN player_ships ps ON s.ship_id = ps.ship_id
               WHERE ps.owner_id = %s AND s.name = %s AND s.ship_id != %s''',
            (self.user_id, new_name, self.ship_id),
            fetch='one'
        )[0]
        
        if existing > 0:
            await interaction.response.send_message(
                "❌ You already have a ship with that name!",
                ephemeral=True
            )
            return
        
        # Check credits
        cost = 1000
        if self.money < cost:
            await interaction.response.send_message(
                f"❌ Insufficient credits! Need {cost:,} credits",
                ephemeral=True
            )
            return
        
        # Update ship name
        self.bot.db.execute_query(
            "UPDATE ships SET name = %s WHERE ship_id = %s",
            (new_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (cost, self.user_id)
        )
        
        # Success response
        embed = discord.Embed(
            title="✅ Ship Renamed!",
            description=f"**{self.current_name}** is now called **{new_name}**",
            color=0x00ff00
        )
        
        embed.add_field(name="Old Name", value=self.current_name, inline=True)
        embed.add_field(name="New Name", value=new_name, inline=True)
        embed.add_field(name="Cost", value=f"{cost:,} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def _validate_ship_name(self, name: str) -> dict:
        """Validate ship name with various criteria"""
        # Basic length check
        if len(name) < 2:
            return {'valid': False, 'reason': 'Name must be at least 2 characters long'}
        
        if len(name) > 50:
            return {'valid': False, 'reason': 'Name cannot exceed 50 characters'}
        
        # Character validation - allow letters, numbers, spaces, and basic punctuation
        import re
        if not re.match(r'^[a-zA-Z0-9\s\'\-\.\_\(\)\[\]]+$', name):
            return {'valid': False, 'reason': 'Name contains invalid characters'}
        
        # Basic profanity filter (simple word list - in production would use a proper filter)
        profanity_words = ['fuck', 'shit', 'damn', 'hell', 'ass', 'bitch', 'bastard']  # Basic list
        name_lower = name.lower()
        for word in profanity_words:
            if word in name_lower:
                return {'valid': False, 'reason': 'Name contains inappropriate content'}
        
        # Prevent all caps (except for acronyms)
        if name.isupper() and len(name) > 5:
            return {'valid': False, 'reason': 'Name cannot be all capital letters'}
        
        # Prevent excessive whitespace
        if '  ' in name or name.startswith(' ') or name.endswith(' '):
            return {'valid': False, 'reason': 'Name has excessive whitespace'}
        
        return {'valid': True, 'reason': 'Valid name'}


class ShipExchangeView(discord.ui.View):
    """Main ship exchange interface for browsing listings"""
    def __init__(self, bot, user_id: int, location_id: int, money: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.money = money
    
    async def create_exchange_embed(self, interaction: discord.Interaction):
        """Create and display the ship exchange interface"""
        # Get location name
        location_info = self.bot.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (self.location_id,),
            fetch='one'
        )
        location_name = location_info[0] if location_info else "Unknown Location"
        
        # Get active listings at this location
        listings = self.bot.db.execute_query(
            '''SELECT sel.listing_id, sel.ship_id, sel.owner_id, sel.asking_price, 
                      sel.desired_ship_types, sel.listing_description, sel.expires_at,
                      s.name, s.ship_type, s.tier, s.condition_rating, s.market_value,
                      c.name as owner_name
               FROM ship_exchange_listings sel
               JOIN ships s ON sel.ship_id = s.ship_id
               JOIN characters c ON sel.owner_id = c.user_id
               WHERE sel.listed_at_location = %s AND sel.is_active = true 
               AND sel.expires_at > NOW()
               ORDER BY sel.created_at DESC''',
            (self.location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"🔄 Ship Exchange - {location_name}",
            description="Browse ships available for exchange at this location",
            color=0x00ff00
        )
        
        if not listings:
            embed.add_field(
                name="No Ships Available",
                value="No ships are currently listed for exchange at this location.",
                inline=False
            )
        else:
            # Show first few listings
            for i, listing in enumerate(listings[:5]):
                (listing_id, ship_id, owner_id, asking_price, desired_types, 
                 description, expires_at, ship_name, ship_type, tier, condition, 
                 market_value, owner_name) = listing
                
                desired_list = json.loads(desired_types) if desired_types else []
                desired_str = ", ".join(desired_list) if desired_list else "Any ship type"
                
                embed.add_field(
                    name=f"{ship_name} ({ship_type})",
                    value=f"**Owner:** {owner_name}\n"
                          f"**Tier:** {tier} | **Condition:** {condition}%\n"
                          f"**Asking:** {asking_price:,} credits\n"
                          f"**Wants:** {desired_str}",
                    inline=True
                )
            
            if len(listings) > 5:
                embed.add_field(
                    name="More Available",
                    value=f"+ {len(listings) - 5} more ships",
                    inline=False
                )
        
        embed.add_field(
            name="Your Credits", 
            value=f"{self.money:,}", 
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.button(label="List My Ship", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def list_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open interface to list a ship for exchange"""
        view = ListShipView(self.bot, self.user_id, self.location_id)
        await view.show_ship_selection(interaction)
    
    @discord.ui.button(label="Browse Listings", style=discord.ButtonStyle.secondary, emoji="🔍", row=0)
    async def browse_listings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Browse detailed ship listings"""
        view = BrowseListingsView(self.bot, self.user_id, self.location_id, self.money)
        await view.show_listings(interaction)
    
    @discord.ui.button(label="My Listed Ships", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def my_listings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View and manage your listed ships"""
        listings = self.bot.db.execute_query(
            '''SELECT sel.listing_id, sel.ship_id, sel.asking_price, sel.expires_at,
                      s.name, s.ship_type, l.name as location_name
               FROM ship_exchange_listings sel
               JOIN ships s ON sel.ship_id = s.ship_id
               JOIN locations l ON sel.listed_at_location = l.location_id
               WHERE sel.owner_id = %s AND sel.is_active = true
               ORDER BY sel.created_at DESC''',
            (self.user_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="📋 Your Listed Ships",
            color=0x4169e1
        )
        
        if not listings:
            embed.description = "You don't have any ships listed for exchange."
        else:
            for listing in listings[:10]:
                listing_id, ship_id, asking_price, expires_at, ship_name, ship_type, location_name = listing
                embed.add_field(
                    name=f"{ship_name} ({ship_type})",
                    value=f"**Location:** {location_name}\n"
                          f"**Asking:** {asking_price:,} credits\n"
                          f"**Expires:** {expires_at[:16]}",
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ListShipView(discord.ui.View):
    """Interface for listing a ship for exchange"""
    def __init__(self, bot, user_id: int, location_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
    
    async def show_ship_selection(self, interaction: discord.Interaction):
        """Show ships available to list at current location"""
        # Get ships owned by user that are at this location and not active
        ships = self.bot.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.tier, s.condition_rating, s.market_value
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = %s AND ps.is_active = false 
               AND s.docked_at_location = %s
               AND s.ship_id NOT IN (
                   SELECT ship_id FROM ship_exchange_listings 
                   WHERE is_active = true AND expires_at > NOW()
               )''',
            (self.user_id, self.location_id),
            fetch='all'
        )
        
        if not ships:
            embed = discord.Embed(
                title="❌ No Ships Available",
                description="You don't have any ships at this location that can be listed for exchange.\n\n"
                           "**Requirements:**\n"
                           "• Ship must be docked at this location\n"
                           "• Ship cannot be your active ship\n"
                           "• Ship cannot already be listed",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📝 Select Ship to List",
            description="Choose which ship you want to list for exchange:",
            color=0x00ff00
        )
        
        # Add dropdown for ship selection
        options = []
        for ship in ships[:25]:  # Discord limit
            ship_id, name, ship_type, tier, condition, market_value = ship
            options.append(discord.SelectOption(
                label=f"{name} ({ship_type})",
                description=f"Tier {tier} • {condition}% condition • {market_value:,} credits",
                value=str(ship_id)
            ))
        
        select = ShipSelectionDropdown(self.bot, self.user_id, self.location_id, options)
        self.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class ShipSelectionDropdown(discord.ui.Select):
    """Dropdown for selecting a ship to list"""
    def __init__(self, bot, user_id: int, location_id: int, options: list):
        super().__init__(placeholder="Choose a ship to list...", options=options)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
    
    async def callback(self, interaction: discord.Interaction):
        ship_id = int(self.values[0])
        
        # Get ship details
        ship_info = self.bot.db.execute_query(
            '''SELECT s.name, s.ship_type, s.tier, s.condition_rating, s.market_value
               FROM ships s WHERE s.ship_id = %s''',
            (ship_id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("Ship not found!", ephemeral=True)
            return
        
        name, ship_type, tier, condition, market_value = ship_info
        
        # Show listing configuration modal
        modal = ListingConfigModal(self.bot, self.user_id, self.location_id, ship_id, name, ship_type)
        await interaction.response.send_modal(modal)


class ListingConfigModal(discord.ui.Modal):
    """Modal for configuring ship listing details"""
    def __init__(self, bot, user_id: int, location_id: int, ship_id: int, ship_name: str, ship_type: str):
        super().__init__(title=f"List {ship_name} for Exchange")
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.ship_id = ship_id
        self.ship_name = ship_name
        self.ship_type = ship_type
        
        self.asking_price = discord.ui.TextInput(
            label="Asking Price (credits)",
            placeholder="Enter asking price in credits (or 0 for ship trade only)",
            required=True,
            max_length=10
        )
        
        self.desired_types = discord.ui.TextInput(
            label="Desired Ship Types",
            placeholder="e.g., Fighter, Hauler, Explorer (or leave blank for any)",
            required=False,
            max_length=200
        )
        
        self.description = discord.ui.TextInput(
            label="Listing Description",
            placeholder="Optional description of your ship or trade requirements",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.add_item(self.asking_price)
        self.add_item(self.desired_types)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            asking_price = int(self.asking_price.value)
            if asking_price < 0:
                raise ValueError("Price cannot be negative")
        except ValueError:
            await interaction.response.send_message("Invalid asking price!", ephemeral=True)
            return
        
        # Parse desired ship types
        desired_list = []
        if self.desired_types.value:
            desired_list = [t.strip() for t in self.desired_types.value.split(',') if t.strip()]
        
        # Create listing (expires in 7 days)
        expires_at = datetime.now() + timedelta(days=7)
        
        self.bot.db.execute_query(
            '''INSERT INTO ship_exchange_listings 
               (ship_id, owner_id, listed_at_location, asking_price, desired_ship_types, 
                listing_description, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)''',
            (self.ship_id, self.user_id, self.location_id, asking_price, 
             json.dumps(desired_list), self.description.value, expires_at)
        )
        
        embed = discord.Embed(
            title="✅ Ship Listed Successfully",
            description=f"**{self.ship_name}** has been listed for exchange!",
            color=0x00ff00
        )
        
        embed.add_field(name="Asking Price", value=f"{asking_price:,} credits", inline=True)
        embed.add_field(name="Desired Types", value=", ".join(desired_list) if desired_list else "Any", inline=True)
        embed.add_field(name="Expires", value=expires_at.strftime("%Y-%m-%d %H:%M"), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BrowseListingsView(discord.ui.View):
    """Detailed browsing interface for ship listings"""
    def __init__(self, bot, user_id: int, location_id: int, money: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.money = money
        self.current_page = 0
    
    async def show_listings(self, interaction: discord.Interaction):
        """Show detailed listings with pagination"""
        listings = self.bot.db.execute_query(
            '''SELECT sel.listing_id, sel.ship_id, sel.owner_id, sel.asking_price, 
                      sel.desired_ship_types, sel.listing_description, sel.expires_at,
                      s.name, s.ship_type, s.tier, s.condition_rating, s.market_value,
                      c.name as owner_name
               FROM ship_exchange_listings sel
               JOIN ships s ON sel.ship_id = s.ship_id
               JOIN characters c ON sel.owner_id = c.user_id
               WHERE sel.listed_at_location = %s AND sel.is_active = true 
               AND sel.expires_at > NOW()
               AND sel.owner_id != %s
               ORDER BY sel.created_at DESC''',
            (self.location_id, self.user_id),
            fetch='all'
        )
        
        if not listings:
            embed = discord.Embed(
                title="❌ No Listings Available",
                description="No ships are currently available for exchange at this location.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Show current listing
        listing = listings[self.current_page]
        (listing_id, ship_id, owner_id, asking_price, desired_types, 
         description, expires_at, ship_name, ship_type, tier, condition, 
         market_value, owner_name) = listing
        
        desired_list = json.loads(desired_types) if desired_types else []
        
        embed = discord.Embed(
            title=f"🚀 {ship_name}",
            description=description or "No description provided",
            color=0x4169e1
        )
        
        embed.add_field(name="Type", value=ship_type, inline=True)
        embed.add_field(name="Tier", value=str(tier), inline=True)
        embed.add_field(name="Condition", value=f"{condition}%", inline=True)
        embed.add_field(name="Market Value", value=f"{market_value:,} credits", inline=True)
        embed.add_field(name="Owner", value=owner_name, inline=True)
        embed.add_field(name="Asking Price", value=f"{asking_price:,} credits", inline=True)
        embed.add_field(name="Wants", value=", ".join(desired_list) if desired_list else "Any ship type", inline=False)
        embed.add_field(name="Expires", value=expires_at[:16], inline=True)
        
        embed.set_footer(text=f"Listing {self.current_page + 1} of {len(listings)}")
        
        # Add navigation and action buttons
        self.clear_items()
        
        if len(listings) > 1:
            prev_button = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary, disabled=self.current_page == 0)
            prev_button.callback = self.previous_listing
            self.add_item(prev_button)
            
            next_button = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=self.current_page >= len(listings) - 1)
            next_button.callback = self.next_listing
            self.add_item(next_button)
        
        offer_button = discord.ui.Button(label="Make Offer", style=discord.ButtonStyle.primary, emoji="💼")
        offer_button.callback = lambda i: self.make_offer(i, listing_id, ship_name)
        self.add_item(offer_button)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        
        # Store listings for navigation
        self.listings = listings
    
    async def previous_listing(self, interaction: discord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        await self.show_listings(interaction)
    
    async def next_listing(self, interaction: discord.Interaction):
        self.current_page = min(len(self.listings) - 1, self.current_page + 1)
        await self.show_listings(interaction)
    
    async def make_offer(self, interaction: discord.Interaction, listing_id: int, ship_name: str):
        """Start the offer making process"""
        view = MakeOfferView(self.bot, self.user_id, self.location_id, listing_id, ship_name)
        await view.show_offer_interface(interaction)


class MakeOfferView(discord.ui.View):
    """Interface for making an offer on a listed ship"""
    def __init__(self, bot, user_id: int, location_id: int, listing_id: int, target_ship_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.listing_id = listing_id
        self.target_ship_name = target_ship_name
    
    async def show_offer_interface(self, interaction: discord.Interaction):
        """Show the offer making interface"""
        # Get user's ships at this location
        ships = self.bot.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.tier, s.condition_rating, s.market_value
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = %s AND s.docked_at_location = %s
               AND s.ship_id NOT IN (
                   SELECT ship_id FROM ship_exchange_listings 
                   WHERE is_active = true AND expires_at > NOW()
               )''',
            (self.user_id, self.location_id),
            fetch='all'
        )
        
        if not ships:
            embed = discord.Embed(
                title="❌ No Ships Available",
                description="You don't have any ships at this location that can be offered.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"💼 Make Offer for {self.target_ship_name}",
            description="Select which ship you want to offer in exchange:",
            color=0x00ff00
        )
        
        # Add dropdown for ship selection
        options = []
        for ship in ships[:25]:  # Discord limit
            ship_id, name, ship_type, tier, condition, market_value = ship
            options.append(discord.SelectOption(
                label=f"{name} ({ship_type})",
                description=f"Tier {tier} • {condition}% condition • {market_value:,} credits",
                value=str(ship_id)
            ))
        
        select = OfferShipDropdown(self.bot, self.user_id, self.listing_id, self.target_ship_name, options)
        self.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class OfferShipDropdown(discord.ui.Select):
    """Dropdown for selecting ship to offer"""
    def __init__(self, bot, user_id: int, listing_id: int, target_ship_name: str, options: list):
        super().__init__(placeholder="Choose ship to offer...", options=options)
        self.bot = bot
        self.user_id = user_id
        self.listing_id = listing_id
        self.target_ship_name = target_ship_name
    
    async def callback(self, interaction: discord.Interaction):
        offered_ship_id = int(self.values[0])
        
        # Show offer details modal
        modal = OfferDetailsModal(self.bot, self.user_id, self.listing_id, offered_ship_id, self.target_ship_name)
        await interaction.response.send_modal(modal)


class OfferDetailsModal(discord.ui.Modal):
    """Modal for configuring offer details"""
    def __init__(self, bot, user_id: int, listing_id: int, offered_ship_id: int, target_ship_name: str):
        super().__init__(title=f"Offer Details for {target_ship_name}")
        self.bot = bot
        self.user_id = user_id
        self.listing_id = listing_id
        self.offered_ship_id = offered_ship_id
        
        self.credits_adjustment = discord.ui.TextInput(
            label="Credits Adjustment",
            placeholder="Enter + or - credits (e.g., +5000 or -2000, or 0 for even trade)",
            required=True,
            max_length=10
        )
        
        self.offer_message = discord.ui.TextInput(
            label="Message to Owner",
            placeholder="Optional message to include with your offer",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.add_item(self.credits_adjustment)
        self.add_item(self.offer_message)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            credits_adj = int(self.credits_adjustment.value.replace('+', '').replace(' ', ''))
        except ValueError:
            await interaction.response.send_message("Invalid credits adjustment!", ephemeral=True)
            return
        
        # Get listing owner for DM
        listing_info = self.bot.db.execute_query(
            '''SELECT sel.owner_id, s.name as ship_name
               FROM ship_exchange_listings sel
               JOIN ships s ON sel.ship_id = s.ship_id
               WHERE sel.listing_id = %s''',
            (self.listing_id,),
            fetch='one'
        )
        
        if not listing_info:
            await interaction.response.send_message("Listing not found!", ephemeral=True)
            return
        
        owner_id, target_ship_name = listing_info
        
        # Create offer (expires in 48 hours)
        offer_expires_at = datetime.now() + timedelta(hours=48)
        
        offer_id = self.bot.db.execute_query(
            '''INSERT INTO ship_exchange_offers 
               (listing_id, offerer_id, offered_ship_id, credits_adjustment, 
                offer_message, offer_expires_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING offer_id''',
            (self.listing_id, self.user_id, self.offered_ship_id, credits_adj, 
             self.offer_message.value, offer_expires_at),
            fetch='one'
        )[0]
        
        # Send DM to listing owner
        try:
            owner = self.bot.get_user(owner_id)
            if owner:
                await self.send_offer_dm(owner, offer_id, target_ship_name)
        except:
            pass  # DM failed, but offer is still recorded
        
        embed = discord.Embed(
            title="✅ Offer Submitted",
            description=f"Your offer for **{target_ship_name}** has been submitted!",
            color=0x00ff00
        )
        
        embed.add_field(name="Credits Adjustment", value=f"{credits_adj:+,}" if credits_adj != 0 else "Even trade", inline=True)
        embed.add_field(name="Expires", value=offer_expires_at.strftime("%Y-%m-%d %H:%M"), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def send_offer_dm(self, owner, offer_id: int, target_ship_name: str):
        """Send DM notification to listing owner"""
        # Get offer details
        offer_info = self.bot.db.execute_query(
            '''SELECT seo.credits_adjustment, seo.offer_message, seo.offer_expires_at,
                      s.name as offered_ship_name, s.ship_type, s.tier, s.condition_rating,
                      c.name as offerer_name
               FROM ship_exchange_offers seo
               JOIN ships s ON seo.offered_ship_id = s.ship_id
               JOIN characters c ON seo.offerer_id = c.user_id
               WHERE seo.offer_id = %s''',
            (offer_id,),
            fetch='one'
        )
        
        if not offer_info:
            return
        
        (credits_adj, message, expires_at, offered_ship_name, 
         ship_type, tier, condition, offerer_name) = offer_info
        
        embed = discord.Embed(
            title=f"💼 New Ship Exchange Offer",
            description=f"You've received an offer for your **{target_ship_name}**!",
            color=0x00ff00
        )
        
        embed.add_field(name="Offerer", value=offerer_name, inline=True)
        embed.add_field(name="Offered Ship", value=f"{offered_ship_name} ({ship_type})", inline=True)
        embed.add_field(name="Ship Details", value=f"Tier {tier} • {condition}% condition", inline=True)
        embed.add_field(name="Credits", value=f"{credits_adj:+,}" if credits_adj != 0 else "Even trade", inline=True)
        embed.add_field(name="Expires", value=expires_at[:16], inline=True)
        
        if message:
            embed.add_field(name="Message", value=message, inline=False)
        
        # Create response view
        view = OfferResponseView(self.bot, offer_id)
        
        try:
            await owner.send(embed=embed, view=view)
        except discord.Forbidden:
            pass  # User has DMs disabled


class OfferResponseView(discord.ui.View):
    """View for responding to ship exchange offers via DM"""
    def __init__(self, bot, offer_id: int):
        super().__init__(timeout=172800)  # 48 hours
        self.bot = bot
        self.offer_id = offer_id
    
    @discord.ui.button(label="Accept Offer", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_offer_response(interaction, 'accepted')
    
    @discord.ui.button(label="Decline Offer", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_offer_response(interaction, 'declined')
    
    async def process_offer_response(self, interaction: discord.Interaction, response: str):
        """Process the offer response"""
        # Get offer details
        offer_info = self.bot.db.execute_query(
            '''SELECT seo.listing_id, seo.offerer_id, seo.offered_ship_id, seo.credits_adjustment,
                      sel.ship_id as listed_ship_id, sel.owner_id, sel.listed_at_location,
                      s1.name as offered_ship_name, s2.name as listed_ship_name
               FROM ship_exchange_offers seo
               JOIN ship_exchange_listings sel ON seo.listing_id = sel.listing_id
               JOIN ships s1 ON seo.offered_ship_id = s1.ship_id
               JOIN ships s2 ON sel.ship_id = s2.ship_id
               WHERE seo.offer_id = %s AND seo.status = 'pending' ''',
            (self.offer_id,),
            fetch='one'
        )
        
        if not offer_info:
            await interaction.response.send_message("Offer not found or already processed!", ephemeral=True)
            return
        
        # Update offer status
        self.bot.db.execute_query(
            "UPDATE ship_exchange_offers SET status = %s, responded_at = NOW() WHERE offer_id = %s",
            (response, self.offer_id)
        )
        
        if response == 'accepted':
            # Execute the trade
            await self.execute_trade(interaction, offer_info)
        else:
            embed = discord.Embed(
                title="❌ Offer Declined",
                description="You have declined the ship exchange offer.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def execute_trade(self, interaction: discord.Interaction, offer_info):
        """Execute the ship exchange trade"""
        (listing_id, offerer_id, offered_ship_id, credits_adj, listed_ship_id, 
         owner_id, location_id, offered_ship_name, listed_ship_name) = offer_info
        
        try:
            # Begin database transaction
            conn = self.bot.db.begin_transaction()
            
            # Transfer ships
            self.bot.db.execute_in_transaction(conn,
                "UPDATE player_ships SET owner_id = %s WHERE ship_id = %s",
                (owner_id, offered_ship_id)
            )
            
            self.bot.db.execute_in_transaction(conn,
                "UPDATE player_ships SET owner_id = %s WHERE ship_id = %s",
                (offerer_id, listed_ship_id)
            )
            
            # Handle credits
            if credits_adj > 0:
                # Offerer pays additional credits to owner
                self.bot.db.execute_in_transaction(conn,
                    "UPDATE characters SET money = money - %s WHERE user_id = %s",
                    (abs(credits_adj), offerer_id)
                )
                self.bot.db.execute_in_transaction(conn,
                    "UPDATE characters SET money = money + %s WHERE user_id = %s",
                    (abs(credits_adj), owner_id)
                )
            elif credits_adj < 0:
                # Owner pays additional credits to offerer
                self.bot.db.execute_in_transaction(conn,
                    "UPDATE characters SET money = money + %s WHERE user_id = %s",
                    (abs(credits_adj), offerer_id)
                )
                self.bot.db.execute_in_transaction(conn,
                    "UPDATE characters SET money = money - %s WHERE user_id = %s",
                    (abs(credits_adj), owner_id)
                )
            
            # Record exchange history
            self.bot.db.execute_in_transaction(conn,
                '''INSERT INTO ship_exchange_history 
                   (original_listing_id, seller_id, buyer_id, seller_ship_id, buyer_ship_id, 
                    credits_exchanged, exchange_location)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                (listing_id, owner_id, offerer_id, listed_ship_id, offered_ship_id, 
                 credits_adj, location_id)
            )
            
            # Deactivate listing
            self.bot.db.execute_in_transaction(conn,
                "UPDATE ship_exchange_listings SET is_active = false WHERE listing_id = %s",
                (listing_id,)
            )
            
            # Commit transaction
            self.bot.db.commit_transaction(conn)
            
            embed = discord.Embed(
                title="✅ Exchange Complete!",
                description=f"Ship exchange completed successfully!",
                color=0x00ff00
            )
            
            embed.add_field(name="You Received", value=offered_ship_name, inline=True)
            embed.add_field(name="You Traded", value=listed_ship_name, inline=True)
            
            if credits_adj != 0:
                embed.add_field(
                    name="Credits", 
                    value=f"You {'received' if credits_adj < 0 else 'paid'} {abs(credits_adj):,} credits", 
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Notify offerer
            try:
                offerer = self.bot.get_user(offerer_id)
                if offerer:
                    embed_offerer = discord.Embed(
                        title="✅ Offer Accepted!",
                        description=f"Your ship exchange offer has been accepted!",
                        color=0x00ff00
                    )
                    embed_offerer.add_field(name="You Received", value=listed_ship_name, inline=True)
                    embed_offerer.add_field(name="You Traded", value=offered_ship_name, inline=True)
                    await offerer.send(embed=embed_offerer)
            except:
                pass
                
        except Exception as e:
            # Rollback transaction on error
            self.bot.db.rollback_transaction(conn)
            await interaction.response.send_message(f"Trade failed: {str(e)}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShipSystemsCog(bot))