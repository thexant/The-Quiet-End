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
from typing import Optional, List, Literal


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
        
        # Auto-create local gate option (only for major locations)
        if location_data['type'] in ['colony', 'space_station', 'outpost']:
            self.auto_gate = discord.ui.TextInput(
                label="Auto-create Local Gate? (yes/no)",
                placeholder="Create a local gate for easier connections? (yes/no)",
                default="yes",
                required=True,
                max_length=3
            )
            self.add_item(self.auto_gate)
        else:
            self.auto_gate = None
    
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
        pop = int(pop * (self.location_data['wealth_level'] / 5))
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
            
            # Handle auto-gate option
            if self.auto_gate:
                auto_gate_value = self.auto_gate.value.lower().strip()
                if auto_gate_value in ['yes', 'y', 'true', '1']:
                    self.location_data['create_local_gate'] = True
                elif auto_gate_value in ['no', 'n', 'false', '0']:
                    self.location_data['create_local_gate'] = False
                else:
                    await interaction.response.send_message("Auto-gate option must be 'yes' or 'no'", ephemeral=True)
                    return
            else:
                self.location_data['create_local_gate'] = False
            
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
        self.selected_sub_locations = set()
        
        # Available services based on location type
        services = self._get_available_services()
        
        # Create services selection dropdown
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
        
        # Available sub-locations based on location type and wealth
        sub_locations = self._get_available_sub_locations()
        
        # Create sub-locations selection dropdown
        if sub_locations:
            sub_select_menu = discord.ui.Select(
                placeholder="Choose sub-locations for this location...",
                min_values=0,
                max_values=min(len(sub_locations), 25),  # Discord limit of 25 options
                options=[
                    discord.SelectOption(
                        label=sub_loc['name'],
                        value=sub_loc['id'],
                        description=sub_loc['description'][:100],  # Keep under 100 chars
                        emoji=sub_loc.get('icon', '🏢')
                    ) for sub_loc in sub_locations
                ]
            )
            sub_select_menu.callback = self.sub_location_callback
            self.add_item(sub_select_menu)
    
    def _get_available_services(self) -> List[dict]:
        """Get available services based on location type"""
        location_type = self.location_data.get('type', 'outpost')
        wealth = self.location_data.get('wealth_level', 5)
        
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
    
    def _get_available_sub_locations(self) -> List[dict]:
        """Get available sub-locations based on location type and wealth"""
        location_type = self.location_data.get('type', 'outpost')
        wealth = self.location_data.get('wealth_level', 5)
        
        # Import sub-location types from utils
        try:
            from utils.sub_locations import SubLocationManager
            # Create temporary instance to access sub_location_types
            temp_manager = SubLocationManager(self.cog.bot)
            sub_location_types = temp_manager.sub_location_types
        except ImportError:
            # Fallback if import fails
            return []
        
        available_sub_locations = []
        
        for sub_type, data in sub_location_types.items():
            # Check if compatible with location type
            if location_type not in data.get('location_types', []):
                continue
            
            # Check wealth requirement
            if wealth < data.get('min_wealth', 0):
                continue
            
            # Skip derelict-only locations for non-derelict locations
            if data.get('derelict_only', False):
                continue
            
            available_sub_locations.append({
                'id': sub_type,
                'name': data['name'],
                'description': data['description'],
                'icon': data.get('icon', '🏢')
            })
        
        return available_sub_locations
    
    async def service_callback(self, interaction: discord.Interaction):
        """Handle service selection"""
        self.selected_services = set(interaction.data['values'])
        await self._update_selection_display(interaction)
    
    async def sub_location_callback(self, interaction: discord.Interaction):
        """Handle sub-location selection"""
        self.selected_sub_locations = set(interaction.data['values'])
        await self._update_selection_display(interaction)
    
    async def _update_selection_display(self, interaction: discord.Interaction):
        """Update the display to show current selections"""
        content_parts = []
        
        # Show selected services
        if self.selected_services:
            selected_names = []
            services = self._get_available_services()
            for service_id in self.selected_services:
                for service in services:
                    if service['id'] == service_id:
                        selected_names.append(service['name'])
                        break
            content_parts.append(f"**Selected services:** {', '.join(selected_names)}")
        else:
            content_parts.append("**Selected services:** None")
        
        # Show selected sub-locations
        if self.selected_sub_locations:
            selected_names = []
            sub_locations = self._get_available_sub_locations()
            for sub_id in self.selected_sub_locations:
                for sub_loc in sub_locations:
                    if sub_loc['id'] == sub_id:
                        selected_names.append(sub_loc['name'])
                        break
            content_parts.append(f"**Selected sub-locations:** {', '.join(selected_names)}")
        else:
            content_parts.append("**Selected sub-locations:** None")
        
        content_parts.append("\nReady to create location with these selections?")
        
        await interaction.response.edit_message(
            content="\n".join(content_parts),
            view=self
        )
    
    @discord.ui.button(label="Create Location", style=discord.ButtonStyle.primary, emoji="✅")
    async def create_location_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Finalize location creation"""
        self.location_data['services'] = list(self.selected_services)
        self.location_data['sub_locations'] = list(self.selected_sub_locations)
        
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
    
    def _calculate_gated_route_times(self, distance: float) -> tuple[int, int]:
        """Calculate travel times for gated routes (approach + main corridor) - 7-20 minute total limit"""
        
        # Total time budget: 7-20 minutes (420-1200 seconds)
        min_total_time = 7 * 60  # 7 minutes
        max_total_time = 20 * 60  # 20 minutes
        
        # Scale base time with distance but within constraints
        distance_factor = min(distance / 50.0, 2.0)  # Cap at 2x multiplier
        base_total_time = min_total_time + (max_total_time - min_total_time) * (distance_factor / 2.0)
        
        # Add randomization (±15%)
        variance = base_total_time * 0.15
        total_time = base_total_time + random.uniform(-variance, variance)
        
        # Clamp to 7-20 minute range
        total_time = max(min_total_time, min(max_total_time, int(total_time)))
        
        # Split into approach (30%) and main corridor (70%)
        approach_time = int(total_time * 0.3)
        main_time = int(total_time * 0.7)
        
        return approach_time, main_time

    def _calculate_ungated_route_time(self, distance: float) -> int:
        """Calculate travel time for ungated routes - 6-18 minute limit"""
        
        min_time = 6 * 60  # 6 minutes
        max_time = 18 * 60  # 18 minutes
        
        # Scale with distance
        distance_factor = min(distance / 50.0, 2.0)  # Cap at 2x multiplier
        base_time = min_time + (max_time - min_time) * (distance_factor / 2.0)
        
        # Add randomization (±30% for ungated danger)
        variance = base_time * 0.3
        ungated_time = base_time + random.uniform(-variance, variance)
        
        # Clamp to 6-18 minute range
        ungated_time = max(min_time, min(max_time, int(ungated_time)))
        
        return int(ungated_time)
    
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
        rarity="Item rarity level",
        equippable="Whether item can be equipped (for equipment type)",
        equipment_slot="Equipment slot (head, eyes, torso, arms_left, hands_both, etc)",
        stat_modifiers="Stat bonuses in format 'stat:value,stat:value' (e.g. 'defense:5,combat:2')"
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
            app_commands.Choice(name="Stat Modifier", value="stat_modifier"),
            app_commands.Choice(name="Emergency Signal", value="emergency_signal"),
            app_commands.Choice(name="Narrative Only", value="narrative"),
            app_commands.Choice(name="No Usage", value="none")
        ],
        rarity=[
            app_commands.Choice(name="Common", value="common"),
            app_commands.Choice(name="Uncommon", value="uncommon"),
            app_commands.Choice(name="Rare", value="rare"),
            app_commands.Choice(name="Legendary", value="legendary")
        ],
        equipment_slot=[
            app_commands.Choice(name="Head", value="head"),
            app_commands.Choice(name="Eyes", value="eyes"),
            app_commands.Choice(name="Torso", value="torso"),
            app_commands.Choice(name="Arms Left", value="arms_left"),
            app_commands.Choice(name="Arms Right", value="arms_right"),
            app_commands.Choice(name="Hands Left", value="hands_left"),
            app_commands.Choice(name="Hands Right", value="hands_right"),
            app_commands.Choice(name="Hands Both", value="hands_both"),
            app_commands.Choice(name="Legs Left", value="legs_left"),
            app_commands.Choice(name="Legs Right", value="legs_right"),
            app_commands.Choice(name="Legs Both", value="legs_both"),
            app_commands.Choice(name="Feet Both", value="feet_both")
        ]
    )
    async def create_item(self, interaction: discord.Interaction, item_name: str, item_type: str,
                         description: str, value: int, location_name: str = None,
                         player: discord.Member = None, price: int = None, stock: int = None,
                         quantity: int = 1, usage_type: str = "none", effect_value: str = None,
                         uses_remaining: int = None, rarity: str = "common", equippable: bool = False,
                         equipment_slot: str = None, stat_modifiers: str = None):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
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
            "rarity": rarity,
            "admin_created": True  # Mark as admin-created for shop refresh preservation
        }
        
        # Parse stat modifiers if provided
        parsed_stat_modifiers = {}
        if stat_modifiers:
            try:
                for modifier in stat_modifiers.split(','):
                    if ':' in modifier:
                        stat, value = modifier.strip().split(':', 1)
                        parsed_stat_modifiers[stat.strip()] = int(value.strip())
            except (ValueError, AttributeError):
                await interaction.response.send_message("Invalid stat_modifiers format. Use 'stat:value,stat:value' (e.g. 'defense:5,combat:2')", ephemeral=True)
                return
        
        # Add equipment metadata
        if equippable or item_type in ["equipment", "clothing"]:
            metadata["equippable"] = True
            if equipment_slot:
                metadata["equipment_slot"] = equipment_slot
            if parsed_stat_modifiers:
                metadata["stat_modifiers"] = parsed_stat_modifiers
        elif parsed_stat_modifiers:
            # For consumables with stat modifiers
            metadata["stat_modifiers"] = parsed_stat_modifiers
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        metadata_str = json.dumps(metadata)
        
        if player:
            # Give item to player
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = %s",
                (player.id,),
                fetch='one'
            )
            
            if not char_check:
                await interaction.response.send_message(f"{player.mention} doesn't have a character.", ephemeral=True)
                return
            
            # Add to player inventory
            existing_item = self.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
                (player.id, item_name),
                fetch='one'
            )
            
            if existing_item:
                self.db.execute_query(
                    "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                    (quantity, existing_item[0])
                )
            else:
                self.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata, equippable, equipment_slot, stat_modifiers)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (player.id, item_name, item_type, quantity, description, value, metadata_str, 
                     equippable or item_type in ["equipment", "clothing"], equipment_slot, json.dumps(parsed_stat_modifiers) if parsed_stat_modifiers else None)
                )
            
            embed = discord.Embed(
                title="✅ Item Created",
                description=f"Gave {quantity}x **{item_name}** to {player.mention}",
                color=0x00ff00
            )
            embed.add_field(name="Type", value=item_type.title(), inline=True)
            embed.add_field(name="Value", value=f"{value} credits each", inline=True)
            embed.add_field(name="Usage", value=usage_type.replace('_', ' ').title() if usage_type != "none" else "No usage", inline=True)
            
            if equippable or item_type in ["equipment", "clothing"]:
                embed.add_field(name="Equipment", value=f"Slot: {equipment_slot or 'Not specified'}", inline=True)
            
            if parsed_stat_modifiers:
                stat_text = ", ".join([f"{stat.title()}: +{value}" for stat, value in parsed_stat_modifiers.items()])
                embed.add_field(name="Stat Bonuses", value=stat_text, inline=False)
            
        else:
            # Add to location shop
            location = self.db.execute_query(
                "SELECT location_id FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
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
                "SELECT item_id, stock FROM shop_items WHERE location_id = %s AND LOWER(item_name) = LOWER(%s)",
                (location_id, item_name),
                fetch='one'
            )
            
            if existing_item:
                shop_item_id, current_stock = existing_item
                new_stock = current_stock + stock if current_stock != -1 else -1
                self.db.execute_query(
                    "UPDATE shop_items SET stock = %s, metadata = %s WHERE item_id = %s",
                    (new_stock, metadata_str, shop_item_id)
                )
            else:
                self.db.execute_query(
                    '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata, sold_by_player)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                    (location_id, item_name, item_type, price, stock, description, metadata_str, False)
                )
            
            embed = discord.Embed(
                title="✅ Item Created",
                description=f"Added **{item_name}** to shop at {location_name}",
                color=0x00ff00
            )
            embed.add_field(name="Price", value=f"{price} credits", inline=True)
            embed.add_field(name="Stock", value=str(stock), inline=True)
            embed.add_field(name="Usage", value=usage_type.replace('_', ' ').title() if usage_type != "none" else "No usage", inline=True)
            
            if equippable or item_type in ["equipment", "clothing"]:
                embed.add_field(name="Equipment", value=f"Slot: {equipment_slot or 'Not specified'}", inline=True)
            
            if parsed_stat_modifiers:
                stat_text = ", ".join([f"{stat.title()}: +{value}" for stat, value in parsed_stat_modifiers.items()])
                embed.add_field(name="Stat Bonuses", value=stat_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @creation_group.command(name="location", description="Create a custom location with full configuration")
    @app_commands.describe(
        name="Name of the location",
        location_type="Type of location",
        wealth="Wealth level 1-10",
        faction="Faction alignment",
        connect_to="Location to connect this to",
        system="System name (optional - will use nearest if not specified)"
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
                             connect_to: str,
                             system: str = None):
        """Create a fully configured custom location"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Find the connection location
        connection = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate, location_type, system_name 
               FROM locations 
               WHERE LOWER(name) LIKE LOWER(%s)""",
            (f"%{connect_to}%",),
            fetch='one'
        )
        
        if not connection:
            await interaction.response.send_message(
                f"Connection location '{connect_to}' not found.",
                ephemeral=True
            )
            return
        
        connect_id, connect_name, connect_x, connect_y, connect_type, connect_system = connection
        
        # Generate coordinates near the connection
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(5, 15)
        x_coordinate = connect_x + distance * math.cos(angle)
        y_coordinate = connect_y + distance * math.sin(angle)
        
        # Determine system name
        if system:
            # Use the provided system name
            system_name = system
        elif connect_system:
            # Use the connection location's system
            system_name = connect_system
        else:
            # Connection location has no system, create a new one
            galaxy_gen = self.bot.get_cog('GalaxyGeneratorCog')
            if galaxy_gen:
                system_name = f"{random.choice(galaxy_gen.location_prefixes)} System"
            else:
                system_name = f"System {random.randint(1000, 9999)}"
        
        # Prepare location data
        location_data = {
            'name': name,
            'type': location_type,
            'wealth_level': wealth,
            'faction': faction,
            'x_coordinate': x_coordinate,
            'y_coordinate': y_coordinate,
            'system_name': system_name,
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
                        f"System: {system_name}\n"
                        f"Wealth Level: {wealth}/10\n"
                        f"Faction: {faction.title()}\n"
                        f"Connecting to: {connect_name}",
            color=0x00ff00
        )
        embed.add_field(
            name="📋 Instructions",
            value="1. Select services from the first dropdown\n"
                  "2. Select sub-locations from the second dropdown\n"
                  "3. Click 'Create Location' when ready",
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
                    x_coordinate, y_coordinate, system_name,
                    has_jobs, has_shops, has_medical, has_repairs, has_fuel, 
                    has_upgrades, has_shipyard,
                    has_federal_supplies, has_black_market,
                    created_at, is_generated)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), false)""",
                (
                    location_data['name'],
                    location_data['type'],
                    location_data.get('description', ''),
                    location_data['wealth_level'],
                    location_data.get('population', 10000),
                    location_data['x_coordinate'],
                    location_data['y_coordinate'],
                    location_data['system_name'],
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
                       VALUES (%s, %s, %s, %s, true)""",
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
                        location_data['wealth_level'],
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
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        npc_data_list
                    )
            
            # Create local gate if requested
            gate_id = None
            if location_data.get('create_local_gate', False) and location_data['type'] in ['colony', 'space_station', 'outpost']:
                gate_id = await self._create_local_gate_in_transaction(conn, location_data, location_id)
            
            # Commit the location creation
            self.db.commit_transaction(conn)
            
            # Now create corridors (outside transaction to avoid locks)
            await self._create_location_corridors(
                location_id, 
                location_data['name'],
                location_data['type'],
                location_data['connect_to_id'],
                location_data['connect_to_name'],
                location_data['x_coordinate'],
                location_data['y_coordinate']
            )
            
            # If gate was created, create local space connection
            if gate_id:
                await self._create_local_gate_connection(location_id, location_data, gate_id)
            
            # Run architecture validation to ensure compliance
            validation_warnings = await self._validate_new_location_architecture(location_id)
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Location Created Successfully",
                description=f"**{location_data['name']}** has been created and integrated into the galaxy!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📍 Location Details",
                value=f"Type: {location_data['type'].replace('_', ' ').title()}\n"
                      f"System: {location_data['system_name']}\n"
                      f"Wealth: {location_data['wealth_level']}/10\n"
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
            
            # Add validation warnings if any
            if validation_warnings:
                warning_text = "\n".join([f"• {warning}" for warning in validation_warnings[:5]])  # Limit to 5 warnings
                if len(validation_warnings) > 5:
                    warning_text += f"\n• ... and {len(validation_warnings) - 5} more fixes"
                embed.add_field(
                    name="⚠️ Auto-Fixes Applied",
                    value=warning_text,
                    inline=False
                )
                embed.color = 0xffaa00  # Change to orange if warnings
            
            embed.add_field(
                name="🤖 NPCs",
                value=f"{location_data.get('npc_count', 0)} static NPCs created",
                inline=True
            )
            
            connections_text = f"Connected to {location_data['connect_to_name']} and 2-5 other locations"
            if location_data.get('create_local_gate', False) and gate_id:
                connections_text += f"\n**Local Gate Created**: {location_data['name']} Gate with local_space routes"
            
            embed.add_field(
                name="🗺️ Connections",
                value=connections_text,
                inline=False
            )
            
            # Queue galactic news for location establishment
            galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
            if galactic_news_cog:
                await galactic_news_cog.queue_news(
                    interaction.guild.id,
                    'location_establishment',
                    f"New Facility Established: {location_data['name']}",
                    f"A new {location_data['type'].replace('_', ' ')} facility has been established in "
                    f"{location_data['system_name']} System. The {location_data['faction'].title()} "
                    f"administration has confirmed the facility is now operational and open for business.",
                    location_id
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
        
        # Get connection location details including system info for route type detection
        connect_info = self.db.execute_query(
            "SELECT x_coordinate, y_coordinate, location_type, system_name FROM locations WHERE location_id = %s",
            (connect_to_id,),
            fetch='one'
        )
        
        if not connect_info:
            return
        
        cx, cy, connect_type, connect_system = connect_info
        distance = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        # Get new location's system info
        new_location_info = self.db.execute_query(
            "SELECT system_name FROM locations WHERE location_id = %s",
            (location_id,),
            fetch='one'
        )
        new_system = new_location_info[0] if new_location_info else None
        
        # Create primary connection with smart route type detection
        await self._create_smart_corridor(
            location_id, location_name, location_type, new_system,
            connect_to_id, connect_to_name, connect_type, connect_system,
            distance
        )
        
        # Add 2-5 random connections to existing locations
        await self._add_random_connections(location_id, location_name, x, y, location_type, new_system)
    
    async def _create_smart_corridor(self, loc1_id: int, loc1_name: str, loc1_type: str, loc1_system: str,
                                   loc2_id: int, loc2_name: str, loc2_type: str, loc2_system: str,
                                   distance: float):
        """Create corridor with smart route type detection based on ROUTE-LOCATION-RULES.md"""
        
        same_system = loc1_system == loc2_system
        
        # Determine corridor type based on rules
        corridor_type = self._determine_corridor_type(loc1_type, loc2_type, same_system)
        
        if corridor_type == 'local_space':
            # Local space connections (same system, short travel times)
            travel_time = random.randint(60, 180)  # 1-3 minutes for local space
            fuel_cost = random.randint(2, 8)
            danger_level = 1
            
            # Bidirectional local space routes
            route_name = f"{loc1_name} - {loc2_name} Local Space"
            self._create_corridor_with_type(
                route_name, loc1_id, loc2_id, travel_time, fuel_cost, danger_level, 'local_space'
            )
            
            reverse_route_name = f"{loc2_name} - {loc1_name} Local Space"
            self._create_corridor_with_type(
                reverse_route_name, loc2_id, loc1_id, travel_time, fuel_cost, danger_level, 'local_space'
            )
            
        elif corridor_type == 'gated':
            # Gated corridors (gate to gate connections across systems)
            await self._create_gated_corridor_with_type(
                loc1_id, loc1_name, loc1_type,
                loc2_id, loc2_name, loc2_type,
                distance
            )
            
        elif corridor_type == 'ungated':
            # Ungated corridors (direct major location connections or dangerous routes)
            travel_time = self._calculate_ungated_route_time(distance)
            fuel_cost = int(distance * 2) + random.randint(10, 30)
            danger_level = min(5, max(1, int(distance / 10) + 2))
            
            # Bidirectional ungated routes
            route_name = f"{loc1_name} - {loc2_name} Route (Ungated)"
            self._create_corridor_with_type(
                route_name, loc1_id, loc2_id, travel_time, fuel_cost, danger_level, 'ungated'
            )
            
            reverse_route_name = f"{loc2_name} - {loc1_name} Route (Ungated)"
            self._create_corridor_with_type(
                reverse_route_name, loc2_id, loc1_id, travel_time, fuel_cost, danger_level, 'ungated'
            )
    
    def _determine_corridor_type(self, loc1_type: str, loc2_type: str, same_system: bool) -> str:
        """Determine corridor type based on ROUTE-LOCATION-RULES.md"""
        
        major_types = ['colony', 'space_station', 'outpost']
        
        # Rule: Major locations should always connect to their local gates via local space routes
        if ((loc1_type in major_types and loc2_type == 'gate') or 
            (loc1_type == 'gate' and loc2_type in major_types)) and same_system:
            return 'local_space'
        
        # Rule: Gates connect to other distant gates via Gated Corridors
        if loc1_type == 'gate' and loc2_type == 'gate' and not same_system:
            return 'gated'
        
        # Rule: Gates in same system connect via local_space
        if loc1_type == 'gate' and loc2_type == 'gate' and same_system:
            return 'local_space'
        
        # Rule: Major location should NEVER connect to any of its local gates via a corridor
        # (This is handled by the local_space case above)
        
        # Rule: Ungated corridors can connect major locations, gates, etc
        # All other connections default to ungated
        return 'ungated'
    
    def _create_corridor_with_type(self, name: str, origin_id: int, dest_id: int, 
                                 travel_time: int, fuel_cost: int, danger_level: int, corridor_type: str):
        """Create a single corridor with proper corridor_type field"""
        self.db.execute_query(
            """INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time,
                fuel_cost, danger_level, corridor_type, is_active, is_generated)
               VALUES (%s, %s, %s, %s, %s, %s, %s, true, false)""",
            (name, origin_id, dest_id, travel_time, fuel_cost, danger_level, corridor_type)
        )

    async def _create_gated_corridor_with_type(self, loc1_id: int, loc1_name: str, loc1_type: str,
                                              loc2_id: int, loc2_name: str, loc2_type: str,
                                              distance: float):
        """Create a gated corridor with proper corridor_type field"""
        
        # For gate-to-gate connections, create a single gated corridor
        if loc1_type == 'gate' and loc2_type == 'gate':
            travel_time = self._calculate_ungated_route_time(distance)  # Use similar timing
            fuel_cost = int(distance * 1.5) + random.randint(15, 35)  # Slightly less fuel than ungated
            danger_level = max(1, min(4, int(distance / 15) + 1))  # Lower danger than ungated
            
            # Bidirectional gated corridors
            route_name = f"{loc1_name} - {loc2_name} Gated Corridor"
            self._create_corridor_with_type(
                route_name, loc1_id, loc2_id, travel_time, fuel_cost, danger_level, 'gated'
            )
            
            reverse_route_name = f"{loc2_name} - {loc1_name} Gated Corridor"
            self._create_corridor_with_type(
                reverse_route_name, loc2_id, loc1_id, travel_time, fuel_cost, danger_level, 'gated'
            )
            return
        
        # For other gated connections, fall back to original logic but with corridor_type
        # Determine which location is the gate
        if loc1_type == 'gate':
            gate_id, gate_name = loc1_id, loc1_name
            other_id, other_name = loc2_id, loc2_name
        elif loc2_type == 'gate':
            gate_id, gate_name = loc2_id, loc2_name
            other_id, other_name = loc1_id, loc1_name
        else:
            # Neither is a gate, create ungated corridor instead
            travel_time = self._calculate_ungated_route_time(distance)
            fuel_cost = int(distance * 2) + random.randint(10, 30)
            danger_level = min(5, max(1, int(distance / 10) + 2))
            
            route_name = f"{loc1_name} - {loc2_name} Route (Ungated)"
            self._create_corridor_with_type(
                route_name, loc1_id, loc2_id, travel_time, fuel_cost, danger_level, 'ungated'
            )
            
            reverse_route_name = f"{loc2_name} - {loc1_name} Route (Ungated)"
            self._create_corridor_with_type(
                reverse_route_name, loc2_id, loc1_id, travel_time, fuel_cost, danger_level, 'ungated'
            )
            return
        
        # Calculate times using galaxy generator's gated route calculation
        approach_time, arrival_time = self._calculate_gated_route_times(distance)
        
        # Create approach corridor (typically local_space for major-to-gate)
        self._create_corridor_with_type(
            f"{gate_name} Approach", other_id, gate_id, approach_time, 
            int(distance * 0.5) + 5, 1, 'local_space'
        )
        
        # Create arrival corridor (typically local_space for gate-to-major)
        self._create_corridor_with_type(
            f"{gate_name} Arrival", gate_id, other_id, arrival_time,
            int(distance * 0.5) + 5, 1, 'local_space'
        )
    
    # Keep the old function for backward compatibility, but mark as deprecated
    async def _create_gated_corridor(self, loc1_id: int, loc1_name: str, loc1_type: str,
                                   loc2_id: int, loc2_name: str, loc2_type: str,
                                   distance: float):
        """[DEPRECATED] Create a gated corridor - use _create_gated_corridor_with_type instead"""
        await self._create_gated_corridor_with_type(loc1_id, loc1_name, loc1_type,
                                                   loc2_id, loc2_name, loc2_type, distance)

    async def _add_random_connections(self, location_id: int, location_name: str,
                                    x: float, y: float, location_type: str, location_system: str):
        """Add 2-5 random connections to nearby locations with smart route typing"""
        
        # Find nearby locations with system info
        nearby = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate, location_type, system_name
               FROM locations
               WHERE location_id != %s
               AND ABS(x_coordinate - %s) < 30
               AND ABS(y_coordinate - %s) < 30
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
            other_id, other_name, ox, oy, other_type, other_system = nearby[i]
            
            # Check if corridor already exists
            existing = self.db.execute_query(
                """SELECT corridor_id FROM corridors
                   WHERE (origin_location = %s AND destination_location = %s)
                   OR (origin_location = %s AND destination_location = %s)""",
                (location_id, other_id, other_id, location_id),
                fetch='one'
            )
            
            if existing:
                continue
            
            distance = math.sqrt((x - ox)**2 + (y - oy)**2)
            
            # Use smart corridor creation with proper route typing
            await self._create_smart_corridor(
                location_id, location_name, location_type, location_system,
                other_id, other_name, other_type, other_system,
                distance
            )

    def _find_nearest_gate(self, loc1_id: int, loc2_id: int) -> Optional[tuple]:
        """Find the nearest gate to route through"""
        result = self.db.execute_query(
            """SELECT g.location_id, g.name
               FROM locations g
               JOIN locations l1 ON l1.location_id = %s
               JOIN locations l2 ON l2.location_id = %s
               WHERE g.location_type = 'gate'
               ORDER BY (ABS(g.x_coordinate - l1.x_coordinate) + ABS(g.y_coordinate - l1.y_coordinate) +
                        ABS(g.x_coordinate - l2.x_coordinate) + ABS(g.y_coordinate - l2.y_coordinate))
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
        route_type="Type of route: gated (safe), local_space (short range), ungated (dangerous)",
        travel_time="Travel time in seconds",
        fuel_cost="Fuel cost for travel",
        danger_level="Danger level 1-5"
    )
    async def create_corridor(self, interaction: discord.Interaction, origin: str, destination: str,
                             corridor_name: str, route_type: Literal["gated", "local_space", "ungated"] = "gated",
                             travel_time: int = 300, fuel_cost: int = 20, danger_level: int = 3):
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Find locations by name (case insensitive) and get their types
        origin_loc = self.db.execute_query(
            "SELECT location_id, name, location_type, system_name FROM locations WHERE LOWER(name) LIKE LOWER(%s)", 
            (f"%{origin}%",), 
            fetch='one'
        )
        dest_loc = self.db.execute_query(
            "SELECT location_id, name, location_type, system_name FROM locations WHERE LOWER(name) LIKE LOWER(%s)", 
            (f"%{destination}%",), 
            fetch='one'
        )
        
        if not origin_loc:
            await interaction.followup.send(f"Origin location '{origin}' not found.", ephemeral=True)
            return
        
        if not dest_loc:
            await interaction.followup.send(f"Destination location '{destination}' not found.", ephemeral=True)
            return
        
        if origin_loc[0] == dest_loc[0]:
            await interaction.followup.send("Origin and destination cannot be the same.", ephemeral=True)
            return

        # Auto-detect route type if user selected "gated" as default but locations suggest otherwise
        origin_id, origin_name, origin_type, origin_system = origin_loc
        dest_id, dest_name, dest_type, dest_system = dest_loc
        
        # Auto-detection logic based on location relationships
        major_types = {'colony', 'space_station', 'outpost'}
        same_system = origin_system == dest_system
        is_major_to_gate = (origin_type in major_types and dest_type == 'gate') or (origin_type == 'gate' and dest_type in major_types)
        
        # If route_type is default "gated", suggest better type based on locations
        if route_type == "gated":
            if is_major_to_gate and same_system and travel_time <= 300:
                # Short route between major location and gate in same system = local space
                suggested_type = "local_space"
                await interaction.followup.send(
                    f"💡 **Auto-detection**: Route between {origin_type} and {dest_type} in same system suggests **local_space** route type.",
                    ephemeral=True
                )
                route_type = suggested_type
        
        # Check if corridor already exists
        existing = self.db.execute_query(
            '''SELECT corridor_id FROM corridors 
               WHERE origin_location = %s AND destination_location = %s''',
            (origin_id, dest_id),
            fetch='one'
        )
        
        if existing:
            await interaction.followup.send(
                f"Corridor from {origin_name} to {dest_name} already exists.",
                ephemeral=True
            )
            return
        
        # Validate parameters
        if travel_time < 60 or travel_time > 3600:
            await interaction.followup.send("Travel time must be between 60 and 3600 seconds.", ephemeral=True)
            return
        
        if danger_level < 1 or danger_level > 5:
            await interaction.followup.send("Danger level must be between 1 and 5.", ephemeral=True)
            return
        
        # Apply route type specific naming conventions and create corridors
        if route_type == "local_space":
            # Local space routes get "Local Space" or "Approach" in name if not already present
            if "Local Space" not in corridor_name and "Approach" not in corridor_name:
                corridor_name = f"Local Space - {corridor_name}"
        elif route_type == "ungated":
            # Ungated routes get "Ungated" in name if not already present
            if "Ungated" not in corridor_name:
                corridor_name = f"Ungated {corridor_name}"
        elif route_type == "gated":
            # For gated routes, use the existing _create_gated_corridor method if available
            # Get coordinates to calculate distance
            origin_coords = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
                (origin_id,), fetch='one'
            )
            dest_coords = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate FROM locations WHERE location_id = %s", 
                (dest_id,), fetch='one'
            )
            
            if origin_coords and dest_coords:
                ox, oy = origin_coords
                dx, dy = dest_coords
                distance = math.sqrt((ox - dx)**2 + (oy - dy)**2)
                
                await self._create_gated_corridor(origin_id, origin_name, origin_type,
                                                dest_id, dest_name, dest_type, distance)
                
                # Calculate route emoji for display
                route_emoji = "🔵"  # Gated
                
                embed = discord.Embed(
                    title="Gated Corridor Created",
                    description=f"Successfully created gated corridor system '{corridor_name}'",
                    color=0x00ff00
                )
                embed.add_field(name="Route", value=f"{origin_name} ↔ {dest_name}", inline=False)
                embed.add_field(name="Type", value=f"{route_emoji} Gated Corridor", inline=True)
                embed.add_field(name="Distance", value=f"{distance:.1f} AU", inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Create standard corridor in both directions for non-gated routes
        for curr_origin_id, curr_dest_id, curr_orig_name, curr_dest_name in [(origin_id, dest_id, origin_name, dest_name),
                                                                            (dest_id, origin_id, dest_name, origin_name)]:
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, is_generated)
                   VALUES (%s, %s, %s, %s, %s, %s, 0)''',
                (corridor_name, curr_origin_id, curr_dest_id, travel_time, fuel_cost, danger_level)
            )
        
        # Determine route emoji for display
        route_emojis = {
            "gated": "🔵",
            "local_space": "🌌", 
            "ungated": "⭕"
        }
        route_emoji = route_emojis.get(route_type, "🔵")
        
        embed = discord.Embed(
            title="Corridor Created",
            description=f"Successfully created corridor '{corridor_name}'",
            color=0x00ff00
        )
        embed.add_field(name="Route", value=f"{origin_name} ↔ {dest_name}", inline=False)
        embed.add_field(name="Type", value=f"{route_emoji} {route_type.replace('_', ' ').title()}", inline=True)
        embed.add_field(name="Travel Time", value=f"{travel_time//60}m {travel_time%60}s", inline=True)
        embed.add_field(name="Fuel Cost", value=f"{fuel_cost} units", inline=True)
        embed.add_field(name="Danger Level", value="⚠️" * danger_level, inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @creation_group.command(name="delete_corridor", description="Delete a corridor by name (handles all types)")
    @app_commands.describe(corridor_name="Name of the corridor to delete (partial match supported)")
    async def delete_corridor(self, interaction: discord.Interaction, corridor_name: str):
        """Delete a corridor by name, handling all types (gated, ungated, local space)"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Find corridors matching the name (case-insensitive partial match)
        matching_corridors = self.db.execute_query(
            """SELECT c.corridor_id, c.name, c.origin_location, c.destination_location, 
                      ol.name as origin_name, dl.name as dest_name, c.is_active
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE LOWER(c.name) LIKE LOWER(%s)
               ORDER BY c.name""",
            (f"%{corridor_name}%",),
            fetch='all'
        )
        
        if not matching_corridors:
            await interaction.followup.send(
                f"❌ No corridors found matching '{corridor_name}'.", 
                ephemeral=True
            )
            return
        
        # Show matching corridors for confirmation
        if len(matching_corridors) > 10:
            await interaction.followup.send(
                f"❌ Too many matches ({len(matching_corridors)}). Please be more specific.", 
                ephemeral=True
            )
            return
        
        # Prepare confirmation embed
        embed = discord.Embed(
            title="🗑️ Corridor Deletion Confirmation",
            description=f"Found {len(matching_corridors)} corridor(s) matching '{corridor_name}':",
            color=0xff6600
        )
        
        corridors_to_delete = []
        for corridor_id, name, origin_id, dest_id, origin_name, dest_name, is_active in matching_corridors:
            status = "🟢 Active" if is_active else "🔴 Inactive"
            corridors_to_delete.append(corridor_id)
            embed.add_field(
                name=f"{name}",
                value=f"{origin_name} ↔ {dest_name}\n{status}",
                inline=False
            )
        
        # Check for travelers in these corridors
        travelers_affected = []
        for corridor_id in corridors_to_delete:
            # Check for players traveling through this corridor
            player_travelers = self.db.execute_query(
                """SELECT ts.user_id, c.name, ch.name as char_name, ts.temp_channel_id
                   FROM travel_sessions ts
                   JOIN corridors c ON ts.corridor_id = c.corridor_id  
                   JOIN characters ch ON ts.user_id = ch.user_id
                   WHERE ts.corridor_id = %s AND ts.status = 'traveling'""",
                (corridor_id,),
                fetch='all'
            )
            
            # Check for NPCs traveling through this corridor
            npc_travelers = self.db.execute_query(
                """SELECT n.npc_id, n.name, n.callsign, c.name as corridor_name
                   FROM dynamic_npcs n
                   JOIN corridors c ON (
                       (n.current_location = c.origin_location AND n.destination_location = c.destination_location) OR
                       (n.current_location = c.destination_location AND n.destination_location = c.origin_location)
                   )
                   WHERE c.corridor_id = %s AND n.travel_start_time IS NOT NULL AND n.is_alive = TRUE""",
                (corridor_id,),
                fetch='all'
            )
            
            travelers_affected.extend([(t, 'player') for t in player_travelers])
            travelers_affected.extend([(t, 'npc') for t in npc_travelers])
        
        if travelers_affected:
            traveler_names = []
            for traveler_data, traveler_type in travelers_affected:
                if traveler_type == 'player':
                    _, _, char_name, _ = traveler_data
                    traveler_names.append(f"👤 {char_name}")
                else:  # NPC
                    _, npc_name, callsign, _ = traveler_data
                    traveler_names.append(f"🤖 {npc_name} ({callsign})")
            
            embed.add_field(
                name="⚠️ Travelers Affected",
                value=f"**{len(travelers_affected)} travelers will be killed:**\n" + "\n".join(traveler_names[:10]) + 
                      (f"\n... and {len(traveler_names)-10} more" if len(traveler_names) > 10 else ""),
                inline=False
            )
        
        embed.add_field(
            name="⚠️ Warning",
            value="This action cannot be undone! All travelers in these corridors will be killed.",
            inline=False
        )
        
        # Create confirmation view
        class DeleteConfirmationView(discord.ui.View):
            def __init__(self, cog, corridors_to_delete, travelers_affected):
                super().__init__(timeout=60)
                self.cog = cog
                self.corridors_to_delete = corridors_to_delete
                self.travelers_affected = travelers_affected
            
            @discord.ui.button(label="🗑️ Delete Corridors", style=discord.ButtonStyle.danger)
            async def confirm_delete(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                await button_interaction.response.defer()
                
                deleted_count = 0
                killed_count = 0
                
                # Kill travelers first (like corridor collapse)
                for traveler_data, traveler_type in self.travelers_affected:
                    if traveler_type == 'player':
                        user_id, corridor_name, char_name, temp_channel_id = traveler_data
                        # Use the same logic as corridor collapse
                        events_cog = self.cog.bot.get_cog('EventsCog')
                        if events_cog:
                            await events_cog._handle_traveler_in_collapse(
                                user_id, temp_channel_id, char_name, corridor_name
                            )
                        killed_count += 1
                    else:  # NPC
                        npc_id, npc_name, callsign, corridor_name = traveler_data
                        # Kill the NPC
                        self.cog.db.execute_query(
                            "UPDATE dynamic_npcs SET is_alive = false WHERE npc_id = %s",
                            (npc_id,)
                        )
                        # Log NPC death
                        print(f"💀 NPC {npc_name} ({callsign}) killed in manual corridor deletion: {corridor_name}")
                        killed_count += 1
                
                # Delete corridors and clean up related data
                for corridor_id in self.corridors_to_delete:
                    # Clean up travel sessions
                    self.cog.db.execute_query(
                        "DELETE FROM travel_sessions WHERE corridor_id = %s",
                        (corridor_id,)
                    )
                    
                    # Clean up corridor events (corridor_events are linked to transit channels, not corridor IDs directly)
                    # Events are automatically cleaned up when travel sessions are deleted above
                    
                    # Delete the corridor itself
                    self.cog.db.execute_query(
                        "DELETE FROM corridors WHERE corridor_id = %s",
                        (corridor_id,)
                    )
                    deleted_count += 1
                
                # Send success message
                success_embed = discord.Embed(
                    title="✅ Corridor Deletion Complete",
                    description=f"Successfully deleted {deleted_count} corridor(s)",
                    color=0x00ff00
                )
                
                if killed_count > 0:
                    success_embed.add_field(
                        name="💀 Casualties",
                        value=f"{killed_count} traveler(s) were killed in the process",
                        inline=False
                    )
                
                success_embed.add_field(
                    name="🧹 Cleanup",
                    value="All related travel sessions and corridor events have been removed",
                    inline=False
                )
                
                await button_interaction.followup.send(embed=success_embed, ephemeral=True)
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_delete(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                cancel_embed = discord.Embed(
                    title="❌ Deletion Cancelled",
                    description="No corridors were deleted.",
                    color=0x808080
                )
                await button_interaction.response.send_message(embed=cancel_embed, ephemeral=True)
        
        view = DeleteConfirmationView(self, corridors_to_delete, travelers_affected)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @creation_group.command(name="dynamic_npc", description="Manually spawn a dynamic NPC")
    async def spawn_dynamic_npc(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            await interaction.response.send_message("NPC system not available!", ephemeral=True)
            return
        
        npc_id = await npc_cog.create_dynamic_npc()
        if npc_id:
            npc_info = self.db.execute_query(
                "SELECT name, callsign, ship_name FROM dynamic_npcs WHERE npc_id = %s",
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
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
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
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)''',
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
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Find location
        location = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
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
            "SELECT wealth_level FROM locations WHERE location_id = %s",
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
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
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
    
    @creation_group.command(name="random_location", description="Create a random location with auto-generated details")
    @app_commands.describe(
        location_type="Type of location to generate",
        connect_to="Location to connect this to (optional - will find closest if not specified)"
    )
    @app_commands.choices(
        location_type=[
            Choice(name="Colony", value="colony"),
            Choice(name="Space Station", value="space_station"),
            Choice(name="Outpost", value="outpost"),
            Choice(name="Gate", value="gate")
        ]
    )
    async def create_random_location(self, interaction: discord.Interaction, 
                                   location_type: str,
                                   connect_to: str = None):
        """Create a fully randomized location using galaxy generator logic"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get galaxy generator for location creation logic
            galaxy_gen = self.bot.get_cog('GalaxyGeneratorCog')
            if not galaxy_gen:
                await interaction.followup.send("❌ Galaxy generator not available.", ephemeral=True)
                return
            
            # Generate random location data using galaxy generator logic
            from datetime import datetime
            import random
            
            # Create location name using galaxy generator name lists
            prefix = random.choice(galaxy_gen.location_prefixes)
            suffix = random.choice(galaxy_gen.location_names)
            location_name = f"{prefix} {suffix}"
            
            # Generate establishment date
            current_year = datetime.now().year
            establishment_year = random.randint(current_year - 200, current_year - 5)
            establishment_date = f"{establishment_year}"
            
            # Generate system name (simplified version)
            system_name = f"{random.choice(galaxy_gen.location_prefixes)} System"
            
            # Find connection location first to determine positioning
            connection_id = None
            connection_info = None
            if connect_to:
                connection_info = self.db.execute_query(
                    """SELECT location_id, name, x_coordinate, y_coordinate, location_type, system_name
                       FROM locations 
                       WHERE LOWER(name) LIKE LOWER(%s)""",
                    (f"%{connect_to}%",),
                    fetch='one'
                )
                if not connection_info:
                    await interaction.followup.send(
                        f"Connection location '{connect_to}' not found. Will connect to nearest location instead.",
                        ephemeral=True
                    )
                else:
                    connection_id = connection_info[0]

            # If no specific connection, use galaxy generator's default location creation logic
            if not connection_info:
                location_data = galaxy_gen._create_location_data(
                    location_name, location_type, system_name, establishment_date
                )
            else:
                # Extract connection details
                conn_id, conn_name, conn_x, conn_y, conn_type, conn_system = connection_info
                
                # Check if this involves gates and should use same system + nearby coordinates
                if location_type == 'gate' or conn_type == 'gate':
                    # Gates and gate-connected locations should be in same system with nearby coordinates
                    system_name = conn_system if conn_system else system_name
                    
                    # Generate nearby coordinates (within local space range)
                    angle = random.uniform(0, 2 * math.pi)
                    distance = random.uniform(2, 8)  # Closer for local space connections
                    x_coordinate = conn_x + distance * math.cos(angle)
                    y_coordinate = conn_y + distance * math.sin(angle)
                    
                    # Use galaxy generator for other properties but override coordinates and system
                    location_data = galaxy_gen._create_location_data(
                        location_name, location_type, system_name, establishment_date
                    )
                    location_data['x_coordinate'] = x_coordinate
                    location_data['y_coordinate'] = y_coordinate
                    location_data['system_name'] = system_name
                else:
                    # Normal location creation logic
                    location_data = galaxy_gen._create_location_data(
                        location_name, location_type, system_name, establishment_date
                    )
            
            # If no specific connection, find nearest location and potentially adjust positioning
            if not connection_id:
                nearest = self.db.execute_query(
                    """SELECT location_id, name, x_coordinate, y_coordinate, location_type, system_name,
                       SQRT(POWER(x_coordinate - %s, 2) + POWER(y_coordinate - %s, 2)) as distance
                       FROM locations 
                       ORDER BY distance 
                       LIMIT 1""",
                    (location_data['x_coordinate'], location_data['y_coordinate']),
                    fetch='one'
                )
                if nearest:
                    connection_id = nearest[0]
                    connect_to = nearest[1]
                    nearest_x, nearest_y, nearest_type, nearest_system = nearest[2], nearest[3], nearest[4], nearest[5]
                    
                    # If this involves gates, adjust positioning to be in same system and nearby
                    if location_type == 'gate' or nearest_type == 'gate':
                        system_name = nearest_system if nearest_system else location_data['system_name']
                        
                        # Generate nearby coordinates for gate connections
                        angle = random.uniform(0, 2 * math.pi)
                        distance = random.uniform(2, 8)  # Closer for local space connections
                        x_coordinate = nearest_x + distance * math.cos(angle)
                        y_coordinate = nearest_y + distance * math.sin(angle)
                        
                        # Update location data
                        location_data['x_coordinate'] = x_coordinate
                        location_data['y_coordinate'] = y_coordinate
                        location_data['system_name'] = system_name
            
            if not connection_id:
                await interaction.followup.send("❌ No existing locations found to connect to.", ephemeral=True)
                return
            
            # Start transaction for safe creation
            conn = self.db.begin_transaction()
            
            # Create the location in database
            location_id = self.db.execute_in_transaction(
                conn,
                """INSERT INTO locations 
                   (name, location_type, description, wealth_level, population,
                    x_coordinate, y_coordinate, system_name,
                    has_jobs, has_shops, has_medical, has_repairs, has_fuel, 
                    has_upgrades, has_shipyard, has_federal_supplies, has_black_market,
                    created_at, is_generated, is_derelict)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 1, %s)""",
                (
                    location_data['name'],
                    location_data['type'],
                    location_data['description'],
                    location_data['wealth_level'],
                    location_data['population'],
                    location_data['x_coordinate'],
                    location_data['y_coordinate'],
                    location_data['system_name'],
                    location_data['has_jobs'],
                    location_data['has_shops'],
                    location_data['has_medical'],
                    location_data['has_repairs'],
                    location_data['has_fuel'],
                    location_data['has_upgrades'],
                    location_data['has_shipyard'],
                    location_data['has_federal_supplies'],
                    location_data['has_black_market'],
                    location_data.get('is_derelict', False)
                ),
                fetch='lastrowid'
            )
            
            # Generate sub-locations using existing logic
            if location_data['wealth_level'] > 0:  # Only for non-derelict locations
                try:
                    from utils.sub_locations import SubLocationManager
                    sub_manager = SubLocationManager(self.bot)
                    
                    generated_subs = await sub_manager.get_persistent_sub_locations_data(
                        location_id,
                        location_data['type'],
                        location_data['wealth_level'],
                        location_data.get('is_derelict', False)
                    )
                    
                    if generated_subs:
                        query = '''INSERT INTO sub_locations 
                                  (parent_location_id, name, sub_type, description, is_active)
                                  VALUES (%s, %s, %s, %s, true)'''
                        self.db.executemany_in_transaction(conn, query, generated_subs)
                
                except ImportError:
                    pass  # Sub-location system not available
            
            # Generate static NPCs
            npc_count = self._get_default_npc_count_for_type(location_data['type'])
            if npc_count > 0 and location_data['wealth_level'] > 0:
                npc_cog = self.bot.get_cog('NPCCog')
                if npc_cog:
                    try:
                        npc_data_list = npc_cog.generate_static_npc_batch_data(
                            location_id,
                            location_data['population'],
                            location_data['type'],
                            location_data['wealth_level'],
                            location_data.get('has_black_market', False)
                        )
                        
                        npc_data_list = npc_data_list[:npc_count]
                        
                        if npc_data_list:
                            self.db.executemany_in_transaction(
                                conn,
                                """INSERT INTO static_npcs 
                                   (location_id, name, age, occupation, personality, alignment, 
                                    hp, max_hp, combat_rating, credits)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                npc_data_list
                            )
                    except Exception as e:
                        print(f"Warning: Could not generate NPCs: {e}")
            
            # Commit location creation
            self.db.commit_transaction(conn)
            
            # Create corridors (outside transaction to avoid locks)
            await self._create_random_location_corridors(
                location_id, location_data['name'], location_data['type'],
                connection_id, connect_to,
                location_data['x_coordinate'], location_data['y_coordinate']
            )
            
            # Queue galactic news
            await self._queue_location_establishment_news(
                location_id, location_data['name'], location_data['type']
            )
            
            # Create success embed
            embed = discord.Embed(
                title="🌟 Random Location Created",
                description=f"**{location_data['name']}** has been randomly generated and added to the galaxy!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📍 Location Details",
                value=f"Type: {location_data['type'].replace('_', ' ').title()}\n"
                      f"System: {location_data['system_name']}\n"
                      f"Wealth: {location_data['wealth_level']}/10\n"
                      f"Population: {location_data['population']:,}",
                inline=True
            )
            
            services = []
            service_map = {
                'has_jobs': '💼 Jobs',
                'has_shops': '🛒 Shops', 
                'has_medical': '⚕️ Medical',
                'has_repairs': '🔨 Repairs',
                'has_fuel': '⛽ Fuel',
                'has_upgrades': '⬆️ Upgrades',
                'has_shipyard': '🚢 Shipyard'
            }
            
            for key, emoji_name in service_map.items():
                if location_data.get(key, False):
                    services.append(emoji_name)
            
            embed.add_field(
                name="🛠️ Services",
                value='\n'.join(services) if services else "No services",
                inline=True
            )
            
            embed.add_field(
                name="🤖 NPCs",
                value=f"{npc_count} static NPCs created",
                inline=True
            )
            
            embed.add_field(
                name="🗺️ Connection",
                value=f"Connected to {connect_to}",
                inline=False
            )
            
            if location_data.get('is_derelict'):
                embed.add_field(
                    name="💀 Status",
                    value="**DERELICT** - This location is abandoned and dangerous",
                    inline=False
                )
            
            embed.add_field(
                name="📰 News",
                value="Galactic news about this location's establishment has been queued for delivery",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if 'conn' in locals():
                self.db.rollback_transaction(conn)
            
            await interaction.followup.send(
                f"❌ Error creating random location: {str(e)}",
                ephemeral=True
            )
    
    def _get_default_npc_count_for_type(self, location_type: str) -> int:
        """Get default NPC count based on location type"""
        return {
            'colony': 15,
            'space_station': 12,
            'outpost': 8,
            'gate': 5
        }.get(location_type, 10)
    
    async def _create_random_location_corridors(self, location_id: int, location_name: str, 
                                              location_type: str, connect_to_id: int, 
                                              connect_to_name: str, x: float, y: float):
        """Create corridors connecting the random location to nearby locations"""
        
        # Get connection location details
        connect_info = self.db.execute_query(
            "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s",
            (connect_to_id,),
            fetch='one'
        )
        
        if not connect_info:
            return
        
        cx, cy, connect_type = connect_info
        distance = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        # Create primary connection using similar logic to existing system
        if location_type == 'gate' or connect_type == 'gate':
            # Create gated corridor segments
            await self._create_gated_corridor(
                location_id, location_name, location_type,
                connect_to_id, connect_to_name, connect_type,
                distance
            )
        else:
            # Create ungated corridor using galaxy generator's restricted calculation
            travel_time = self._calculate_ungated_route_time(distance)
            fuel_cost = int(distance * 1.8) + random.randint(8, 25)
            danger_level = min(5, max(1, int(distance / 12) + 1))
            
            # Create bidirectional corridors
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time,
                    fuel_cost, danger_level, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, %s, 1, 1)""",
                (f"{location_name} - {connect_to_name} Route",
                 location_id, connect_to_id, travel_time, fuel_cost, danger_level)
            )
            
            self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time,
                    fuel_cost, danger_level, is_active, is_generated)
                   VALUES (%s, %s, %s, %s, %s, %s, 1, 1)""",
                (f"{connect_to_name} - {location_name} Route",
                 connect_to_id, location_id, travel_time, fuel_cost, danger_level)
            )
        
        # Add 1-3 additional random connections to create better connectivity
        await self._add_additional_random_connections(location_id, location_name, x, y, location_type)

    async def _add_additional_random_connections(self, location_id: int, location_name: str,
                                               x: float, y: float, location_type: str):
        """Add 1-3 additional random connections to nearby locations"""
        
        # Find nearby locations (smaller radius for random locations)
        nearby = self.db.execute_query(
            """SELECT location_id, name, x_coordinate, y_coordinate, location_type
               FROM locations
               WHERE location_id != %s
               AND ABS(x_coordinate - %s) < 20
               AND ABS(y_coordinate - %s) < 20
               ORDER BY RANDOM()
               LIMIT 5""",
            (location_id, x, y),
            fetch='all'
        )
        
        if not nearby:
            return
        
        # Create 1-3 connections (fewer than manual creation)
        num_connections = random.randint(1, min(3, len(nearby)))
        for i in range(num_connections):
            other_id, other_name, ox, oy, other_type = nearby[i]
            
            # Check if corridor already exists
            existing = self.db.execute_query(
                """SELECT corridor_id FROM corridors
                   WHERE (origin_location = %s AND destination_location = %s)
                   OR (origin_location = %s AND destination_location = %s)""",
                (location_id, other_id, other_id, location_id),
                fetch='one'
            )
            
            if existing:
                continue
            
            distance = math.sqrt((x - ox)**2 + (y - oy)**2)
            
            # Create shorter, safer routes for random locations
            if location_type == 'gate' or other_type == 'gate':
                await self._create_gated_corridor(
                    location_id, location_name, location_type,
                    other_id, other_name, other_type,
                    distance
                )
            else:
                # Create ungated corridor with moderate danger using galaxy generator's calculation
                travel_time = self._calculate_ungated_route_time(distance)
                fuel_cost = int(distance * 2.2) + random.randint(12, 35)
                danger_level = min(4, max(2, int(distance / 10) + 1))
                
                # Bidirectional
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, %s, 1, 1)""",
                    (f"{location_name} - {other_name} Passage", location_id, other_id,
                     travel_time, fuel_cost, danger_level)
                )
                
                self.db.execute_query(
                    """INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time,
                        fuel_cost, danger_level, is_active, is_generated)
                       VALUES (%s, %s, %s, %s, %s, %s, 1, 1)""",
                    (f"{other_name} - {location_name} Passage", 
                     other_id, location_id, travel_time, fuel_cost, danger_level)
                )

    async def _queue_location_establishment_news(self, location_id: int, location_name: str, location_type: str):
        """Queue galactic news about the new location's establishment"""
        galactic_news_cog = self.bot.get_cog('GalacticNewsCog')
        if not galactic_news_cog:
            return
        
        # Get all guilds with galactic updates channels
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        if not guilds_with_updates:
            return
        
        # Create different news variants for variety based on location type
        establishment_variants = {
            'colony': [
                {
                    "title": f"New Colony Established: {location_name}",
                    "description": f"Pioneers have successfully established {location_name}, marking another milestone in galactic expansion. The new colony is expected to provide fresh opportunities for settlers and traders alike."
                },
                {
                    "title": f"Colonial Expansion: {location_name} Founded",
                    "description": f"The galactic frontier grows as {location_name} officially opens its doors to colonists. This new settlement promises to become a beacon of civilization in the outer reaches."
                },
                {
                    "title": f"Breaking: {location_name} Colony Operational",
                    "description": f"After months of construction, {location_name} has been declared fully operational. Colonial authorities report successful establishment of essential services and infrastructure."
                }
            ],
            'space_station': [
                {
                    "title": f"New Space Station Online: {location_name}",
                    "description": f"The space station {location_name} has come online, providing crucial services to vessels traveling through the sector. The station's advanced facilities are now available to all authorized personnel."
                },
                {
                    "title": f"Station Launch: {location_name} Operational",
                    "description": f"Engineering teams celebrate as {location_name} achieves full operational status. The new station significantly expands our presence in this strategic region of space."
                },
                {
                    "title": f"Orbital Platform Complete: {location_name}",
                    "description": f"The construction of {location_name} marks a significant achievement in orbital engineering. This state-of-the-art facility will serve as a vital hub for regional operations."
                }
            ],
            'outpost': [
                {
                    "title": f"Remote Outpost Established: {location_name}",
                    "description": f"Frontier specialists have successfully established {location_name} in a previously uncharted region. The outpost will serve as a vital waypoint for deep space operations."
                },
                {
                    "title": f"New Frontier Post: {location_name} Active",
                    "description": f"The remote outpost {location_name} has begun operations, extending our reach into the galaxy's outer territories. Basic services are now available to explorers and traders."
                },
                {
                    "title": f"Outpost Deployment: {location_name} Online",
                    "description": f"Military engineers report successful deployment of {location_name}. This strategic outpost will provide essential support for operations in the frontier regions."
                }
            ],
            'gate': [
                {
                    "title": f"Gate Facility Activated: {location_name}",
                    "description": f"The gate facility {location_name} has been successfully activated, creating new pathways through the galaxy. This technological marvel will revolutionize travel in the region."
                },
                {
                    "title": f"New Gate Online: {location_name} Operational",
                    "description": f"Quantum engineers celebrate the successful activation of {location_name}. The new gate facility promises to significantly reduce travel times across multiple sectors."
                },
                {
                    "title": f"Gate Network Expanded: {location_name}",
                    "description": f"The galactic gate network grows with the addition of {location_name}. This advanced facility will provide rapid transit capabilities for authorized vessels."
                }
            ]
        }
        
        # Select random variant for this location type
        variants = establishment_variants.get(location_type, establishment_variants['outpost'])
        selected_news = random.choice(variants)
        
        # Queue the news for all guilds
        for guild_row in guilds_with_updates:
            guild_id = guild_row[0]
            await galactic_news_cog.queue_news(
                guild_id=guild_id,
                news_type='location_establishment',
                title=selected_news['title'],
                description=selected_news['description'],
                location_id=location_id
            )
    
    @creation_group.command(name="delete_location", description="Delete a location and all associated data (Admin only)")
    @app_commands.describe(
        location_name="Name of the location to delete"
    )
    async def delete_location(self, interaction: discord.Interaction, location_name: str):
        """Delete a location from the galaxy with confirmation"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Find the location
        location = self.db.execute_query(
            "SELECT location_id, name, population, location_type, COALESCE(is_derelict, 0) FROM locations WHERE LOWER(name) LIKE LOWER(%s)",
            (f"%{location_name}%",),
            fetch='one'
        )
        
        if not location:
            await interaction.response.send_message(f"Location '{location_name}' not found.", ephemeral=True)
            return
        
        location_id, actual_name, population, location_type, is_derelict = location
        
        # Get NPC count
        npc_count = self.db.execute_query(
            "SELECT COUNT(*) FROM static_npcs WHERE location_id = %s",
            (location_id,),
            fetch='one'
        )[0]
        
        # Create confirmation embed
        embed = discord.Embed(
            title="⚠️ Delete Location Confirmation",
            description=f"You are about to **permanently delete** the location **{actual_name}**.",
            color=0xff0000
        )
        embed.add_field(
            name="📊 Location Statistics",
            value=f"Type: {location_type.replace('_', ' ').title()}\n"
                  f"Population: {population:,}\n"
                  f"Static NPCs: {npc_count}",
            inline=True
        )
        embed.add_field(
            name="💥 Casualties",
            value=f"Total: {population + npc_count:,}",
            inline=True
        )
        embed.add_field(
            name="🗑️ What will be deleted:",
            value="• Location and all data\n"
                  "• All corridors connecting to this location\n"
                  "• All NPCs at this location\n"
                  "• All jobs posted here\n"
                  "• All shop items\n"
                  "• All sub-locations\n"
                  "• All player homes\n"
                  "• All related records",
            inline=False
        )
        embed.add_field(
            name="📰 News Impact",
            value="A galactic news report will be generated about the location's destruction.",
            inline=False
        )
        embed.add_field(
            name="⚠️ Warning:",
            value="**This operation is IRREVERSIBLE!** All data associated with this location will be permanently lost.",
            inline=False
        )
        
        # Create confirmation view
        view = LocationDeletionConfirmView(self, location_id, actual_name, population, npc_count, location_type, is_derelict)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @creation_group.command(name="shuffle_sublocations", description="Shuffle all sub-locations in the galaxy (Admin only)")
    async def shuffle_sublocations(self, interaction: discord.Interaction):
        """Shuffle and regenerate all sub-locations in the galaxy"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        # Create confirmation embed
        embed = discord.Embed(
            title="⚠️ Shuffle Sub-Locations Confirmation",
            description="This will **clear all existing sub-locations** and regenerate them based on current location types and wealth levels.",
            color=0xffa500
        )
        embed.add_field(
            name="📋 What this does:",
            value="• Clears all sub-locations from the database\n"
                  "• Regenerates sub-locations for all locations\n"
                  "• Applies current generation rules\n"
                  "• Introduces newly added sub-location types",
            inline=False
        )
        embed.add_field(
            name="⚠️ Warning:",
            value="This operation is **irreversible** and will affect the entire galaxy.",
            inline=False
        )
        
        # Create confirmation view
        view = SubLocationShuffleConfirmView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @creation_group.command(name="link", description="Create a route connection between two locations")
    @app_commands.describe(
        location1="First location name (exact)",
        location2="Second location name (exact)",
        name="Optional custom name for the route"
    )
    async def link_locations(self, interaction: discord.Interaction, location1: str, location2: str, name: str = None):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Validate both locations exist
        loc1_data = self.db.execute_query(
            "SELECT location_id, name, location_type, system_name, x_coordinate, y_coordinate FROM locations WHERE name = %s",
            (location1,), fetch='one'
        )
        
        if not loc1_data:
            await interaction.followup.send(f"❌ Location '{location1}' not found.", ephemeral=True)
            return
        
        loc2_data = self.db.execute_query(
            "SELECT location_id, name, location_type, system_name, x_coordinate, y_coordinate FROM locations WHERE name = %s", 
            (location2,), fetch='one'
        )
        
        if not loc2_data:
            await interaction.followup.send(f"❌ Location '{location2}' not found.", ephemeral=True)
            return
        
        loc1_id, loc1_name, loc1_type, loc1_system, loc1_x, loc1_y = loc1_data
        loc2_id, loc2_name, loc2_type, loc2_system, loc2_x, loc2_y = loc2_data
        
        if loc1_id == loc2_id:
            await interaction.followup.send("❌ Cannot create route to the same location.", ephemeral=True)
            return
        
        # Check if route already exists
        existing_route = self.db.execute_query(
            """SELECT corridor_id FROM corridors 
               WHERE (origin_location = %s AND destination_location = %s) 
               OR (origin_location = %s AND destination_location = %s AND is_bidirectional = true)""",
            (loc1_id, loc2_id, loc2_id, loc1_id), fetch='one'
        )
        
        if existing_route:
            await interaction.followup.send(f"❌ Route between {loc1_name} and {loc2_name} already exists.", ephemeral=True)
            return
        
        # Determine corridor type intelligently
        corridor_type = "ungated"  # Default
        
        # Both are gates = gated corridor
        if loc1_type == 'gate' and loc2_type == 'gate':
            corridor_type = "gated"
        # Same system/region = local space
        elif loc1_system == loc2_system and loc1_x == loc2_x and loc1_y == loc2_y:
            corridor_type = "local_space"
        # Otherwise ungated (cross-system, gate-to-location, etc.)
        
        # Generate name if not provided
        if not name:
            if corridor_type == "local_space":
                name = f"{loc1_name} Local Approach"
            elif corridor_type == "gated":
                name = f"{loc1_name}-{loc2_name} Gate Link"
            else:
                name = f"{loc1_name}-{loc2_name} Corridor"
        
        # Create the corridor
        try:
            corridor_id = self.db.execute_query(
                """INSERT INTO corridors 
                   (name, origin_location, destination_location, corridor_type, travel_time, fuel_cost, danger_level, is_active, is_bidirectional)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1)""",
                (name, loc1_id, loc2_id, corridor_type, 300, 20, 3),
                fetch='lastrowid'
            )
            
            # Activate unused or moving gates when they get connected
            gates_activated = []
            if loc1_type == 'gate':
                gate_status = self.db.execute_query("SELECT gate_status FROM locations WHERE location_id = %s", (loc1_id,), fetch='one')
                if gate_status and gate_status[0] in ['unused', 'moving']:
                    self.db.execute_query("UPDATE locations SET gate_status = 'active' WHERE location_id = %s", (loc1_id,))
                    gates_activated.append(loc1_name)
                    
            if loc2_type == 'gate':
                gate_status = self.db.execute_query("SELECT gate_status FROM locations WHERE location_id = %s", (loc2_id,), fetch='one')
                if gate_status and gate_status[0] in ['unused', 'moving']:
                    self.db.execute_query("UPDATE locations SET gate_status = 'active' WHERE location_id = %s", (loc2_id,))
                    gates_activated.append(loc2_name)
            
            # Create success embed
            embed = discord.Embed(
                title="🔗 Route Created Successfully",
                description=f"New corridor established between locations",
                color=0x00ff00
            )
            
            embed.add_field(name="Origin", value=loc1_name, inline=True)
            embed.add_field(name="Destination", value=loc2_name, inline=True) 
            embed.add_field(name="Type", value=corridor_type.replace('_', ' ').title(), inline=True)
            embed.add_field(name="Route Name", value=name, inline=False)
            embed.add_field(name="Corridor ID", value=str(corridor_id), inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            
            if gates_activated:
                embed.add_field(name="Gates Activated", value=", ".join(gates_activated), inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            print(f"🔗 Admin created route: {name} ({loc1_name} -> {loc2_name}, type: {corridor_type}) by {interaction.user.name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create route: {str(e)}", ephemeral=True)
            print(f"❌ Route creation failed: {e}")
            
    @creation_group.command(name="fix_long_routes", description="Fix existing routes with overly long travel times or excessive fuel costs")
    async def fix_long_routes(self, interaction: discord.Interaction):
        """Identify and fix routes with travel times over 20 minutes"""
        
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Bot owner permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Find routes with travel times over 15 minutes (900 seconds) OR fuel costs over 100 
        long_routes = self.db.execute_query(
            """SELECT corridor_id, name, origin_location, destination_location, travel_time, fuel_cost
               FROM corridors 
               WHERE travel_time > 900 OR fuel_cost > 100
               ORDER BY travel_time DESC, fuel_cost DESC""",
            fetch='all'
        )
        
        if not long_routes:
            await interaction.followup.send("✅ No routes found with travel times over 15 minutes or fuel costs over 100.", ephemeral=True)
            return
        
        # Process each long route
        fixed_count = 0
        details = []
        
        for corridor_id, name, origin_id, dest_id, old_time, old_fuel_cost in long_routes:
            # Get location coordinates to calculate distance
            origin_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s",
                (origin_id,), fetch='one'
            )
            dest_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s", 
                (dest_id,), fetch='one'
            )
            
            if not origin_info or not dest_info:
                continue
                
            ox, oy, origin_type = origin_info
            dx, dy, dest_type = dest_info
            distance = math.sqrt((ox - dx)**2 + (oy - dy)**2)
            
            # Calculate new travel time based on corridor type with proper variation
            if "Approach" in name or "Arrival" in name or "Local Space" in name:
                # Local space routes (approach/arrival/local space)
                new_time = max(60, int(distance * 3) + 60)  # 1-3 minutes for local space
                # Local space fuel: 5-15 fuel (very cheap for short hops)
                new_fuel_cost = max(5, min(15, int(new_time / 30) + random.randint(3, 8)))
            elif origin_type == 'gate' and dest_type == 'gate':
                # Gate-to-gate routes (gated corridors) - ~8min average, 5-15min range
                target_time = 8 * 60  # 8 minutes
                min_time = 5 * 60     # 5 minutes  
                max_time = 15 * 60    # 15 minutes
                distance_factor = min(distance / 80.0, 1.0)
                base_time = target_time + (max_time - target_time) * (distance_factor * 0.6)
                variance = base_time * 0.2
                new_time = max(min_time, min(max_time, int(base_time + random.uniform(-variance, variance))))
                # Gated route fuel: 20-60 fuel (safe but expensive)
                new_fuel_cost = max(20, min(60, int(new_time / 12) + random.randint(15, 25)))
            else:
                # Ungated routes - ~6min average, 3-15min range
                target_time = 6 * 60  # 6 minutes
                min_time = 3 * 60     # 3 minutes
                max_time = 15 * 60    # 15 minutes
                distance_factor = min(distance / 80.0, 1.0)
                base_time = target_time + (max_time - target_time) * (distance_factor * 0.5)
                variance = base_time * 0.25
                new_time = max(min_time, min(max_time, int(base_time + random.uniform(-variance, variance))))
                # Ungated route fuel: 15-50 fuel (cheaper but dangerous)
                new_fuel_cost = max(15, min(50, int(new_time / 15) + random.randint(10, 20)))
            
            # Update the corridor with both travel time and fuel cost
            self.db.execute_query(
                "UPDATE corridors SET travel_time = %s, fuel_cost = %s WHERE corridor_id = %s",
                (new_time, new_fuel_cost, corridor_id)
            )
            
            fixed_count += 1
            old_minutes = old_time // 60
            new_minutes = new_time // 60
            details.append(f"• {name}: {old_minutes}m → {new_minutes}m, {old_fuel_cost}⚡ → {new_fuel_cost}⚡")
        
        # Create response
        embed = discord.Embed(
            title="🔧 Routes Fixed",
            description=f"Fixed {fixed_count} routes with overly long travel times and excessive fuel costs.",
            color=0x00ff00
        )
        
        if details:
            # Split details into chunks if too long
            detail_text = "\n".join(details)
            if len(detail_text) > 1000:
                detail_text = "\n".join(details[:10]) + f"\n... and {len(details)-10} more routes"
            embed.add_field(name="Fixed Routes", value=detail_text, inline=False)
        
        embed.add_field(
            name="New Limits", 
            value="• Local space: 1-3 minutes\n• Ungated routes: 3-15 minutes (~6min avg)\n• Gated routes: 5-15 minutes (~8min avg)", 
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _execute_fix_long_routes_logic(self) -> dict:
        """Execute the core logic of fix_long_routes for automatic corridor shifts"""
        import math
        
        # Find routes with travel times over 15 minutes (900 seconds) OR fuel costs over 100 
        long_routes = self.db.execute_query(
            """SELECT corridor_id, name, origin_location, destination_location, travel_time, fuel_cost
               FROM corridors 
               WHERE travel_time > 900 OR fuel_cost > 100
               ORDER BY travel_time DESC, fuel_cost DESC""",
            fetch='all'
        )
        
        if not long_routes:
            return {'routes_fixed': 0, 'routes_checked': 0}
        
        # Process each long route
        fixed_count = 0
        
        for corridor_id, name, origin_id, dest_id, old_time, old_fuel_cost in long_routes:
            # Get location coordinates to calculate distance
            origin_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s",
                (origin_id,), fetch='one'
            )
            dest_info = self.db.execute_query(
                "SELECT x_coordinate, y_coordinate, location_type FROM locations WHERE location_id = %s", 
                (dest_id,), fetch='one'
            )
            
            if not origin_info or not dest_info:
                continue
                
            ox, oy, origin_type = origin_info
            dx, dy, dest_type = dest_info
            distance = math.sqrt((ox - dx)**2 + (oy - dy)**2)
            
            # Calculate new travel time based on corridor type with proper variation
            if "Approach" in name or "Arrival" in name or "Local Space" in name:
                # Local space routes (approach/arrival/local space)
                new_time = max(60, int(distance * 3) + 60)  # 1-3 minutes for local space
                # Local space fuel: 5-15 fuel (very cheap for short hops)
                new_fuel_cost = max(5, min(15, int(new_time / 30) + random.randint(3, 8)))
            elif origin_type == 'gate' and dest_type == 'gate':
                # Gate-to-gate routes (gated corridors) - ~8min average, 5-15min range
                target_time = 8 * 60  # 8 minutes
                min_time = 5 * 60     # 5 minutes  
                max_time = 15 * 60    # 15 minutes
                distance_factor = min(distance / 80.0, 1.0)
                base_time = target_time + (max_time - target_time) * (distance_factor * 0.6)
                variance = base_time * 0.2
                new_time = max(min_time, min(max_time, int(base_time + random.uniform(-variance, variance))))
                # Gated route fuel: 20-60 fuel (safe but expensive)
                new_fuel_cost = max(20, min(60, int(new_time / 12) + random.randint(15, 25)))
            else:
                # Ungated routes - ~6min average, 3-15min range
                target_time = 6 * 60  # 6 minutes
                min_time = 3 * 60     # 3 minutes
                max_time = 15 * 60    # 15 minutes
                distance_factor = min(distance / 80.0, 1.0)
                base_time = target_time + (max_time - target_time) * (distance_factor * 0.5)
                variance = base_time * 0.25
                new_time = max(min_time, min(max_time, int(base_time + random.uniform(-variance, variance))))
                # Ungated route fuel: 15-50 fuel (cheaper but dangerous)
                new_fuel_cost = max(15, min(50, int(new_time / 15) + random.randint(10, 20)))
            
            # Update the corridor with both travel time and fuel cost
            self.db.execute_query(
                "UPDATE corridors SET travel_time = %s, fuel_cost = %s WHERE corridor_id = %s",
                (new_time, new_fuel_cost, corridor_id)
            )
            
            fixed_count += 1
        
        return {
            'routes_fixed': fixed_count,
            'routes_checked': len(long_routes)
        }
    
    async def _create_local_gate_in_transaction(self, conn, location_data: dict, location_id: int) -> int:
        """Create a local gate for a major location within a transaction"""
        
        # Generate gate coordinates near the main location
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(2, 8)  # Close enough for local_space connection
        gate_x = location_data['x_coordinate'] + distance * math.cos(angle)
        gate_y = location_data['y_coordinate'] + distance * math.sin(angle)
        
        # Generate gate name
        gate_name = f"{location_data['name']} Gate"
        
        # Create the gate location
        gate_id = self.db.execute_in_transaction(
            conn,
            """INSERT INTO locations 
               (name, location_type, description, wealth_level, population,
                x_coordinate, y_coordinate, system_name,
                has_jobs, has_shops, has_medical, has_repairs, has_fuel, 
                has_upgrades, has_shipyard,
                has_federal_supplies, has_black_market,
                created_at, is_generated)
               VALUES (%s, 'gate', %s, %s, %s, %s, %s, %s, FALSE, TRUE, TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, FALSE, NOW(), FALSE)""",
            (
                gate_name,
                f"Local gate providing access to {location_data['name']}",
                max(1, location_data['wealth_level'] - 1),  # Gates are typically slightly less wealthy
                min(500, max(50, location_data.get('population', 1000) // 100)),  # Gate staff population
                gate_x,
                gate_y,
                location_data['system_name']
            ),
            fetch='lastrowid'
        )
        
        # Create a few NPCs for the gate
        npc_cog = self.bot.get_cog('NPCCog')
        if npc_cog:
            npc_data_list = npc_cog.generate_static_npc_batch_data(
                gate_id,
                min(500, max(50, location_data.get('population', 1000) // 100)),
                'gate',
                max(1, location_data['wealth_level'] - 1),
                location_data['faction'] == 'outlaw'
            )
            
            # Limit to 3-5 NPCs for gates
            npc_data_list = npc_data_list[:random.randint(3, 5)]
            
            if npc_data_list:
                self.db.executemany_in_transaction(
                    conn,
                    """INSERT INTO static_npcs 
                       (location_id, name, age, occupation, personality, alignment, 
                        hp, max_hp, combat_rating, credits)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    npc_data_list
                )
        
        return gate_id
    
    async def _create_local_gate_connection(self, location_id: int, location_data: dict, gate_id: int):
        """Create local space connection between main location and its gate"""
        
        # Get gate info
        gate_info = self.db.execute_query(
            "SELECT name, system_name FROM locations WHERE location_id = %s",
            (gate_id,),
            fetch='one'
        )
        
        if not gate_info:
            return
        
        gate_name, gate_system = gate_info
        
        # Create bidirectional local space connections
        travel_time = random.randint(60, 180)  # 1-3 minutes for local space
        fuel_cost = random.randint(2, 8)
        danger_level = 1
        
        # Main location to gate
        self._create_corridor_with_type(
            f"{location_data['name']} - {gate_name} Local Space",
            location_id, gate_id, travel_time, fuel_cost, danger_level, 'local_space'
        )
        
        # Gate to main location
        self._create_corridor_with_type(
            f"{gate_name} - {location_data['name']} Local Space",
            gate_id, location_id, travel_time, fuel_cost, danger_level, 'local_space'
        )
    
    async def _validate_new_location_architecture(self, location_id: int) -> List[str]:
        """Run basic architecture validation on the newly created location"""
        warnings = []
        
        try:
            # Import the architecture validator
            from utils.architecture_validator import ArchitectureValidator
            validator = ArchitectureValidator(self.bot)
            
            # Check for rule violations involving this location
            location_info = self.db.execute_query(
                "SELECT name, location_type, system_name FROM locations WHERE location_id = %s",
                (location_id,),
                fetch='one'
            )
            
            if not location_info:
                return warnings
            
            location_name, location_type, system_name = location_info
            
            # Check major-to-gate connections in same system
            if location_type in ['colony', 'space_station', 'outpost']:
                incorrect_routes = self.db.execute_query(
                    """SELECT c.corridor_id, c.name, c.corridor_type
                       FROM corridors c
                       JOIN locations o ON c.origin_location = o.location_id
                       JOIN locations d ON c.destination_location = d.location_id
                       WHERE (c.origin_location = %s OR c.destination_location = %s)
                       AND ((o.location_type IN ('colony', 'space_station', 'outpost') AND d.location_type = 'gate')
                            OR (o.location_type = 'gate' AND d.location_type IN ('colony', 'space_station', 'outpost')))
                       AND o.system_name = d.system_name
                       AND c.corridor_type != 'local_space'""",
                    (location_id, location_id),
                    fetch='all'
                )
                
                for route_id, route_name, corridor_type in incorrect_routes:
                    # Auto-fix the route type
                    self.db.execute_query(
                        "UPDATE corridors SET corridor_type = 'local_space' WHERE corridor_id = %s",
                        (route_id,)
                    )
                    warnings.append(f"Auto-fixed route '{route_name}' to use local_space type")
            
            # Check for gated corridors that should be local_space or ungated
            if location_type == 'gate':
                incorrect_gated = self.db.execute_query(
                    """SELECT c.corridor_id, c.name, c.corridor_type
                       FROM corridors c
                       JOIN locations o ON c.origin_location = o.location_id
                       JOIN locations d ON c.destination_location = d.location_id
                       WHERE (c.origin_location = %s OR c.destination_location = %s)
                       AND c.corridor_type = 'gated'
                       AND o.system_name = d.system_name""",
                    (location_id, location_id),
                    fetch='all'
                )
                
                for route_id, route_name, corridor_type in incorrect_gated:
                    # Auto-fix to local_space since they're in same system
                    self.db.execute_query(
                        "UPDATE corridors SET corridor_type = 'local_space' WHERE corridor_id = %s",
                        (route_id,)
                    )
                    warnings.append(f"Auto-fixed route '{route_name}' from gated to local_space (same system)")
            
        except ImportError:
            warnings.append("Architecture validator not available - manual validation recommended")
        except Exception as e:
            warnings.append(f"Validation warning: {str(e)}")
        
        return warnings


class LocationDeletionConfirmView(discord.ui.View):
    """Confirmation view for location deletion"""
    
    def __init__(self, cog, location_id: int, location_name: str, population: int, npc_count: int, location_type: str, is_derelict: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.location_id = location_id
        self.location_name = location_name
        self.population = population
        self.npc_count = npc_count
        self.location_type = location_type
        self.is_derelict = bool(is_derelict)
    
    @discord.ui.button(label="CONFIRM DELETE", style=discord.ButtonStyle.danger, emoji="💥")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Execute the location deletion"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get location coordinates for finding nearest location
            location_coords = self.cog.db.execute_query(
                "SELECT x_coordinate, y_coordinate FROM locations WHERE location_id = %s",
                (self.location_id,),
                fetch='one'
            )
            
            if not location_coords:
                await interaction.followup.send("❌ Error: Location data not found.", ephemeral=True)
                return
            
            x_coordinate, y_coordinate = location_coords
            
            # Find nearest location for news broadcast
            nearest_location = self.cog.db.execute_query(
                """SELECT location_id, name, 
                   SQRT(POWER(x_coordinate - %s, 2) + POWER(y_coordinate - %s, 2)) as distance
                   FROM locations 
                   WHERE location_id != %s 
                   ORDER BY distance 
                   LIMIT 1""",
                (x_coordinate, y_coordinate, self.location_id),
                fetch='one'
            )
            
            # Execute the deletion
            await self._delete_location_safely()
            
            # Queue galactic news
            if nearest_location:
                nearest_location_id = nearest_location[0]
                await self._queue_destruction_news(nearest_location_id)
            
            # Create success embed
            embed = discord.Embed(
                title="💥 Location Destroyed",
                description=f"**{self.location_name}** has been completely destroyed and erased from the galaxy.",
                color=0xff0000
            )
            embed.add_field(
                name="💀 Casualties",
                value=f"Population: {self.population:,}\n"
                      f"NPCs: {self.npc_count}\n"
                      f"**Total: {self.population + self.npc_count:,}**",
                inline=True
            )
            embed.add_field(
                name="📰 News Broadcast",
                value="A galactic news report has been queued and will be delivered to all sectors.",
                inline=False
            )
            embed.add_field(
                name="🗑️ Cleanup Complete",
                value="All associated data has been safely removed from the galaxy database.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Deletion Failed",
                description=f"An error occurred during the deletion operation:\n```{str(e)}```",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the deletion operation"""
        embed = discord.Embed(
            title="✅ Deletion Cancelled",
            description=f"**{self.location_name}** remains intact. No changes were made.",
            color=0x00ff00
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def _delete_location_safely(self):
        """Safely delete the location and all related data"""
        conn = self.cog.db.begin_transaction()
        
        try:
            # Delete in correct order to respect foreign key constraints
            
            # 1. Delete NPCs and their data
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM npc_jobs WHERE npc_id IN (SELECT npc_id FROM static_npcs WHERE location_id = %s)",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM npc_trade_inventory WHERE npc_id IN (SELECT npc_id FROM static_npcs WHERE location_id = %s)",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM static_npcs WHERE location_id = %s",
                (self.location_id,)
            )
            
            # 2. Delete jobs
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM job_tracking WHERE job_id IN (SELECT job_id FROM jobs WHERE location_id = %s)",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM jobs WHERE location_id = %s",
                (self.location_id,)
            )
            
            # 3. Delete shop items
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM shop_items WHERE location_id = %s",
                (self.location_id,)
            )
            
            # 4. Delete sub-locations
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM sub_locations WHERE parent_location_id = %s",
                (self.location_id,)
            )
            
            # 5. Delete location homes and related data
            home_ids = self.cog.db.execute_in_transaction(
                conn, "SELECT home_id FROM location_homes WHERE location_id = %s",
                (self.location_id,), fetch='all'
            )
            
            if home_ids:
                home_id_list = [str(home[0]) for home in home_ids]
                home_ids_str = ','.join(home_id_list)
                
                self.cog.db.execute_in_transaction(
                    conn, f"DELETE FROM home_storage WHERE home_id IN ({home_ids_str})"
                )
                self.cog.db.execute_in_transaction(
                    conn, f"DELETE FROM home_activities WHERE home_id IN ({home_ids_str})"
                )
                self.cog.db.execute_in_transaction(
                    conn, f"DELETE FROM home_recovery_tracking WHERE home_id IN ({home_ids_str})"
                )
            
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_homes WHERE location_id = %s",
                (self.location_id,)
            )
            
            # 6. Delete location-related data
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_items WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_logs WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_ownership WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_upgrades WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_access_control WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_income_log WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_storage WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM location_economy WHERE location_id = %s",
                (self.location_id,)
            )
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM user_location_panels WHERE location_id = %s",
                (self.location_id,)
            )
            
            # 7. Update characters who were at this location (move them to a safe location)
            # First, find a safe location to move them to
            safe_location = self.cog.db.execute_in_transaction(
                conn, "SELECT location_id FROM locations WHERE location_id != %s LIMIT 1",
                (self.location_id,), fetch='one'
            )
            
            if safe_location:
                safe_location_id = safe_location[0]
                self.cog.db.execute_in_transaction(
                    conn, "UPDATE characters SET current_location = %s WHERE current_location = %s",
                    (safe_location_id, self.location_id)
                )
            
            # 8. Update ships docked at this location
            if safe_location:
                self.cog.db.execute_in_transaction(
                    conn, "UPDATE ships SET docked_at_location = %s WHERE docked_at_location = %s",
                    (safe_location_id, self.location_id)
                )
                self.cog.db.execute_in_transaction(
                    conn, "UPDATE player_ships SET stored_at_shipyard = %s WHERE stored_at_shipyard = %s",
                    (safe_location_id, self.location_id)
                )
            
            # 9. Delete all corridors connecting to this location
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM corridors WHERE origin_location = %s OR destination_location = %s",
                (self.location_id, self.location_id)
            )
            
            # 10. Finally, delete the location itself
            self.cog.db.execute_in_transaction(
                conn, "DELETE FROM locations WHERE location_id = %s",
                (self.location_id,)
            )
            
            # Commit all changes
            self.cog.db.commit_transaction(conn)
            
        except Exception as e:
            self.cog.db.rollback_transaction(conn)
            raise e
    
    async def _queue_destruction_news(self, nearest_location_id: int):
        """Queue a galactic news message about the location's destruction with thematic variants"""
        galactic_news_cog = self.cog.bot.get_cog('GalacticNewsCog')
        if not galactic_news_cog:
            return
        
        import random
        
        total_casualties = self.population + self.npc_count
        
        # Create thematic news variants based on location type and derelict status
        if self.is_derelict:
            # Derelict locations get different treatment
            news_variants = [
                {
                    "title": f"SALVAGE OPERATION: {self.location_name} Finally Demolished",
                    "description": f"The long-abandoned {self.location_name} has been completely cleared from its coordinates. "
                                  f"Salvage crews report the derelict structure posed a navigation hazard. "
                                  f"The space lane is now clear for safe passage."
                },
                {
                    "title": f"CLEANUP COMPLETE: Derelict {self.location_name} Removed",
                    "description": f"Emergency services have successfully demolished the abandoned {self.location_name}. "
                                  f"The deteriorating structure was classified as a safety risk. "
                                  f"Debris has been cleared and the area is safe for transit."
                },
                {
                    "title": f"STRUCTURAL COLLAPSE: {self.location_name} Disintegrates",
                    "description": f"The derelict {self.location_name} has finally succumbed to decades of neglect and collapsed completely. "
                                  f"No casualties reported as the facility has been uninhabited for years. "
                                  f"Automated warning beacons continue to mark the debris field."
                }
            ]
        else:
            # Populate locations get type-specific variants
            location_type_variants = {
                'colony': [
                    {
                        "title": f"COLONIAL DISASTER: {self.location_name} Colony Lost",
                        "description": f"The thriving colony of {self.location_name} has been completely destroyed in a catastrophic event. "
                                      f"All {total_casualties:,} colonists and administrative personnel are confirmed lost. "
                                      f"Colonial authorities are investigating the cause of this unprecedented disaster."
                    },
                    {
                        "title": f"TRAGEDY: {self.location_name} Settlement Wiped Out",
                        "description": f"Emergency broadcasts confirm the total annihilation of {self.location_name} colony. "
                                      f"The {total_casualties:,} residents had no time to evacuate. "
                                      f"This marks one of the worst colonial disasters in recent history."
                    },
                    {
                        "title": f"COLONIAL MOURNING: {self.location_name} Destroyed",
                        "description": f"The galactic colonial administration confirms the complete loss of {self.location_name}. "
                                      f"Memorial services for the {total_casualties:,} lost colonists are being organized. "
                                      f"The tragedy has prompted renewed safety reviews across all colonial territories."
                    }
                ],
                'space_station': [
                    {
                        "title": f"STATION CATASTROPHE: {self.location_name} Completely Destroyed",
                        "description": f"The space station {self.location_name} has been utterly annihilated in a catastrophic failure. "
                                      f"All {total_casualties:,} crew members, residents and visitors are confirmed lost. "
                                      f"Emergency protocols have been activated at all nearby stations."
                    },
                    {
                        "title": f"ORBITAL DISASTER: {self.location_name} Station Lost",
                        "description": f"Critical system failures led to the complete destruction of {self.location_name} station. "
                                      f"No survivors among the {total_casualties:,} personnel aboard. "
                                      f"Station security footage is being analyzed to determine the cause."
                    },
                    {
                        "title": f"SPACE TRAGEDY: {self.location_name} Obliterated",
                        "description": f"The orbital facility {self.location_name} has been completely destroyed. "
                                      f"Search and rescue operations confirm {total_casualties:,} casualties. "
                                      f"All nearby traffic has been rerouted as a safety precaution."
                    }
                ],
                'outpost': [
                    {
                        "title": f"INFRASTRUCTURAL LOSS: {self.location_name} Outpost Destroyed",
                        "description": f"The remote outpost {self.location_name} has been completely obliterated. "
                                      f"All {total_casualties:,} personnel are presumed lost. "
                                      f"The outpost's final transmission indicated no immediate danger, making this loss particularly tragic."
                    },
                    {
                        "title": f"OUTPOST TRAGEDY: {self.location_name} Goes Silent",
                        "description": f"Contact with {self.location_name} outpost has been permanently lost following its complete destruction. "
                                      f"The {total_casualties:,} brave souls manning this post made the ultimate sacrifice. "
                                      f"Their contributions to security and research will not be forgotten."
                    },
                    {
                        "title": f"TRAGEDY STRIKES: {self.location_name} Eliminated",
                        "description": f"The outpost {self.location_name} has been wiped from existence. "
                                      f"The galaxy mourns the loss of {total_casualties:,} dedicated personnel. "
                                      f"Security protocols are being reviewed at all installations."
                    }
                ],
                'gate': [
                    {
                        "title": f"TRANSIT CATASTROPHE: {self.location_name} Gate Destroyed",
                        "description": f"The critical transit gate {self.location_name} has been completely destroyed in an unprecedented event. "
                                      f"All {total_casualties:,} gate technicians and traffic controllers are confirmed lost. "
                                      f"This loss severely impacts corridor network efficiency and will require major rerouting."
                    },
                    {
                        "title": f"INFRASTRUCTURE DISASTER: {self.location_name} Gate Lost",
                        "description": f"The vital transportation hub {self.location_name} has been utterly annihilated. "
                                      f"The destruction claimed {total_casualties:,} lives and severed a major trade route. "
                                      f"Emergency traffic management protocols are now in effect throughout the sector."
                    },
                    {
                        "title": f"NETWORK BREAKDOWN: {self.location_name} Gate Obliterated",
                        "description": f"Transit authorities confirm the complete destruction of {self.location_name} gate facility. "
                                      f"The {total_casualties:,} personnel who maintained this crucial link died at their posts. "
                                      f"Alternative routing is being established, but expect significant delays."
                    }
                ]
            }
            
            # Get variants for this location type, fallback to generic if type not found
            news_variants = location_type_variants.get(self.location_type, [
                {
                    "title": f"BREAKING: {self.location_name} Completely Destroyed",
                    "description": f"In a catastrophic event, {self.location_name} has been completely annihilated. "
                                  f"All {total_casualties:,} inhabitants are confirmed lost. "
                                  f"The cause of the destruction remains unknown."
                },
                {
                    "title": f"DISASTER: {self.location_name} Wiped From Galaxy Maps",
                    "description": f"Tragic news reaches us as {self.location_name} has been utterly destroyed. "
                                  f"Emergency services report {total_casualties:,} casualties. "
                                  f"The location has been removed from all navigation systems."
                }
            ])
        
        selected_news = random.choice(news_variants)
        
        # Queue the news message
        await galactic_news_cog.queue_news(
            guild_id=self.cog.bot.guilds[0].id if self.cog.bot.guilds else None,
            news_type='major_event',
            title=selected_news['title'],
            description=selected_news['description'],
            location_id=nearest_location_id
        )




