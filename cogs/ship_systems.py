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
               WHERE c.user_id = ?''',
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
            "SELECT COUNT(*) FROM player_ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Get active ship for trade-in options
        active_ship = self.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.condition_rating, s.market_value
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = ? AND ps.is_active = 1''',
            (interaction.user.id,),
            fetch='one'
        )
        
        # Create ship browser view
        view = ShipBrowserView(self.bot, interaction.user.id, money, wealth_level, location_name, active_ship, ship_count)
        
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
    
    @ship_group.command(name="upgrade", description="Access comprehensive ship upgrade systems")
    async def ship_upgrade(self, interaction: discord.Interaction):
        """Enhanced upgrade system with components and modifications"""
        # Get character and ship info
        char_info = self.db.execute_query(
            '''SELECT c.current_location, c.money, l.has_upgrades, l.wealth_level, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
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
               WHERE ps.owner_id = ? AND ps.is_active = 1''',
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
            '''SELECT l.location_id, l.name, l.has_shipyard, l.wealth_level, c.money
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message("Location not found!", ephemeral=True)
            return
        
        location_id, location_name, has_shipyard, wealth_level, money = location_info
        
        if not has_shipyard:
            await interaction.response.send_message(f"{location_name} doesn't have a shipyard.", ephemeral=True)
            return
        
        # Get fleet overview
        fleet = self.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_type, s.tier, s.condition_rating, 
                      ps.is_active, s.market_value
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = ?
               ORDER BY ps.is_active DESC, ps.acquired_date DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        view = ShipyardHubView(self.bot, interaction.user.id, wealth_level, money, fleet)
        
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
    def __init__(self, bot, user_id: int, money: int, wealth_level: int, location_name: str, active_ship, ship_count: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.money = money
        self.wealth_level = wealth_level
        self.location_name = location_name
        self.active_ship = active_ship
        self.ship_count = ship_count
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
        """Generate ships based on category and shipyard tier"""
        from utils.ship_data import generate_random_ship_name, SHIP_TYPES
        
        ships = []
        
        # Define ship templates by category
        templates = self._get_ship_templates()
        
        # Filter by category
        if self.current_category == "all":
            available_templates = templates
        else:
            available_templates = [t for t in templates if self.current_category in t['categories']]
        
        # Filter by shipyard tier
        tier_limit = min(self.wealth_level // 2 + 1, 5)
        available_templates = [t for t in available_templates if t['tier'] <= tier_limit]
        
        # Generate ships from templates
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
            ships.append(ship)
        
        # Sort by price
        ships.sort(key=lambda x: x['price'])
        
        # Add special offers for high-tier shipyards
        if self.current_category == "special" and self.wealth_level >= 6:
            ships.extend(self._generate_special_offers())
        
        return ships
    
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
        try:
            # Deduct credits
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
            self.bot.db.execute_query(
                '''INSERT INTO ships 
                   (owner_id, name, ship_type, tier, condition_rating,
                    fuel_capacity, cargo_capacity, combat_rating, fuel_efficiency,
                    exterior_description, interior_description,
                    engine_level, hull_level, systems_level,
                    max_upgrade_slots, market_value, special_mods, current_fuel)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (self.user_id, self.ship_data['name'], ship_type, self.ship_data['tier'], 100,
                 fuel_capacity, self.ship_data['cargo_capacity'],
                 self.ship_data['combat_rating'], self.ship_data['fuel_efficiency'],
                 exterior, interior, 1, 1, 1, 3 + self.ship_data['tier'],
                 self.ship_data['price'], json.dumps([]), fuel_capacity)  # Initialize current_fuel to fuel_capacity
            )
            
            # Get new ship ID
            new_ship_id = self.bot.db.execute_query(
                "SELECT last_insert_rowid()",
                fetch='one'
            )[0]
            
            # Generate ship activities
            activity_manager = ShipActivityManager(self.bot)
            activity_manager.generate_ship_activities(new_ship_id, ship_type)
            
            # Add to player_ships
            self.bot.db.execute_query(
                '''INSERT INTO player_ships (owner_id, ship_id, is_active)
                   VALUES (?, ?, ?)''',
                (self.user_id, new_ship_id, 1 if not self.has_trade else 1)
            )
            
            # Update BOTH ship_id and active_ship_id to the new ship
            self.bot.db.execute_query(
                "UPDATE characters SET ship_id = ?, active_ship_id = ? WHERE user_id = ?",
                (new_ship_id, new_ship_id, self.user_id)
            )
            
            # Handle trade-in if applicable
            if self.has_trade:
                # Deactivate old ship
                self.bot.db.execute_query(
                    "UPDATE player_ships SET is_active = 0 WHERE owner_id = ? AND is_active = 1 AND ship_id != ?",
                    (self.user_id, new_ship_id)
                )
                
                # Remove old ship from player_ships (sold)
                active_ship = self.bot.db.execute_query(
                    "SELECT ship_id FROM player_ships WHERE owner_id = ? AND is_active = 0 ORDER BY ship_storage_id DESC LIMIT 1",
                    (self.user_id,),
                    fetch='one'
                )
                
                if active_ship:
                    self.bot.db.execute_query(
                        "DELETE FROM player_ships WHERE ship_id = ?",
                        (active_ship[0],)
                    )
                    self.bot.db.execute_query(
                        "DELETE FROM ships WHERE ship_id = ?",
                        (active_ship[0],)
                    )
            
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
                value="• Use `/ship info` to view your new ship\n• Visit the upgrade workshop to enhance it\n• Check ship activities in your interior",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
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
               WHERE ship_id = ?''',
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
               WHERE i.owner_id = ? AND i.item_type = 'ship_upgrade'
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
                f"UPDATE ships SET {component}_level = {component}_level + 1 WHERE ship_id = ?",
                (self.ship_info[0],)
            )
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
            "UPDATE ships SET special_mods = ?, used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = ?",
            (json.dumps(current_mods), self.ship_info[0])
        )
        
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
                "UPDATE ships SET condition_rating = LEAST(condition_rating + ?, 100) WHERE ship_id = ?",
                (amount, self.ship_id)
            )
            
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
            "SELECT name, ship_type FROM ships WHERE ship_id = ?",
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
            "SELECT paint_job FROM ship_customization WHERE ship_id = ?",
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
            "SELECT decals FROM ship_customization WHERE ship_id = ?",
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
            "SELECT interior_style FROM ship_customization WHERE ship_id = ?",
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
            "SELECT item_name, metadata FROM inventory WHERE item_id = ?",
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
                    "UPDATE ships SET fuel_efficiency = fuel_efficiency + ? WHERE ship_id = ?",
                    (bonus, self.ship_id)
                )
            elif upgrade_type == 'cargo_capacity':
                self.bot.db.execute_query(
                    "UPDATE ships SET cargo_capacity = cargo_capacity + ? WHERE ship_id = ?",
                    (bonus, self.ship_id)
                )
            elif upgrade_type == 'combat_rating':
                self.bot.db.execute_query(
                    "UPDATE ships SET combat_rating = combat_rating + ? WHERE ship_id = ?",
                    (bonus, self.ship_id)
                )
            
            # Remove item from inventory
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?",
                (item_id,)
            )
            
            self.bot.db.execute_query(
                "DELETE FROM inventory WHERE item_id = ? AND quantity <= 0",
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
    def __init__(self, bot, user_id: int, wealth_level: int, money: int, fleet: list):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.wealth_level = wealth_level
        self.money = money
        self.fleet = fleet
        
    @discord.ui.button(label="Browse Ships", style=discord.ButtonStyle.primary, emoji="🛒", row=0)
    async def browse_ships(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Redirect to ship purchase command
        await self.bot.get_cog('ShipSystemsCog').ship_purchase.callback(
            self.bot.get_cog('ShipSystemsCog'), interaction
        )
    
    @discord.ui.button(label="Upgrade Workshop", style=discord.ButtonStyle.primary, emoji="🔧", row=0)
    async def upgrade_workshop(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        
        await interaction.response.send_message(
            "Ship Exchange feature coming soon! Trade ships with other players.",
            ephemeral=True
        )
    
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
            "UPDATE player_ships SET is_active = 0 WHERE owner_id = ?",
            (self.user_id,)
        )
        
        # Activate the selected ship
        self.bot.db.execute_query(
            "UPDATE player_ships SET is_active = 1 WHERE owner_id = ? AND ship_id = ?",
            (self.user_id, new_ship_id)
        )
        
        # UPDATE BOTH ship_id AND active_ship_id
        self.bot.db.execute_query(
            "UPDATE characters SET ship_id = ?, active_ship_id = ? WHERE user_id = ?",
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
            description=f"Are you sure you want to sell **{ship[1]}**?",
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
        # Remove from player_ships
        self.bot.db.execute_query(
            "DELETE FROM player_ships WHERE ship_id = ? AND owner_id = ?",
            (self.ship_id, self.user_id)
        )
        
        # Delete ship
        self.bot.db.execute_query(
            "DELETE FROM ships WHERE ship_id = ?",
            (self.ship_id,)
        )
        
        # Add credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
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
            '''INSERT OR IGNORE INTO ship_customization (ship_id, paint_job, decals, interior_style)
               VALUES (?, ?, ?, ?)''',
            (self.ship_id, 'Default', 'None', 'Standard')
        )
        
        # Update paint job
        self.bot.db.execute_query(
            "UPDATE ship_customization SET paint_job = ? WHERE ship_id = ?",
            (paint_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
            '''INSERT OR IGNORE INTO ship_customization (ship_id, paint_job, decals, interior_style)
               VALUES (?, ?, ?, ?)''',
            (self.ship_id, 'Default', 'None', 'Standard')
        )
        
        # Update decals
        self.bot.db.execute_query(
            "UPDATE ship_customization SET decals = ? WHERE ship_id = ?",
            (decal_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
            '''INSERT OR IGNORE INTO ship_customization (ship_id, paint_job, decals, interior_style)
               VALUES (?, ?, ?, ?)''',
            (self.ship_id, 'Default', 'None', 'Standard')
        )
        
        # Update interior theme
        self.bot.db.execute_query(
            "UPDATE ship_customization SET interior_style = ? WHERE ship_id = ?",
            (theme_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
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
               WHERE ps.owner_id = ? AND s.name = ? AND s.ship_id != ?''',
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
            "UPDATE ships SET name = ? WHERE ship_id = ?",
            (new_name, self.ship_id)
        )
        
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
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


async def setup(bot):
    await bot.add_cog(ShipSystemsCog(bot))