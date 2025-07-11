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
        """Generate shop items using the new item configuration system"""
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
        
        # Add items to shop
        for item_name in items_to_add:
            item_def = ItemConfig.get_item_definition(item_name)
            if not item_def:
                continue
            
            # Calculate price and stock
            base_value = item_def["base_value"]
            price_modifier = 1.5 - (wealth_level * 0.05)  # Wealthy locations have better prices
            price = max(1, int(base_value * price_modifier))
            
            # Stock based on rarity and wealth
            rarity = item_def.get("rarity", "common")
            base_stock = {"common": 8, "uncommon": 4, "rare": 2, "legendary": 1}[rarity]
            stock_modifier = 0.5 + (wealth_level * 0.1)
            stock = max(1, int(base_stock * stock_modifier))
            
            # Create metadata
            metadata = ItemConfig.create_item_metadata(item_name)
            
            self.db.execute_query(
                '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (location_id, item_name, item_def["type"], price, stock, 
                 item_def["description"], metadata)
            )
    # Shop Commands
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
        
        embed = discord.Embed(
            title=f"🛒 Shop - {location_info[1]}",
            description="Available items for purchase",
            color=0xffd700
        )
        
        if items:
            # Group items by type
            item_types = {}
            for item_name, item_type, price, stock, description in items:
                if item_type not in item_types:
                    item_types[item_type] = []
                
                stock_text = f"({stock} in stock)" if stock != -1 else "(Unlimited)"
                item_types[item_type].append(f"**{item_name}** - {price:,} credits {stock_text}")
            
            for item_type, type_items in item_types.items():
                embed.add_field(
                    name=item_type.replace('_', ' ').title(),
                    value="\n".join(type_items[:5]),  # Limit to 5 items per type
                    inline=True
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
            name="💡 How to Buy",
            value="Use `/shop buy <item_name> [quantity]` to purchase items",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
            '''SELECT item_id, item_name, price, stock, description, item_type
               FROM shop_items 
               WHERE location_id = ? AND LOWER(item_name) LIKE LOWER(?)
               AND (stock >= ? OR stock = -1)''',
            (current_location, f"%{item_name}%", quantity),
            fetch='one'
        )
        
        if not item:
            await interaction.response.send_message(f"Item '{item_name}' not found or insufficient stock.", ephemeral=True)
            return
        
        item_id, actual_name, price, stock, description, item_type = item
        total_cost = price * quantity
        
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
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.user.id, actual_name, item_type, quantity, description, price)
            )
        
        embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"Bought {quantity}x **{actual_name}** for {total_cost:,} credits",
            color=0x00ff00
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

        
        # Calculate sell price (typically 60-80% of base value depending on location wealth)
        wealth_level = has_shops[1]
        sell_multiplier = 0.5 + (wealth_level * 0.03)  # 50% to 80% based on wealth
        sell_price = max(1, int(base_value * sell_multiplier))
        total_earnings = sell_price * quantity
        
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
        markup_price = max(sell_price + 1, int(sell_price * 1.2))

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
        embed.add_field(name="Price per Item", value=f"{sell_price:,} credits", inline=True)
        embed.add_field(name="New Balance", value=f"{current_money + total_earnings:,} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @job_group.command(name="list", description="View available jobs at current location")
    async def job_list(self, interaction: discord.Interaction):
        # 1) Defer right away to avoid "Unknown interaction"
        await interaction.response.defer(ephemeral=True)

        # 2) Fetch character location
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        if not char_location:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return

        # 3) Check for jobs at that location
        location_info = self.db.execute_query(
            "SELECT has_jobs, name, wealth_level FROM locations WHERE location_id = ?",
            (char_location[0],),
            fetch='one'
        )
        if not location_info or not location_info[0]:
            await interaction.followup.send("No jobs available at this location.", ephemeral=True)
            return

        # 4) Load the jobs
        jobs = self.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill,
                      min_skill_level, danger_level, duration_minutes
               FROM jobs
               WHERE location_id = ? AND is_taken = 0 AND expires_at > datetime('now')
               ORDER BY reward_money DESC''',
            (char_location[0],),
            fetch='all'
        )

        # 5) Build the embed
        embed = discord.Embed(
            title=f"💼 Jobs Available - {location_info[1]}",
            description="Available work opportunities",
            color=0x4169E1
        )

        if not jobs:
            embed.add_field(
                name="No Jobs Currently Available",
                value="Check back later or try other locations.",
                inline=False
            )
        else:
            for job in jobs[:8]:
                job_id, title, desc, reward, skill, min_level, danger, duration = job

                # Build human-readable skill requirement
                if skill:
                    skill_text = f"Requires **{skill.title()}** (Level {min_level})"
                else:
                    skill_text = "No special skill required"

                # Danger indicator
                danger_text = "⚠️" * danger if danger > 0 else "None"

                # Compose the job description
                job_desc = (
                    f"**#{job_id} {title}**\n"
                    f"{desc}\n\n"
                    f"💰 **{reward:,} credits** | ⏱️ {duration} min | {danger_text}\n"
                    f"{skill_text}"
                )

                embed.add_field(name="\u200b", value=job_desc, inline=False)

        embed.add_field(
            name="💡 How to Accept Jobs",
            value="Use `/job accept <job_title>` to take a job",
            inline=False
        )

        # 6) Send as a follow-up
        await interaction.followup.send(embed=embed, ephemeral=True)

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

        # Determine job type from title and description
        title_lower = title.lower()
        desc_lower = description.lower()
        is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier'])

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
            
            # Check if player is at the job's destination (the location where job was posted)
            # Check if player is at the job's destination
            if not destination_location_id or current_location != destination_location_id:
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

            # Check location-based tracking for stationary jobs
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
            base_success = max(20, 75 - (danger * 10))
            
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
                # More rewarding skill bonus: +3% per point above requirement
                skill_bonus = (player_skill_level - min_skill_level) * 3
            
            # Final success chance calculation
            success_chance = max(15, min(98, base_success + skill_bonus))
            roll = random.randint(1, 100)
            success = roll <= success_chance

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
        """Start the unloading phase for transport jobs (1-3 minutes)"""
        import random
        
        # Mark job as awaiting finalization
        self.db.execute_query(
            "UPDATE jobs SET job_status = 'awaiting_finalization' WHERE job_id = ?",
            (job_id,)
        )
        
        # Random unloading time (1-3 minutes)
        unloading_minutes = random.randint(1, 3)
        
        embed = discord.Embed(
            title="🚛 Transport Job - Cargo Unloading",
            description=f"**{title}** delivery confirmed!\n\nUnloading cargo and processing delivery paperwork...",
            color=0x00aa00
        )
        
        embed.add_field(name="✅ Delivery Status", value="Successfully delivered to destination", inline=True)
        embed.add_field(name="⏱️ Unloading Time", value=f"{unloading_minutes} minutes", inline=True)
        embed.add_field(name="💰 Pending Reward", value=f"{reward:,} credits", inline=True)
        
        embed.add_field(
            name="📋 Next Steps",
            value=f"• Cargo unloading in progress\n• Job will **auto-complete** in {unloading_minutes} minutes\n• Or use `/job complete` again to finalize immediately",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Schedule automatic completion
        import asyncio
        asyncio.create_task(self._auto_complete_transport_job(interaction.user.id, job_id, title, reward, unloading_minutes))

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
        
        # Create the response embed
        embed = discord.Embed(
            title="✅ Job Completed Successfully!",
            description=f"**{title}** has been completed!",
            color=0x00ff00
        )
        
        embed.add_field(name="✅ Success Roll", value=f"{roll}/{success_chance} - Success!", inline=True)
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
        
        embed.add_field(name="❌ Failure Roll", value=f"{roll}/{success_chance} - Failed", inline=True)
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
        
        # Create completion embed
        if success:
            embed = discord.Embed(
                title="✅ Group Job Completed Successfully!",
                description=f"**{title}** has been completed by the group!",
                color=0x00ff00
            )
            embed.add_field(name="✅ Success Roll", value=f"{roll}/{success_chance} - Success!", inline=True)
            embed.add_field(name="💰 Reward Each", value=f"{reward:,} credits", inline=True)
            embed.add_field(name="👥 Group Members", value=str(len(group_members)), inline=True)
        else:
            embed = discord.Embed(
                title="❌ Group Job Failed",
                description=f"**{title}** was not completed successfully",
                color=0xff4444
            )
            embed.add_field(name="❌ Failure Roll", value=f"{roll}/{success_chance} - Failed", inline=True)
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
        items = self.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, required_reputation
               FROM federal_supply_items 
               WHERE location_id = ? AND (stock > 0 OR stock = -1) AND ? >= required_reputation
               ORDER BY required_reputation ASC, price ASC''',
            (current_location_id, current_reputation),
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
        """Create jobs with heavy emphasis on travel between locations."""
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

        expire_time = datetime.now() + timedelta(hours=random.randint(3, 8))
        expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")

        # 4) Generate MANY travel jobs (80% of all jobs should be travel)
        num_travel_jobs = random.randint(4, 8)  # Much more travel jobs
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

        # 5) Add fewer stationary jobs (20% of jobs)
        stationary_jobs = [
            ("Local Systems Check", f"Perform routine system diagnostics at {loc_name}."),
            ("Station Maintenance", f"Carry out maintenance duties at {loc_name}."),
            ("Security Patrol", f"Patrol the perimeter of {loc_name}."),
            ("Inventory Management", f"Organize and audit supplies at {loc_name}."),
        ]
        
        num_stationary = random.randint(1, 2)  # Much fewer stationary jobs
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
        is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier'])
        
        # Create job tracking record for stationary jobs
        if not is_transport_job:
            current_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            self.db.execute_query(
                '''INSERT INTO job_tracking
                   (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
                   VALUES (?, ?, ?, ?, 0.0, datetime('now'))''',
                (job_id, interaction.user.id, current_location, duration)
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
        # Fetch active job with status - ADD job_id to the SELECT
        job_info = self.db.execute_query(
            '''SELECT j.job_id, j.title, j.description, j.reward_money, j.taken_at, j.duration_minutes,
                      j.danger_level, l.name as location_name, j.job_status
               FROM jobs j
               JOIN locations l ON j.location_id = l.location_id
               WHERE j.taken_by = ? AND j.is_taken = 1''',
            (interaction.user.id,),
            fetch='one'
        )
        if not job_info:
            await interaction.response.send_message("You don't have any active jobs.", ephemeral=True)
            return

        # UPDATE unpacking to include job_id
        job_id, title, description, reward, taken_at, duration_minutes, danger, location_name, job_status = job_info

        # Determine job type
        title_lower = title.lower()
        desc_lower = description.lower()
        is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier'])

        taken_time = datetime.fromisoformat(taken_at)
        current_time = datetime.utcnow()
        elapsed_minutes = (current_time - taken_time).total_seconds() / 60

        # TRUNCATE description to prevent Discord limit issues
        truncated_description = description[:800] + "..." if len(description) > 800 else description
        
        embed = discord.Embed(
            title="💼 Current Job Status",
            description=f"**{title}**\n{truncated_description}",
            color=0x4169E1
        )

        # Status based on job type and current state
        if job_status == 'awaiting_finalization':
            status_text = "🚛 **Unloading cargo** - Use `/job complete` to finalize immediately"
            progress_text = "✅ Transport completed, finalizing delivery..."
        elif job_status == 'completed':
            status_text = "✅ **Completed** - Job finished!"
            progress_text = "Job has been completed successfully"
        elif is_transport_job:
            if elapsed_minutes >= duration_minutes:
                status_text = "✅ **Ready for completion** - Use `/job complete`"
                progress_text = "Minimum travel time completed"
            else:
                remaining_minutes = duration_minutes - elapsed_minutes
                status_text = f"⏳ **In Transit** - {remaining_minutes:.1f} minutes remaining"
                progress_pct = (elapsed_minutes / duration_minutes) * 100
                bars = int(progress_pct // 10)
                progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
        else:
            # Stationary job - check tracking - FIX: use job_id instead of job_info
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

        # TRUNCATE field values to stay under Discord's 1024 character limit
        status_text = status_text[:1020] + "..." if len(status_text) > 1020 else status_text
        progress_text = progress_text[:1020] + "..." if len(progress_text) > 1020 else progress_text

        embed.add_field(name="Status", value=status_text, inline=False)
        embed.add_field(name="Progress", value=progress_text, inline=False)
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger if danger > 0 else "Safe", inline=True)
        embed.add_field(name="Location", value=location_name[:1020] if len(location_name) > 1020 else location_name, inline=True)

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