class SubLocationShuffleConfirmView(discord.ui.View):
    """Confirmation view for sub-location shuffling"""
    
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
    
    @discord.ui.button(label="Confirm Shuffle", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Execute the sub-location shuffle"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Start transaction for safe operation
            conn = self.cog.db.begin_transaction()
            
            # Get all locations for regeneration
            all_locations = self.cog.db.execute_in_transaction(
                conn,
                """SELECT location_id, location_type, wealth_level, is_derelict 
                   FROM locations 
                   WHERE is_generated = true OR is_generated = false""",
                fetch='all'
            )
            
            if not all_locations:
                await interaction.followup.send("❌ No locations found to process.", ephemeral=True)
                self.cog.db.rollback_transaction(conn)
                return
            
            # Clear all existing sub-locations
            self.cog.db.execute_in_transaction(
                conn,
                "DELETE FROM sub_locations",
            )
            
            # Import SubLocationManager
            from utils.sub_locations import SubLocationManager
            sub_manager = SubLocationManager(self.cog.bot)
            
            # Regenerate sub-locations for all locations
            sub_locations_to_insert = []
            
            for location in all_locations:
                location_id, location_type, wealth_level, is_derelict = location
                
                # Get sub-location data for this location
                generated_subs = await sub_manager.get_persistent_sub_locations_data(
                    location_id,
                    location_type,
                    wealth_level,
                    bool(is_derelict)
                )
                
                sub_locations_to_insert.extend(generated_subs)
            
            # Bulk insert new sub-locations
            if sub_locations_to_insert:
                query = '''INSERT INTO sub_locations 
                          (parent_location_id, name, sub_type, description, is_active)
                          VALUES (%s, %s, %s, %s, 1)'''
                self.cog.db.executemany_in_transaction(conn, query, sub_locations_to_insert)
            
            # Commit the transaction
            self.cog.db.commit_transaction(conn)
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Sub-Locations Shuffled Successfully",
                description=f"Regenerated **{len(sub_locations_to_insert)}** sub-locations across **{len(all_locations)}** locations.",
                color=0x00ff00
            )
            embed.add_field(
                name="📊 Statistics",
                value=f"Locations processed: {len(all_locations)}\n"
                      f"Sub-locations created: {len(sub_locations_to_insert)}\n"
                      f"Average per location: {len(sub_locations_to_insert) / len(all_locations):.1f}",
                inline=False
            )
            embed.add_field(
                name="🔄 What's New",
                value="• All sub-locations follow current generation rules\n"
                      "• Newly added sub-location types are now included\n"
                      "• Sub-locations match current location wealth levels",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            # Rollback on error
            if 'conn' in locals():
                self.cog.db.rollback_transaction(conn)
            
            error_embed = discord.Embed(
                title="❌ Shuffle Failed",
                description=f"An error occurred during the shuffle operation:\n```{str(e)}```",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the shuffle operation"""
        embed = discord.Embed(
            title="❌ Shuffle Cancelled",
            description="Sub-location shuffle has been cancelled. No changes were made.",
            color=0x808080
        )
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(CreationCog(bot))