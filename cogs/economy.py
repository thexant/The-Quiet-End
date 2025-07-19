# cogs/economy.py

import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta
import math
import asyncio
class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.job_tracking_task = None
        # DON'T start background tasks in __init__
        
    shop_group = app_commands.Group(name="shop", description="Buy and sell items")
    job_group  = app_commands.Group(name="job",  description="Find and complete jobs")
  
    async def cog_load(self):
            """Called when the cog is loaded - safer place to start background tasks"""
            print("💰 Economy cog loaded, starting background tasks...")
            
            # Wait a bit to ensure database is ready
            await asyncio.sleep(1)
            
            try:
                # Start background task after cog is fully loaded
                self.job_tracking_task = self.bot.loop.create_task(self.start_job_tracking())
                print("✅ Economy background tasks started")
            except Exception as e:
                print(f"❌ Error starting economy tasks: {e}")

    async def cog_unload(self):
        """Called when the cog is unloaded - clean up tasks"""
        if self.job_tracking_task and not self.job_tracking_task.done():
            self.job_tracking_task.cancel()
            try:
                await self.job_tracking_task
            except asyncio.CancelledError:
                pass
            print("🔄 Job tracking task stopped")

    async def start_job_tracking(self):
        """Start the job tracking background task"""
        await self.bot.wait_until_ready()  # Wait for bot to be ready
        print("🔄 Starting job tracking task...")
        await self.job_tracking_loop()

    async def job_tracking_loop(self):
        """The actual job tracking loop"""
        print("🔄 Job tracking background task started")
        iteration = 0
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                iteration += 1
                
                # Log every 10 minutes to show it's running
                if iteration % 10 == 0:
                    print(f"🔄 Job tracking running (iteration {iteration})")

                # Get all active job tracking records
                active_tracking = self.db.execute_query(
                    '''
                    SELECT
                      jt.tracking_id,
                      jt.job_id,
                      jt.user_id,
                      jt.start_location,
                      jt.required_duration,
                      jt.time_at_location,
                      jt.last_location_check,
                      j.title
                    FROM job_tracking jt
                    JOIN jobs j ON jt.job_id = j.job_id
                    WHERE j.is_taken = 1
                    ''',
                    fetch='all'
                )

                if not active_tracking:
                    if iteration % 10 == 0:  # Log every 10 minutes when no jobs
                        print("🔄 No active job tracking records found")
                    continue

                print(f"🔄 Processing {len(active_tracking)} job tracking records")
                updated_count = 0
                
                for record in active_tracking:
                    try:
                        tracking_id, job_id, user_id, start_location, required_duration, time_at_location, last_check, job_title = record
                        
                        # Check if user is still at the required location
                        current_location_result = self.db.execute_query(
                            "SELECT current_location FROM characters WHERE user_id = ?",
                            (user_id,),
                            fetch='one'
                        )
                        
                        if not current_location_result:
                            print(f"⚠️ Character not found for user {user_id}")
                            continue
                        
                        current_location = current_location_result[0]
                        
                        if current_location == start_location:
                            # User is at correct location, add time
                            # Always add 1 minute since this runs every minute
                            new_time_at_location = float(time_at_location or 0) + 1.0
                            
                            # Update the tracking record
                            self.db.execute_query(
                                '''UPDATE job_tracking
                                   SET time_at_location = ?, 
                                       last_location_check = datetime('now')
                                   WHERE tracking_id = ?''',
                                (new_time_at_location, tracking_id)
                            )
                            
                            print(f"✅ Updated job tracking for user {user_id} (job: {job_title[:30]}): +1.0min (total: {new_time_at_location:.1f}/{required_duration})")
                            updated_count += 1
                        else:
                            # User not at location, just update timestamp
                            self.db.execute_query(
                                "UPDATE job_tracking SET last_location_check = datetime('now') WHERE tracking_id = ?",
                                (tracking_id,)
                            )
                            
                            if iteration % 5 == 0:  # Log occasionally
                                print(f"📍 User {user_id} not at job location (at {current_location}, needs {start_location})")
                    
                    except Exception as record_error:
                        print(f"❌ Error processing tracking record {tracking_id}: {record_error}")
                        continue
                
                if updated_count > 0:
                    print(f"✅ Updated {updated_count} job tracking records")

            except Exception as e:
                print(f"❌ Critical error in job tracking loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)  # Wait before retrying
    async def check_location_access_fee(self, user_id: int, location_id: int) -> tuple:
        """Check if user needs to pay a fee to access this location"""
        # Check if location is owned and has access controls
        ownership = self.db.execute_query(
            '''SELECT lo.owner_id, lo.group_id
               FROM location_ownership lo
               WHERE lo.location_id = ?''',
            (location_id,),
            fetch='one'
        )
        
        if not ownership:
            return True, 0  # Not owned, free access
        
        owner_id, owner_group_id = ownership
        
        # Owner and owner's group get free access
        if user_id == owner_id:
            return True, 0
        
        # Check if user is in owner's group
        if owner_group_id:
            user_group = self.db.execute_query(
                "SELECT group_id FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            if user_group and user_group[0] == owner_group_id:
                return True, 0
        
        # Check access control settings
        access_control = self.db.execute_query(
            '''SELECT access_type, fee_amount FROM location_access_control
               WHERE location_id = ? AND (user_id = ? OR user_id IS NULL)
               ORDER BY user_id IS NULL ASC''',  # Specific user rules first
            (location_id, user_id),
            fetch='one'
        )
        
        if access_control:
            access_type, fee_amount = access_control
            if access_type == 'banned':
                return False, 0
            elif access_type == 'allowed':
                return True, fee_amount or 0
        
        # Default: allow with no fee
        return True, 0
    async def _generate_shop_items(self, location_id: int, wealth_level: int, location_type: str):
        """Generate shop items using the new item configuration system with supply/demand"""
        from utils.item_config import ItemConfig
        
        # Get base items that should appear everywhere
        base_items = [
            "Emergency Rations", "Basic Med Kit", "Fuel Cell", "Repair Kit"
        ]
        
        # Get location-appropriate items
        location_modifiers = ItemConfig.LOCATION_SPAWN_MODIFIERS.get(location_type, {})
        
        items_to_add = []
        
        # Add base items
        for item_name in base_items:
            item_def = ItemConfig.get_item_definition(item_name)
            if item_def and random.random() < 0.8:  # 80% chance for base items
                items_to_add.append(item_name)
        
        # Add random items based on location type and wealth
        for rarity in ["common", "uncommon", "rare", "legendary"]:
            rarity_items = ItemConfig.get_items_by_rarity(rarity)
            
            # Adjust spawn chance by rarity and wealth
            spawn_chances = {
                "common": 0.6 + (wealth_level * 0.02),
                "uncommon": 0.3 + (wealth_level * 0.03), 
                "rare": 0.1 + (wealth_level * 0.02),
                "legendary": 0.02 + (wealth_level * 0.01)
            }
            
            spawn_chance = spawn_chances.get(rarity, 0.1)
            
            for item_name in rarity_items:
                if item_name in items_to_add:
                    continue  # Already added
                
                item_def = ItemConfig.get_item_definition(item_name)
                item_type = item_def.get("type")
                
                # Apply location modifier
                type_modifier = location_modifiers.get(item_type, 1.0)
                final_chance = spawn_chance * type_modifier
                
                if random.random() < final_chance:
                    items_to_add.append(item_name)
        
        # Add items to shop with economic modifiers
        for item_name in items_to_add:
            item_def = ItemConfig.get_item_definition(item_name)
            if not item_def:
                continue
            
            # Calculate base price and stock
            base_value = item_def["base_value"]
            price_modifier = 1.5 - (wealth_level * 0.05)  # Wealthy locations have better prices
            base_price = max(1, int(base_value * price_modifier))
            
            # Stock based on rarity and wealth
            rarity = item_def.get("rarity", "common")
            base_stock = {"common": 8, "uncommon": 4, "rare": 2, "legendary": 1}[rarity]
            stock_modifier = 0.5 + (wealth_level * 0.1)
            base_stock = max(1, int(base_stock * stock_modifier))
            
            # Apply economic modifiers
            status, price_mod, stock_mod = self.get_economic_modifiers(location_id, item_name, item_def["type"])
            final_price, final_stock = self.apply_economic_modifiers(
                base_price, base_stock, status, price_mod, stock_mod, is_buying=True
            )
            
            # Create metadata
            metadata = ItemConfig.create_item_metadata(item_name)
            
            self.db.execute_query(
                '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (location_id, item_name, item_def["type"], final_price, final_stock, 
                 item_def["description"], metadata)
            )

    @shop_group.command(name="list", description="View items available for purchase")
    async def shop_list(self, interaction: discord.Interaction):
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        # Check if location has shops
        location_info = self.db.execute_query(
            "SELECT has_shops, name, wealth_level, location_type FROM locations WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )
        
        if not location_info or not location_info[0]:
            await interaction.response.send_message("No shops available at this location.", ephemeral=True)
            return
        
        # Get or generate shop items
        items = self.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description
               FROM shop_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1)
               ORDER BY item_type, price''',
            (char_location[0],),
            fetch='all'
        )
        
        if not items:
            # Generate shop items if none exist
            await self._generate_shop_items(char_location[0], location_info[2], location_info[3])
            items = self.db.execute_query(
                '''SELECT item_name, item_type, price, stock, description
                   FROM shop_items 
                   WHERE location_id = ? AND (stock > 0 OR stock = -1)
                   ORDER BY item_type, price''',
                (char_location[0],),
                fetch='all'
            )
        
        # Create interactive shop view
        view = InteractiveShopView(self.bot, interaction.user.id, char_location[0], location_info[1])
        
        embed = discord.Embed(
            title=f"🛒 Shop - {location_info[1]}",
            description="Interactive shopping interface",
            color=0xffd700
        )
        
        if items:
            # Show summary of available items by category
            item_types = {}
            for item_name, item_type, price, stock, description in items:
                if item_type not in item_types:
                    item_types[item_type] = {'count': 0, 'price_range': []}
                item_types[item_type]['count'] += 1
                item_types[item_type]['price_range'].append(price)
            
            summary = []
            for item_type, data in item_types.items():
                min_price = min(data['price_range'])
                max_price = max(data['price_range'])
                price_text = f"{min_price:,}" if min_price == max_price else f"{min_price:,} - {max_price:,}"
                summary.append(f"**{item_type.replace('_', ' ').title()}**: {data['count']} items ({price_text} credits)")
            
            embed.add_field(
                name="📦 Available Categories",
                value="\n".join(summary),
                inline=False
            )
            
            # Check for economic events
            economic_status = self.db.execute_query(
                '''SELECT item_category, item_name, status FROM location_economy 
                   WHERE location_id = ? AND expires_at > datetime('now')''',
                (char_location[0],),
                fetch='all'
            )
            
            if economic_status:
                status_text = []
                for category, item, status in economic_status:
                    item_desc = item if item else f"{category} items"
                    if status == 'in_demand':
                        status_text.append(f"🔥 **{item_desc}** in high demand")
                    elif status == 'surplus':
                        status_text.append(f"📦 **{item_desc}** in surplus")
                
                if status_text:
                    embed.add_field(
                        name="📈 Economic Status",
                        value="\n".join(status_text),
                        inline=False
                    )
        else:
            embed.add_field(name="No Items Available", value="This shop is currently out of stock.", inline=False)
        
        # Add shop info
        wealth_text = "💰" * min(location_info[2] // 2, 5)
        embed.add_field(
            name="Shop Quality",
            value=f"{wealth_text} Wealth Level: {location_info[2]}/10",
            inline=False
        )
        
        embed.add_field(
            name="💡 How to Use",
            value="Use the buttons below to buy or sell items interactively!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    # Add this to your cogs/economy.py file, in the EconomyCog class

    @shop_group.command(name="depot", description="Access Federal Supply Depot interactive interface")
    async def federal_depot_interface(self, interaction: discord.Interaction):
        char_info = self.db.execute_query(
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in first!", ephemeral=True)
            return
        
        current_location_id = char_info[0]

        # Check if the location has federal supplies
        location_info = self.db.execute_query(
            "SELECT has_federal_supplies, name FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )

        if not location_info or not location_info[0]:
            await interaction.response.send_message("No Federal Supply Depot available at this location.", ephemeral=True)
            return

        # Get the character's reputation at this location
        reputation_data = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (interaction.user.id, current_location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0

        # Get federal supply items
        items = self.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, clearance_level
               FROM federal_supply_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1) AND ? >= clearance_level
               ORDER BY clearance_level ASC, price ASC''',
            (current_location_id, current_reputation),
            fetch='all'
        )

        # Create interactive view
        view = InteractiveFederalDepotView(self.bot, interaction.user.id, current_location_id, location_info[1])
        
        embed = discord.Embed(
            title=f"🏛️ Federal Supply Depot - {location_info[1]}",
            description="Official equipment and supplies for trusted allies.",
            color=0x0066cc
        )
        embed.set_footer(text=f"Your Local Reputation: {current_reputation}")

        if items:
            # Show summary by category
            item_types = {}
            for item_name, item_type, price, stock, description, clearance_level in items:
                if item_type not in item_types:
                    item_types[item_type] = {'count': 0, 'min_rep': req_rep}
                item_types[item_type]['count'] += 1
                item_types[item_type]['min_rep'] = min(item_types[item_type]['min_rep'], req_rep)
            
            summary = []
            for item_type, data in item_types.items():
                rep_text = f" (Rep {data['min_rep']}+)" if data['min_rep'] > 0 else ""
                summary.append(f"**{item_type.replace('_', ' ').title()}**: {data['count']} items{rep_text}")
            
            embed.add_field(
                name="📦 Available Categories",
                value="\n".join(summary),
                inline=False
            )
        else:
            embed.add_field(
                name="Access Denied", 
                value="No items available. Improve your reputation with federal forces.",
                inline=False
            )
        
        embed.add_field(
            name="💡 Federal Access",
            value="• Higher reputation unlocks premium equipment\n• All sales support federal operations\n• Quality guaranteed by federal standards",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @shop_group.command(name="black_market", description="Access Black Market interactive interface")
    async def black_market_interface(self, interaction: discord.Interaction):
        char_info = self.db.execute_query(
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in first!", ephemeral=True)
            return
        
        current_location_id = char_info[0]

        # Check if the location has black market
        location_info = self.db.execute_query(
            "SELECT has_black_market, name FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )

        if not location_info or not location_info[0]:
            await interaction.response.send_message("No black market available at this location.", ephemeral=True)
            return

        # Get black market items
        # WITH THIS:
        items = self.db.execute_query(
            '''SELECT bmi.item_name, bmi.item_type, bmi.price, bmi.stock, bmi.description
               FROM black_market_items bmi
               JOIN black_markets bm ON bmi.market_id = bm.market_id
               WHERE bm.location_id = ? AND (bmi.stock > 0 OR bmi.stock = -1)
               ORDER BY bmi.item_type, bmi.price''',
            (current_location_id,),
            fetch='all'
        )

        # Create interactive view
        view = InteractiveBlackMarketView(self.bot, interaction.user.id, current_location_id, location_info[1])
        
        embed = discord.Embed(
            title=f"💀 Black Market - {location_info[1]}",
            description="Discretion advised. No questions asked, no warranties given.",
            color=0x8b0000
        )
        embed.set_footer(text="⚠️ Trading in contraband carries significant risks")

        if items:
            # Show summary by category
            item_types = {}
            for item_name, item_type, price, stock, description in items:
                if item_type not in item_types:
                    item_types[item_type] = {'count': 0, 'price_range': []}
                item_types[item_type]['count'] += 1
                item_types[item_type]['price_range'].append(price)
            
            summary = []
            for item_type, data in item_types.items():
                min_price = min(data['price_range'])
                max_price = max(data['price_range'])
                price_text = f"{min_price:,}" if min_price == max_price else f"{min_price:,} - {max_price:,}"
                summary.append(f"**{item_type.replace('_', ' ').title()}**: {data['count']} items ({price_text} credits)")
            
            embed.add_field(
                name="📦 Available Contraband",
                value="\n".join(summary),
                inline=False
            )
        else:
            embed.add_field(
                name="Currently Closed", 
                value="Check back later for new arrivals.",
                inline=False
            )
        
        embed.add_field(
            name="💀 Black Market Rules",
            value="• All sales final - no returns\n• Cash only, no credit traces\n• What you do with items is your business",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @shop_group.command(name="buy", description="Purchase an item from the shop")
    @app_commands.describe(
        item_name="Name of the item to buy",
        quantity="Number of items to buy (default: 1)"
    )
    async def shop_buy(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        if quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than 0.", ephemeral=True)
            return
        
        char_info = self.db.execute_query(
            "SELECT current_location, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Find item in shop
        item = self.db.execute_query(
            '''SELECT item_id, item_name, price, stock, description, item_type, metadata
               FROM shop_items 
               WHERE location_id = ? AND LOWER(item_name) = LOWER(?)''',
            (current_location, item_name),
            fetch='one'
        )
        
        if not item:
            await interaction.response.send_message(f"Item '{item_name}' not found or insufficient stock.", ephemeral=True)
            return
        
        item_id, actual_name, price, stock, description, item_type, metadata = item
        total_cost = price * quantity
        tax_data = self.db.execute_query(
            '''SELECT fst.tax_percentage, f.faction_id, f.name
               FROM faction_sales_tax fst
               JOIN factions f ON fst.faction_id = f.faction_id
               WHERE fst.location_id = ?''',
            (current_location,),
            fetch='one'
        )

        final_price = base_price
        tax_amount = 0
        if tax_data and tax_data[0] > 0:
            tax_amount = int(base_price * tax_data[0] / 100)
            final_price = base_price + tax_amount

        # When processing purchase (after deducting money), ADD:
        if tax_amount > 0:
            self.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance + ? WHERE faction_id = ?",
                (tax_amount, tax_data[1])
            )


        if current_money < total_cost:
            await interaction.response.send_message(
                f"Insufficient credits! Need {total_cost:,}, have {current_money:,}.",
                ephemeral=True
            )
            return
        
        # Process purchase
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        # Update shop stock
        if stock != -1:  # Not unlimited
            self.db.execute_query(
                "UPDATE shop_items SET stock = stock - ? WHERE item_id = ?",
                (quantity, item_id)
            )
        
        # Add to inventory
        existing_item = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, actual_name),
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
                (interaction.user.id, actual_name, item_type, quantity, description, price, metadata)
            )
        embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"Bought {quantity}x **{actual_name}** for {total_cost:,} credits",
            color=0x00ff00
        )
        # In the purchase confirmation embed, ADD:
        if tax_amount > 0:
            embed.add_field(
                name="Sales Tax",
                value=f"{tax_data[0]}% ({tax_amount:,} credits to {tax_data[2]})",
                inline=False
            )
        embed.add_field(name="Remaining Credits", value=f"{current_money - total_cost:,}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @shop_group.command(name="sell", description="Sell items from your inventory")
    @app_commands.describe(
        item_name="Name of the item to sell",
        quantity="Number of items to sell (default: 1)"
    )
    async def shop_sell(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        if quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than 0.", ephemeral=True)
            return
        
        char_info = self.db.execute_query(
            "SELECT current_location, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Check if location has shops
        has_shops = self.db.execute_query(
            "SELECT has_shops, wealth_level FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if not has_shops or not has_shops[0]:
            await interaction.response.send_message("This location doesn't buy items.", ephemeral=True)
            return
        
        # Find item in inventory (also grab its description for resale)
        inventory_item = self.db.execute_query(
            '''SELECT item_id, item_name, quantity, value, item_type, description
               FROM inventory 
               WHERE owner_id = ? AND LOWER(item_name) LIKE LOWER(?) AND quantity >= ?''',
            (interaction.user.id, f"%{item_name}%", quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.response.send_message(f"You don't have enough '{item_name}' to sell.", ephemeral=True)
            return
        
        inv_id, actual_name, current_qty, base_value, item_type, description = inventory_item

        
        # Calculate sell price with economic modifiers (replace existing calculation)
        wealth_level = has_shops[1]
        base_multiplier = 0.5 + (wealth_level * 0.03)  # 50% to 80% based on wealth
        base_sell_price = max(1, int(base_value * base_multiplier))

        # Apply economic modifiers
        status, price_mod, stock_mod = self.get_economic_modifiers(current_location, actual_name, item_type)
        final_sell_price, _ = self.apply_economic_modifiers(
            base_sell_price, 1, status, price_mod, stock_mod, is_buying=False
        )

        total_earnings = final_sell_price * quantity
        seller_faction = self.db.execute_query(
            '''SELECT fm.faction_id, f.name, f.emoji,
                      CASE WHEN lo.faction_id = fm.faction_id THEN 1 ELSE 0 END as is_faction_location
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               LEFT JOIN location_ownership lo ON lo.location_id = ?
               WHERE fm.user_id = ?''',
            (current_location, interaction.user.id),
            fetch='one'
        )

        if seller_faction and not seller_faction[3]:  # Not in faction territory
            # 3% bonus to faction bank for external trade
            trade_bonus = int(total_earnings * 0.03)
            self.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance + ? WHERE faction_id = ?",
                (trade_bonus, seller_faction[0])
            )
            embed.add_field(
                name="Trade Bonus",
                value=f"{seller_faction[2]} +{trade_bonus:,} credits to {seller_faction[1]}",
                inline=False
            )
        # Add economic status message
        status_message = ""
        if status == 'in_demand':
            status_message = f"\n🔥 **{actual_name}** is in high demand here!"
        elif status == 'surplus':
            status_message = f"\n📦 Market is saturated with **{actual_name}**."
        
        # Update inventory
        if current_qty == quantity:
            # Remove item completely
            self.db.execute_query(
                "DELETE FROM inventory WHERE item_id = ?",
                (inv_id,)
            )
        else:
            # Reduce quantity
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                (quantity, inv_id)
            )
        
        # Add money to character
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (total_earnings, interaction.user.id)
        )
                # ─── Put sold items into the shop at a 20% markup ───
        # Calculate the shop purchase price (e.g. 120% of the sell price, at least +1)
        markup_price = max(final_sell_price + 1, int(final_sell_price * 1.2))

        # Check if this item already exists in the local shop
        existing = self.db.execute_query(
            "SELECT item_id, stock, price FROM shop_items WHERE location_id = ? AND LOWER(item_name) = LOWER(?)",
            (current_location, actual_name),
            fetch='one'
        )

        if existing:
            shop_id, shop_stock, shop_price = existing
            # -1 stock means “unlimited,” keep unlimited if so
            new_stock = shop_stock + quantity if shop_stock != -1 else -1
            # never lower the price once set
            new_price = max(shop_price, markup_price)
            self.db.execute_query(
                "UPDATE shop_items SET stock = ?, price = ? WHERE item_id = ?",
                (new_stock, new_price, shop_id)
            )
        else:
            # fresh entry in the shop
            self.db.execute_query(
                '''INSERT INTO shop_items
                   (location_id, item_name, item_type, price, stock, description)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (current_location, actual_name, item_type, markup_price, quantity, description)
            )
        embed = discord.Embed(
            title="💰 Item Sold",
            description=f"Sold {quantity}x **{actual_name}** for {total_earnings:,} credits",
            color=0x00ff00
        )

        embed.add_field(name="Price per Item", value=f"{final_sell_price:,} credits", inline=True)
        embed.add_field(name="New Balance", value=f"{current_money + total_earnings:,} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    def get_shift_job_multiplier(self) -> float:
        """Get job generation multiplier based on current shift"""
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        shift_name, shift_period = time_system.get_current_shift()
        
        # Job generation multipliers by shift (slightly increased)
        shift_multipliers = {
            "morning": 1.2,   # Increased from 0.8
            "day": 1.6,       # Increased from 1.5
            "evening": 1.1,   # Increased from 0.9
            "night": 0.6      # Increased from 0.4
        }
        
        return shift_multipliers.get(shift_period, 1.0)
        
    @job_group.command(name="list", description="View available jobs at current location")
    async def job_list(self, interaction: discord.Interaction):
        # Defer right away to avoid "Unknown interaction"
        await interaction.response.defer(ephemeral=True)

        # Fetch character location
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if not char_location:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return

        # Check for jobs at that location
        location_info = self.db.execute_query(
            "SELECT has_jobs, name, wealth_level FROM locations WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )
        if not location_info or not location_info[0]:
            await interaction.followup.send("No jobs available at this location.", ephemeral=True)
            return

        # Load the jobs
        jobs = self.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill,
                      min_skill_level, danger_level, duration_minutes
               FROM jobs
               WHERE location_id = ? AND is_taken = 0 AND expires_at > datetime('now')
               ORDER BY reward_money DESC''',
            (char_location[0],),
            fetch='all'
        )

        # Build the embed
        embed = discord.Embed(
            title=f"💼 Jobs Available - {location_info[1]}",
            description="Interactive job selection interface",
            color=0x4169E1
        )

        if not jobs:
            embed.add_field(
                name="No Jobs Currently Available",
                value="Check back later or try other locations.",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create interactive job view
        view = InteractiveJobListView(self.bot, interaction.user.id, jobs, location_info[1])
        
        # Show summary of available jobs
        job_summary = []
        total_reward = 0
        danger_counts = {'safe': 0, 'low': 0, 'medium': 0, 'high': 0}
        
        for job in jobs:
            job_id, title, desc, reward, skill, min_level, danger, duration = job
            total_reward += reward
            
            if danger == 0:
                danger_counts['safe'] += 1
            elif danger <= 2:
                danger_counts['low'] += 1
            elif danger <= 4:
                danger_counts['medium'] += 1
            else:
                danger_counts['high'] += 1
        
        embed.add_field(
            name="📊 Job Summary",
            value=f"**{len(jobs)}** jobs available\n**Total Rewards**: {total_reward:,} credits\n**Average**: {total_reward//len(jobs):,} credits per job",
            inline=True
        )
        
        danger_summary = []
        if danger_counts['safe'] > 0:
            danger_summary.append(f"✅ {danger_counts['safe']} Safe")
        if danger_counts['low'] > 0:
            danger_summary.append(f"⚠️ {danger_counts['low']} Low Risk")
        if danger_counts['medium'] > 0:
            danger_summary.append(f"🔥 {danger_counts['medium']} Medium Risk")
        if danger_counts['high'] > 0:
            danger_summary.append(f"💀 {danger_counts['high']} High Risk")
        
        embed.add_field(
            name="⚠️ Risk Levels",
            value="\n".join(danger_summary) if danger_summary else "No risk data",
            inline=True
        )

        embed.add_field(
            name="💡 How to Use",
            value="Select a job from the dropdown below to view details and accept it!",
            inline=False
        )

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @job_group.command(name="complete", description="Complete your current job")
    async def job_complete(self, interaction: discord.Interaction):
                # Fetch the active job with skill requirements and destination_location_id
        job_info = self.db.execute_query(
            '''SELECT j.job_id, j.title, j.reward_money, j.danger_level, j.taken_at,
                      j.duration_minutes, l.name AS location_name, j.job_status,
                      j.description, j.location_id, j.required_skill, j.min_skill_level,
                      j.destination_location_id
               FROM jobs j
               JOIN locations l ON j.location_id = l.location_id
               WHERE j.taken_by = ? AND j.is_taken = 1''',
            (interaction.user.id,),
            fetch='one'
        )

        if not job_info:
            await interaction.response.send_message(
                "You don't have an active job to complete.",
                ephemeral=True
            )
            return

        (job_id, title, reward, danger, taken_at, duration_minutes, location_name, job_status,
         description, job_location_id, required_skill, min_skill_level, destination_location_id) = job_info

        # Check if job was already completed
        if job_status == 'completed':
            await interaction.response.send_message(
                "This job has already been completed!",
                ephemeral=True
            )
            return
        
        # ADD THESE TWO LINES HERE - Define title_lower and desc_lower before they're used
        title_lower = title.lower()
        desc_lower = description.lower()
        
        # Determine job type - check destination_location_id first for definitive classification
        if destination_location_id and destination_location_id != job_location_id:
            # Has a different destination location = definitely a transport job
            is_transport_job = True
        elif destination_location_id is None:
            # No destination set - check keywords to determine if it's a transport job (NPC-style)
            is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                              any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
        else:
            # destination_location_id == job_location_id = stationary job, regardless of keywords
            is_transport_job = False

        # Get player's current location
        player_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not player_location or not player_location[0]:
            await interaction.response.send_message(
                "You cannot complete jobs while in transit!",
                ephemeral=True
            )
            return
        
        current_location = player_location[0]

        if is_transport_job:
            # TRANSPORT JOB LOGIC - Check if at correct destination, then do unloading phase
            
            # Check if this is a finalization attempt for transport jobs
            if job_status == 'awaiting_finalization':
                # Transport job is in finalization phase - complete immediately
                await self._finalize_transport_job(interaction, job_id, title, reward)
                return
            
            # For NPC jobs without destination, allow completion at any location after elapsed time
            if not destination_location_id:
                # Check elapsed time for NPC transport jobs
                taken_time = datetime.fromisoformat(taken_at)
                now = datetime.now()
                elapsed_minutes = (now - taken_time).total_seconds() / 60
                
                if elapsed_minutes >= duration_minutes:
                    # Start unloading phase
                    await self._start_transport_unloading(interaction, job_id, title, reward)
                    return
                else:
                    remaining = duration_minutes - elapsed_minutes
                    await interaction.response.send_message(
                        f"⏳ **Transport Job In Progress**\n\nYou need to wait **{remaining:.1f} more minutes** before completing this delivery.",
                        ephemeral=True
                    )
                    return
            
            # Check if player is at the job's destination (for jobs with destination set)
            if current_location != destination_location_id:
                # Get correct destination location name
                correct_dest_name = "an unknown location"
                if destination_location_id:
                    dest_name_result = self.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = ?",
                        (destination_location_id,),
                        fetch='one'
                    )
                    if dest_name_result:
                        correct_dest_name = dest_name_result[0]
                
                # Get player's current location name for a more accurate error message
                current_location_name_result = self.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = ?",
                    (current_location,),
                    fetch='one'
                )
                current_location_name = current_location_name_result[0] if current_location_name_result else "an unknown location"

                await interaction.response.send_message(
                    f"❌ **Wrong destination!**\n\nThis transport job must be completed at **{correct_dest_name}**.\nYou are currently at {current_location_name}.",
                    ephemeral=True
                )
                return
            
            # Player is at correct destination - start unloading phase
            await self._start_transport_unloading(interaction, job_id, title, reward)
            
        else:
            # STATIONARY JOB LOGIC - Use existing time-based completion
            
            # Parse the time the job was taken
            taken_time = datetime.fromisoformat(taken_at)
            now = datetime.now()
            elapsed_minutes = (now - taken_time).total_seconds() / 60

            # Check location-based tracking for stationary jobs only
            tracking = self.db.execute_query(
                "SELECT time_at_location, required_duration FROM job_tracking WHERE job_id = ? AND user_id = ?",
                (job_id, interaction.user.id),
                fetch='one'
            )
            
            if not tracking:
                await interaction.response.send_message(
                    "❌ **Job tracking error**\n\nNo tracking record found. Please abandon and re-accept this job.",
                    ephemeral=True
                )
                return
            
            time_at_location, required_duration = tracking
            if time_at_location < required_duration:
                remaining = required_duration - time_at_location
                await interaction.response.send_message(
                    f"⏳ **Job not ready for completion**\n\nYou need **{remaining:.1f} more minutes** at this location.\n\nProgress: {time_at_location:.1f}/{required_duration} minutes",
                    ephemeral=True
                )
                return

            # Stationary job is ready - complete with success/failure checks
            await interaction.response.defer(ephemeral=True)

            # --- ENHANCED SKILL CHECK ---
            # Replace the existing skill check section in cogs/economy.py 
            # This affects BOTH regular jobs AND NPC jobs since they use the same completion system

            # --- ENHANCED SKILL CHECK (REBALANCED FOR NPC JOBS) ---
            # Improved base success rates - ordinary jobs should succeed most of the time
            if danger == 0:
                base_success = 85  # Safe jobs should have high success rate
            elif danger == 1:
                base_success = 75  # Slightly risky jobs
            elif danger == 2:
                base_success = 60  # Moderately dangerous 
            elif danger == 3:
                base_success = 45  # Dangerous jobs
            else:
                base_success = 30  # Very dangerous jobs (danger 4+)

            # Get character skills
            char_skills = self.db.execute_query(
                "SELECT engineering, navigation, combat, medical FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )

            skill_map = {
                'engineering': char_skills[0] if char_skills else 0,
                'navigation': char_skills[1] if char_skills else 0,
                'combat': char_skills[2] if char_skills else 0,
                'medical': char_skills[3] if char_skills else 0
            }

            skill_bonus = 0
            if required_skill and required_skill in skill_map:
                player_skill_level = skill_map[required_skill]
                
                # Improved skill bonus calculation
                skill_difference = player_skill_level - min_skill_level
                
                if skill_difference >= 0:
                    # Meeting requirements gives good bonus, exceeding gives even more
                    skill_bonus = min(15, skill_difference * 4)  # +4% per point above minimum, capped at +15%
                else:
                    # Below minimum should be rare due to job acceptance checks, but penalize if it happens
                    skill_bonus = skill_difference * 5  # -5% per point below minimum

            # Final success chance calculation
            success_chance = max(10, min(95, base_success + skill_bonus))
            roll = random.randint(1, 100)
            success = roll <= success_chance

            # Optional: Add debug logging to help you monitor the changes
            # With this clearer version:
            if success:
                print(f"Job success check - Target: ≤{success_chance}, Rolled: {roll} ✓ SUCCESS (Base: {base_success}% + Skill: {skill_bonus}%)")
            else:
                print(f"Job success check - Target: ≤{success_chance}, Rolled: {roll} ✗ FAILED by {roll - success_chance} (Base: {base_success}% + Skill: {skill_bonus}%)")

            # Check if this is a group job
            group_id = self.db.execute_query(
                "SELECT group_id FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )

            if group_id and group_id[0]:
                # Check if the job was taken by the group
                job_taken_by_group = self.db.execute_query(
                    "SELECT 1 FROM jobs WHERE job_id = ? AND taken_by = ?",
                    (job_id, group_id[0]),
                    fetch='one'
                )
                
                if job_taken_by_group:
                    # Group job
                    await self._complete_group_job(interaction, job_id, title, reward, roll, success_chance, success)
                else:
                    # Solo job while in a group
                    if success:
                        await self._complete_job_immediately(interaction, job_id, title, reward, roll, success_chance, "stationary")
                    else:
                        await self._complete_job_failed(interaction, job_id, title, reward, roll, success_chance)
            else:
                # Solo job
                if success:
                    await self._complete_job_immediately(interaction, job_id, title, reward, roll, success_chance, "stationary")
                else:
                    await self._complete_job_failed(interaction, job_id, title, reward, roll, success_chance)
                    
    def get_economic_modifiers(self, location_id: int, item_name: str, item_type: str) -> tuple:
        """Get supply/demand modifiers for an item at a location"""
        # Check for specific item demand/surplus
        specific_modifier = self.db.execute_query(
            '''SELECT status, price_modifier, stock_modifier FROM location_economy 
               WHERE location_id = ? AND item_name = ? AND expires_at > datetime('now')''',
            (location_id, item_name),
            fetch='one'
        )
        
        if specific_modifier:
            return specific_modifier
        
        # Check for category demand/surplus
        category_modifier = self.db.execute_query(
            '''SELECT status, price_modifier, stock_modifier FROM location_economy 
               WHERE location_id = ? AND item_category = ? AND expires_at > datetime('now')''',
            (location_id, item_type),
            fetch='one'
        )
        
        if category_modifier:
            return category_modifier
        
        return ('normal', 1.0, 1.0)

    def apply_economic_modifiers(self, base_price: int, base_stock: int, status: str, price_mod: float, stock_mod: float, is_buying: bool) -> tuple:
        """Apply economic modifiers to price and stock"""
        if status == 'in_demand':
            if is_buying:
                # Buying from shop - prices are higher due to scarcity
                modified_price = int(base_price * price_mod * 1.2)  # 20% higher
            else:
                # Selling to shop - get bonus for in-demand items
                modified_price = int(base_price * price_mod * 1.15)  # 15% bonus
            modified_stock = max(0, int(base_stock * stock_mod * 0.3))  # Much lower stock
        
        elif status == 'surplus':
            if is_buying:
                # Buying from shop - prices are lower due to surplus
                modified_price = int(base_price * price_mod * 0.8)  # 20% lower
            else:
                # Selling to shop - get less due to surplus
                modified_price = int(base_price * price_mod * 0.7)  # 30% less
            modified_stock = int(base_stock * stock_mod * 2.0)  # Double stock
        
        else:  # normal
            modified_price = int(base_price * price_mod)
            modified_stock = int(base_stock * stock_mod)
        
        return max(1, modified_price), max(0, modified_stock)
    async def _auto_complete_transport_job(self, user_id: int, job_id: int, title: str, reward: int, delay_minutes: int):
        """Automatically complete a transport job after unloading delay"""
        import asyncio
        
        await asyncio.sleep(delay_minutes * 60)  # Convert to seconds
        
        # Check if job still exists and is in finalization
        job_check = self.db.execute_query(
            "SELECT job_status FROM jobs WHERE job_id = ? AND taken_by = ?",
            (job_id, user_id),
            fetch='one'
        )
        
        if job_check and job_check[0] == 'awaiting_finalization':
            # Complete the job automatically - TRANSPORT JOBS ALWAYS SUCCEED
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, user_id)
            )
            
            # Add experience for transport jobs
            exp_gain = random.randint(20, 40)
            self.db.execute_query(
                "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                (exp_gain, user_id)
            )
            
            # Clean up job
            self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, user_id))
            
            # Try to notify user
            user = self.bot.get_user(user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="✅ Transport Job Auto-Completed",
                        description=f"**{title}** has been automatically finalized!",
                        color=0x00ff00
                    )
                    embed.add_field(name="💰 Reward Received", value=f"{reward:,} credits", inline=True)
                    embed.add_field(name="⭐ Experience Gained", value=f"+{exp_gain} EXP", inline=True)
                    embed.add_field(name="📦 Status", value="Cargo delivered successfully", inline=True)
                    
                    # Get the current location channel and send there instead of DM
                    # Assuming the user is at the destination location when this auto-completes
                    current_location_id = self.db.execute_query(
                        "SELECT current_location FROM characters WHERE user_id = ?", (user_id,), fetch='one'
                    )[0]
                    location_channel_id = self.db.execute_query(
                        "SELECT channel_id FROM locations WHERE location_id = ?", (current_location_id,), fetch='one'
                    )[0]
                    
                    if location_channel_id:
                        channel = self.bot.get_channel(location_channel_id)
                        if channel:
                            await channel.send(embed=embed) # Public message in location channel
                    else:
                        await user.send(embed=embed) # Fallback to DM if no channel
                except Exception as e:
                    print(f"❌ Failed to send transport job auto-completion message to user {user_id}: {e}")
                    pass  # Failed to send DM or channel message

            # Check for level up
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.level_up_check(user_id)

    async def _finalize_transport_job(self, interaction: discord.Interaction, job_id: int, title: str, reward: int):
        """Immediately finalize a transport job that's awaiting finalization"""
        # Complete the job - TRANSPORT JOBS ALWAYS SUCCEED
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (reward, interaction.user.id)
        )
        
        # Add experience for transport jobs
        exp_gain = random.randint(20, 40)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
            (exp_gain, interaction.user.id)
        )
        
        # Clean up
        self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, interaction.user.id))
        
        embed = discord.Embed(
            title="✅ Transport Job Completed!",
            description=f"**{title}** has been finalized immediately!",
            color=0x00ff00
        )
        
        embed.add_field(name="💰 Reward Received", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="⭐ Experience Gained", value=f"+{exp_gain} EXP", inline=True)
        embed.add_field(name="📦 Finalization", value="Cargo unloading completed", inline=True)
        
        # Check for level up
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.level_up_check(interaction.user.id)
        
        # Send publicly in the current channel
        await interaction.response.send_message(embed=embed, ephemeral=False) # MODIFIED THIS LINE
        
    async def _start_transport_unloading(self, interaction: discord.Interaction, job_id: int, title: str, reward: int):
        """Start the unloading phase for transport jobs (2 minutes fixed)"""
        
        # Mark job as awaiting finalization with timestamp
        current_time = datetime.now()
        self.db.execute_query(
            "UPDATE jobs SET job_status = 'awaiting_finalization', unloading_started_at = ? WHERE job_id = ?",
            (current_time.strftime("%Y-%m-%d %H:%M:%S"), job_id)
        )
        
        # Fixed 2-minute unloading time
        unloading_seconds = 120
        
        embed = discord.Embed(
            title="🚛 Transport Job - Cargo Unloading",
            description=f"**{title}** delivery confirmed!\n\nUnloading cargo and processing delivery paperwork...",
            color=0x00aa00
        )
        
        embed.add_field(name="✅ Delivery Status", value="Successfully delivered to destination", inline=True)
        embed.add_field(name="⏱️ Unloading Time", value="2 minutes", inline=True)
        embed.add_field(name="💰 Pending Reward", value=f"{reward:,} credits", inline=True)
        
        # Initial progress bar
        embed.add_field(
            name="📊 Unloading Cargo...",
            value="Please wait for cargo to unload.",
            inline=False
        )
        
        embed.add_field(
            name="📋 Options",
            value="• Wait for automatic completion in 2 minutes\n• Check progress with `/job status`\n• Use `/job complete` to skip waiting (costs 10% of reward)",
            inline=False
        )
        
        # Send initial message and store it for updates
        message = await interaction.response.send_message(embed=embed, ephemeral=False)
        
        # Schedule automatic completion
        import asyncio
        asyncio.create_task(self._auto_complete_transport_job_with_updates(
            interaction.user.id, job_id, title, reward, interaction.channel_id
        ))
        
    async def _auto_complete_transport_job_with_updates(self, user_id: int, job_id: int, title: str, reward: int, channel_id: int):
        """Auto-complete transport job after 2 minutes with progress updates"""
        await asyncio.sleep(10)  # Wait 10 seconds before first update
        
        # Progress update loop (every 30 seconds)
        for i in range(3):  # Updates at 10s, 40s, 70s
            # Check if job still exists and is awaiting finalization
            job_check = self.db.execute_query(
                "SELECT job_status, unloading_started_at FROM jobs WHERE job_id = ? AND taken_by = ?",
                (job_id, user_id),
                fetch='one'
            )
            
            if not job_check or job_check[0] != 'awaiting_finalization':
                return  # Job was completed manually or deleted
            
            # Calculate progress
            unloading_start = datetime.fromisoformat(job_check[1])
            elapsed = (datetime.now() - unloading_start).total_seconds()
            progress_pct = min(100, (elapsed / 120) * 100)
            
            # Send progress update in channel
            channel = self.bot.get_channel(channel_id)
            if channel:
                bars = int(progress_pct // 10)
                progress_bar = "🟩" * bars + "⬜" * (10 - bars)
                
                user = self.bot.get_user(user_id)
                await channel.send(
                    f"{user.mention} - Unloading progress: {progress_bar} {progress_pct:.0f}%",
                    delete_after=30  # Delete after 30 seconds to reduce spam
                )
            
            if i < 2:  # Don't sleep after last update
                await asyncio.sleep(30)
        
        # Wait for remaining time (total 2 minutes)
        await asyncio.sleep(50)  # 120 - 70 = 50 seconds
        
        # Final completion (same as before)
        job_check = self.db.execute_query(
            "SELECT job_status FROM jobs WHERE job_id = ? AND taken_by = ?",
            (job_id, user_id),
            fetch='one'
        )
        
        if job_check and job_check[0] == 'awaiting_finalization':
            # Complete the job
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (reward, user_id)
            )
            
            exp_gain = random.randint(20, 40)
            self.db.execute_query(
                "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                (exp_gain, user_id)
            )
            
            # Clean up job
            self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, user_id))
            
            # Send completion notification
            user = self.bot.get_user(user_id)
            if user and channel:
                embed = discord.Embed(
                    title="✅ Transport Job Auto-Completed",
                    description=f"**{title}** has been automatically finalized!",
                    color=0x00ff00
                )
                embed.add_field(name="💰 Reward Received", value=f"{reward:,} credits", inline=True)
                embed.add_field(name="⭐ Experience Gained", value=f"+{exp_gain} EXP", inline=True)
                embed.add_field(name="📦 Status", value="Cargo unloading completed", inline=True)
                
                await channel.send(f"{user.mention}", embed=embed)
                
    async def _finalize_transport_job(self, interaction: discord.Interaction, job_id: int, title: str, reward: int):
        """Finalize a transport job that's in the unloading phase"""
        
        # Check how long they've been unloading
        unloading_info = self.db.execute_query(
            "SELECT unloading_started_at FROM jobs WHERE job_id = ?",
            (job_id,),
            fetch='one'
        )
        
        penalty = 0
        if unloading_info and unloading_info[0]:
            unloading_start = datetime.fromisoformat(unloading_info[0])
            elapsed = (datetime.now() - unloading_start).total_seconds()
            
            if elapsed < 120:  # Less than 2 minutes
                # Apply 10% penalty for rushing
                penalty = int(reward * 0.1)
                reward = reward - penalty
        
        # Give reward
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (reward, interaction.user.id)
        )
        
        exp_gain = random.randint(20, 40)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
            (exp_gain, interaction.user.id)
        )
        
        # Clean up
        self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, interaction.user.id))
        
        embed = discord.Embed(
            title="✅ Transport Job Completed!",
            description=f"**{title}** has been finalized!",
            color=0x00ff00
        )
        
        embed.add_field(name="💰 Reward Received", value=f"{reward:,} credits", inline=True)
        if penalty > 0:
            embed.add_field(name="⚡ Rush Penalty", value=f"-{penalty:,} credits", inline=True)
        embed.add_field(name="⭐ Experience Gained", value=f"+{exp_gain} EXP", inline=True)
        embed.add_field(name="📦 Finalization", value="Cargo unloading completed", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)            
                
    async def _complete_job_immediately(self, interaction: discord.Interaction, job_id: int, title: str, reward: int, roll: int, success_chance: int, job_type: str):
        """Complete a job immediately with full reward, experience, skill, and karma effects."""
        # Give full reward
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (reward, interaction.user.id)
        )
        
        # Experience gain
        exp_gain = random.randint(25, 50)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
            (exp_gain, interaction.user.id)
        )
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.emoji
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               WHERE fm.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )

        if faction_data:
            # 5% bonus goes to faction bank
            faction_bonus = int(reward * 0.05)
            self.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance + ? WHERE faction_id = ?",
                (faction_bonus, faction_data[0])
            )
            embed.add_field(
                name="Faction Contribution",
                value=f"{faction_data[2]} +{faction_bonus:,} credits to {faction_data[1]}",
                inline=False
            )
        # Create the response embed
        embed = discord.Embed(
            title="✅ Job Completed Successfully!",
            description=f"**{title}** has been completed!",
            color=0x00ff00
        )
        
        # Convert to intuitive display (invert the roll display)
        # Internal: roll <= success_chance means success
        # Display: show it as if they needed to roll above a failure threshold
        failure_threshold = 100 - success_chance
        displayed_roll = 100 - roll + 1  # Invert the roll for display
        
        embed.add_field(
            name="🎲 Success Roll", 
            value=f"Rolled **{displayed_roll}** (needed {failure_threshold+1}+)", 
            inline=True
        )
        embed.add_field(name="💰 Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="⭐ Experience", value=f"+{exp_gain} EXP", inline=True)
        embed.add_field(name="📋 Job Type", value=job_type.title(), inline=True)
        
        # 15% chance for skill improvement
        if random.random() < 0.15:
            skill_to_improve = random.choice(['engineering', 'navigation', 'combat', 'medical'])
            self.db.execute_query(
                f"UPDATE characters SET {skill_to_improve} = {skill_to_improve} + 1 WHERE user_id = ?",
                (interaction.user.id,)
            )
            embed.add_field(name="🎯 Skill Bonus", value=f"**{skill_to_improve.title()}** skill increased by 1!", inline=True)

        # Handle karma/reputation change
        job_details = self.db.execute_query(
            "SELECT karma_change, location_id FROM jobs WHERE job_id = ?",
            (job_id,),
            fetch='one'
        )

        if job_details:
            karma_change, location_id = job_details
            if karma_change != 0:
                reputation_cog = self.bot.get_cog('ReputationCog')
                if reputation_cog:
                    await reputation_cog.update_reputation(interaction.user.id, location_id, karma_change)
                    karma_text = f"+{karma_change}" if karma_change > 0 else str(karma_change)
                    embed.add_field(name="⚖️ Reputation Change", value=f"**{karma_text}** with local faction", inline=True)
        
        # Clean up job from the database
        self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, interaction.user.id))
        
        # Check for level up
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.level_up_check(interaction.user.id)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


    async def _complete_job_failed(self, interaction: discord.Interaction, job_id: int, title: str, reward: int, roll: int, success_chance: int):
        """Complete a failed job with partial reward"""
        partial = reward // 3
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (partial, interaction.user.id)
        )
        
        # Small experience consolation
        exp_gain = random.randint(5, 15)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
            (exp_gain, interaction.user.id)
        )
        
        # Clean up
        self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ? AND user_id = ?", (job_id, interaction.user.id))
        
        embed = discord.Embed(
            title="❌ Job Failed",
            description=f"**{title}** was not completed successfully",
            color=0xff4444
        )
        
        # Convert to intuitive display
        failure_threshold = 100 - success_chance
        displayed_roll = 100 - roll + 1  # Invert the roll for display
        
        embed.add_field(
            name="🎲 Failure Roll", 
            value=f"Rolled **{displayed_roll}** (needed {failure_threshold+1}+ to succeed)", 
            inline=True
        )
        embed.add_field(name="💰 Partial Payment", value=f"{partial:,} credits", inline=True)
        embed.add_field(name="⭐ Experience", value=f"+{exp_gain} EXP", inline=True)
        
        embed.add_field(
            name="💡 Try Again",
            value="Look for new job opportunities to improve your skills and earn better rewards.",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _complete_group_job(self, interaction: discord.Interaction, job_id: int, title: str, reward: int, roll: int, success_chance: int, success: bool):
        """Complete a job for all group members"""
        # Get the user's group ID first
        group_id = self.db.execute_query(
            "SELECT group_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not group_id or not group_id[0]:
            # Not in a group, handle as solo
            if success:
                await self._complete_job_immediately(interaction, job_id, title, reward, roll, success_chance, "stationary")
            else:
                await self._complete_job_failed(interaction, job_id, title, reward, roll, success_chance)
            return
        
        # Get all group members
        group_members = self.db.execute_query(
            '''SELECT c.user_id, c.name
               FROM characters c
               WHERE c.group_id = ?''',
            (group_id[0],),
            fetch='all'
        )
        
        if not group_members:
            group_members = [(interaction.user.id, "Unknown")]
        
        # Award each member based on success/failure
        for member_id, member_name in group_members:
            if success:
                # Full reward for each member on success
                self.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward, member_id)
                )
                
                # Experience gain
                exp_gain = random.randint(25, 50)
                self.db.execute_query(
                    "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                    (exp_gain, member_id)
                )
                
                # 15% chance for skill improvement per member
                if random.random() < 0.15:
                    skill = random.choice(['engineering', 'navigation', 'combat', 'medical'])
                    self.db.execute_query(
                        f"UPDATE characters SET {skill} = {skill} + 1 WHERE user_id = ?",
                        (member_id,)
                    )
                    
                    # Don't notify via DM - we'll announce in location channel instead
            else:
                # Partial reward for failure (same for all members)
                partial = reward // 3
                self.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (partial, member_id)
                )
                
                # Small experience consolation
                exp_gain = random.randint(5, 15)
                self.db.execute_query(
                    "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                    (exp_gain, member_id)
                )
            
            # Check for level up for each member
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.level_up_check(member_id)
        
        # Clean up job - ONLY ONCE (this was already correct)
        self.db.execute_query("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = ?", (job_id,))
        
        if success:
            embed = discord.Embed(
                title="✅ Group Job Completed Successfully!",
                description=f"**{title}** has been completed by the group!",
                color=0x00ff00
            )
            
            # Convert to intuitive display
            failure_threshold = 100 - success_chance
            displayed_roll = 100 - roll + 1
            
            embed.add_field(
                name="🎲 Success Roll", 
                value=f"Rolled **{displayed_roll}** (needed {failure_threshold+1}+)", 
                inline=True
            )
            embed.add_field(name="💰 Reward Each", value=f"{reward:,} credits", inline=True)
            embed.add_field(name="👥 Group Members", value=str(len(group_members)), inline=True)
        else:
            embed = discord.Embed(
                title="❌ Group Job Failed",
                description=f"**{title}** was not completed successfully",
                color=0xff4444
            )
            
            # Convert to intuitive display
            failure_threshold = 100 - success_chance
            displayed_roll = 100 - roll + 1
            
            embed.add_field(
                name="🎲 Failure Roll", 
                value=f"Rolled **{displayed_roll}** (needed {failure_threshold+1}+ to succeed)", 
                inline=True
            )
            embed.add_field(name="💰 Partial Payment Each", value=f"{reward // 3:,} credits", inline=True)
            embed.add_field(name="👥 Group Members", value=str(len(group_members)), inline=True)


        
        # List all group members who received rewards
        member_names = [name for _, name in group_members]
        embed.add_field(
            name="👥 Rewarded Members",
            value=", ".join(member_names),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)  # Make it public in the location channel
    
    federal_supply_group = app_commands.Group(name="federal_supply", description="Access the Federal Supply depot")
    @federal_supply_group.command(name="list", description="View items available from the Federal Supply")
    async def federal_supply_list(self, interaction: discord.Interaction):
        # First, get the character's current location
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location_id = char_info[0]

        # Check if the location has a Federal Supply
        location_info = self.db.execute_query(
            "SELECT has_federal_supply, name, faction FROM locations WHERE location_id = ?",
            (current_location_id,),
            fetch='one'
        )

        if not location_info or not location_info[0]:
            await interaction.response.send_message("No Federal Supply depot available at this location.", ephemeral=True)
            return

        # Get the character's reputation at this specific location
        reputation_data = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (interaction.user.id, current_location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0

        # Fetch items from Federal Supply, checking reputation
        items = self.bot.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, clearance_level
               FROM federal_supply_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1) AND ? >= clearance_level
               ORDER BY clearance_level ASC, price ASC''',
            (self.location_id, current_reputation),
            fetch='all'
        )

        embed = discord.Embed(
            title=f"🛡️ Federal Supply Depot - {location_info[1]}",
            description=f"Official equipment and supplies for trusted allies of the {location_info[2].title()} faction.",
            color=0x4169E1
        )
        embed.set_footer(text=f"Your Local Reputation: {current_reputation}")

        if items:
            for item_name, item_type, price, stock, description, req_rep in items[:10]:
                stock_text = f"({stock} in stock)" if stock != -1 else "(Unlimited)"
                rep_text = f" [Rep: {req_rep}+]" if req_rep > 0 else ""
                embed.add_field(
                    name=f"{item_name} - {price:,} credits",
                    value=f"_{description}_\n**Requirements:**{rep_text} {stock_text}",
                    inline=False
                )
        else:
            embed.add_field(name="Access Denied or No Stock", value="No items are available to you at this time. Improve your reputation with this faction or check back later.", inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _generate_jobs_for_location(self, location_id: int):
        """Create jobs with heavy emphasis on travel between locations and shift-aware generation."""
        # 1) Remove all untaken jobs here
        self.db.execute_query(
            "DELETE FROM jobs WHERE location_id = ? AND is_taken = 0",
            (location_id,)
        )

        # 2) Get this location's info
        row = self.db.execute_query(
            "SELECT name, x_coord, y_coord, wealth_level, location_type FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        if not row:
            return
        loc_name, x0, y0, wealth, loc_type = row

        # 3) Find all connected destinations
        connected_destinations = self.db.execute_query(
            """SELECT DISTINCT l.location_id, l.name, l.x_coord, l.y_coord, l.location_type, l.wealth_level
               FROM corridors c 
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = ? AND c.is_active = 1""",
            (location_id,),
            fetch='all'
        )
        
        if not connected_destinations:
            return

        # Get shift multiplier for job generation
        shift_multiplier = self.get_shift_job_multiplier()
        
        expire_time = datetime.now() + timedelta(hours=random.randint(3, 8))
        expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")

        # 4) Generate travel jobs with shift-aware counts
        base_travel_jobs = random.randint(6, 12)
        num_travel_jobs = max(2, int(base_travel_jobs * shift_multiplier))  # Apply shift multiplier
        
        print(f"🕐 Generating {num_travel_jobs} travel jobs (shift multiplier: {shift_multiplier:.1f})")
        
        for _ in range(num_travel_jobs):
            dest_id, dest_name, x1, y1, dest_type, dest_wealth = random.choice(connected_destinations)
            
            # Calculate distance-based rewards (travel jobs pay well!)
            dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            base_reward = max(100, int(dist * random.uniform(8, 15)))  # Much better pay
            
            # Wealth bonus for wealthy destinations
            wealth_bonus = (dest_wealth + wealth) * 5
            final_reward = base_reward + wealth_bonus + random.randint(-20, 50)
            
            # Duration based on distance
            duration = max(10, int(dist * random.uniform(1.0, 2.0)))
            danger = min(5, max(1, int(dist / 25) + random.randint(0, 2)))
            
            # Variety of travel job types
            travel_job_types = [
                (f"Urgent Cargo to {dest_name}", f"Transport time-sensitive cargo from {loc_name} to {dest_name}. Speed is essential."),
                (f"Passenger Transport to {dest_name}", f"Ferry passengers safely from {loc_name} to {dest_name}."),
                (f"Medical Supply Run to {dest_name}", f"Deliver critical medical supplies to {dest_name} from {loc_name}."),
                (f"Data Courier to {dest_name}", f"Securely transport encrypted data from {loc_name} to {dest_name}."),
                (f"Equipment Delivery to {dest_name}", f"Transport specialized equipment from {loc_name} to {dest_name}."),
                (f"Emergency Relief to {dest_name}", f"Rush emergency supplies from {loc_name} to {dest_name}."),
                (f"Trade Goods to {dest_name}", f"Transport valuable trade goods from {loc_name} to {dest_name}."),
                (f"Scientific Samples to {dest_name}", f"Carefully transport research samples from {loc_name} to {dest_name}."),
            ]
            
            title, desc = random.choice(travel_job_types)
            
            # Higher rewards for dangerous/long routes
            if danger >= 4:
                final_reward = int(final_reward * 1.5)
                title = f"HAZARD PAY: {title}"
            
            self.db.execute_query(
                '''INSERT INTO jobs
                   (location_id, title, description, reward_money, required_skill, min_skill_level,
                    danger_level, duration_minutes, expires_at, is_taken, destination_location_id)
                   VALUES (?, ?, ?, ?, NULL, 0, ?, ?, ?, 0, ?)''',
                (location_id, title, desc, final_reward, danger, duration, expire_str, dest_id)
            )

        # 5) Add fewer stationary jobs with shift multiplier
        base_stationary = random.randint(2, 4)
        num_stationary = max(1, int(base_stationary * shift_multiplier))   # Can be 0 during night shift
        
        if num_stationary > 0:
            stationary_jobs = [
                ("Local Systems Check", f"Perform routine system diagnostics at {loc_name}."),
                ("Station Maintenance", f"Carry out maintenance duties at {loc_name}."),
                ("Security Patrol", f"Patrol the perimeter of {loc_name}."),
                ("Inventory Management", f"Organize and audit supplies at {loc_name}."),
            ]
            
            for _ in range(num_stationary):
                title, desc = random.choice(stationary_jobs)
                reward = random.randint(40, 80)  # Lower pay for local work
                duration = random.randint(2, 8)  
                danger = random.randint(0, 2)
                
                self.db.execute_query(
                    '''INSERT INTO jobs
                       (location_id, title, description, reward_money, required_skill, min_skill_level,
                        danger_level, duration_minutes, expires_at, is_taken)
                       VALUES (?, ?, ?, ?, NULL, 0, ?, ?, ?, 0)''',
                    (location_id, title, desc, reward, danger, duration, expire_str)
                )

    @job_group.command(name="accept", description="Accept a job by title or ID number")
    @app_commands.describe(job_identifier="Job title/partial title OR job ID number")
    async def job_accept(self, interaction: discord.Interaction, job_identifier: str):
        # Check if player has a character and is not in transit
        char_info = self.db.execute_query(
            "SELECT current_location, hp, money, group_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("You need to create a character first!", ephemeral=True)
            return
        
        current_location, health, money, group_id = char_info
        
        if not current_location:
            await interaction.response.send_message("You cannot accept jobs while in transit!", ephemeral=True)
            return
        
        # Check if in a group
        if group_id:
            # Handle group job acceptance
            await self._handle_group_job_acceptance(interaction, job_id, group_id, current_location)
            return
        # 1) Ensure no other active job
        has_job = self.db.execute_query(
            "SELECT job_id FROM jobs WHERE taken_by = ? AND is_taken = 1",
            (interaction.user.id,),
            fetch='one'
        )
        if has_job:
            return await interaction.response.send_message(
                "You already have an active job. Complete or abandon it first.",
                ephemeral=True
            )

        # 2) Get character info
        char = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if not char:
            return await interaction.response.send_message("Character not found!", ephemeral=True)
        current_location = char[0]

        # 3) Try to find job by ID first, then by title
        job = None
        
        # Check if identifier is numeric (job ID)
        if job_identifier.isdigit():
            job = self.db.execute_query(
                '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
                   FROM jobs
                   WHERE location_id = ? AND job_id = ? AND is_taken = 0 AND expires_at > datetime('now')''',
                (current_location, int(job_identifier)),
                fetch='one'
            )
        
        # If not found by ID or not numeric, search by title
        if not job:
            job = self.db.execute_query(
                '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
                   FROM jobs
                   WHERE location_id = ? AND LOWER(title) LIKE LOWER(?) 
                         AND is_taken = 0 AND expires_at > datetime('now')
                   ORDER BY reward_money DESC
                   LIMIT 1''',
                (current_location, f"%{job_identifier}%"),
                fetch='one'
            )
        
        if not job:
            return await interaction.response.send_message(
                f"Job '{job_identifier}' not found or no longer available.",
                ephemeral=True
            )
        
        # 4) Handle group or solo job acceptance
        await self._accept_solo_job(interaction, job[0], job)

    async def _handle_group_job_acceptance(self, interaction: discord.Interaction, job_id: int, group_id: int, current_location: int):
        """Handle job acceptance for group members"""
        # Get job details
        job_info = self.db.execute_query(
            '''SELECT j.job_id, j.title, j.description, j.reward_money, j.danger_level, 
                      j.duration_minutes, j.is_taken, l.name as location_name
               FROM jobs j
               JOIN locations l ON j.location_id = l.location_id
               WHERE j.job_id = ? AND j.location_id = ? AND j.is_taken = 0''',
            (job_id, current_location),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("This job is not available or already taken.", ephemeral=True)
            return
        
        job_id, title, description, reward, danger, duration, is_taken, location_name = job_info
        
        # Get group info
        group_info = self.db.execute_query(
            "SELECT name, leader_id FROM groups WHERE group_id = ?",
            (group_id,),
            fetch='one'
        )
        
        if not group_info:
            await interaction.response.send_message("Group not found!", ephemeral=True)
            return
        
        group_name, leader_id = group_info
        
        # Check for existing active job vote
        existing_vote = self.db.execute_query(
            '''SELECT session_id FROM group_vote_sessions 
               WHERE group_id = ? AND vote_type = 'job' AND expires_at > datetime('now')''',
            (group_id,),
            fetch='one'
        )
        
        if existing_vote:
            await interaction.response.send_message("Your group already has an active job vote.", ephemeral=True)
            return
        
        # Create vote data
        vote_data = {
            'type': 'job',
            'job_id': job_id,
            'title': title,
            'reward_money': reward,
            'danger_level': danger,
            'duration_minutes': duration,
            'location_name': location_name
        }
        
        import json
        expire_time = datetime.now() + timedelta(minutes=5)
        
        # Create vote session
        self.db.execute_query(
            '''INSERT INTO group_vote_sessions (group_id, vote_type, vote_data, channel_id, expires_at) 
               VALUES (?, ?, ?, ?, ?)''',
            (group_id, 'job', json.dumps(vote_data), interaction.channel.id, expire_time.isoformat())
        )
        
        # Get group members
        members = self.db.execute_query(
            "SELECT user_id, name FROM characters WHERE group_id = ?",
            (group_id,),
            fetch='all'
        )
        
        # Create vote embed
        embed = discord.Embed(
            title="🗳️ Group Job Vote",
            description=f"**{group_name}** - Vote to accept this job",
            color=0x4169E1
        )
        
        embed.add_field(name="Job", value=title, inline=False)
        embed.add_field(name="Description", value=description[:200] + "..." if len(description) > 200 else description, inline=False)
        embed.add_field(name="Total Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Per Member", value=f"{reward//len(members):,} credits", inline=True)
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        embed.add_field(name="Danger Level", value="⚠️" * danger if danger else "Safe", inline=True)
        
        embed.add_field(
            name="📋 How to Vote",
            value="All group members must use `/group vote yes` or `/group vote no` to participate.\nVote expires in 5 minutes.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    async def _accept_solo_job(self, interaction: discord.Interaction, job_id: int, job_info: tuple):
        """Handle solo job acceptance (original logic)"""
        job_id, title, desc, reward, skill, min_level, danger, duration = job_info
        
        # Accept the job
        self.db.execute_query(
            '''UPDATE jobs
               SET is_taken = 1, taken_by = ?, taken_at = datetime('now')
               WHERE job_id = ?''',
            (interaction.user.id, job_id)
        )

        # Determine if this is a stationary job that needs tracking
        title_lower = title.lower()
        desc_lower = desc.lower()

        # Get destination_location_id from the job info
        job_destination = self.db.execute_query(
            "SELECT destination_location_id, location_id FROM jobs WHERE job_id = ?",
            (job_id,),
            fetch='one'
        )

        if job_destination:
            destination_location_id, job_location_id = job_destination
            
            # Determine job type - check destination_location_id first for definitive classification
            if destination_location_id and destination_location_id != job_location_id:
                # Has a different destination location = definitely a transport job
                is_transport_job = True
            elif destination_location_id is None:
                # No destination set - check keywords to determine if it's a transport job (NPC-style)
                is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                                  any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
            else:
                # destination_location_id == job_location_id = stationary job, regardless of keywords
                is_transport_job = False
        else:
            # Fallback to keyword detection if job data not found
            is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                              any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
        
        # Create job tracking record - all jobs get one for consistency
        current_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # For transport jobs, use 0 duration so they don't need location tracking
        tracking_duration = 0 if is_transport_job else duration

        self.db.execute_query(
            '''INSERT INTO job_tracking
               (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
               VALUES (?, ?, ?, ?, 0.0, datetime('now'))''',
            (job_id, interaction.user.id, current_location, tracking_duration)
        )
        embed = discord.Embed(
            title="✅ Job Accepted",
            description=f"You have taken: **{title}** (ID: {job_id})",
            color=0x00ff00
        )
        embed.add_field(name="Details", value=desc, inline=False)
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Duration", value=f"{duration} min", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger, inline=True)
        
        # Add tracking info for stationary jobs
        if not is_transport_job:
            embed.add_field(
                name="📍 Job Type", 
                value="Location-based work - stay at this location to make progress", 
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    @job_group.command(name="abandon", description="Abandon your current job")
    async def job_abandon(self, interaction: discord.Interaction):
        job_info = self.db.execute_query(
            "SELECT job_id, title FROM jobs WHERE taken_by = ? AND is_taken = 1",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("You don't have an active job to abandon.", ephemeral=True)
            return
        
        job_id, title = job_info
        
        # Remove the job assignment (make it available again)
        self.db.execute_query(
            "UPDATE jobs SET is_taken = 0, taken_by = NULL, taken_at = NULL WHERE job_id = ?",
            (job_id,)
        )
        
        embed = discord.Embed(
            title="🚫 Job Abandoned",
            description=f"You have abandoned: **{title}**",
            color=0xff9900
        )
        embed.add_field(
            name="⚠️ Note",
            value="The job is now available for other players to accept.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @job_group.command(name="status", description="Check your current job status")
    async def job_status(self, interaction: discord.Interaction):
        # FORCE a manual update first
        await self._manual_job_update(interaction.user.id)
        
        # Fetch active job with status - INCLUDE destination_location_id and unloading_started_at
        job_info = self.db.execute_query(
            '''SELECT j.job_id, j.title, j.description, j.reward_money, j.taken_at, j.duration_minutes,
                      j.danger_level, l.name as location_name, j.job_status, j.location_id, 
                      j.destination_location_id, j.unloading_started_at
               FROM jobs j
               JOIN locations l ON j.location_id = l.location_id
               WHERE j.taken_by = ? AND j.is_taken = 1''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("You don't have any active jobs.", ephemeral=True)
            return
        
        # Unpack all values including destination_location_id and unloading_started_at
        (job_id, title, desc, reward, taken_at, duration, danger, 
         location_name, job_status, job_location_id, destination_location_id, unloading_started_at) = job_info
        
        # Now we can safely use destination_location_id
        title_lower = title.lower()
        desc_lower = desc.lower()
        
        # Determine job type - check destination_location_id first for definitive classification
        if destination_location_id and destination_location_id != job_location_id:
            # Has a different destination location = definitely a transport job
            is_transport_job = True
        elif destination_location_id is None:
            # No destination set - check keywords to determine if it's a transport job (NPC-style)
            is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                              any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
        else:
            # destination_location_id == job_location_id = stationary job, regardless of keywords
            is_transport_job = False

        taken_time = datetime.fromisoformat(taken_at)
        current_time = datetime.utcnow()
        elapsed_minutes = (current_time - taken_time).total_seconds() / 60

        # TRUNCATE description to prevent Discord limit issues
        truncated_description = desc[:800] + "..." if len(desc) > 800 else desc
        
        embed = discord.Embed(
            title="💼 Current Job Status",
            description=f"**{title}**\n{truncated_description}",
            color=0x4169E1
        )

        # Status based on job type and current state
        if job_status == 'awaiting_finalization':
            # Enhanced unloading phase display
            if unloading_started_at:
                unloading_time = datetime.fromisoformat(unloading_started_at)
                unloading_elapsed = (current_time - unloading_time).total_seconds()
                unloading_duration = 120  # 2 minutes in seconds
                unloading_remaining = max(0, unloading_duration - unloading_elapsed)
                
                status_text = f"🚛 **Unloading Cargo** - {unloading_remaining:.0f}s remaining"
                progress_pct = min(100, (unloading_elapsed / unloading_duration) * 100)
                bars = int(progress_pct // 10)
                progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
                
                if unloading_remaining > 0:
                    status_text += "\n💡 Use `/job complete` to rush (10% penalty)"
            else:
                status_text = "🚛 **Unloading cargo** - Starting..."
                progress_text = "⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%"
        elif job_status == 'completed':
            status_text = "✅ **Completed** - Job finished!"
            progress_text = "Job has been completed successfully"
        elif is_transport_job:
            # Enhanced transport job display
            if destination_location_id:
                # Get destination name
                dest_name = self.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = ?",
                    (destination_location_id,),
                    fetch='one'
                )
                dest_name = dest_name[0] if dest_name else "Unknown Location"
                
                # Check if player is at destination
                player_location = self.db.execute_query(
                    "SELECT current_location FROM characters WHERE user_id = ?",
                    (interaction.user.id,),
                    fetch='one'
                )[0]
                
                if player_location == destination_location_id:
                    status_text = f"📍 **At Destination** - {dest_name}\n✅ Use `/job complete` to start unloading"
                    progress_text = "Ready to unload cargo"
                else:
                    status_text = f"📦 **In Transit** to {dest_name}"
                    # Show expiry time instead of completion time
                    remaining_minutes = duration - elapsed_minutes
                    if remaining_minutes > 0:
                        progress_text = f"⏱️ Expires in {remaining_minutes:.1f} minutes"
                    else:
                        progress_text = "❌ EXPIRED - Complete before auto-cancellation!"
            else:
                # NPC transport job without specific destination
                if elapsed_minutes >= duration:
                    status_text = "✅ **Ready for delivery** - Use `/job complete` at any location"
                    progress_text = "Minimum travel time completed"
                else:
                    remaining_minutes = duration - elapsed_minutes
                    status_text = f"📦 **In Transit** - General delivery"
                    progress_text = f"⏱️ Travel for {remaining_minutes:.1f} more minutes"
            
            # Add fields specific to transport jobs
            embed.add_field(name="💰 Reward", value=f"{reward:,} credits", inline=True)
            embed.add_field(name="⚠️ Danger", value="⚠️" * danger if danger > 0 else "Safe", inline=True)
            
            if destination_location_id:
                embed.add_field(name="🎯 Destination", value=dest_name[:1020], inline=True)
            else:
                embed.add_field(name="📍 Origin", value=location_name[:1020], inline=True)
                
            embed.add_field(name="Status", value=status_text[:1020], inline=False)
            embed.add_field(name="Progress", value=progress_text[:1020], inline=False)
            
            # Skip the default fields since we added them above
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
            
        else:
            # Stationary job - check tracking
            tracking = self.db.execute_query(
                "SELECT time_at_location, required_duration FROM job_tracking WHERE job_id = ? AND user_id = ?",
                (job_id, interaction.user.id),
                fetch='one'
            )
            
            if tracking:
                time_at_location, required_duration = tracking
                # FIX: Ensure values are treated as floats and handle edge cases
                time_at_location = float(time_at_location) if time_at_location else 0.0
                required_duration = float(required_duration) if required_duration else 1.0
                
                if time_at_location >= required_duration:
                    status_text = "✅ **Ready for completion** - Use `/job complete`"
                    progress_text = "Required time at location completed"
                else:
                    remaining = max(0, required_duration - time_at_location)  # Prevent negative values
                    status_text = f"📍 **Working on-site** - {remaining:.1f} minutes remaining"
                    progress_pct = min(100, (time_at_location / required_duration) * 100)  # Cap at 100%
                    bars = int(progress_pct // 10)
                    progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
            else:
                status_text = "📍 **Needs location tracking** - Use `/job complete` to start"
                progress_text = "Location-based work not yet started"

        # Default field layout for non-transport jobs
        embed.add_field(name="Status", value=status_text[:1020], inline=False)
        embed.add_field(name="Progress", value=progress_text[:1020], inline=False)
        embed.add_field(name="💰 Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="⚠️ Danger", value="⚠️" * danger if danger > 0 else "Safe", inline=True)
        embed.add_field(name="📍 Location", value=location_name[:1020], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def _manual_job_update(self, user_id: int):
        """Manually update job tracking for a specific user"""
        try:
            tracking = self.db.execute_query(
                '''SELECT jt.tracking_id, jt.job_id, jt.start_location, jt.required_duration, 
                          jt.time_at_location, jt.last_location_check
                   FROM job_tracking jt
                   JOIN jobs j ON jt.job_id = j.job_id
                   WHERE jt.user_id = ? AND j.is_taken = 1''',
                (user_id,),
                fetch='one'
            )
            
            if tracking:
                tracking_id, job_id, start_location, required_duration, time_at_location, last_check = tracking
                
                # Check current location
                current_location = self.db.execute_query(
                    "SELECT current_location FROM characters WHERE user_id = ?",
                    (user_id,),
                    fetch='one'
                )
                
                if current_location and current_location[0] == start_location:
                    # Force add 1 minute to the tracking
                    new_time = float(time_at_location or 0) + 1.0
                    self.db.execute_query(
                        '''UPDATE job_tracking
                           SET time_at_location = ?, last_location_check = datetime('now')
                           WHERE tracking_id = ?''',
                        (new_time, tracking_id)
                    )
                    print(f"🔄 Manual update: User {user_id} +1.0 minutes (total: {new_time})")
                    return True
            return False
        except Exception as e:
            print(f"❌ Manual job update failed for user {user_id}: {e}")
            return False

    @job_group.command(name="debug", description="Debug job tracking (admin only)")
    async def job_debug(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only command.", ephemeral=True)
            return
        
        # Get all active tracking
        tracking_records = self.db.execute_query(
            '''
            SELECT
              jt.tracking_id,
              jt.job_id,
              jt.user_id,
              jt.start_location,
              jt.required_duration,
              jt.time_at_location,
              jt.last_location_check,
              j.title,
              c.current_location,
              c.name as char_name
            FROM job_tracking jt
            JOIN jobs j ON jt.job_id = j.job_id
            JOIN characters c ON jt.user_id = c.user_id
            WHERE j.is_taken = 1
            ''',
            fetch='all'
        )
        
        if not tracking_records:
            await interaction.response.send_message("No active job tracking records found.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🔍 Job Tracking Debug", color=0x4169E1)
        
        for record in tracking_records:
            tracking_id, job_id, user_id, start_loc, req_duration, time_at_loc, last_check, job_title, current_loc, char_name = record
            
            status = "✅ At location" if current_loc == start_loc else f"❌ Wrong location ({current_loc} vs {start_loc})"
            progress = f"{float(time_at_loc or 0):.1f}/{req_duration} min"
            
            embed.add_field(
                name=f"{char_name} - {job_title[:30]}",
                value=f"Status: {status}\nProgress: {progress}\nLast Check: {last_check}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @job_group.command(name="force_update", description="Force update job progress (admin only)")
    async def job_force_update(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only command.", ephemeral=True)
            return
        
        updated = await self._manual_job_update(interaction.user.id)
        
        if updated:
            await interaction.response.send_message("✅ Job progress manually updated by 1 minute.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No active job tracking found or player not at correct location.", ephemeral=True)
async def setup(bot):
    economy_cog = EconomyCog(bot)
    await bot.add_cog(economy_cog)
    print("📊 Economy system loaded with automatic job tracking")
    
class InteractiveShopView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, location_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.location_name = location_name
    
    @discord.ui.button(label="Buy Items", style=discord.ButtonStyle.success, emoji="🛒")
    async def buy_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your shop interface!", ephemeral=True)
            return
        
        # Get available items
        items = self.bot.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description
               FROM shop_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1)
               ORDER BY item_type, price''',
            (self.location_id,),
            fetch='all'
        )
        
        if not items:
            await interaction.response.send_message("No items available for purchase.", ephemeral=True)
            return
        
        view = ShopBuySelectView(self.bot, self.user_id, self.location_id, items)
        
        embed = discord.Embed(
            title=f"🛒 Buy Items - {self.location_name}",
            description="Select an item to purchase:",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Sell Items", style=discord.ButtonStyle.primary, emoji="💰")
    async def sell_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your shop interface!", ephemeral=True)
            return
        
        # Get player's inventory - MODIFIED to include item_id
        inventory_items = self.bot.db.execute_query(
            '''SELECT item_id, item_name, quantity, value, item_type, description
               FROM inventory 
               WHERE owner_id = ? AND quantity > 0
               ORDER BY item_type, item_name''',
            (self.user_id,),
            fetch='all'
        )
        
        if not inventory_items:
            await interaction.response.send_message("You don't have any items to sell.", ephemeral=True)
            return
        
        view = ShopSellSelectView(self.bot, self.user_id, self.location_id, inventory_items)
        
        embed = discord.Embed(
            title=f"💰 Sell Items - {self.location_name}",
            description="Select an item to sell:",
            color=0xffd700
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ShopBuySelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, items: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        if items:
            options = []
            for item_name, item_type, price, stock, description in items[:25]:  # Discord limit
                stock_text = f"({stock} in stock)" if stock != -1 else "(Unlimited)"
                
                # Check economic status
                econ_cog = bot.get_cog('EconomyCog')
                if econ_cog:
                    status, _, _ = econ_cog.get_economic_modifiers(location_id, item_name, item_type)
                    status_emoji = ""
                    if status == 'in_demand':
                        status_emoji = " 🔥"
                    elif status == 'surplus':
                        status_emoji = " 📦"
                else:
                    status_emoji = ""
                
                options.append(
                    discord.SelectOption(
                        label=f"{item_name} - {price:,} credits",
                        description=f"{description[:80]}{'...' if len(description) > 80 else ''} {stock_text}{status_emoji}"[:100],
                        value=item_name
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose an item to buy...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your shop interface!", ephemeral=True)
            return
        
        item_name = interaction.data['values'][0]
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_name, price, stock, description, item_type
               FROM shop_items 
               WHERE location_id = ? AND item_name = ?''',
            (self.location_id, item_name),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return
        
        view = ShopBuyQuantityView(self.bot, self.user_id, self.location_id, item_info)
        
        embed = discord.Embed(
            title=f"🛒 Purchase: {item_name}",
            description=item_info[3],  # description
            color=0x00ff00
        )
        
        embed.add_field(name="Price per Item", value=f"{item_info[1]:,} credits", inline=True)
        stock_text = f"{item_info[2]} available" if item_info[2] != -1 else "Unlimited stock"
        embed.add_field(name="Stock", value=stock_text, inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ShopBuyQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, item_info: tuple):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.item_name, self.price, self.stock, self.description, self.item_type = item_info
        self.quantity = 1
        self.max_quantity = self.stock if self.stock != -1 else 10  # Cap unlimited at 10 for UI
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Quantity controls
        decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.quantity <= 1))
        decrease_btn.callback = self.decrease_quantity
        self.add_item(decrease_btn)
        
        quantity_btn = discord.ui.Button(label=f"Qty: {self.quantity}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(quantity_btn)
        
        increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.quantity >= self.max_quantity))
        increase_btn.callback = self.increase_quantity
        self.add_item(increase_btn)
        
        # Purchase button
        total_cost = self.price * self.quantity
        buy_btn = discord.ui.Button(label=f"Buy for {total_cost:,} credits", style=discord.ButtonStyle.success, emoji="💳")
        buy_btn.callback = self.confirm_purchase
        self.add_item(buy_btn)
        
        # Cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
        cancel_btn.callback = self.cancel_purchase
        self.add_item(cancel_btn)
    
    async def decrease_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = max(1, self.quantity - 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = min(self.max_quantity, self.quantity + 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def confirm_purchase(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        # Use the existing shop_buy logic from EconomyCog
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            # Create a mock interaction for the shop_buy method
            # We'll call the logic directly
            await self._execute_purchase(interaction, econ_cog)
        else:
            await interaction.response.send_message("Shop system unavailable.", ephemeral=True)
    
    async def _execute_purchase(self, interaction: discord.Interaction, econ_cog):
        """Execute the purchase using existing economy logic"""
        await interaction.response.defer(ephemeral=True)
        
        char_info = econ_cog.db.execute_query(
            "SELECT current_location, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Find item in shop
        item = econ_cog.db.execute_query(
            '''SELECT item_id, item_name, price, stock, description, item_type
               FROM shop_items 
               WHERE location_id = ? AND item_name = ?
               AND (stock >= ? OR stock = -1)''',
            (current_location, self.item_name, self.quantity),
            fetch='one'
        )
        
        if not item:
            await interaction.followup.send(f"Item '{self.item_name}' not available or insufficient stock.", ephemeral=True)
            return
        
        item_id, actual_name, price, stock, description, item_type = item
        total_cost = price * self.quantity
        
        if current_money < total_cost:
            await interaction.followup.send(
                f"Insufficient credits! Need {total_cost:,}, have {current_money:,}.",
                ephemeral=True
            )
            return
        
        # Process purchase (same logic as shop_buy)
        econ_cog.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        # Update shop stock
        if stock != -1:
            econ_cog.db.execute_query(
                "UPDATE shop_items SET stock = stock - ? WHERE item_id = ?",
                (self.quantity, item_id)
            )
        
        # Add to inventory
        existing_item = econ_cog.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, actual_name),
            fetch='one'
        )
        
        if existing_item:
            econ_cog.db.execute_query(
                "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
                (self.quantity, existing_item[0])
            )
        else:
            econ_cog.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, actual_name, item_type, self.quantity, description, price)
            )
        
        embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"Bought {self.quantity}x **{actual_name}** for {total_cost:,} credits",
            color=0x00ff00
        )
        embed.add_field(name="Remaining Credits", value=f"{current_money - total_cost:,}", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def cancel_purchase(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        await interaction.response.send_message("Purchase cancelled.", ephemeral=True)

class ShopSellSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, inventory_items: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        if inventory_items:
            options = []
            # MODIFIED to unpack item_id from the tuple
            for item_id, item_name, quantity, value, item_type, description in inventory_items[:25]:
                # Calculate approximate sell price (60% of value)
                sell_price = max(1, int(value * 0.6))
                
                options.append(
                    discord.SelectOption(
                        label=f"{item_name} (x{quantity})",
                        description=f"~{sell_price:,} credits each - {description[:60]}{'...' if len(description) > 60 else ''}"[:100],
                        value=str(item_id)  # MODIFIED to use item_id as the unique value
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose an item to sell...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        # MODIFIED to get item_id from the selection
        item_id = int(interaction.data['values'][0])
        
        # Get item details from inventory using item_id
        item_info = self.bot.db.execute_query(
            '''SELECT item_name, quantity, value, item_type, description
               FROM inventory 
               WHERE owner_id = ? AND item_id = ?''',
            (self.user_id, item_id),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item not found in inventory.", ephemeral=True)
            return
        
        view = ShopSellQuantityView(self.bot, self.user_id, self.location_id, item_info)
        
        # Calculate sell price with economic modifiers
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            # Get location wealth for sell price calculation
            wealth_level = self.bot.db.execute_query(
                "SELECT wealth_level FROM locations WHERE location_id = ?",
                (self.location_id,),
                fetch='one'
            )[0]
            
            base_multiplier = 0.5 + (wealth_level * 0.03)
            base_sell_price = max(1, int(item_info[2] * base_multiplier))
            
            status, price_mod, stock_mod = econ_cog.get_economic_modifiers(self.location_id, item_info[0], item_info[3])
            final_sell_price, _ = econ_cog.apply_economic_modifiers(
                base_sell_price, 1, status, price_mod, stock_mod, is_buying=False
            )
        else:
            final_sell_price = max(1, int(item_info[2] * 0.6))
        
        embed = discord.Embed(
            title=f"💰 Sell: {item_info[0]}",
            description=item_info[4],  # description
            color=0xffd700
        )
        
        embed.add_field(name="Price per Item", value=f"{final_sell_price:,} credits", inline=True)
        embed.add_field(name="Available", value=f"{item_info[1]} in inventory", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ShopSellQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, item_info: tuple):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.item_name, self.max_quantity, self.base_value, self.item_type, self.description = item_info
        self.quantity = 1
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Calculate current sell price
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            wealth_level = self.bot.db.execute_query(
                "SELECT wealth_level FROM locations WHERE location_id = ?",
                (self.location_id,),
                fetch='one'
            )[0]
            
            base_multiplier = 0.5 + (wealth_level * 0.03)
            base_sell_price = max(1, int(self.base_value * base_multiplier))
            
            status, price_mod, stock_mod = econ_cog.get_economic_modifiers(self.location_id, self.item_name, self.item_type)
            self.sell_price, _ = econ_cog.apply_economic_modifiers(
                base_sell_price, 1, status, price_mod, stock_mod, is_buying=False
            )
        else:
            self.sell_price = max(1, int(self.base_value * 0.6))
        
        # Quantity controls
        decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.quantity <= 1))
        decrease_btn.callback = self.decrease_quantity
        self.add_item(decrease_btn)
        
        quantity_btn = discord.ui.Button(label=f"Qty: {self.quantity}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(quantity_btn)
        
        increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.quantity >= self.max_quantity))
        increase_btn.callback = self.increase_quantity
        self.add_item(increase_btn)
        
        # Max button
        max_btn = discord.ui.Button(label="Max", style=discord.ButtonStyle.secondary, disabled=(self.quantity >= self.max_quantity))
        max_btn.callback = self.set_max_quantity
        self.add_item(max_btn)
        
        # Sell button
        total_earnings = self.sell_price * self.quantity
        sell_btn = discord.ui.Button(label=f"Sell for {total_earnings:,} credits", style=discord.ButtonStyle.success, emoji="💰")
        sell_btn.callback = self.confirm_sale
        self.add_item(sell_btn)
        
        # Cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
        cancel_btn.callback = self.cancel_sale
        self.add_item(cancel_btn)
    
    async def decrease_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = max(1, self.quantity - 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = min(self.max_quantity, self.quantity + 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def set_max_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = self.max_quantity
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def confirm_sale(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        # Use the existing shop_sell logic
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            await self._execute_sale(interaction, econ_cog)
        else:
            await interaction.response.send_message("Shop system unavailable.", ephemeral=True)
    
    async def _execute_sale(self, interaction: discord.Interaction, econ_cog):
        """Execute the sale using existing economy logic"""
        await interaction.response.defer(ephemeral=True)
        
        char_info = econ_cog.db.execute_query(
            "SELECT current_location, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Check if location has shops
        has_shops = econ_cog.db.execute_query(
            "SELECT has_shops, wealth_level FROM locations WHERE location_id = ?",
            (current_location,),
            fetch='one'
        )
        
        if not has_shops or not has_shops[0]:
            await interaction.followup.send("This location doesn't buy items.", ephemeral=True)
            return
        
        # Find item in inventory
        inventory_item = econ_cog.db.execute_query(
            '''SELECT item_id, item_name, quantity, value, item_type, description
               FROM inventory 
               WHERE owner_id = ? AND item_name = ? AND quantity >= ?''',
            (interaction.user.id, self.item_name, self.quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.followup.send(f"You don't have enough '{self.item_name}' to sell.", ephemeral=True)
            return
        
        inv_id, actual_name, current_qty, base_value, item_type, description = inventory_item
        
        total_earnings = self.sell_price * self.quantity
        
        # Update inventory
        if current_qty == self.quantity:
            econ_cog.db.execute_query("DELETE FROM inventory WHERE item_id = ?", (inv_id,))
        else:
            econ_cog.db.execute_query(
                "UPDATE inventory SET quantity = quantity - ? WHERE item_id = ?",
                (self.quantity, inv_id)
            )
        
        # Add money to character
        econ_cog.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (total_earnings, interaction.user.id)
        )
        
        # Add sold items to shop (same logic as existing shop_sell)
        markup_price = max(self.sell_price + 1, int(self.sell_price * 1.2))
        
        existing = econ_cog.db.execute_query(
            "SELECT item_id, stock, price FROM shop_items WHERE location_id = ? AND LOWER(item_name) = LOWER(?)",
            (current_location, actual_name),
            fetch='one'
        )
        
        if existing:
            shop_id, shop_stock, shop_price = existing
            new_stock = shop_stock + self.quantity if shop_stock != -1 else -1
            new_price = max(shop_price, markup_price)
            econ_cog.db.execute_query(
                "UPDATE shop_items SET stock = ?, price = ? WHERE item_id = ?",
                (new_stock, new_price, shop_id)
            )
        else:
            econ_cog.db.execute_query(
                '''INSERT INTO shop_items
                   (location_id, item_name, item_type, price, stock, description)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (current_location, actual_name, item_type, markup_price, self.quantity, description)
            )
        
        embed = discord.Embed(
            title="💰 Item Sold",
            description=f"Sold {self.quantity}x **{actual_name}** for {total_earnings:,} credits",
            color=0x00ff00
        )
        embed.add_field(name="Price per Item", value=f"{self.sell_price:,} credits", inline=True)
        embed.add_field(name="New Balance", value=f"{current_money + total_earnings:,} credits", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def cancel_sale(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        await interaction.response.send_message("Sale cancelled.", ephemeral=True)

class InteractiveJobListView(discord.ui.View):
    def __init__(self, bot, user_id: int, jobs: list, location_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_name = location_name
        
        if jobs:
            options = []
            for job in jobs[:25]:  # Discord limit
                job_id, title, desc, reward, skill, min_level, danger, duration = job
                
                danger_text = "⚠️" * danger if danger > 0 else ""
                skill_text = f" (Requires {skill} {min_level}+)" if skill else ""
                time_text = f"{duration}min"
                
                options.append(
                    discord.SelectOption(
                        label=f"{title} - {reward:,} credits",
                        description=f"{desc[:60]}{'...' if len(desc) > 60 else ''} | {time_text}{skill_text} {danger_text}"[:100],
                        value=str(job_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose a job to view details...", options=options)
                select.callback = self.job_selected
                self.add_item(select)
    
    async def job_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your job interface!", ephemeral=True)
            return
        
        job_id = int(interaction.data['values'][0])
        
        # Get job details
        job_info = self.bot.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, 
                      danger_level, duration_minutes, destination_location_id
               FROM jobs WHERE job_id = ?''',
            (job_id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("Job no longer available.", ephemeral=True)
            return
        
        view = JobDetailView(self.bot, self.user_id, job_info)
        
        job_id, title, desc, reward, skill, min_skill, danger, duration, dest_location_id = job_info
        
        embed = discord.Embed(
            title=f"💼 Job Details: {title}",
            description=desc,
            color=0x4169E1
        )
        
        embed.add_field(name="💰 Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="⏱️ Duration", value=f"{duration} minutes", inline=True)
        embed.add_field(name="⚠️ Danger", value="⚠️" * danger if danger > 0 else "Safe", inline=True)
        
        if skill:
            embed.add_field(name="🎯 Requirements", value=f"{skill.title()} Level {min_skill}+", inline=True)
        
        # Determine job type
        if dest_location_id:
            dest_name = self.bot.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (dest_location_id,),
                fetch='one'
            )
            if dest_name:
                embed.add_field(name="📍 Destination", value=dest_name[0], inline=True)
                embed.add_field(name="🚀 Job Type", value="Transport Mission", inline=True)
        else:
            # Check if it's a transport job by keywords
            title_lower = title.lower()
            desc_lower = desc.lower()
            is_transport = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
            
            if is_transport:
                embed.add_field(name="🚀 Job Type", value="Transport Mission", inline=True)
            else:
                embed.add_field(name="📍 Job Type", value="Location-based Work", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class JobDetailView(discord.ui.View):
    def __init__(self, bot, user_id: int, job_info: tuple):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.job_info = job_info
    
    @discord.ui.button(label="Accept Job", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_job(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your job interface!", ephemeral=True)
            return
        
        job_id = self.job_info[0]
        
        # Use existing job acceptance logic from EconomyCog
        econ_cog = self.bot.get_cog('EconomyCog')
        if econ_cog:
            await self._execute_job_acceptance(interaction, econ_cog, job_id)
        else:
            await interaction.response.send_message("Job system unavailable.", ephemeral=True)
    
    async def _execute_job_acceptance(self, interaction: discord.Interaction, econ_cog, job_id: int):
        """Execute job acceptance using existing economy logic"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user already has a job
        has_job = econ_cog.db.execute_query(
            "SELECT job_id FROM jobs WHERE taken_by = ? AND is_taken = 1",
            (interaction.user.id,),
            fetch='one'
        )
        
        if has_job:
            await interaction.followup.send("You already have an active job. Complete or abandon it first.", ephemeral=True)
            return
        
        # Get character info
        char = econ_cog.db.execute_query(
            "SELECT current_location, group_id FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_location, group_id = char
        
        # Get job details again to ensure it's still available
        job = econ_cog.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
               FROM jobs
               WHERE location_id = ? AND job_id = ? AND is_taken = 0 AND expires_at > datetime('now')''',
            (current_location, job_id),
            fetch='one'
        )
        
        if not job:
            await interaction.followup.send("Job is no longer available.", ephemeral=True)
            return
        
        # Check for group job acceptance if in a group
        if group_id:
            await interaction.followup.send("Group job acceptance not supported in this interface. Use `/job accept` command.", ephemeral=True)
            return
        
        # Extract job info
        job_id, title, desc, reward, skill, min_level, danger, duration = job
        
        # Check skill requirements
        if skill:
            char_skills = econ_cog.db.execute_query(
                f"SELECT {skill} FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_skills or char_skills[0] < min_level:
                await interaction.followup.send(
                    f"You need at least {min_level} {skill} skill for this job.",
                    ephemeral=True
                )
                return
        
        # Accept the job (using the same logic as _accept_solo_job but without sending response)
        econ_cog.db.execute_query(
            '''UPDATE jobs
               SET is_taken = 1, taken_by = ?, taken_at = datetime('now')
               WHERE job_id = ?''',
            (interaction.user.id, job_id)
        )

        # Determine if this is a stationary job that needs tracking
        title_lower = title.lower()
        desc_lower = desc.lower()

        # Get destination_location_id from the job info
        job_destination = econ_cog.db.execute_query(
            "SELECT destination_location_id, location_id FROM jobs WHERE job_id = ?",
            (job_id,),
            fetch='one'
        )

        if job_destination:
            destination_location_id, job_location_id = job_destination
            
            # Determine job type - check destination_location_id first for definitive classification
            if destination_location_id and destination_location_id != job_location_id:
                # Has a different destination location = definitely a transport job
                is_transport_job = True
            elif destination_location_id is None:
                # No destination set - check keywords to determine if it's a transport job (NPC-style)
                is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                                  any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
            else:
                # destination_location_id == job_location_id = stationary job, regardless of keywords
                is_transport_job = False
        else:
            # Fallback to keyword detection if job data not found
            is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                              any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
        
        # Create job tracking record - all jobs get one for consistency
        current_location = econ_cog.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # For transport jobs, use 0 duration so they don't need location tracking
        tracking_duration = 0 if is_transport_job else duration

        econ_cog.db.execute_query(
            '''INSERT INTO job_tracking
               (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
               VALUES (?, ?, ?, ?, 0.0, datetime('now'))''',
            (job_id, interaction.user.id, current_location, tracking_duration)
        )
        
        # Build success embed
        embed = discord.Embed(
            title="✅ Job Accepted",
            description=f"You have taken: **{title}** (ID: {job_id})",
            color=0x00ff00
        )
        embed.add_field(name="Details", value=desc, inline=False)
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Duration", value=f"{duration} min", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger, inline=True)
        
        # Add tracking info for stationary jobs
        if not is_transport_job:
            embed.add_field(
                name="📍 Job Type", 
                value="Location-based work - stay at this location to make progress", 
                inline=False
            )

        # Use followup since we already deferred the response
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_job(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your job interface!", ephemeral=True)
            return
        
        await interaction.response.send_message("Job viewing cancelled.", ephemeral=True)
        
        
        
class InteractiveFederalDepotView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, location_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.location_name = location_name
    
    @discord.ui.button(label="Browse Equipment", style=discord.ButtonStyle.primary, emoji="🛒")
    async def browse_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your federal depot interface!", ephemeral=True)
            return
        
        # Get character reputation
        reputation_data = self.bot.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (self.user_id, self.location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0
        
        # Get available items based on reputation - THIS IS THE FIX
        items = self.bot.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, clearance_level
               FROM federal_supply_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1) AND ? >= clearance_level
               ORDER BY clearance_level ASC, price ASC''',
            (self.location_id, current_reputation),
            fetch='all'
        )
        
        if not items:
            await interaction.response.send_message("No federal equipment available with your current reputation level.", ephemeral=True)
            return
        
        view = FederalDepotBuySelectView(self.bot, self.user_id, self.location_id, items)
        
        embed = discord.Embed(
            title=f"🏛️ Federal Equipment Catalog - {self.location_name}",
            description="Select federal equipment to purchase:",
            color=0x0066cc
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class InteractiveBlackMarketView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, location_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.location_name = location_name
    
    @discord.ui.button(label="Browse Contraband", style=discord.ButtonStyle.danger, emoji="💀")
    async def browse_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your black market interface!", ephemeral=True)
            return
        
        # Get available items
        items = self.bot.db.execute_query(
            '''SELECT bmi.item_name, bmi.item_type, bmi.price, bmi.stock, bmi.description
               FROM black_market_items bmi
               JOIN black_markets bm ON bmi.market_id = bm.market_id
               WHERE bm.location_id = ? AND (bmi.stock > 0 OR bmi.stock = -1)
               ORDER BY bmi.item_type, bmi.price''',
            (self.location_id,),
            fetch='all'
        )
        
        if not items:
            await interaction.response.send_message("No contraband available at this time.", ephemeral=True)
            return
        
        view = BlackMarketBuySelectView(self.bot, self.user_id, self.location_id, items)
        
        embed = discord.Embed(
            title=f"💀 Contraband Catalog - {self.location_name}",
            description="Select contraband to purchase (discretion advised):",
            color=0x8b0000
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class FederalDepotBuySelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, items: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        if items:
            options = []
            for item_name, item_type, price, stock, description, req_rep in items[:25]:
                stock_text = f"({stock} in stock)" if stock != -1 else "(Unlimited)"
                rep_text = f" [Rep {req_rep}+]" if req_rep > 0 else ""
                
                options.append(
                    discord.SelectOption(
                        label=f"{item_name} - {price:,} credits",
                        description=f"{description[:70]}{'...' if len(description) > 70 else ''} {stock_text}{rep_text}"[:100],
                        value=item_name,
                        emoji="🏛️"
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose federal equipment to purchase...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your federal depot interface!", ephemeral=True)
            return
        
        item_name = interaction.data['values'][0]
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_name, price, stock, description, item_type, required_reputation
               FROM federal_supply_items 
               WHERE location_id = ? AND item_name = ?''',
            (self.location_id, item_name),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return
        
        view = FederalDepotQuantityView(self.bot, self.user_id, self.location_id, item_info)
        
        embed = discord.Embed(
            title=f"🏛️ Purchase: {item_name}",
            description=f"**Federal Equipment**\n{item_info[3]}",
            color=0x0066cc
        )
        
        embed.add_field(name="Price per Item", value=f"{item_info[1]:,} credits", inline=True)
        stock_text = f"{item_info[2]} available" if item_info[2] != -1 else "Unlimited stock"
        embed.add_field(name="Stock", value=stock_text, inline=True)
        if item_info[5] > 0:
            embed.add_field(name="Required Reputation", value=f"{item_info[5]}+", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class BlackMarketBuySelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, items: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        if items:
            options = []
            for item_name, item_type, price, stock, description in items[:25]:
                stock_text = f"({stock} available)" if stock != -1 else "(Unlimited)"
                
                options.append(
                    discord.SelectOption(
                        label=f"{item_name} - {price:,} credits",
                        description=f"{description[:80]}{'...' if len(description) > 80 else ''} {stock_text}"[:100],
                        value=item_name,
                        emoji="💀"
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose contraband to purchase...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your black market interface!", ephemeral=True)
            return
        
        item_name = interaction.data['values'][0]
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT bmi.item_name, bmi.price, bmi.stock, bmi.description, bmi.item_type
               FROM black_market_items bmi
               JOIN black_markets bm ON bmi.market_id = bm.market_id
               WHERE bm.location_id = ? AND bmi.item_name = ?''',
            (self.location_id, item_name),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return
        
        view = BlackMarketQuantityView(self.bot, self.user_id, self.location_id, item_info)
        
        embed = discord.Embed(
            title=f"💀 Purchase: {item_name}",
            description=f"**Contraband Item**\n{item_info[3]}",
            color=0x8b0000
        )
        
        embed.add_field(name="Price per Item", value=f"{item_info[1]:,} credits", inline=True)
        stock_text = f"{item_info[2]} available" if item_info[2] != -1 else "Unlimited stock"
        embed.add_field(name="Stock", value=stock_text, inline=True)
        embed.add_field(name="⚠️ Risk", value="High", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class FederalDepotQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, item_info: tuple):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.item_name, self.price, self.stock, self.description, self.item_type, self.required_reputation = item_info
        self.quantity = 1
        self.max_quantity = self.stock if self.stock != -1 else 10
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Quantity controls
        decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.quantity <= 1))
        decrease_btn.callback = self.decrease_quantity
        self.add_item(decrease_btn)
        
        quantity_btn = discord.ui.Button(label=f"Qty: {self.quantity}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(quantity_btn)
        
        increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.quantity >= self.max_quantity))
        increase_btn.callback = self.increase_quantity
        self.add_item(increase_btn)
        
        # Purchase button
        total_cost = self.price * self.quantity
        buy_btn = discord.ui.Button(label=f"Purchase for {total_cost:,} credits", style=discord.ButtonStyle.success, emoji="🏛️")
        buy_btn.callback = self.confirm_purchase
        self.add_item(buy_btn)
        
        # Cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
        cancel_btn.callback = self.cancel_purchase
        self.add_item(cancel_btn)
    
    async def decrease_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = max(1, self.quantity - 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = min(self.max_quantity, self.quantity + 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def confirm_purchase(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        await self._execute_federal_purchase(interaction)
    
    async def cancel_purchase(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        await interaction.response.send_message("Federal purchase cancelled.", ephemeral=True)
    
    async def _execute_federal_purchase(self, interaction: discord.Interaction):
        """Execute federal depot purchase"""
        await interaction.response.defer(ephemeral=True)
        
        # Check character funds and reputation
        char_info = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_money = char_info[0]
        total_cost = self.price * self.quantity
        
        if current_money < total_cost:
            await interaction.followup.send(
                f"Insufficient credits! Need {total_cost:,}, have {current_money:,}.",
                ephemeral=True
            )
            return
        
        # Check reputation
        reputation_data = self.bot.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (interaction.user.id, self.location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0
        
        if current_reputation < self.required_reputation:
            await interaction.followup.send(
                f"Insufficient reputation! Need {self.required_reputation}, have {current_reputation}.",
                ephemeral=True
            )
            return
        
        # Execute purchase
        from item_config import ItemConfig
        
        # Deduct money
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        # Add item to inventory
        existing_item = self.bot.db.execute_query(
            "SELECT quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, self.item_name),
            fetch='one'
        )
        
        item_data = ItemConfig.get_item_definition(self.item_name)
        item_value = item_data.get("base_value", self.price) if item_data else self.price
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + ? WHERE owner_id = ? AND item_name = ?",
                (self.quantity, interaction.user.id, self.item_name)
            )
        else:
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, value, description)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, self.item_name, self.item_type, self.quantity, item_value, self.description)
            )
        
        # Update stock if not unlimited
        if self.stock != -1:
            self.bot.db.execute_query(
                "UPDATE federal_supply_items SET stock = stock - ? WHERE location_id = ? AND item_name = ?",
                (self.quantity, self.location_id, self.item_name)
            )
        
        embed = discord.Embed(
            title="🏛️ Federal Purchase Complete",
            description=f"Successfully purchased {self.quantity}x **{self.item_name}** for {total_cost:,} credits",
            color=0x00ff00
        )
        embed.add_field(name="New Balance", value=f"{current_money - total_cost:,} credits", inline=True)
        embed.add_field(name="Federal Status", value="Purchase logged in federal records", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class BlackMarketQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, item_info: tuple):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        self.item_name, self.price, self.stock, self.description, self.item_type = item_info
        self.quantity = 1
        self.max_quantity = self.stock if self.stock != -1 else 10
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Quantity controls
        decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.quantity <= 1))
        decrease_btn.callback = self.decrease_quantity
        self.add_item(decrease_btn)
        
        quantity_btn = discord.ui.Button(label=f"Qty: {self.quantity}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(quantity_btn)
        
        increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.quantity >= self.max_quantity))
        increase_btn.callback = self.increase_quantity
        self.add_item(increase_btn)
        
        # Purchase button
        total_cost = self.price * self.quantity
        buy_btn = discord.ui.Button(label=f"Buy for {total_cost:,} credits", style=discord.ButtonStyle.danger, emoji="💀")
        buy_btn.callback = self.confirm_purchase
        self.add_item(buy_btn)
        
        # Cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
        cancel_btn.callback = self.cancel_purchase
        self.add_item(cancel_btn)
    
    async def decrease_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = max(1, self.quantity - 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        self.quantity = min(self.max_quantity, self.quantity + 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def confirm_purchase(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        await self._execute_black_market_purchase(interaction)
    
    async def cancel_purchase(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interface!", ephemeral=True)
            return
        
        await interaction.response.send_message("Black market deal cancelled.", ephemeral=True)
    
    async def _execute_black_market_purchase(self, interaction: discord.Interaction):
        """Execute black market purchase"""
        await interaction.response.defer(ephemeral=True)
        
        # Check character funds
        char_info = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_money = char_info[0]
        total_cost = self.price * self.quantity
        
        if current_money < total_cost:
            await interaction.followup.send(
                f"Insufficient credits! Need {total_cost:,}, have {current_money:,}.",
                ephemeral=True
            )
            return
        
        # Execute purchase
        from item_config import ItemConfig
        
        # Deduct money
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (total_cost, interaction.user.id)
        )
        
        # Add item to inventory
        existing_item = self.bot.db.execute_query(
            "SELECT quantity FROM inventory WHERE owner_id = ? AND item_name = ?",
            (interaction.user.id, self.item_name),
            fetch='one'
        )
        
        item_data = ItemConfig.get_item_definition(self.item_name)
        item_value = item_data.get("base_value", self.price) if item_data else self.price
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + ? WHERE owner_id = ? AND item_name = ?",
                (self.quantity, interaction.user.id, self.item_name)
            )
        else:
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, value, description)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, self.item_name, self.item_type, self.quantity, item_value, self.description)
            )
        
        # Update stock if not unlimited
        if self.stock != -1:
            self.bot.db.execute_query(
                "UPDATE black_market_items SET stock = stock - ? WHERE location_id = ? AND item_name = ?",
                (self.quantity, self.location_id, self.item_name)
            )
        
        embed = discord.Embed(
            title="💀 Black Market Deal Complete",
            description=f"Successfully acquired {self.quantity}x **{self.item_name}** for {total_cost:,} credits",
            color=0x8b0000
        )
        embed.add_field(name="New Balance", value=f"{current_money - total_cost:,} credits", inline=True)
        embed.add_field(name="⚠️ Warning", value="Transaction untraceable", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)