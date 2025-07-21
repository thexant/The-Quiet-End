# cogs/creation.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import io
import zipfile
import re
import json
from datetime import datetime, timedelta
import asyncio
import math
from discord.app_commands import Choice
from typing import Optional, List


class LocationCreationModal(discord.ui.Modal):
    """Modal for additional location configuration"""
    def __init__(self, cog, location_data: dict):
        super().__init__(title="Configure Location Details")
        self.cog = cog
        self.location_data = location_data
        
        # Description field
        self.description = discord.ui.TextInput(
            label="Location Description",
            placeholder="Describe the location's atmosphere and features...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.description)
        
        # Population field
        self.population = discord.ui.TextInput(
            label="Population Size",
            placeholder="Number of inhabitants (e.g., 50000)",
            default=str(self._get_default_population()),
            required=True,
            max_length=10
        )
        self.add_item(self.population)
        
        # Number of Static NPCs
        self.npc_count = discord.ui.TextInput(
            label="Number of Static NPCs",
            placeholder="How many notable NPCs (e.g., 5-20)",
            default=str(self._get_default_npc_count()),
            required=True,
            max_length=3
        )
        self.add_item(self.npc_count)
    
    def _get_default_population(self) -> int:
        """Get default population based on location type and wealth"""
        base_pop = {
            'colony': 50000,
            'space_station': 10000,
            'outpost': 1000,
            'gate': 500
        }
        pop = base_pop.get(self.location_data['type'], 5000)
        # Adjust for wealth
        pop = int(pop * (self.location_data['wealth'] / 5))
        return pop
    
    def _get_default_npc_count(self) -> int:
        """Get default NPC count based on location type"""
        return {
            'colony': 15,
            'space_station': 12,
            'outpost': 8,
            'gate': 5
        }.get(self.location_data['type'], 10)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate and store additional data
            pop = int(self.population.value)
            if pop < 1 or pop > 10000000:
                await interaction.response.send_message("Population must be between 1 and 10,000,000", ephemeral=True)
                return
            
            npc_count = int(self.npc_count.value)
            if npc_count < 0 or npc_count > 100:
                await interaction.response.send_message("NPC count must be between 0 and 100", ephemeral=True)
                return
            
            self.location_data['description'] = self.description.value or ""
            self.location_data['population'] = pop
            self.location_data['npc_count'] = npc_count
            
            # Continue with location creation
            await self.cog._finalize_location_creation(interaction, self.location_data)
            
        except ValueError:
            await interaction.response.send_message("Invalid number format. Please enter valid numbers.", ephemeral=True)


class ServiceSelectionView(discord.ui.View):
    """View for selecting location services"""
    def __init__(self, cog, location_data: dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.location_data = location_data
        self.selected_services = set()
        
        # Available services based on location type
        services = self._get_available_services()
        
        # Create selection dropdowns
        if services:
            select_menu = discord.ui.Select(
                placeholder="Choose services for this location...",
                min_values=0,
                max_values=len(services),
                options=[
                    discord.SelectOption(
                        label=service['name'],
                        value=service['id'],
                        description=service['description'],
                        emoji=service.get('emoji', '🏪')
                    ) for service in services
                ]
            )
            select_menu.callback = self.service_callback
            self.add_item(select_menu)
    
    def _get_available_services(self) -> List[dict]:
        """Get available services based on location type"""
        location_type = self.location_data.get('type', 'outpost')
        wealth = self.location_data.get('wealth', 5)
        
        all_services = [
            {'id': 'shop', 'name': 'Trading Post', 'description': 'Buy and sell items', 'emoji': '🏪', 'min_wealth': 1},
            {'id': 'cantina', 'name': 'Cantina', 'description': 'Social hub and information', 'emoji': '🍺', 'min_wealth': 2},
            {'id': 'shipyard', 'name': 'Shipyard', 'description': 'Ship repairs and upgrades', 'emoji': '🔧', 'min_wealth': 3},
            {'id': 'housing', 'name': 'Housing', 'description': 'Player housing options', 'emoji': '🏠', 'min_wealth': 2},
            {'id': 'medical', 'name': 'Medical Bay', 'description': 'Healing and medical services', 'emoji': '🏥', 'min_wealth': 2},
            {'id': 'fuel', 'name': 'Fuel Depot', 'description': 'Refuel ships', 'emoji': '⛽', 'min_wealth': 1},
            {'id': 'jobs', 'name': 'Job Board', 'description': 'Available contracts', 'emoji': '📋', 'min_wealth': 1},
        ]
        
        # Filter services by wealth and location type
        available = []
        for service in all_services:
            if wealth >= service['min_wealth']:
                # Some restrictions by location type
                if location_type == 'gate' and service['id'] in ['housing', 'jobs']:
                    continue
                if location_type == 'outpost' and service['id'] in ['housing'] and wealth < 4:
                    continue
                available.append(service)
        
        return available
    
    async def service_callback(self, interaction: discord.Interaction):
        """Handle service selection"""
        self.selected_services = set(interaction.data['values'])
        
        selected_names = []
        for service_id in self.selected_services:
            services = self._get_available_services()
            for service in services:
                if service['id'] == service_id:
                    selected_names.append(service['name'])
                    break
        
        if selected_names:
            services_text = ", ".join(selected_names)
            await interaction.response.edit_message(
                content=f"Selected services: {services_text}\n\nReady to create location with these services?",
                view=self
            )
        else:
            await interaction.response.edit_message(
                content="No services selected. Ready to create basic location?",
                view=self
            )
    
    @discord.ui.button(label="Create Location", style=discord.ButtonStyle.primary, emoji="✅")
    async def create_location_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Finalize location creation"""
        self.location_data['services'] = list(self.selected_services)
        
        # Show the modal for additional details
        modal = LocationCreationModal(self.cog, self.location_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel location creation"""
        await interaction.response.edit_message(content="Location creation canceled.", view=None)


class CreationCog(commands.Cog):
    """Admin commands for creating game content"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    creation_group = app_commands.Group(name="create", description="Create game content (Admin only)")
    
    @creation_group.command(name="item", description="Create a new item and add to location shop or player inventory")
    @app_commands.describe(
        item_name="Name of the item",
        item_type="Type of item",
        description="Item description", 
        value="Base value of the item",
        location_name="Location to add item shop (ignored if giving to player)",
        player="Player to give item to (ignored if adding to shop)",
        price="Price in shop (ignored if giving to player)",
        stock="Stock amount for shop (ignored if giving to player)",
        quantity="Quantity to give to player (ignored if adding to shop)",
        usage_type="How the item can be used",
        effect_value="Effect value (healing amount, fuel amount, etc)",
        uses_remaining="Number of uses for multi-use items",
        rarity="Item rarity level"
    )
    @app_commands.choices(
        item_type=[
            app_commands.Choice(name="Consumable", value="consumable"),
            app_commands.Choice(name="Equipment", value="equipment"), 
            app_commands.Choice(name="Medical", value="medical"),
            app_commands.Choice(name="Fuel", value="fuel"),
            app_commands.Choice(name="Trade", value="trade"),
            app_commands.Choice(name="Upgrade", value="upgrade")
        ],
        usage_type=[
            app_commands.Choice(name="Heal HP", value="heal_hp"),
            app_commands.Choice(name="Restore Fuel", value="restore_fuel"),
            app_commands.Choice(name="Repair Hull", value="repair_hull"),
            app_commands.Choice(name="Restore Energy", value="restore_energy"),
            app_commands.Choice(name="Temporary Boost", value="temp_boost"),
            app_commands.Choice(name="Ship Upgrade", value="upgrade_ship"),
            app_commands.Choice(name="Emergency Signal", value="emergency_signal"),
            app_commands.Choice(name="Narrative Only", value="narrative"),
            app_commands.Choice(name="No Usage", value="none")
        ],
        rarity=[
            app_commands.Choice(name="Common", value="common"),
            app_commands.Choice(name="Uncommon", value="uncommon"),
            app_commands.Choice(name="Rare", value="rare"),
            app_commands.Choice(name="Legendary", value="legendary")
        ]
    )
    async def create_item(self, interaction: discord.Interaction, item_name: str, item_type: str,
                         description: str, value: int, location_name: str = None,
                         player: discord.Member = None, price: int = None, stock: int = None,
                         quantity: int = 1, usage_type: str = "none", effect_value: str = None,
                         uses_remaining: int = None, rarity: str = "common"):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not location_name and not player:
            await interaction.response.send_message("Must specify either a location or a player.", ephemeral=True)
            return
        
        if location_name and player:
            await interaction.response.send_message("Cannot specify both location and player.", ephemeral=True)
            return
        
        # Create metadata
        import json
        metadata = {
            "usage_type": usage_type if usage_type != "none" else None,
            "effect_value": effect_value,
            "single_use": True if usage_type and usage_type != "narrative" and not uses_remaining else False,
            "uses_remaining": uses_remaining,
            "rarity": rarity
        }
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        metadata_str = json.dumps(metadata)
        
        if player:
            # Give item to player
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = ?",
                (player.id,),
                fetch='one'
            )
            
            if not char_check:
                await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
                return
            
            # Add to player inventory
            existing_item = self.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
                (player.id, item_name),
                fetch='one'
            )
            
            if existing_item:
                self.db.execute_query(
                    "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
                    (quantity, existing_item[0])
                )
            else:
                self.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (player.id, item_name, item_type, quantity, description, value, metadata_str)
                )
            
            embed = discord.Embed(
                title="✅ Item Created",
                description=f"Gave {quantity}x **{item_name}** to {player.mention}",
                color=0x00ff00
            )
            embed.add_field(name="Type", value=item_type.title(), inline=True)
            embed.add_field(name="Value", value=f"{value} credits each", inline=True)
            embed.add_field(name="Usage", value=usage_type.replace('_', ' ').title() if usage_type != "none" else "No usage", inline=True)
            
        else:
            # Add to location shop
            location = self.db.execute_query(
                "SELECT location_id FROM locations WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{location_name}%",),
                fetch='one'
            )
            
            if not location:
                await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
                return
            
            location_id = location[0]
            
            # Set default price and stock if not provided
            if price is None:
                price = int(value * 1.5)  # 50% markup
            if stock is None:
                stock = 5
            
            # Check if item already exists in shop
            existing_item = self.db.execute_query(
                "SELECT item_id, stock FROM shop_items WHERE location_id = ? AND LOWER(item_name) = LOWER(?)",
                (location_id, item_name),
                fetch='one'
            )
            
            if existing_item:
                shop_item_id, current_stock = existing_item
                new_stock = current_stock + stock if current_stock != -1 else -1
                self.db.execute_query(
                    "UPDATE shop_items SET stock = ?, metadata = ? WHERE item_id = ?",
                    (new_stock, metadata_str, shop_item_id)
                )
            else:
                self.db.execute_query(
                    '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (location_id, item_name, item_type, price, stock, description, metadata_str)
                )
            
            embed = discord.Embed(
                title="✅ Item Created",
                description=f"Added **{item_name}** to shop at {location_name}",
                color=0x00ff00
            )
            embed.add_field(name="Price", value=f"{price} credits", inline=True)
            embed.add_field(name="Stock", value=str(stock), inline=True)
            embed.add_field(name="Usage", value=usage_type.replace('_', ' ').title() if usage_type != "none" else "No usage", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @creation_group.command(name="location", description="Create a custom location with full configuration")
    @app_commands.describe(
        name="Name of the location",
        location_type="Type of location",
        wealth="Wealth level 1-10",
        faction="Faction alignment",
        connect_to="Location to connect this to"
    )
    @app_commands.choices(
        location_type=[
            Choice(name="Colony", value="colony"),
            Choice(name="Space Station", value="space_station"),
            Choice(name="Outpost", value="outpost"),
            Choice(name="Gate", value="gate")
        ],
        faction=[
            Choice(name="Loyalist (Federal)", value="loyalist"),
            Choice(name="Outlaw (Bandit)", value="outlaw"),
            Choice(name="Independent", value="independent")
        ]
    )
    async def create_location(self, interaction: discord.Interaction, 
                             name: str, 
                             location_type: str,
                             wealth: app_commands.Range[int, 1, 10],
                             faction: str,
                             connect_to: str):
        """Create a fully configured custom location"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Find the connection location
        connection = self.db.execute_query(
            """SELECT location_id, name, x_coord, y_coord, location_type 
               FROM locations 
               WHERE LOWER(name) LIKE LOWER(?)""",
            (f"%{connect_to}%",),
            fetch='one'
        )
        
        if not connection:
            await interaction.response.send_message(
                f"Connection location '{connect_to}' not found.",
                ephemeral=True
            )
            return
        
        connect_id, connect_name, connect_x, connect_y, connect_type = connection
        
        # Generate coordinates near the connection
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(5, 15)
        x_coord = connect_x + distance * math.cos(angle)
        y_coord = connect_y + distance * math.sin(angle)
        
        # Prepare location data
        location_data = {
            'name': name,
            'type': location_type,
            'wealth': wealth,
            'faction': faction,
            'x_coord': x_coord,
            'y_coord': y_coord,
            'connect_to_id': connect_id,
            'connect_to_name': connect_name,
            'guild': interaction.guild,
            'user': interaction.user
        }
        
        # Show service selection view
        view = ServiceSelectionView(self, location_data)
        embed = discord.Embed(
            title="🏗️ Configure Location Services",
            description=f"Setting up **{name}** ({location_type})\n"
                        f"Wealth Level: {wealth}/10\n"
                        f"Faction: {faction.title()}\n"
                        f"Connecting to: {connect_name}",
            color=0x00ff00
        )
        embed.add_field(
            name="📋 Instructions",
            value="1. Click buttons to toggle services\n"
                  "2. Select sub-locations from dropdown\n"
                  "3. Click Continue when ready",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _finalize_location_creation(self, interaction: discord.Interaction, location_data: dict):
        """Finalize the location creation process"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Convert service list to database boolean flags
            service_list = location_data.get('services', [])
            service_flags = self._convert_services_to_flags(service_list)
            location_data['services'] = service_flags
            
            # Start transaction for safety
            conn = self.db.begin_transaction()
            
            # Create the location
            location_id = self.db.execute_in_transaction(
                conn,
                """INSERT INTO locations 
                   (name, location_type, description, wealth_level, population,
                    x_coord, y_coord,
                    has_jobs, has_shops, has_medical, has_repairs, has_fuel, 
                    has_upgrades, has_shipyard,
                    has_federal_supplies, has_black_market,
                    created_at, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 0)""",
                (
                    location_data['name'],
                    location_data['type'],
                    location_data.get('description', ''),
                    location_data['wealth'],
                    location_data.get('population', 10000),
                    location_data['x_coord'],
                    location_data['y_coord'],
                    location_data['services']['has_jobs'],
                    location_data['services']['has_shops'],
                    location_data['services']['has_medical'],
                    location_data['services']['has_repairs'],
                    location_data['services']['has_fuel'],
                    location_data['services']['has_upgrades'],
                    location_data['services']['has_shipyard'],
                    location_data['faction'] == 'loyalist',
                    location_data['faction'] == 'outlaw'
                ),
                fetch='lastrowid'
            )
            
            # Create sub-locations
            for sub_type in location_data.get('sub_locations', []):
                sub_name = self._get_sub_location_name(sub_type)
                sub_desc = self._get_sub_location_description(sub_type)
                
                self.db.execute_in_transaction(
                    conn,
                    """INSERT INTO sub_locations 
                       (parent_location_id, name, sub_type, description, is_active)
                       VALUES (?, ?, ?, ?, 1)""",
                    (location_id, sub_name, sub_type, sub_desc)
                )
            
            # Create static NPCs
            npc_count = location_data.get('npc_count', 10)
            if npc_count > 0:
                npc_cog = self.bot.get_cog('NPCCog')
                if npc_cog:
                    # Generate NPC data
                    npc_data_list = npc_cog.generate_static_npc_batch_data(
                        location_id,
                        location_data.get('population', 10000),
                        location_data['type'],
                        location_data['wealth'],
                        location_data['faction'] == 'outlaw'
                    )
                    
                    # Limit to requested count
                    npc_data_list = npc_data_list[:npc_count]
                    
                    # Insert NPCs
                    self.db.executemany_in_transaction(
                        conn,
                        """INSERT INTO static_npcs 
                           (location_id, name, age, occupation, personality, alignment, 
                            hp, max_hp, combat_rating, credits)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        npc_data_list
                    )
            
            # Create the gate if it's a gate location
            if location_data['type'] == 'gate':
                # Gates connect to themselves for the main corridor
                pass  # Gate handling is done in corridor creation
            
            # Commit the location creation
            self.db.commit_transaction(conn)
            
            # Now create corridors (outside transaction to avoid locks)
            await self._create_location_corridors(
                location_id, 
                location_data['name'],
                location_data['type'],
                location_data['connect_to_id'],
                location_data['connect_to_name'],
                location_data['x_coord'],
                location_data['y_coord']
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Location Created Successfully",
                description=f"**{location_data['name']}** has been created and integrated into the galaxy!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📍 Location Details",
                value=f"Type: {location_data['type'].replace('_', ' ').title()}\n"
                      f"Wealth: {location_data['wealth']}/10\n"
                      f"Population: {location_data.get('population', 10000):,}\n"
                      f"Faction: {location_data['faction'].title()}",
                inline=True
            )
            
            embed.add_field(
                name="🛠️ Services",
                value=self._format_services(location_data['services']),
                inline=True
            )
            
            if location_data.get('sub_locations'):
                embed.add_field(
                    name="🏢 Sub-Locations",
                    value="\n".join([f"• {self._get_sub_location_name(s)}" 
                                   for s in location_data['sub_locations']]),
                    inline=False
                )
            
            embed.add_field(
                name="🤖 NPCs",
                value=f"{location_data.get('npc_count', 0)} static NPCs created",
                inline=True
            )
            
            embed.add_field(
                name="🗺️ Connections",
                value=f"Connected to {location_data['connect_to_name']} and 2-5 other locations",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if 'conn' in locals():
                self.db.rollback_transaction(conn)
            
            await interaction.followup.send(
                f"❌ Error creating location: {str(e)}",
                ephemeral=True
            )

    async def _create_location_corridors(self, location_id: int, location_name: str, 
                                       location_type: str, connect_to_id: int, 
                                       connect_to_name: str, x: float, y: float):
        """Create corridors connecting the new location to the galaxy"""
        
        # Get connection location details
        connect_info = self.db.execute_query(
            "SELECT x_coord, y_coord, location_type FROM locations WHERE location_id = ?",
            (connect_to_id,),
            fetch='one'
        )
        
        if not connect_info:
            return
        
        cx, cy, connect_type = connect_info
        distance = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        # Create primary connection
        if location_type == 'gate' or connect_type == 'gate':
            # Create gated corridor segments
            await self._create_gated_corridor(
                location_id, location_name, location_type,
                connect_to_id, connect_to_name, connect_type,
                distance
            )
        else:
            # Create ungated corridor
            travel_time = int(distance * 60) + random.randint(300, 600)
            fuel_cost = int(distance * 2) + random.randint(10, 30)
            danger_level = min(5, max(1, int(distance / 10) + 2))
            
            # Create bidirectional corridors
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time,
                    fuel_cost, danger_level, is_active, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                (f"{location_name} - {connect_to_name} Route (Ungated)",
                 location_id, connect_to_id, travel_time, fuel_cost, danger_level)
            )
            
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time,
                    fuel_cost, danger_level, is_active, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                (f"{connect_to_name} - {location_name} Route (Ungated)",
                 connect_to_id, location_id, travel_time, fuel_cost, danger_level)
            )
        
        # Add 2-5 random connections to existing locations
        await self._add_random_connections(location_id, location_name, x, y, location_type)

    async def _create_gated_corridor(self, loc1_id: int, loc1_name: str, loc1_type: str,
                                   loc2_id: int, loc2_name: str, loc2_type: str,
                                   distance: float):
        """Create a gated corridor with all segments"""
        
        # Determine which location is the gate
        if loc1_type == 'gate':
            gate_id, gate_name = loc1_id, loc1_name
            other_id, other_name = loc2_id, loc2_name
        elif loc2_type == 'gate':
            gate_id, gate_name = loc2_id, loc2_name
            other_id, other_name = loc1_id, loc1_name
        else:
            # Neither is a gate, create a route through nearest gate
            nearest_gate = self._find_nearest_gate(loc1_id, loc2_id)
            if nearest_gate:
                gate_id, gate_name = nearest_gate
                # Create routes from both locations to the gate
                await self._create_gated_corridor(loc1_id, loc1_name, loc1_type,
                                                gate_id, gate_name, 'gate', distance/2)
                await self._create_gated_corridor(loc2_id, loc2_name, loc2_type,
                                                gate_id, gate_name, 'gate', distance/2)
                return
            else:
                # No gates available, fall back to ungated
                return
        
        # Calculate times
        approach_time = int(distance * 20) + random.randint(180, 300)
        arrival_time = approach_time
        
        # Create approach corridor
        self.db.execute_query(
            """INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time,
                fuel_cost, danger_level, is_active, is_generated)
               VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
            (f"{gate_name} Approach", other_id, gate_id, approach_time, 
             int(distance * 0.5) + 5, 1)
        )
        
        # Create arrival corridor
        self.db.execute_query(
            """INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time,
                fuel_cost, danger_level, is_active, is_generated)
               VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
            (f"{gate_name} Arrival", gate_id, other_id, arrival_time,
             int(distance * 0.5) + 5, 1)
        )
        
        # If connecting two non-gate locations through a gate, create gate-to-gate corridor
        if loc1_type != 'gate' and loc2_type != 'gate':
            # This would be handled by the recursive calls above
            pass

    async def _add_random_connections(self, location_id: int, location_name: str,
                                    x: float, y: float, location_type: str):
        """Add 2-5 random connections to nearby locations"""
        
        # Find nearby locations
        nearby = self.db.execute_query(
            """SELECT location_id, name, x_coord, y_coord, location_type
               FROM locations
               WHERE location_id != ?
               AND ABS(x_coord - ?) < 30
               AND ABS(y_coord - ?) < 30
               ORDER BY RANDOM()
               LIMIT 10""",
            (location_id, x, y),
            fetch='all'
        )
        
        if not nearby:
            return
        
        # Create 2-5 connections
        num_connections = random.randint(2, min(5, len(nearby)))
        for i in range(num_connections):
            other_id, other_name, ox, oy, other_type = nearby[i]
            
            # Check if corridor already exists
            existing = self.db.execute_query(
                """SELECT corridor_id FROM corridors
                   WHERE (origin_location = ? AND destination_location = ?)
                   OR (origin_location = ? AND destination_location = ?)""",
                (location_id, other_id, other_id, location_id),
                fetch='one'
            )
            
            if existing:
                continue
            
            distance = math.sqrt((x - ox)**2 + (y - oy)**2)
            
            # Decide corridor type
            if location_type == 'gate' or other_type == 'gate':
                await self._create_gated_corridor(
                    location_id, location_name, location_type,
                    other_id, other_name, other_type,
                    distance
                )
            else:
                # Create ungated corridor with higher danger
                travel_time = int(distance * 80) + random.randint(400, 800)
                fuel_cost = int(distance * 3) + random.randint(20, 50)
                danger_level = min(5, max(3, int(distance / 8) + 2))
                
                corridor_name = f"{location_name} - {other_name} Route"
                
                # Bidirectional
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, is_active, is_generated)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                    (f"{corridor_name} (Ungated)", location_id, other_id,
                     travel_time, fuel_cost, danger_level)
                )
                
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, is_active, is_generated)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 0)""",
                    (f"{other_name} - {location_name} Route (Ungated)", 
                     other_id, location_id, travel_time, fuel_cost, danger_level)
                )

    def _find_nearest_gate(self, loc1_id: int, loc2_id: int) -> Optional[tuple]:
        """Find the nearest gate to route through"""
        result = self.db.execute_query(
            """SELECT g.location_id, g.name
               FROM locations g
               JOIN locations l1 ON l1.location_id = ?
               JOIN locations l2 ON l2.location_id = ?
               WHERE g.location_type = 'gate'
               ORDER BY (ABS(g.x_coord - l1.x_coord) + ABS(g.y_coord - l1.y_coord) +
                        ABS(g.x_coord - l2.x_coord) + ABS(g.y_coord - l2.y_coord))
               LIMIT 1""",
            (loc1_id, loc2_id),
            fetch='one'
        )
        return result if result else None

    def _get_sub_location_name(self, sub_type: str) -> str:
        """Get the display name for a sub-location type"""
        names = {
            'administration': 'Administration',
            'market_district': 'Market District',
            'entertainment_district': 'Entertainment District',
            'industrial_zone': 'Industrial Zone',
            'medical_district': 'Medical District',
            'historical_archive': 'Historical Archive',
            'command_center': 'Command Center',
            'research_lab': 'Research Lab',
            'promenade': 'Promenade',
            'engineering_bay': 'Engineering Bay',
            'med_bay': 'Med Bay',
            'communications': 'Communications',
            'trading_post': 'Trading Post',
            'security_office': 'Security Office',
            'maintenance_bay': 'Maintenance Bay',
            'control_room': 'Control Room',
            'security_checkpoint': 'Security Checkpoint',
            'duty_free_shop': 'Duty Free Shop'
        }
        return names.get(sub_type, sub_type.replace('_', ' ').title())

    def _get_sub_location_description(self, sub_type: str) -> str:
        """Get the description for a sub-location type"""
        descriptions = {
            'administration': 'The bureaucratic heart of the location, handling permits and documentation.',
            'market_district': 'A bustling commercial area with shops and traders.',
            'entertainment_district': 'Bars, clubs, and entertainment venues for off-duty personnel.',
            'industrial_zone': 'Manufacturing and industrial facilities.',
            'medical_district': 'Advanced medical facilities and research centers.',
            'historical_archive': 'A repository of historical records and cultural artifacts.',
            'command_center': 'The strategic command hub for station operations.',
            'research_lab': 'Cutting-edge research facilities and laboratories.',
            'promenade': 'A central hub with shops, restaurants, and social spaces.',
            'engineering_bay': 'Technical workshops and engineering facilities.',
            'med_bay': 'Medical treatment and emergency care facilities.',
            'communications': 'Communication arrays and message relay systems.',
            'trading_post': 'A hub for traders and merchants.',
            'security_office': 'Local security and law enforcement headquarters.',
            'maintenance_bay': 'Repair and maintenance facilities.',
            'control_room': 'Gate operations and navigation control.',
            'security_checkpoint': 'Security screening and customs.',
            'duty_free_shop': 'Tax-free shopping for travelers.'
        }
        return descriptions.get(sub_type, f"A {sub_type.replace('_', ' ')} area.")

    def _convert_services_to_flags(self, service_list: list) -> dict:
        """Convert service list to database boolean flags"""
        # Initialize all services as False
        service_flags = {
            'has_jobs': False,
            'has_shops': False,
            'has_medical': False,
            'has_repairs': False,
            'has_fuel': False,
            'has_upgrades': False,
            'has_shipyard': False,
            'has_federal_supplies': False,
            'has_black_market': False
        }
        
        # Map service IDs to database columns
        service_mapping = {
            'jobs': 'has_jobs',
            'shop': 'has_shops',
            'medical': 'has_medical',
            'shipyard': 'has_shipyard',
            'fuel': 'has_fuel',
            'cantina': 'has_shops',  # Cantinas are considered shops
            'housing': 'has_shops'   # Housing services are handled via shops
        }
        
        # Set flags for selected services
        for service_id in service_list:
            if service_id in service_mapping:
                service_flags[service_mapping[service_id]] = True
                
        # Auto-enable repairs if shipyard is enabled
        if service_flags['has_shipyard']:
            service_flags['has_repairs'] = True
            service_flags['has_upgrades'] = True
        
        return service_flags

    def _format_services(self, services: dict) -> str:
        """Format services dictionary into a readable string"""
        active_services = []
        service_names = {
            'has_jobs': '💼 Jobs',
            'has_shops': '🛒 Shops',
            'has_medical': '⚕️ Medical',
            'has_repairs': '🔨 Repairs',
            'has_fuel': '⛽ Fuel',
            'has_upgrades': '⬆️ Upgrades',
            'has_shipyard': '🚢 Shipyard'
        }
        
        for key, name in service_names.items():
            if services.get(key, False):
                active_services.append(name)
        
        return '\n'.join(active_services) if active_services else "No services"
    
    @creation_group.command(name="corridor", description="Create a corridor between locations")
    @app_commands.describe(
        origin="Origin location name",
        destination="Destination location name", 
        corridor_name="Name of the corridor",
        travel_time="Travel time in seconds",
        fuel_cost="Fuel cost for travel",
        danger_level="Danger level 1-5"
    )
    async def create_corridor(self, interaction: discord.Interaction, origin: str, destination: str,
                             corridor_name: str, travel_time: int = 300, fuel_cost: int = 20, 
                             danger_level: int = 3):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Find locations by name (case insensitive)
        origin_loc = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)", 
            (f"%{origin}%",), 
            fetch='one'
        )
        dest_loc = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)", 
            (f"%{destination}%",), 
            fetch='one'
        )
        
        if not origin_loc:
            await interaction.response.send_message(f"Origin location '{origin}' not found.", ephemeral=True)
            return
        
        if not dest_loc:
            await interaction.response.send_message(f"Destination location '{destination}' not found.", ephemeral=True)
            return
        
        if origin_loc[0] == dest_loc[0]:
            await interaction.response.send_message("Origin and destination cannot be the same.", ephemeral=True)
            return
        
        # Check if corridor already exists
        existing = self.db.execute_query(
            '''SELECT corridor_id FROM corridors 
               WHERE origin_location = ? AND destination_location = ?''',
            (origin_loc[0], dest_loc[0]),
            fetch='one'
        )
        
        if existing:
            await interaction.response.send_message(
                f"Corridor from {origin_loc[1]} to {dest_loc[1]} already exists.",
                ephemeral=True
            )
            return
        
        # Validate parameters
        if travel_time < 60 or travel_time > 3600:
            await interaction.response.send_message("Travel time must be between 60 and 3600 seconds.", ephemeral=True)
            return
        
        if danger_level < 1 or danger_level > 5:
            await interaction.response.send_message("Danger level must be between 1 and 5.", ephemeral=True)
            return
        
        # Create corridor in both directions
        for origin_id, dest_id, orig_name, dest_name in [(origin_loc[0], dest_loc[0], origin_loc[1], dest_loc[1]),
                                                         (dest_loc[0], origin_loc[0], dest_loc[1], origin_loc[1])]:
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 0)''',
                (corridor_name, origin_id, dest_id, travel_time, fuel_cost, danger_level)
            )
        
        embed = discord.Embed(
            title="Corridor Created",
            description=f"Successfully created corridor '{corridor_name}'",
            color=0x00ff00
        )
        embed.add_field(name="Route", value=f"{origin_loc[1]} ↔ {dest_loc[1]}", inline=False)
        embed.add_field(name="Travel Time", value=f"{travel_time//60}m {travel_time%60}s", inline=True)
        embed.add_field(name="Fuel Cost", value=f"{fuel_cost} units", inline=True)
        embed.add_field(name="Danger Level", value="⚠️" * danger_level, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @creation_group.command(name="dynamic_npc", description="Manually spawn a dynamic NPC")
    async def spawn_dynamic_npc(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            await interaction.response.send_message("NPC system not available!", ephemeral=True)
            return
        
        npc_id = await npc_cog.create_dynamic_npc()
        if npc_id:
            npc_info = self.db.execute_query(
                "SELECT name, callsign, ship_name FROM dynamic_npcs WHERE npc_id = ?",
                (npc_id,),
                fetch='one'
            )
            name, callsign, ship_name = npc_info
            await interaction.response.send_message(
                f"✅ Spawned dynamic NPC: **{name}** ({callsign}) aboard *{ship_name}*",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Failed to spawn dynamic NPC", ephemeral=True)
    
    @creation_group.command(name="job", description="Create a custom job at a location")
    @app_commands.describe(
        location_name="Location where job will be posted",
        title="Job title/name",
        description="Job description and requirements",
        reward="Money reward in credits",
        duration="Duration in minutes",
        danger_level="Danger level 1-5",
        required_skill="Required skill (optional)",
        min_skill_level="Minimum skill level required",
        expires_hours="Hours until job expires"
    )
    async def create_job(self, interaction: discord.Interaction, location_name: str, title: str, 
                        description: str, reward: int, duration: int, danger_level: int,
                        required_skill: str = None, min_skill_level: int = 0, expires_hours: int = 8):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{location_name}%",),
            fetch='one'
        )
        
        if not location:
            await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
            return
        
        location_id, actual_name = location
        
        # Determine job type based on title/description
        is_travel_job = any(word in title.lower() for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger']) or any(word in description.lower() for word in ['transport', 'deliver', 'take to', 'bring to'])
        job_type = 'travel' if is_travel_job else 'stationary'
        
        expire_time = datetime.now() + timedelta(hours=expires_hours)
        
        self.db.execute_query(
            '''INSERT INTO jobs
               (location_id, title, description, reward_money, required_skill,
                min_skill_level, danger_level, duration_minutes, expires_at, is_taken)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)''',
            (
                location_id,
                title,
                description,
                reward,
                required_skill,
                min_skill_level,
                danger_level,
                duration,
                expire_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        
        embed = discord.Embed(
            title="✅ Job Created",
            description=f"Created job at **{actual_name}**",
            color=0x00ff00
        )
        embed.add_field(name="Title", value=title, inline=False)
        embed.add_field(name="Type", value=job_type.title(), inline=True)
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger_level, inline=True)
        embed.add_field(name="Expires", value=f"<t:{int(expire_time.timestamp())}:R>", inline=True)
        
        if required_skill:
            embed.add_field(name="Skill Requirement", value=f"{required_skill.title()} Level {min_skill_level}+", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @creation_group.command(name="static_npc", description="Create a static NPC at a specific location")
    @app_commands.describe(
        location_name="Location where NPC will be placed",
        name="NPC name",
        occupation="NPC occupation/role",
        personality="NPC personality description",
        age="NPC age (optional)",
        alignment="NPC alignment (loyalist, outlaw, independent)",
        combat_rating="Combat rating 1-10 (optional)"
    )
    @app_commands.choices(
        alignment=[
            Choice(name="Loyalist (Federal)", value="loyalist"),
            Choice(name="Outlaw (Bandit)", value="outlaw"),
            Choice(name="Independent", value="independent")
        ]
    )
    async def create_static_npc(self, interaction: discord.Interaction, 
                               location_name: str, name: str, occupation: str, 
                               personality: str, age: int = None, 
                               alignment: str = "independent", combat_rating: int = None):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Find location
        location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{location_name}%",),
            fetch='one'
        )
        
        if not location:
            await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
            return
        
        location_id, actual_location_name = location
        
        # Set defaults if not provided
        if age is None:
            age = random.randint(25, 65)
        
        if combat_rating is None:
            combat_rating = random.randint(1, 5)
        
        # Calculate HP based on combat rating
        max_hp = 50 + (combat_rating * 10)
        hp = max_hp
        
        # Generate credits based on occupation and location wealth
        location_wealth = self.db.execute_query(
            "SELECT wealth_level FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        base_credits = random.randint(100, 500)
        if location_wealth:
            base_credits *= location_wealth[0]
        credits = base_credits + random.randint(0, 1000)
        
        # Insert NPC into database
        self.db.execute_query(
            '''INSERT INTO static_npcs 
               (location_id, name, age, occupation, personality, alignment, 
                hp, max_hp, combat_rating, credits)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (location_id, name, age, occupation, personality, alignment,
             hp, max_hp, combat_rating, credits)
        )
        
        # Create success embed
        embed = discord.Embed(
            title="✅ Static NPC Created",
            description=f"Created **{name}** at {actual_location_name}",
            color=0x00ff00
        )
        
        embed.add_field(name="📋 Details", 
                       value=f"Age: {age}\nOccupation: {occupation}\nAlignment: {alignment.title()}", 
                       inline=True)
        
        embed.add_field(name="⚔️ Combat Stats", 
                       value=f"HP: {hp}/{max_hp}\nCombat Rating: {combat_rating}/10", 
                       inline=True)
        
        embed.add_field(name="💰 Credits", value=f"{credits:,} credits", inline=True)
        embed.add_field(name="🧠 Personality", value=personality, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CreationCog(bot))