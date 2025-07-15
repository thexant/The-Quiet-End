# cogs/ship_systems.py
import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime
from utils.channel_manager import ChannelManager
from discord.ui import View, Button, button
import re

class BoardingRequestView(View):
    def __init__(self, bot, requester: discord.Member, target_ship_id: int, target_owner: discord.Member):
        super().__init__(timeout=300)
        self.bot = bot
        self.requester = requester
        self.target_ship_id = target_ship_id
        self.target_owner = target_owner
        self.response = None
    
    @button(label="Accept Boarding", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_owner.id:
            await interaction.response.send_message("This is not your decision to make.", ephemeral=True)
            return

        # Check if requester is still at the same location as the owner's ship
        requester_char = self.bot.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (self.requester.id,), fetch='one'
        )
        owner_char = self.bot.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (self.target_owner.id,), fetch='one'
        )

        if not requester_char or not owner_char or requester_char[0] != owner_char[0] or requester_char[1] != 'docked':
            await interaction.response.edit_message(content="Boarding cancelled. The requesting player is no longer docked at your location.", view=None)
            return

        # Grant access and move player
        channel_manager = ChannelManager(self.bot)
        success = await channel_manager.give_user_ship_access(self.requester, self.target_ship_id)

        if success:
            # Remove from location, put in ship
            self.bot.db.execute_query(
                "UPDATE characters SET current_ship_id = ?, current_location = NULL WHERE user_id = ?",
                (self.target_ship_id, self.requester.id)
            )
            await channel_manager.remove_user_location_access(self.requester, owner_char[0])

            await interaction.response.edit_message(content=f"✅ You have granted {self.requester.display_name} access to your ship.", view=None)
            try:
                await interaction.followup.send(f"🚀 {self.requester.mention} - {self.target_owner.display_name} has accepted your boarding request! You may now enter their ship's channel.")
            except discord.Forbidden:
                pass
        else:
            await interaction.response.edit_message(content="Failed to grant access to the ship. An error occurred.", view=None)

        self.response = True
        self.stop()

    @button(label="Deny Boarding", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_owner.id:
            await interaction.response.send_message("This is not your decision to make.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"❌ You have denied {self.requester.display_name}'s boarding request.", view=None)
        try:
            await interaction.followup.send(f"🚫 {self.requester.mention} - {self.target_owner.display_name} has denied your boarding request.")
        except discord.Forbidden:
            pass

        self.response = False
        self.stop()
class ShipSystemsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    ship_group = app_commands.Group(name="ship", description="Ship management and customization")
    
    @ship_group.command(name="customize", description="Customize your ship's appearance, name, and apply upgrades")
    @app_commands.describe(
        new_name="New name for your ship",
        ship_class="Ship class (civilian, military, industrial)",
        exterior_addition="Add to exterior description (additive)",
        interior_addition="Add to interior description (additive)"
    )
    @app_commands.choices(ship_class=[
        app_commands.Choice(name="Civilian", value="civilian"),
        app_commands.Choice(name="Military", value="military"), 
        app_commands.Choice(name="Industrial", value="industrial"),
        app_commands.Choice(name="Explorer", value="explorer")
    ])
    async def customize_ship(self, interaction: discord.Interaction, 
                            new_name: str = None, 
                            ship_class: str = None,
                            exterior_addition: str = None,
                            interior_addition: str = None):
        # Get character's active ship
        ship_info = self.db.execute_query(
            '''SELECT s.ship_id, s.name, s.ship_class, s.ship_type, s.exterior_description, s.interior_description, c.money
               FROM characters c
               JOIN ships s ON c.active_ship_id = s.ship_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("You don't have an active ship!", ephemeral=True)
            return
        
        ship_id, current_name, current_class, ship_type, current_exterior, current_interior, money = ship_info
        
        # Check if character is at a location with shipyard services
        location_info = self.db.execute_query(
            '''SELECT l.has_shipyard, l.name FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.response.send_message("You need to be at a shipyard to customize your ship.", ephemeral=True)
            return
        
        costs = []
        total_cost = 0
        changes = []
        
        # Name change cost
        if new_name and new_name != current_name:
            if len(new_name) > 50:
                await interaction.response.send_message("Ship name must be 50 characters or less.", ephemeral=True)
                return
            cost = 150
            costs.append(f"Name change: {cost} credits")
            total_cost += cost
            changes.append(f"Name: {current_name} → {new_name}")
        
        # Class change cost
        if ship_class and ship_class != current_class:
            cost = 500
            costs.append(f"Class change: {cost} credits")
            total_cost += cost
            changes.append(f"Class: {current_class} → {ship_class}")
        
        # Exterior description addition cost
        if exterior_addition:
            if len(exterior_addition) > 200:
                await interaction.response.send_message("Exterior addition must be 200 characters or less.", ephemeral=True)
                return
            cost = 300
            costs.append(f"Exterior addition: {cost} credits")
            total_cost += cost
            changes.append(f"Added exterior detail: {exterior_addition[:50]}...")
        
        # Interior description addition cost
        if interior_addition:
            if len(interior_addition) > 200:
                await interaction.response.send_message("Interior addition must be 200 characters or less.", ephemeral=True)
                return
            cost = 300
            costs.append(f"Interior addition: {cost} credits")
            total_cost += cost
            changes.append(f"Added interior detail: {interior_addition[:50]}...")
        
        if total_cost == 0:
            # Show upgrade application interface if no other changes
            await self._show_upgrade_application_interface(interaction, ship_id, money)
            return
        
        if money < total_cost:
            await interaction.response.send_message(
                f"Insufficient credits! Need {total_cost:,}, have {money:,}.",
                ephemeral=True
            )
            return
        
        # Apply changes
        update_query = "UPDATE ships SET "
        update_params = []
        
        if new_name:
            update_query += "name = ?, "
            update_params.append(new_name)
        
        if ship_class:
            update_query += "ship_class = ?, "
            update_params.append(ship_class)
        
        # Handle additive descriptions
        if exterior_addition:
            new_exterior = current_exterior + f"\n\n--- Custom Addition ---\n{exterior_addition}"
            update_query += "exterior_description = ?, "
            update_params.append(new_exterior)
            
            # Record customization
            self.db.execute_query(
                '''INSERT INTO ship_customizations (ship_id, customization_type, addition_text, added_by, cost_paid)
                   VALUES (?, 'exterior', ?, ?, ?)''',
                (ship_id, exterior_addition, interaction.user.id, 300)
            )
        
        if interior_addition:
            new_interior = current_interior + f"\n\n--- Custom Addition ---\n{interior_addition}"
            update_query += "interior_description = ?, "
            update_params.append(new_interior)
            
            # Record customization
            self.db.execute_query(
                '''INSERT INTO ship_customizations (ship_id, customization_type, addition_text, added_by, cost_paid)
                   VALUES (?, 'interior', ?, ?, ?)''',
                (ship_id, interior_addition, interaction.user.id, 300)
            )
        
        update_query = update_query.rstrip(", ") + " WHERE ship_id = ?"
        update_params.append(ship_id)
        
        self.db.execute_query(update_query, update_params)
        
        # Deduct credits
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚀 Ship Customization Complete",
            description="Your ship has been successfully customized!",
            color=0x00ff00
        )
        
        embed.add_field(name="Changes Made", value="\n".join(changes), inline=False)
        embed.add_field(name="Total Cost", value=f"{total_cost:,} credits", inline=True)
        embed.add_field(name="Remaining Credits", value=f"{money - total_cost:,}", inline=True)
        
        # Show upgrade application interface
        view = UpgradeApplicationView(self.bot, interaction.user.id, ship_id)
        embed.add_field(name="💡 Apply Upgrades", value="Use the buttons below to apply upgrade items from your inventory", inline=False)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_upgrade_application_interface(self, interaction: discord.Interaction, ship_id: int, money: int):
        """Show interface for applying upgrades from inventory"""
        embed = discord.Embed(
            title="🔧 Apply Ship Upgrades",
            description="Apply upgrade items from your inventory to your ship",
            color=0x4169e1
        )
        
        view = UpgradeApplicationView(self.bot, interaction.user.id, ship_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @ship_group.command(name="upgrade", description="Upgrade your ship with new components")
    async def upgrade_ship(self, interaction: discord.Interaction):
        # Get character location and ship info
        char_info = self.db.execute_query(
            '''SELECT c.current_location, c.money, l.has_upgrades, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, money, has_upgrades, location_name = char_info
        
        if not has_upgrades:
            await interaction.response.send_message(f"{location_name} doesn't offer ship upgrade services.", ephemeral=True)
            return
        
        # Get ship info
        ship_info = self.db.execute_query(
            '''SELECT ship_id, name, upgrade_slots, used_upgrade_slots, fuel_efficiency, 
                      combat_rating, cargo_capacity
               FROM ships WHERE owner_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("You don't have a ship!", ephemeral=True)
            return
        
        ship_id, ship_name, upgrade_slots, used_slots, fuel_eff, combat_rating, cargo_cap = ship_info
        
        if used_slots >= upgrade_slots:
            await interaction.response.send_message("Your ship has no available upgrade slots!", ephemeral=True)
            return
        
        # Generate available upgrades based on location wealth
        location_wealth = self.db.execute_query(
            "SELECT wealth_level FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )[0]
        
        available_upgrades = self._generate_upgrades(location_wealth)
        
        embed = discord.Embed(
            title=f"🔧 Ship Upgrades - {location_name}",
            description=f"**{ship_name}** - {used_slots}/{upgrade_slots} upgrade slots used",
            color=0x4169e1
        )
        
        upgrade_text = []
        for upgrade_name, upgrade_type, cost, bonus, description in available_upgrades:
            upgrade_text.append(f"**{upgrade_name}** - {cost:,} credits")
            upgrade_text.append(f"  {description}")
            upgrade_text.append(f"  Effect: +{bonus} {upgrade_type}")
            upgrade_text.append("")
        
        embed.add_field(
            name="Available Upgrades",
            value="\n".join(upgrade_text[:20]),  # Limit display
            inline=False
        )
        
        embed.add_field(name="Your Credits", value=f"{money:,}", inline=True)
        embed.add_field(name="Available Slots", value=f"{upgrade_slots - used_slots}", inline=True)
        
        view = ShipUpgradeView(self.bot, interaction.user.id, available_upgrades)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _generate_upgrades(self, location_wealth):
        """Generate available upgrades based on location wealth"""
        
        base_upgrades = [
            ("Basic Engine Tuning", "fuel_efficiency", 300, 1, "Improves fuel consumption"),
            ("Cargo Bay Expansion", "cargo_capacity", 500, 25, "Increases cargo storage"),
            ("Hull Reinforcement", "max_hull", 400, 20, "Strengthens ship structure"),
            ("Improved Cooling", "fuel_efficiency", 450, 2, "Better heat management"),
            ("Storage Optimization", "cargo_capacity", 350, 15, "Optimizes storage space"),
        ]
        
        advanced_upgrades = [
            ("Military-Grade Engines", "fuel_efficiency", 1200, 3, "High-performance propulsion"),
            ("Combat Targeting System", "combat_rating", 800, 2, "Improved weapon accuracy"),
            ("Advanced Navigation", "navigation_bonus", 600, 2, "Enhanced pathfinding"),
            ("Emergency Shields", "max_hull", 900, 35, "Defensive energy barriers"),
            ("Rapid-Fire Systems", "combat_rating", 1100, 3, "Increased combat effectiveness"),
        ]
        
        premium_upgrades = [
            ("Quantum Drive Core", "fuel_efficiency", 2500, 5, "Revolutionary propulsion"),
            ("Aegis Defense Grid", "combat_rating", 2000, 5, "Ultimate defensive system"),
            ("Dimensional Storage", "cargo_capacity", 1800, 50, "Extra-dimensional cargo space"),
            ("AI Navigation Core", "navigation_bonus", 2200, 5, "Artificial intelligence guidance"),
        ]
        
        # Select upgrades based on wealth
        available = base_upgrades.copy()
        
        if location_wealth >= 6:
            available.extend(random.sample(advanced_upgrades, min(3, len(advanced_upgrades))))
        
        if location_wealth >= 8:
            available.extend(random.sample(premium_upgrades, min(2, len(premium_upgrades))))
        
        return random.sample(available, min(6, len(available)))
    
    @ship_group.command(name="group_ship", description="Manage group ship settings")
    async def group_ship(self, interaction: discord.Interaction):
        # Check if user is in a group
        group_info = self.db.execute_query(
            '''SELECT g.group_id, g.name, g.leader_id
               FROM characters c
               JOIN groups g ON c.group_id = g.group_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("You're not in a group!", ephemeral=True)
            return
        
        group_id, group_name, leader_id = group_info
        
        # Check if group already has a ship
        group_ship = self.db.execute_query(
            '''SELECT gs.ship_id, gs.captain_id, s.name, s.ship_type, c.name as captain_name
               FROM group_ships gs
               JOIN ships s ON gs.ship_id = s.ship_id
               LEFT JOIN characters c ON gs.captain_id = c.user_id
               WHERE gs.group_id = ?''',
            (group_id,),
            fetch='one'
        )
        
        embed = discord.Embed(
            title=f"🚀 Group Ship - {group_name}",
            color=0x9932cc
        )
        
        if group_ship:
            ship_id, captain_id, ship_name, ship_type, captain_name = group_ship
            
            embed.add_field(name="Current Group Ship", value=f"**{ship_name}** ({ship_type})", inline=False)
            embed.add_field(name="Captain", value=captain_name or "None", inline=True)
            
            # Get crew positions
            crew_positions = self.db.execute_query(
                "SELECT crew_positions FROM group_ships WHERE group_id = ?",
                (group_id,),
                fetch='one'
            )[0]
            
            if crew_positions:
                import json
                positions = json.loads(crew_positions)
                crew_text = []
                for position, user_id in positions.items():
                    member = interaction.guild.get_member(int(user_id)) if user_id else None
                    crew_text.append(f"{position}: {member.display_name if member else 'Empty'}")
                
                embed.add_field(name="Crew Positions", value="\n".join(crew_text), inline=False)
        else:
            embed.add_field(name="No Group Ship", value="This group doesn't have a designated group ship yet.", inline=False)
        
        view = GroupShipView(self.bot, interaction.user.id, group_id, leader_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    # In cogs/ship_systems.py, inside the ShipSystemsCog class

    interior_group = app_commands.Group(name="interior", description="Manage your ship's interior", parent=ship_group)

    @interior_group.command(name="enter", description="Enter your own ship's interior.")
    async def enter_ship(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check character status
        char_info = self.db.execute_query(
            "SELECT current_location, location_status, current_ship_id FROM characters WHERE user_id = ?",
            (interaction.user.id,), fetch='one'
        )
        if not char_info:
            await interaction.followup.send("You don't have a character.", ephemeral=True)
            return

        current_location, location_status, current_ship_id = char_info

        if current_ship_id:
            await interaction.followup.send("You are already inside a ship!", ephemeral=True)
            return
        if not current_location or location_status != 'docked':
            await interaction.followup.send("You must be docked at a location to enter your ship.", ephemeral=True)
            return

        # Get ship info for channel creation
        ship_info_raw = self.db.execute_query(
            "SELECT ship_id, name, ship_type, interior_description, channel_id FROM ships WHERE owner_id = ?",
            (interaction.user.id,), fetch='one'
        )
        if not ship_info_raw:
            await interaction.followup.send("You don't own a ship.", ephemeral=True)
            return

        ship_id = ship_info_raw[0]

        # Update ship's docking location
        self.db.execute_query(
            "UPDATE ships SET docked_at_location = ? WHERE ship_id = ?",
            (current_location, ship_id)
        )

        # Get or create channel
        channel_manager = ChannelManager(self.bot)
        ship_channel = await channel_manager.get_or_create_ship_channel(interaction.guild, ship_info_raw, interaction.user)

        if not ship_channel:
            await interaction.followup.send("Could not access the ship's interior. Please try again later.", ephemeral=True)
            return

        # Update player location (set ship_id, nullify location_id)
        self.db.execute_query(
            "UPDATE characters SET current_ship_id = ?, current_location = NULL WHERE user_id = ?",
            (ship_id, interaction.user.id)
        )

        # Remove from physical location channel
        await channel_manager.remove_user_location_access(interaction.user, current_location)

        await interaction.followup.send(f"You have entered your ship, '{ship_info_raw[1]}'. Head to {ship_channel.mention}.", ephemeral=True)

    @interior_group.command(name="leave", description="Leave the ship interior and return to the docking location.")
    async def leave_ship(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check if character is in a ship
        char_info = self.db.execute_query(
            "SELECT current_ship_id FROM characters WHERE user_id = ?",
            (interaction.user.id,), fetch='one'
        )
        if not char_info or not char_info[0]:
            await interaction.followup.send("You are not currently inside a ship.", ephemeral=True)
            return

        current_ship_id = char_info[0]

        # Get the ship's docking location
        ship_location = self.db.execute_query(
            "SELECT docked_at_location FROM ships WHERE ship_id = ?",
            (current_ship_id,), fetch='one'
        )

        if not ship_location or not ship_location[0]:
            await interaction.followup.send("Cannot leave ship. The ship is not currently docked at a known location.", ephemeral=True)
            return

        ship_location_id = ship_location[0]

        # Update player location (set location_id, nullify ship_id)
        self.db.execute_query(
            "UPDATE characters SET current_location = ?, current_ship_id = NULL WHERE user_id = ?",
            (ship_location_id, interaction.user.id)
        )

        # Manage channel access
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        await channel_manager.remove_user_ship_access(interaction.user, current_ship_id)
        await channel_manager.give_user_location_access(interaction.user, ship_location_id)
        
        # NEW: Trigger immediate ship cleanup check
        await channel_manager.immediate_ship_cleanup(interaction.guild, current_ship_id)

        location_name = self.db.execute_query("SELECT name FROM locations WHERE location_id = ?", (ship_location_id,), fetch='one')[0]
        await interaction.followup.send(f"You have left the ship and returned to **{location_name}**.", ephemeral=True)

    @interior_group.command(name="board", description="Request to board another player's ship.")
    @app_commands.describe(target="The player whose ship you want to board.")
    async def board_ship(self, interaction: discord.Interaction, target: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if target.id == interaction.user.id:
            await interaction.followup.send("Use `/ship interior enter` to get into your own ship.", ephemeral=True)
            return

        # Check that both players are docked at the same location
        requester_char = self.db.execute_query(
            "SELECT current_location, location_status, name FROM characters WHERE user_id = ?",
            (interaction.user.id,), fetch='one'
        )
        target_char = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = ?",
            (target.id,), fetch='one'
        )

        if not requester_char or requester_char[1] != 'docked':
            await interaction.followup.send("You must be docked to request boarding.", ephemeral=True)
            return
        if not target_char or target_char[1] != 'docked':
            await interaction.followup.send(f"{target.display_name}'s ship is not currently docked.", ephemeral=True)
            return
        if requester_char[0] != target_char[0]:
            await interaction.followup.send(f"You must be at the same location as {target.display_name} to board their ship.", ephemeral=True)
            return

        # Get target ship ID
        target_ship_id = self.db.execute_query(
            "SELECT ship_id FROM characters WHERE user_id = ?", (target.id,), fetch='one'
        )
        if not target_ship_id:
            await interaction.followup.send(f"{target.display_name} does not seem to have a ship.", ephemeral=True)
            return
        target_ship_id = target_ship_id[0]

        # Send boarding request to location channel instead of DM
        try:
            location_channel_id = self.db.execute_query(
                "SELECT channel_id FROM locations WHERE location_id = ?",
                (requester_char[0],),  # current_location
                fetch='one'
            )
            
            if location_channel_id and location_channel_id[0]:
                location_channel = interaction.guild.get_channel(location_channel_id[0])
                if location_channel:
                    view = BoardingRequestView(self.bot, interaction.user, target_ship_id, target)
                    embed = discord.Embed(
                        title="🚀 Boarding Request",
                        description=f"**{interaction.user.display_name}** (character: {requester_char[2]}) is requesting to board {target.mention}'s ship.",
                        color=0x4169e1
                    )
                    embed.add_field(name="⏰ Time Limit", value="5 minutes to respond", inline=False)
                    
                    await location_channel.send(f"{target.mention}", embed=embed, view=view)
                    await interaction.followup.send(f"Boarding request sent to the location channel for {target.display_name}.", ephemeral=True)
                else:
                    await interaction.followup.send("Could not send boarding request - location channel not found.", ephemeral=True)
            else:
                await interaction.followup.send("Could not send boarding request - this location doesn't have a channel.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"Error sending boarding request: {e}", ephemeral=True)
            
    @ship_group.command(name="shipyard", description="Access shipyard services")
    async def shipyard(self, interaction: discord.Interaction):
        # Check if at a shipyard
        location_info = self.db.execute_query(
            '''SELECT l.has_shipyard, l.name, l.wealth_level FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.response.send_message("This location doesn't have shipyard services.", ephemeral=True)
            return
        
        _, location_name, wealth_level = location_info
        
        # Get character info
        char_info = self.db.execute_query(
            "SELECT money, active_ship_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        money, active_ship_id = char_info
        
        # Get active ship info if any
        active_ship_info = None
        if active_ship_id:
            active_ship_info = self.db.execute_query(
                "SELECT name, ship_type FROM ships WHERE ship_id = ?",
                (active_ship_id,),
                fetch='one'
            )
        
        # Get stored ships
        stored_ships = self.db.execute_query(
            '''SELECT ps.ship_storage_id, s.ship_id, s.name, s.ship_type, ps.is_active
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = ?
               ORDER BY ps.acquired_date DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"🚢 Shipyard Services - {location_name}",
            description="Manage your fleet and purchase new ships",
            color=0x2F4F4F
        )
        
        if active_ship_info:
            embed.add_field(
                name="🚀 Active Ship",
                value=f"**{active_ship_info[0]}** ({active_ship_info[1]})",
                inline=True
            )
        else:
            embed.add_field(
                name="🚀 Active Ship",
                value="None (You need a ship to travel)",
                inline=True
            )
        
        embed.add_field(name="💰 Credits", value=f"{money:,}", inline=True)
        embed.add_field(name="🏭 Shipyard Quality", value=f"Tier {min(wealth_level//2 + 1, 5)}", inline=True)
        
        if stored_ships:
            ship_list = []
            for storage_id, ship_id, ship_name, ship_type, is_active in stored_ships[:5]:
                status = "🟢 Active" if is_active else "🔵 Stored"
                ship_list.append(f"{status} **{ship_name}** ({ship_type})")
            
            embed.add_field(name="🏪 Your Fleet", value="\n".join(ship_list), inline=False)
        
        view = ShipyardView(self.bot, interaction.user.id, wealth_level, active_ship_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)        
async def setup(bot):
    await bot.add_cog(ShipSystemsCog(bot))            
class ShipUpgradeView(discord.ui.View):
    def __init__(self, bot, user_id: int, upgrades: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.upgrades = upgrades
        
        # Add upgrade options to select menu
        options = []
        for i, (name, upgrade_type, cost, bonus, description) in enumerate(upgrades[:25]):
            options.append(
                discord.SelectOption(
                    label=f"{name} - {cost:,} credits",
                    description=f"+{bonus} {upgrade_type}: {description[:50]}",
                    value=str(i)
                )
            )
        
        if options:
            select = discord.ui.Select(placeholder="Choose an upgrade...", options=options)
            select.callback = self.upgrade_callback
            self.add_item(select)
    
    async def upgrade_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your upgrade panel!", ephemeral=True)
            return
        
        upgrade_index = int(interaction.data['values'][0])
        upgrade_name, upgrade_type, cost, bonus, description = self.upgrades[upgrade_index]
        
        # Check if user can afford it
        char_info = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or char_info[0] < cost:
            await interaction.response.send_message(
                f"Insufficient credits! Need {cost:,}, have {char_info[0] if char_info else 0:,}.",
                ephemeral=True
            )
            return
        
        # Get ship info
        ship_info = self.db.execute_query(
            "SELECT ship_id, upgrade_slots, used_upgrade_slots FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if ship_info[2] >= ship_info[1]:
            await interaction.response.send_message("No upgrade slots available!", ephemeral=True)
            return
        
        # Install upgrade
        self.db.execute_query(
            '''INSERT INTO ship_upgrades (ship_id, upgrade_type, upgrade_name, bonus_value)
               VALUES (?, ?, ?, ?)''',
            (ship_info[0], upgrade_type, upgrade_name, bonus)
        )
        
        # Update ship stats
        if upgrade_type == "fuel_efficiency":
            self.db.execute_query(
                "UPDATE ships SET fuel_efficiency = fuel_efficiency + ?, used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = ?",
                (bonus, ship_info[0])
            )
        elif upgrade_type == "cargo_capacity":
            self.db.execute_query(
                "UPDATE ships SET cargo_capacity = cargo_capacity + ?, used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = ?",
                (bonus, ship_info[0])
            )
        elif upgrade_type == "max_hull":
            self.db.execute_query(
                "UPDATE ships SET max_hull = max_hull + ?, hull_integrity = hull_integrity + ?, used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = ?",
                (bonus, bonus, ship_info[0])
            )
        elif upgrade_type == "combat_rating":
            self.db.execute_query(
                "UPDATE ships SET combat_rating = combat_rating + ?, used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = ?",
                (bonus, ship_info[0])
            )
        else:
            # For other upgrades, just mark as installed
            self.db.execute_query(
                "UPDATE ships SET used_upgrade_slots = used_upgrade_slots + 1 WHERE ship_id = ?",
                (ship_info[0],)
            )
        
        # Deduct credits
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (cost, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🔧 Upgrade Installed",
            description=f"Successfully installed **{upgrade_name}**!",
            color=0x00ff00
        )
        
        embed.add_field(name="Effect", value=f"+{bonus} {upgrade_type}", inline=True)
        embed.add_field(name="Cost", value=f"{cost:,} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GroupShipView(discord.ui.View):
    def __init__(self, bot, user_id: int, group_id: int, leader_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.group_id = group_id
        self.leader_id = leader_id
    
    @discord.ui.button(label="Designate My Ship", style=discord.ButtonStyle.primary, emoji="🚀")
    async def designate_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.leader_id:
            await interaction.response.send_message("Only the group leader can designate the group ship!", ephemeral=True)
            return
        
        # Get user's ship
        ship_info = self.db.execute_query(
            "SELECT ship_id, name FROM ships WHERE owner_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("You don't have a ship!", ephemeral=True)
            return
        
        # Set as group ship
        self.db.execute_query(
            "INSERT OR REPLACE INTO group_ships (group_id, ship_id, captain_id) VALUES (?, ?, ?)",
            (self.group_id, ship_info[0], interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚀 Group Ship Designated",
            description=f"**{ship_info[1]}** is now the group ship!",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class UpgradeApplicationView(discord.ui.View):
    def __init__(self, bot, user_id: int, ship_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
    
    @discord.ui.button(label="Apply Upgrade Items", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def apply_upgrades(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your upgrade panel!", ephemeral=True)
            return
        
        # Get upgrade items from inventory
        upgrade_items = self.bot.db.execute_query(
            '''SELECT item_id, item_name, description, quantity
               FROM inventory 
               WHERE owner_id = ? AND item_type = 'upgrade' AND quantity > 0
               ORDER BY item_name''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not upgrade_items:
            await interaction.response.send_message("You don't have any upgrade items in your inventory.", ephemeral=True)
            return
        
        # Create selection interface
        options = []
        for item_id, item_name, description, quantity in upgrade_items[:25]:
            options.append(
                discord.SelectOption(
                    label=f"{item_name} ({quantity}x)",
                    description=description[:100],
                    value=str(item_id)
                )
            )
        
        select = discord.ui.Select(placeholder="Choose an upgrade to apply...", options=options)
        select.callback = self.upgrade_select_callback
        
        view = discord.ui.View(timeout=300)
        view.add_item(select)
        
        embed = discord.Embed(
            title="🔧 Available Upgrade Items",
            description="Select an upgrade item from your inventory to apply to your ship",
            color=0x4169e1
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def upgrade_select_callback(self, interaction: discord.Interaction):
        item_id = int(interaction.data['values'][0])
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_name, description, metadata
               FROM inventory WHERE item_id = ?''',
            (item_id,),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item not found!", ephemeral=True)
            return
        
        item_name, description, metadata = item_info
        
        # Parse upgrade effect from metadata
        import json
        try:
            meta = json.loads(metadata) if metadata else {}
            effect_value = meta.get('effect_value', '')
            
            if ':' in effect_value:
                upgrade_type, bonus_str = effect_value.split(':')
                bonus = int(bonus_str)
            else:
                await interaction.response.send_message("Invalid upgrade item format!", ephemeral=True)
                return
        except:
            await interaction.response.send_message("Error reading upgrade item data!", ephemeral=True)
            return
        
        # Apply upgrade to ship
        if upgrade_type == "fuel_efficiency":
            self.bot.db.execute_query(
                "UPDATE ships SET fuel_efficiency = fuel_efficiency + ? WHERE ship_id = ?",
                (bonus, self.ship_id)
            )
        elif upgrade_type == "max_hull":
            self.bot.db.execute_query(
                "UPDATE ships SET max_hull = max_hull + ?, hull_integrity = hull_integrity + ? WHERE ship_id = ?",
                (bonus, bonus, self.ship_id)
            )
        elif upgrade_type == "cargo_capacity":
            self.bot.db.execute_query(
                "UPDATE ships SET cargo_capacity = cargo_capacity + ? WHERE ship_id = ?",
                (bonus, self.ship_id)
            )
        elif upgrade_type == "combat_rating":
            self.bot.db.execute_query(
                "UPDATE ships SET combat_rating = combat_rating + ? WHERE ship_id = ?",
                (bonus, self.ship_id)
            )
        
        # Remove item from inventory
        self.bot.db.execute_query(
            "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?",
            (item_id,)
        )
        
        # Remove if quantity is 0
        self.bot.db.execute_query(
            "DELETE FROM inventory WHERE item_id = ? AND quantity <= 0",
            (item_id,)
        )
        
        # Record upgrade installation
        self.bot.db.execute_query(
            '''INSERT INTO ship_upgrades (ship_id, upgrade_type, upgrade_name, bonus_value)
               VALUES (?, ?, ?, ?)''',
            (self.ship_id, upgrade_type, item_name, bonus)
        )
        
        embed = discord.Embed(
            title="✅ Upgrade Applied",
            description=f"Successfully applied **{item_name}** to your ship!",
            color=0x00ff00
        )
        
        embed.add_field(name="Effect", value=f"+{bonus} {upgrade_type.replace('_', ' ').title()}", inline=True)
        embed.add_field(name="Item Used", value=item_name, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)        
class ShipyardView(discord.ui.View):
    def __init__(self, bot, user_id: int, wealth_level: int, active_ship_id: int = None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.wealth_level = wealth_level
        self.active_ship_id = active_ship_id
    
    @discord.ui.button(label="Buy Ship", style=discord.ButtonStyle.success, emoji="🛒")
    async def buy_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your shipyard panel!", ephemeral=True)
            return
        
        # Generate available ships based on wealth level
        available_ships = self._generate_available_ships()
        
        if not available_ships:
            await interaction.response.send_message("No ships available for purchase at this shipyard.", ephemeral=True)
            return
        
        options = []
        for ship_data in available_ships[:25]:
            name, ship_type, price, description = ship_data
            options.append(
                discord.SelectOption(
                    label=f"{name} - {price:,} credits",
                    description=f"{ship_type}: {description[:80]}",
                    value=f"{ship_type}|{name}|{price}"
                )
            )
        
        select = discord.ui.Select(placeholder="Choose a ship to purchase...", options=options)
        select.callback = self.purchase_ship_callback
        
        purchase_view = discord.ui.View(timeout=300)
        purchase_view.add_item(select)
        
        embed = discord.Embed(
            title="🛒 Ships for Sale",
            description="Available ships at this shipyard",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, view=purchase_view, ephemeral=True)
    
    @discord.ui.button(label="Sell Ship", style=discord.ButtonStyle.danger, emoji="💰")
    async def sell_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your shipyard panel!", ephemeral=True)
            return
        
        if not self.active_ship_id:
            await interaction.response.send_message("You don't have an active ship to sell.", ephemeral=True)
            return
        
        # Get ship details
        ship_info = self.db.execute_query(
            '''SELECT name, ship_type, fuel_capacity, cargo_capacity, combat_rating, fuel_efficiency
               FROM ships WHERE ship_id = ?''',
            (self.active_ship_id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.response.send_message("Ship not found!", ephemeral=True)
            return
        
        # Calculate sale price (60-80% of estimated value based on specs)
        base_value = self._calculate_ship_value(ship_info)
        sale_price = int(base_value * (0.6 + (self.wealth_level * 0.02)))
        
        embed = discord.Embed(
            title="💰 Sell Ship",
            description=f"Are you sure you want to sell **{ship_info[0]}**?",
            color=0xff9900
        )
        
        embed.add_field(name="Ship Type", value=ship_info[1], inline=True)
        embed.add_field(name="Sale Price", value=f"{sale_price:,} credits", inline=True)
        embed.add_field(name="⚠️ Warning", value="You won't be able to travel without a ship!", inline=False)
        
        view = SellShipConfirmView(self.bot, self.user_id, self.active_ship_id, sale_price)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Swap Ships", style=discord.ButtonStyle.primary, emoji="🔄")
    async def swap_ships(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your shipyard panel!", ephemeral=True)
            return
        
        # Get stored ships
        stored_ships = self.db.execute_query(
            '''SELECT ps.ship_storage_id, s.ship_id, s.name, s.ship_type, ps.is_active
               FROM player_ships ps
               JOIN ships s ON ps.ship_id = s.ship_id
               WHERE ps.owner_id = ? AND ps.is_active = 0
               ORDER BY ps.acquired_date DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not stored_ships:
            await interaction.response.send_message("You don't have any ships in storage.", ephemeral=True)
            return
        
        options = []
        for storage_id, ship_id, ship_name, ship_type, is_active in stored_ships[:25]:
            options.append(
                discord.SelectOption(
                    label=f"{ship_name} ({ship_type})",
                    description=f"Stored ship - Click to make active",
                    value=str(ship_id)
                )
            )
        
        select = discord.ui.Select(placeholder="Choose a ship to activate...", options=options)
        select.callback = self.swap_ship_callback
        
        swap_view = discord.ui.View(timeout=300)
        swap_view.add_item(select)
        
        embed = discord.Embed(
            title="🔄 Ship Storage",
            description="Select a stored ship to make active",
            color=0x4169e1
        )
        
        await interaction.response.send_message(embed=embed, view=swap_view, ephemeral=True)
    
    def _generate_available_ships(self):
        """Generate ships available for purchase based on shipyard tier"""
        from utils.ship_data import STARTER_SHIP_CLASSES, generate_random_ship_name
        import random
        
        available = []
        
        # Basic ships always available
        for ship_type in STARTER_SHIP_CLASSES.keys():
            name = generate_random_ship_name()
            base_price = {"Hauler": 2500, "Scout": 3000, "Courier": 3500, "Shuttle": 2000}
            price = base_price.get(ship_type, 2500) + random.randint(-500, 1000)
            description = f"A reliable {ship_type.lower()} for general use"
            available.append((name, ship_type, price, description))
        
        # Higher tier ships for wealthy shipyards
        if self.wealth_level >= 6:
            advanced_ships = [
                ("Heavy Freighter", 8000, "Large cargo capacity for bulk transport"),
                ("Fast Courier", 6500, "Enhanced speed for urgent deliveries"),
                ("Explorer", 7500, "Long-range vessel with advanced sensors")
            ]
            for ship_type, base_price, desc in advanced_ships:
                name = generate_random_ship_name()
                price = base_price + random.randint(-1000, 2000)
                available.append((name, ship_type, price, desc))
        
        if self.wealth_level >= 8:
            premium_ships = [
                ("Luxury Yacht", 15000, "High-end personal transport"),
                ("Military Corvette", 18000, "Decommissioned combat vessel"),
                ("Research Vessel", 12000, "Specialized scientific platform")
            ]
            for ship_type, base_price, desc in premium_ships:
                name = generate_random_ship_name()
                price = base_price + random.randint(-2000, 3000)
                available.append((name, ship_type, price, desc))
        
        return random.sample(available, min(6, len(available)))
    
    def _calculate_ship_value(self, ship_info):
        """Calculate estimated ship value based on specs"""
        _, ship_type, fuel_cap, cargo_cap, combat, fuel_eff = ship_info
        
        base_values = {"Hauler": 2500, "Scout": 3000, "Courier": 3500, "Shuttle": 2000}
        base_value = base_values.get(ship_type, 3000)
        
        # Add value for enhanced specs
        base_value += (fuel_cap - 100) * 10  # Fuel capacity bonus
        base_value += (cargo_cap - 50) * 5   # Cargo bonus
        base_value += (combat - 10) * 50     # Combat bonus
        base_value += (fuel_eff - 5) * 100   # Efficiency bonus
        
        return max(1000, base_value)
    
    async def purchase_ship_callback(self, interaction: discord.Interaction):
        ship_data = interaction.data['values'][0].split('|')
        ship_type, ship_name, price_str = ship_data
        price = int(price_str)
        
        # Check if user can afford it
        money = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if money < price:
            await interaction.response.send_message(
                f"Insufficient credits! Need {price:,}, have {money:,}.",
                ephemeral=True
            )
            return
        
        # Create the ship
        from utils.ship_data import STARTER_SHIP_CLASSES
        import random
        
        # Get random descriptions for this ship type
        if ship_type in STARTER_SHIP_CLASSES:
            exterior_desc = random.choice(STARTER_SHIP_CLASSES[ship_type]["exterior"])
            interior_desc = random.choice(STARTER_SHIP_CLASSES[ship_type]["interior"])
        else:
            exterior_desc = f"A well-maintained {ship_type.lower()} with standard configuration."
            interior_desc = f"The interior features typical {ship_type.lower()} layout and equipment."
        
        # Create ship in database
        self.bot.db.execute_query(
            '''INSERT INTO ships (owner_id, name, ship_type, exterior_description, interior_description)
               VALUES (?, ?, ?, ?, ?)''',
            (interaction.user.id, ship_name, ship_type, exterior_desc, interior_desc)
        )
        
        # Get the new ship ID
        new_ship_id = self.bot.db.execute_query(
            "SELECT ship_id FROM ships WHERE owner_id = ? ORDER BY ship_id DESC LIMIT 1",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        # Add to player_ships table
        current_location = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        self.bot.db.execute_query(
            '''INSERT INTO player_ships (owner_id, ship_id, is_active, stored_at_shipyard)
               VALUES (?, ?, 0, ?)''',
            (interaction.user.id, new_ship_id, current_location)
        )
        # Generate ship activities
        from utils.ship_activities import ShipActivityManager
        activity_manager = ShipActivityManager(self.bot)
        activity_manager.generate_ship_activities(new_ship_id, ship_type)
        # Deduct credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (price, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="✅ Ship Purchased",
            description=f"Successfully purchased **{ship_name}**!",
            color=0x00ff00
        )
        
        embed.add_field(name="Ship Type", value=ship_type, inline=True)
        embed.add_field(name="Cost", value=f"{price:,} credits", inline=True)
        embed.add_field(name="Status", value="Stored (use Swap Ships to activate)", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def swap_ship_callback(self, interaction: discord.Interaction):
        new_ship_id = int(interaction.data['values'][0])
        
        # Store current active ship if any
        if self.active_ship_id:
            self.bot.db.execute_query(
                "UPDATE player_ships SET is_active = 0 WHERE owner_id = ? AND ship_id = ?",
                (interaction.user.id, self.active_ship_id)
            )
        
        # Activate new ship
        self.bot.db.execute_query(
            "UPDATE player_ships SET is_active = 1 WHERE owner_id = ? AND ship_id = ?",
            (interaction.user.id, new_ship_id)
        )
        
        # Update character's active ship
        self.bot.db.execute_query(
            "UPDATE characters SET active_ship_id = ? WHERE user_id = ?",
            (new_ship_id, interaction.user.id)
        )
        
        # Get ship name
        ship_name = self.bot.db.execute_query(
            "SELECT name FROM ships WHERE ship_id = ?",
            (new_ship_id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="🔄 Ship Activated",
            description=f"**{ship_name}** is now your active ship!",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SellShipConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, ship_id: int, sale_price: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.ship_id = ship_id
        self.sale_price = sale_price
    
    @discord.ui.button(label="Confirm Sale", style=discord.ButtonStyle.danger, emoji="💰")
    async def confirm_sale(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your sale!", ephemeral=True)
            return
        
        # Remove ship from player_ships
        self.bot.db.execute_query(
            "DELETE FROM player_ships WHERE owner_id = ? AND ship_id = ?",
            (interaction.user.id, self.ship_id)
        )
        
        # Delete ship
        self.bot.db.execute_query(
            "DELETE FROM ships WHERE ship_id = ?",
            (self.ship_id,)
        )
        
        # Clear active ship
        self.bot.db.execute_query(
            "UPDATE characters SET active_ship_id = NULL WHERE user_id = ?",
            (interaction.user.id,)
        )
        
        # Add credits
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (self.sale_price, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="💰 Ship Sold",
            description=f"Ship sold for {self.sale_price:,} credits!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="⚠️ Important",
            value="You no longer have an active ship. You cannot travel until you purchase or activate another ship.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_sale(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your sale!", ephemeral=True)
            return
        
        await interaction.response.send_message("Sale cancelled.", ephemeral=True)
