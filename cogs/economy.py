# cogs/economy.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from datetime import datetime, timedelta
import math
import asyncio
from utils.item_effects import ItemEffectChecker
from utils.location_effects import LocationEffectsManager
from utils.datetime_utils import safe_datetime_parse

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.job_tracking_task = None
        self.notified_jobs = set()  # Track jobs that have been notified
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
                # Start batched shop refresh task (no startup delay)
                self.batched_shop_refresh_task.start()
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
        
        # Stop batched shop refresh task
        self.batched_shop_refresh_task.cancel()
        print("🛒 Batched shop refresh task stopped")

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
                      j.title,
                      j.location_id,
                      j.destination_location_id,
                      j.description
                    FROM job_tracking jt
                    JOIN jobs j ON jt.job_id = j.job_id
                    WHERE j.is_taken = true
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
                        tracking_id, job_id, user_id, start_location, required_duration, time_at_location, last_check, job_title, job_location_id, destination_location_id, job_description = record
                        
                        # Check if user is still at the required location
                        current_location_result = self.db.execute_query(
                            "SELECT current_location FROM characters WHERE user_id = %s",
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
                                   SET time_at_location = %s, 
                                       last_location_check = NOW()
                                   WHERE tracking_id = %s''',
                                (new_time_at_location, tracking_id)
                            )
                            
                            print(f"✅ Updated job tracking for user {user_id} (job: {job_title[:30]}): +1.0min (total: {new_time_at_location:.1f}/{required_duration})")
                            updated_count += 1
                            
                            # Determine if this is a transport job
                            title_lower = job_title.lower()
                            desc_lower = job_description.lower() if job_description else ""
                            
                            if destination_location_id and destination_location_id != job_location_id:
                                # Has a different destination location = definitely a transport job
                                is_transport_job = True
                            elif destination_location_id is None:
                                # No destination set - check keywords to determine if it's a transport job (NPC-style)
                                is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                                                  any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])
                            else:
                                # destination_location_id == job_location_id = stationary job
                                is_transport_job = False
                            
                            # Check if job is ready for completion and send notification
                            # ONLY send notifications for stationary jobs - transport jobs handle notifications differently
                            if not is_transport_job and new_time_at_location >= required_duration and job_id not in self.notified_jobs:
                                await self._send_job_ready_notification(user_id, job_id, job_title, start_location)
                                self.notified_jobs.add(job_id)
                        else:
                            # User not at location, just update timestamp
                            self.db.execute_query(
                                "UPDATE job_tracking SET last_location_check = NOW() WHERE tracking_id = %s",
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

    @tasks.loop(seconds=45)  # Check every 45 seconds for batch processing
    async def batched_shop_refresh_task(self):
        """Continuously refresh shops in small batches to avoid database locks"""
        try:
            # Get shops that need refreshing (older than 2 hours or never refreshed)
            cutoff_time = datetime.now() - timedelta(hours=2)
            
            shops_to_refresh = self.db.execute_query(
                '''
                SELECT l.location_id, l.name, l.wealth_level, l.location_type,
                       sr.last_refreshed
                FROM locations l
                LEFT JOIN shop_refresh sr ON l.location_id = sr.location_id
                WHERE sr.last_refreshed IS NULL 
                   OR sr.last_refreshed < %s
                ORDER BY 
                    CASE WHEN sr.last_refreshed IS NULL THEN 0 ELSE 1 END,
                    sr.last_refreshed ASC
                LIMIT 5
                ''',
                (cutoff_time,),
                fetch='all'
            )
            
            if not shops_to_refresh:
                return  # Nothing needs refreshing right now
                
            refreshed_count = 0
            for location_id, name, wealth_level, location_type, last_refreshed in shops_to_refresh:
                try:
                    # Clear existing auto-generated shop items for this location (preserve player-sold items)
                    self.db.execute_query(
                        'DELETE FROM shop_items WHERE location_id = %s AND sold_by_player = FALSE',
                        (location_id,)
                    )
                    
                    # Generate new shop items with wealth-based quantity
                    await self._generate_shop_items(location_id, wealth_level, location_type)
                    
                    # Update refresh tracking
                    self.db.execute_query(
                        '''INSERT INTO shop_refresh (location_id, last_refreshed) 
                           VALUES (%s, CURRENT_TIMESTAMP)
                           ON CONFLICT (location_id) DO UPDATE SET last_refreshed = EXCLUDED.last_refreshed''',
                        (location_id,)
                    )
                    
                    refreshed_count += 1
                    
                    # Small delay between shops to reduce database pressure
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    print(f"❌ Error refreshing shop for {name}: {e}")
                    # Continue with other shops even if one fails
            
            if refreshed_count > 0:
                print(f"🛒 Refreshed {refreshed_count} shop inventories (batch)")
            
        except Exception as e:
            print(f"❌ Error in batched shop refresh: {e}")

    @batched_shop_refresh_task.before_loop
    async def before_batched_shop_refresh(self):
        await self.bot.wait_until_ready()
        # Add initial delay to avoid startup contention
        print("🛒 Starting batched shop refresh system...")
        await asyncio.sleep(30)  # Wait 30 seconds after bot is ready

    async def check_location_access_fee(self, user_id: int, location_id: int) -> tuple:
        """Check if user needs to pay a fee to access this location"""
        # Check if location is owned and has access controls
        ownership = self.db.execute_query(
            '''SELECT lo.owner_id, lo.group_id
               FROM location_ownership lo
               WHERE lo.location_id = %s''',
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
                "SELECT group_id FROM characters WHERE user_id = %s",
                (user_id,),
                fetch='one'
            )
            if user_group and user_group[0] == owner_group_id:
                return True, 0
        
        # Check access control settings
        access_control = self.db.execute_query(
            '''SELECT access_type, fee_amount FROM location_access_control
               WHERE location_id = %s AND (user_id = %s OR user_id IS NULL)
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
        # Wealth affects both spawn chances and total item variety
        wealth_multiplier = wealth_level / 5.0  # Normalize to 0.2-2.0 range for wealth 1-10
        
        for rarity in ["common", "uncommon", "rare", "legendary"]:
            rarity_items = ItemConfig.get_items_by_rarity(rarity, exclude_exclusive=True)
            
            # Adjust spawn chance by rarity and wealth - more significant wealth impact
            spawn_chances = {
                "common": 0.4 + (wealth_level * 0.04),
                "uncommon": 0.2 + (wealth_level * 0.05), 
                "rare": 0.05 + (wealth_level * 0.03),
                "legendary": 0.01 + (wealth_level * 0.015)
            }
            
            spawn_chance = spawn_chances.get(rarity, 0.1)
            
            # Limit items per rarity based on wealth to prevent over-stocking
            items_added_this_rarity = 0
            max_items_per_rarity = {
                "common": max(2, int(4 * wealth_multiplier)),
                "uncommon": max(1, int(3 * wealth_multiplier)),
                "rare": max(1, int(2 * wealth_multiplier)),
                "legendary": max(0, int(1 * wealth_multiplier))
            }
            
            for item_name in rarity_items:
                if item_name in items_to_add:
                    continue  # Already added
                
                if items_added_this_rarity >= max_items_per_rarity[rarity]:
                    break  # Hit limit for this rarity
                
                item_def = ItemConfig.get_item_definition(item_name)
                item_type = item_def.get("type")
                
                # Apply location modifier
                type_modifier = location_modifiers.get(item_type, 1.0)
                final_chance = spawn_chance * type_modifier
                
                if random.random() < final_chance:
                    items_to_add.append(item_name)
                    items_added_this_rarity += 1
        
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
                '''INSERT INTO shop_items (location_id, item_name, item_type, price, stock, description, metadata, sold_by_player)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (location_id, item_name, item_def["type"], final_price, final_stock, 
                 item_def["description"], metadata, False)
            )

    @shop_group.command(name="list", description="View items available for purchase")
    async def shop_list(self, interaction: discord.Interaction):
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        # Check if location has shops
        location_info = self.db.execute_query(
            "SELECT has_shops, name, wealth_level, location_type FROM locations WHERE location_id = %s",
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
               WHERE location_id = %s AND (stock > 0 OR stock = -1)
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
                   WHERE location_id = %s AND (stock > 0 OR stock = -1)
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
        
        # Add active location effects
        effects_manager = LocationEffectsManager(self.db)
        active_effects = effects_manager.get_active_effect_descriptions(char_location[0])
        economic_modifiers = effects_manager.get_economic_modifiers(char_location[0])
        
        if active_effects:
            embed.add_field(
                name="⚡ Active Location Effects",
                value="\n".join(active_effects),
                inline=False
            )
        
        # Show economic impact
        price_modifier = economic_modifiers.get('price_modifier', 1.0)
        if price_modifier != 1.0:
            if price_modifier > 1.0:
                embed.add_field(
                    name="💸 Economic Impact",
                    value=f"Prices increased by {((price_modifier - 1) * 100):.0f}% due to local conditions",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💰 Economic Impact",
                    value=f"Prices reduced by {((1 - price_modifier) * 100):.0f}% due to local conditions",
                    inline=False
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
                   WHERE location_id = %s AND expires_at > NOW()''',
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
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in first!", ephemeral=True)
            return
        
        current_location_id = char_info[0]

        # Check if the location has federal supplies
        location_info = self.db.execute_query(
            "SELECT has_federal_supplies, name FROM locations WHERE location_id = %s",
            (current_location_id,),
            fetch='one'
        )

        if not location_info or not location_info[0]:
            await interaction.response.send_message("No Federal Supply Depot available at this location.", ephemeral=True)
            return

        # Get the character's reputation at this location
        reputation_data = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = %s AND location_id = %s",
            (interaction.user.id, current_location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0

        # Get federal supply items
        items = self.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, clearance_level
               FROM federal_supply_items 
               WHERE location_id = %s AND (stock > 0 OR stock = -1) AND %s >= clearance_level
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
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in first!", ephemeral=True)
            return
        
        current_location_id = char_info[0]

        # Check if the location has black market
        location_info = self.db.execute_query(
            "SELECT has_black_market, name FROM locations WHERE location_id = %s",
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
               WHERE bm.location_id = %s AND (bmi.stock > 0 OR bmi.stock = -1)
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
            "SELECT current_location, money FROM characters WHERE user_id = %s",
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
               WHERE location_id = %s AND LOWER(item_name) = LOWER(%s)''',
            (current_location, item_name),
            fetch='one'
        )
        
        if not item:
            await interaction.response.send_message(f"Item '{item_name}' not found or insufficient stock.", ephemeral=True)
            return
        
        item_id, actual_name, price, stock, description, item_type, metadata = item
        
        # Apply location effects to pricing
        effects_manager = LocationEffectsManager(self.db)
        economic_modifiers = effects_manager.get_economic_modifiers(current_location)
        
        # Apply price modifier from location effects
        price_modifier = economic_modifiers.get('price_modifier', 1.0)
        modified_price = max(1, int(price * price_modifier))
        
        total_cost = modified_price * quantity
        
        # Ensure metadata exists using helper function
        from utils.item_config import ItemConfig
        metadata = ItemConfig.ensure_item_metadata(actual_name, metadata)
        tax_data = self.db.execute_query(
            '''SELECT fst.tax_percentage, f.faction_id, f.name
               FROM faction_sales_tax fst
               JOIN factions f ON fst.faction_id = f.faction_id
               WHERE fst.location_id = %s''',
            (current_location,),
            fetch='one'
        )

        final_price = total_cost
        tax_amount = 0
        if tax_data and tax_data[0] > 0:
            tax_amount = int(total_cost * tax_data[0] / 100)
            final_price = total_cost + tax_amount

        # When processing purchase (after deducting money), ADD:
        if tax_amount > 0:
            self.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance + %s WHERE faction_id = %s",
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
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (total_cost, interaction.user.id)
        )
        
        # Update shop stock
        if stock != -1:  # Not unlimited
            self.db.execute_query(
                "UPDATE shop_items SET stock = stock - %s WHERE item_id = %s",
                (quantity, item_id)
            )
        
        # Add to inventory
        existing_item = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (interaction.user.id, actual_name),
            fetch='one'
        )
        
        if existing_item:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                (quantity, existing_item[0])
            )
        else:
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                (interaction.user.id, actual_name, item_type, quantity, description, price, metadata)
            )
        embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"Bought {quantity}x **{actual_name}** for {total_cost:,} credits",
            color=0x00ff00
        )
        
        # Show price effects if any
        if price_modifier != 1.0:
            base_cost = price * quantity
            savings_or_extra = total_cost - base_cost
            if savings_or_extra > 0:
                embed.add_field(
                    name="💸 Location Effect",
                    value=f"Prices increased by {((price_modifier - 1) * 100):.0f}% (+{savings_or_extra:,} credits)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💰 Location Effect", 
                    value=f"Prices reduced by {((1 - price_modifier) * 100):.0f}% ({savings_or_extra:,} credits)",
                    inline=False
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
            "SELECT current_location, money FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Check if location has shops
        has_shops = self.db.execute_query(
            "SELECT has_shops, wealth_level FROM locations WHERE location_id = %s",
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
               WHERE owner_id = %s AND LOWER(item_name) LIKE LOWER(%s) AND quantity >= %s''',
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
        
        # Apply location effects to selling price
        effects_manager = LocationEffectsManager(self.db)
        economic_modifiers = effects_manager.get_economic_modifiers(current_location)
        
        # For selling, we use the inverse of price_modifier (if buying is more expensive, selling should be too)
        price_modifier = economic_modifiers.get('price_modifier', 1.0)
        location_adjusted_sell_price = max(1, int(final_sell_price * price_modifier))

        total_earnings = location_adjusted_sell_price * quantity
        seller_faction = self.db.execute_query(
            '''SELECT fm.faction_id, f.name, f.emoji,
                      CASE WHEN lo.faction_id = fm.faction_id THEN 1 ELSE 0 END as is_faction_location
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               LEFT JOIN location_ownership lo ON lo.location_id = %s
               WHERE fm.user_id = %s''',
            (current_location, interaction.user.id),
            fetch='one'
        )

        if seller_faction and not seller_faction[3]:  # Not in faction territory
            # 3% bonus to faction bank for external trade
            trade_bonus = int(total_earnings * 0.03)
            self.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance + %s WHERE faction_id = %s",
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
        
        # Check if item is equipped and unequip it before selling
        equipped_check = self.db.execute_query(
            "SELECT equipment_id FROM character_equipment WHERE item_id = %s AND user_id = %s",
            (inv_id, interaction.user.id),
            fetch='all'
        )
        
        if equipped_check:
            # Item is equipped, remove from equipment slots
            self.db.execute_query(
                "DELETE FROM character_equipment WHERE item_id = %s AND user_id = %s",
                (inv_id, interaction.user.id)
            )
        
        # Update inventory
        if current_qty == quantity:
            # Remove item completely
            self.db.execute_query(
                "DELETE FROM inventory WHERE item_id = %s",
                (inv_id,)
            )
        else:
            # Reduce quantity
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                (quantity, inv_id)
            )
        
        # Add money to character
        self.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (total_earnings, interaction.user.id)
        )
                # ─── Put sold items into the shop at a 20% markup ───
        # Calculate the shop purchase price (e.g. 120% of the sell price, at least +1)
        markup_price = max(final_sell_price + 1, int(final_sell_price * 1.2))

        # Check if this item already exists in the local shop
        existing = self.db.execute_query(
            "SELECT item_id, stock, price FROM shop_items WHERE location_id = %s AND LOWER(item_name) = LOWER(%s)",
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
                "UPDATE shop_items SET stock = %s, price = %s WHERE item_id = %s",
                (new_stock, new_price, shop_id)
            )
        else:
            # fresh entry in the shop
            from utils.item_config import ItemConfig
            metadata = ItemConfig.create_item_metadata(actual_name)
            self.db.execute_query(
                '''INSERT INTO shop_items
                   (location_id, item_name, item_type, price, stock, description, metadata, sold_by_player)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (current_location, actual_name, item_type, markup_price, quantity, description, metadata, True)
            )
        embed = discord.Embed(
            title="💰 Item Sold",
            description=f"Sold {quantity}x **{actual_name}** for {total_earnings:,} credits",
            color=0x00ff00
        )

        embed.add_field(name="Price per Item", value=f"{location_adjusted_sell_price:,} credits", inline=True)
        
        # Show location effects if any
        if price_modifier != 1.0:
            base_earnings = final_sell_price * quantity
            earnings_difference = total_earnings - base_earnings
            if earnings_difference > 0:
                embed.add_field(
                    name="💰 Location Effect",
                    value=f"Sell prices increased by {((price_modifier - 1) * 100):.0f}% (+{earnings_difference:,} credits)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💸 Location Effect",
                    value=f"Sell prices reduced by {((1 - price_modifier) * 100):.0f}% ({earnings_difference:,} credits)",
                    inline=False
                )
        embed.add_field(name="New Balance", value=f"{current_money + total_earnings:,} credits", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @shop_group.command(name="refresh_stock", description="Admin: Refresh shop stock at current location")
    async def refresh_shop_stock(self, interaction: discord.Interaction):
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        # Get admin's current location
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[0]:
            await interaction.response.send_message("❌ You must be at a location to refresh shop stock.", ephemeral=True)
            return
        
        location_id = char_info[0]
        
        # Get location info
        location_data = self.db.execute_query(
            "SELECT name, wealth_level, location_type FROM locations WHERE location_id = %s",
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            await interaction.response.send_message("❌ Invalid location.", ephemeral=True)
            return
        
        location_name, wealth_level, location_type = location_data
        
        await interaction.response.defer(ephemeral=True)
        
        # Clear existing auto-generated shop items (preserve player-sold and admin-created items)
        # We preserve items that are either sold by players OR created by admins
        # Admin-created items will have metadata containing "admin_created": true
        admin_created_items = self.db.execute_query(
            '''SELECT item_id FROM shop_items 
               WHERE location_id = %s AND metadata LIKE '%"admin_created": true%' ''',
            (location_id,),
            fetch='all'
        )
        
        admin_item_ids = [str(item[0]) for item in admin_created_items] if admin_created_items else []
        
        if admin_item_ids:
            placeholders = ', '.join(['%s' for _ in admin_item_ids])
            self.db.execute_query(
                f'''DELETE FROM shop_items 
                   WHERE location_id = %s 
                   AND sold_by_player = FALSE 
                   AND item_id NOT IN ({placeholders})''',
                [location_id] + admin_item_ids
            )
        else:
            self.db.execute_query(
                '''DELETE FROM shop_items 
                   WHERE location_id = %s 
                   AND sold_by_player = FALSE''',
                (location_id,)
            )
        
        # Generate new shop items
        await self._generate_shop_items(location_id, wealth_level, location_type)
        
        # Update refresh tracking
        self.db.execute_query(
            '''INSERT INTO shop_refresh (location_id, last_refreshed) 
               VALUES (%s, CURRENT_TIMESTAMP)
               ON CONFLICT (location_id) DO UPDATE SET last_refreshed = EXCLUDED.last_refreshed''',
            (location_id,)
        )
        
        # Get sample of generated items
        new_items = self.db.execute_query(
            '''SELECT item_name, item_type, price, stock FROM shop_items 
               WHERE location_id = %s AND sold_by_player = FALSE 
               ORDER BY price DESC LIMIT 5''',
            (location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🔄 Shop Stock Refreshed",
            description=f"Successfully refreshed shop stock at **{location_name}**",
            color=0x00ff00
        )
        
        if new_items:
            item_list = []
            for item_name, item_type, price, stock in new_items:
                stock_text = f"{stock}" if stock != -1 else "∞"
                item_list.append(f"• {item_name} ({item_type}) - {price:,}c (Stock: {stock_text})")
            
            embed.add_field(
                name="📦 Sample Items Generated",
                value="\n".join(item_list),
                inline=False
            )
        
        embed.add_field(
            name="📍 Location Info",
            value=f"Type: {location_type.replace('_', ' ').title()}\nWealth Level: {wealth_level}/10",
            inline=True
        )
        
        total_items = self.db.execute_query(
            "SELECT COUNT(*) FROM shop_items WHERE location_id = %s AND sold_by_player = FALSE",
            (location_id,),
            fetch='one'
        )[0]
        
        embed.add_field(
            name="📊 Results",
            value=f"Generated: {total_items} items\nPlayer-sold items preserved",
            inline=True
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    def get_shift_job_multiplier(self) -> float:
        """Get job generation multiplier based on current shift"""
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        shift_name, shift_period = time_system.get_current_shift()
        
        # Job generation multipliers by shift (slightly increased)
        shift_multipliers = {
            "morning": 1.5,   # Increased from 0.8
            "day": 2.0,       # Increased from 1.5
            "evening": 1.3,   # Increased from 0.9
            "night": 0.9      # Increased from 0.4
        }
        
        return shift_multipliers.get(shift_period, 1.0)
        
    @job_group.command(name="list", description="View available jobs at current location")
    async def job_list(self, interaction: discord.Interaction):
        # Defer right away to avoid "Unknown interaction"
        await interaction.response.defer(ephemeral=True)

        # Fetch character location
        char_location = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        if not char_location:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return

        # Check for jobs at that location
        location_info = self.db.execute_query(
            "SELECT has_jobs, name, wealth_level FROM locations WHERE location_id = %s",
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
               WHERE location_id = %s AND is_taken = false AND expires_at > NOW()
               ORDER BY reward_money DESC''',
            (char_location[0],),
            fetch='all'
        )
        
        # Get available quests from the quest system
        quest_cog = self.bot.get_cog('QuestsCog')
        quests = []
        if quest_cog:
            quest_data = quest_cog.get_available_quests(char_location[0])
            # Convert quest data to job format for display compatibility
            for quest in quest_data:
                quest_as_job = (
                    quest['quest_id'],
                    quest['title'],  # Already has "QUEST: " prefix
                    quest['description'],
                    quest['reward_money'],
                    None,  # required_skill
                    quest['required_level'],  # min_skill_level
                    quest['danger_level'],
                    quest.get('estimated_duration', 'Unknown')  # duration
                )
                quests.append(quest_as_job)
        
        # Combine jobs and quests
        all_jobs = list(jobs) + quests

        # Build the embed
        embed = discord.Embed(
            title=f"💼 Jobs Available - {location_info[1]}",
            description="Interactive job selection interface",
            color=0x4169E1
        )

        if not all_jobs:
            embed.add_field(
                name="No Jobs Currently Available",
                value="Check back later or try other locations.",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create interactive job view
        view = InteractiveJobListView(self.bot, interaction.user.id, all_jobs, location_info[1])
        
        # Show summary of available jobs
        job_summary = []
        total_reward = 0
        danger_counts = {'safe': 0, 'low': 0, 'medium': 0, 'high': 0}
        quest_count = len(quests)
        
        for job in all_jobs:
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
        
        summary_text = f"**{len(jobs)}** regular jobs available"
        if quest_count > 0:
            summary_text += f"\n**{quest_count}** quests available"
        summary_text += f"\n**Total Rewards**: {total_reward:,} credits"
        if len(all_jobs) > 0:
            summary_text += f"\n**Average**: {total_reward//len(all_jobs):,} credits per job"
        
        embed.add_field(
            name="📊 Job Summary",
            value=summary_text,
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
               WHERE j.taken_by = %s AND j.is_taken = true''',
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

        # Get player's current location and docking status
        player_info = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not player_info or not player_info[0]:
            await interaction.response.send_message(
                "You cannot complete jobs while in transit!",
                ephemeral=True
            )
            return
        
        current_location, location_status = player_info

        # Check if player is docked
        if location_status != 'docked':
            await interaction.response.send_message(
                "You must be docked at a location to complete jobs. Use `/tqe` to dock first.",
                ephemeral=True
            )
            return

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
                taken_time = safe_datetime_parse(taken_at)
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
                        "SELECT name FROM locations WHERE location_id = %s",
                        (destination_location_id,),
                        fetch='one'
                    )
                    if dest_name_result:
                        correct_dest_name = dest_name_result[0]
                
                # Get player's current location name for a more accurate error message
                current_location_name_result = self.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = %s",
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
            taken_time = safe_datetime_parse(taken_at)
            now = datetime.now()
            elapsed_minutes = (now - taken_time).total_seconds() / 60

            # Check location-based tracking for stationary jobs only
            tracking = self.db.execute_query(
                "SELECT time_at_location, required_duration FROM job_tracking WHERE job_id = %s AND user_id = %s",
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
                "SELECT engineering, navigation, combat, medical FROM characters WHERE user_id = %s",
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
                "SELECT group_id FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )

            if group_id and group_id[0]:
                # Check if the job was taken by the group
                job_taken_by_group = self.db.execute_query(
                    "SELECT 1 FROM jobs WHERE job_id = %s AND taken_by = %s",
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
               WHERE location_id = %s AND item_name = %s AND expires_at > NOW()''',
            (location_id, item_name),
            fetch='one'
        )
        
        if specific_modifier:
            return specific_modifier
        
        # Check for category demand/surplus
        category_modifier = self.db.execute_query(
            '''SELECT status, price_modifier, stock_modifier FROM location_economy 
               WHERE location_id = %s AND item_category = %s AND expires_at > NOW()''',
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
            "SELECT job_status FROM jobs WHERE job_id = %s AND taken_by = %s",
            (job_id, user_id),
            fetch='one'
        )
        
        if job_check and job_check[0] == 'awaiting_finalization':
            # Complete the job automatically - TRANSPORT JOBS ALWAYS SUCCEED
            self.db.execute_query(
                "UPDATE characters SET money = money + %s WHERE user_id = %s",
                (reward, user_id)
            )
            
            # Add experience for transport jobs
            exp_gain = random.randint(20, 40)
            self.db.execute_query(
                "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                (exp_gain, user_id)
            )
            
            # Clean up job
            self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
            self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s", (job_id, user_id))
            self.notified_jobs.discard(job_id)  # Clean up notification tracking
            
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
                    
                    # Get the current location and send via cross-guild broadcast
                    # Assuming the user is at the destination location when this auto-completes
                    current_location_id = self.db.execute_query(
                        "SELECT current_location FROM characters WHERE user_id = %s", (user_id,), fetch='one'
                    )[0]
                    
                    # Use cross-guild broadcasting for transport job completion
                    from utils.channel_manager import ChannelManager
                    channel_manager = ChannelManager(self.bot)
                    cross_guild_channels = await channel_manager.get_cross_guild_location_channels(current_location_id)
                    
                    if cross_guild_channels:
                        for guild_channel, channel in cross_guild_channels:
                            try:
                                await channel.send(embed=embed) # Public message in location channel
                            except:
                                pass  # Skip if can't send to this guild
                    else:
                        await user.send(embed=embed) # Fallback to DM if no channels
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
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (reward, interaction.user.id)
        )
        
        # Add experience for transport jobs
        exp_gain = random.randint(20, 40)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
            (exp_gain, interaction.user.id)
        )
        
        # Clean up
        self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s", (job_id, interaction.user.id))
        self.notified_jobs.discard(job_id)  # Clean up notification tracking
        
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
            "UPDATE jobs SET job_status = 'awaiting_finalization', unloading_started_at = %s WHERE job_id = %s",
            (current_time, job_id)
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
            value="• Wait for automatic completion in 2 minutes\n• Check progress with the 'Job Status' button\n• Use `the 'Complete Job' button to skip waiting (costs 10% of reward)",
            inline=False
        )
        
        # Send initial message and store it for updates
        message = await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=60)
        
        # Schedule automatic completion
        import asyncio
        asyncio.create_task(self._auto_complete_transport_job_with_updates(
            interaction.user.id, job_id, title, reward, interaction.channel_id
        ))
        
    async def _auto_complete_transport_job_with_updates(self, user_id: int, job_id: int, title: str, reward: int, channel_id: int):
        """Auto-complete transport job after 2 minutes with progress updates"""
        await asyncio.sleep(10)  # Wait 10 seconds before first update
        
        channel = self.bot.get_channel(channel_id)
        user = self.bot.get_user(user_id)
        progress_message = None
        
        # Progress update loop (every 30 seconds)
        for i in range(3):  # Updates at 10s, 40s, 70s
            # Check if job still exists and is awaiting finalization
            job_check = self.db.execute_query(
                "SELECT job_status, unloading_started_at FROM jobs WHERE job_id = %s AND taken_by = %s",
                (job_id, user_id),
                fetch='one'
            )
            
            if not job_check or job_check[0] != 'awaiting_finalization':
                return  # Job was completed manually or deleted
            
            # Calculate progress
            unloading_start = safe_datetime_parse(job_check[1])
            elapsed = (datetime.now() - unloading_start).total_seconds()
            progress_pct = min(100, (elapsed / 120) * 100)
            
            # Send or edit progress update in channel
            if channel:
                bars = int(progress_pct // 10)
                progress_bar = "🟩" * bars + "⬜" * (10 - bars)
                
                progress_text = f"{user.mention} - Unloading progress: {progress_bar} {progress_pct:.0f}%"
                
                if progress_message is None:
                    # Send initial message
                    progress_message = await channel.send(progress_text)
                else:
                    # Edit existing message
                    await progress_message.edit(content=progress_text)
            
            if i < 2:  # Don't sleep after last update
                await asyncio.sleep(30)
        
        # Wait for remaining time (total 2 minutes)
        await asyncio.sleep(50)  # 120 - 70 = 50 seconds
        
        # Edit final 100% progress message
        if channel and progress_message:
            progress_bar = "🟩" * 10  # Full green bar
            final_text = f"{user.mention} - Unloading progress: {progress_bar} 100% - **COMPLETED!**"
            await progress_message.edit(content=final_text, delete_after=150)
        
        # Final completion (same as before)
        job_check = self.db.execute_query(
            "SELECT job_status FROM jobs WHERE job_id = %s AND taken_by = %s",
            (job_id, user_id),
            fetch='one'
        )
        
        if job_check and job_check[0] == 'awaiting_finalization':
            # Complete the job
            self.db.execute_query(
                "UPDATE characters SET money = money + %s WHERE user_id = %s",
                (reward, user_id)
            )
            
            exp_gain = random.randint(20, 40)
            self.db.execute_query(
                "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                (exp_gain, user_id)
            )
            
            # Clean up job
            self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
            self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s", (job_id, user_id))
            self.notified_jobs.discard(job_id)  # Clean up notification tracking
            
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
                
                await self.bot.send_with_cross_guild_broadcast(channel, f"{user.mention}", embed=embed)
                
    async def _finalize_transport_job(self, interaction: discord.Interaction, job_id: int, title: str, reward: int):
        """Finalize a transport job that's in the unloading phase"""
        
        # Check how long they've been unloading
        unloading_info = self.db.execute_query(
            "SELECT unloading_started_at FROM jobs WHERE job_id = %s",
            (job_id,),
            fetch='one'
        )
        
        penalty = 0
        if unloading_info and unloading_info[0]:
            unloading_start = safe_datetime_parse(unloading_info[0])
            elapsed = (datetime.now() - unloading_start).total_seconds()
            
            if elapsed < 120:  # Less than 2 minutes
                # Apply 10% penalty for rushing
                penalty = int(reward * 0.1)
                reward = reward - penalty
        
        # Give reward
        self.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (reward, interaction.user.id)
        )
        
        exp_gain = random.randint(20, 40)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
            (exp_gain, interaction.user.id)
        )
        
        # Clean up
        self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s", (job_id, interaction.user.id))
        self.notified_jobs.discard(job_id)  # Clean up notification tracking
        
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

    async def _send_job_ready_notification(self, user_id: int, job_id: int, job_title: str, location_id: int):
        """Send notification when a stationary job is ready for completion"""
        try:
            # Get location channel info
            location_info = self.db.execute_query(
                "SELECT name, channel_id FROM locations WHERE location_id = %s",
                (location_id,),
                fetch='one'
            )
            
            if not location_info:
                print(f"❌ Could not find location info for location_id {location_id}")
                return
                
            location_name, channel_id = location_info
            
            if not channel_id:
                print(f"❌ No channel_id set for location {location_name}")
                return
                
            # Get the channel and user
            channel = self.bot.get_channel(channel_id)
            user = self.bot.get_user(user_id)
            
            if not channel:
                print(f"❌ Could not find channel {channel_id} for location {location_name}")
                return
                
            if not user:
                print(f"❌ Could not find user {user_id}")
                return
            
            # Send notification message
            embed = discord.Embed(
                title="✅ Job Ready for Completion!",
                description=f"**{job_title}** is now ready to complete!",
                color=0x00ff00
            )
            embed.add_field(name="📍 Location", value=location_name, inline=True)
            
            await self.bot.send_with_cross_guild_broadcast(channel, f"{user.mention}, your job is ready for completion!", embed=embed, delete_after=60)
            print(f"✅ Sent job completion notification for job {job_id} to {user.name} in {location_name}")
            
        except Exception as e:
            print(f"❌ Error sending job ready notification: {e}")
                
    async def _complete_job_immediately(self, interaction: discord.Interaction, job_id: int, title: str, reward: int, roll: int, success_chance: int, job_type: str):
        """Complete a job immediately with full reward, experience, skill, and karma effects."""
        # Give full reward
        self.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (reward, interaction.user.id)
        )
        
        # Experience gain
        exp_gain = random.randint(25, 50)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
            (exp_gain, interaction.user.id)
        )
        faction_data = self.db.execute_query(
            '''SELECT f.faction_id, f.name, f.emoji
               FROM faction_members fm
               JOIN factions f ON fm.faction_id = f.faction_id
               WHERE fm.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )

        if faction_data:
            # 5% bonus goes to faction bank
            faction_bonus = int(reward * 0.05)
            self.db.execute_query(
                "UPDATE factions SET bank_balance = bank_balance + %s WHERE faction_id = %s",
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
                f"UPDATE characters SET {skill_to_improve} = {skill_to_improve} + 1 WHERE user_id = %s",
                (interaction.user.id,)
            )
            embed.add_field(name="🎯 Skill Bonus", value=f"**{skill_to_improve.title()}** skill increased by 1!", inline=True)

        # Handle karma/reputation change
        job_details = self.db.execute_query(
            "SELECT karma_change, location_id FROM jobs WHERE job_id = %s",
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
        self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s", (job_id, interaction.user.id))
        
        # Check for level up
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.level_up_check(interaction.user.id)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


    async def _complete_job_failed(self, interaction: discord.Interaction, job_id: int, title: str, reward: int, roll: int, success_chance: int):
        """Complete a failed job with partial reward"""
        partial = reward // 3
        self.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (partial, interaction.user.id)
        )
        
        # Small experience consolation
        exp_gain = random.randint(5, 15)
        self.db.execute_query(
            "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
            (exp_gain, interaction.user.id)
        )
        
        # Clean up
        self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s", (job_id, interaction.user.id))
        self.notified_jobs.discard(job_id)  # Clean up notification tracking
        
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
            "SELECT group_id FROM characters WHERE user_id = %s",
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
               WHERE c.group_id = %s''',
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
                    "UPDATE characters SET money = money + %s WHERE user_id = %s",
                    (reward, member_id)
                )
                
                # Experience gain
                exp_gain = random.randint(25, 50)
                self.db.execute_query(
                    "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                    (exp_gain, member_id)
                )
                
                # 15% chance for skill improvement per member
                if random.random() < 0.15:
                    skill = random.choice(['engineering', 'navigation', 'combat', 'medical'])
                    self.db.execute_query(
                        f"UPDATE characters SET {skill} = {skill} + 1 WHERE user_id = %s",
                        (member_id,)
                    )
                    
                    # Don't notify via DM - we'll announce in location channel instead
            else:
                # Partial reward for failure (same for all members)
                partial = reward // 3
                self.db.execute_query(
                    "UPDATE characters SET money = money + %s WHERE user_id = %s",
                    (partial, member_id)
                )
                
                # Small experience consolation
                exp_gain = random.randint(5, 15)
                self.db.execute_query(
                    "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                    (exp_gain, member_id)
                )
            
            # Check for level up for each member
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.level_up_check(member_id)
        
        # Clean up job - ONLY ONCE (this was already correct)
        self.db.execute_query("DELETE FROM jobs WHERE job_id = %s", (job_id,))
        self.db.execute_query("DELETE FROM job_tracking WHERE job_id = %s", (job_id,))
        self.notified_jobs.discard(job_id)  # Clean up notification tracking
        
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
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location_id = char_info[0]

        # Check if the location has a Federal Supply
        location_info = self.db.execute_query(
            "SELECT has_federal_supply, name, faction FROM locations WHERE location_id = %s",
            (current_location_id,),
            fetch='one'
        )

        if not location_info or not location_info[0]:
            await interaction.response.send_message("No Federal Supply depot available at this location.", ephemeral=True)
            return

        # Get the character's reputation at this specific location
        reputation_data = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = %s AND location_id = %s",
            (interaction.user.id, current_location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0

        # Fetch items from Federal Supply, checking reputation
        items = self.bot.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, clearance_level
               FROM federal_supply_items 
               WHERE location_id = %s AND (stock > 0 OR stock = -1) AND %s >= clearance_level
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

    async def _find_multi_jump_destinations(self, origin_id: int, max_jumps: int = 3):
        """Find reachable destinations within max_jumps from origin"""
        visited = set()
        routes = []  # (destination_id, destination_name, jump_count, dest_wealth, dest_type)
        queue = [(origin_id, 0)]
        
        while queue:
            current_loc, jumps = queue.pop(0)
            
            if current_loc in visited or jumps >= max_jumps:
                continue
                
            visited.add(current_loc)
            
            # Get all connections from current location
            connections = self.db.execute_query(
                '''SELECT c.destination_location, l.name, l.location_type, l.wealth_level, l.x_coordinate, l.y_coordinate
                   FROM corridors c
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = %s AND c.is_active = true''',
                (current_loc,),
                fetch='all'
            )
            
            for dest_id, dest_name, dest_type, dest_wealth, x1, y1 in connections:
                if dest_id not in visited:
                    if jumps + 1 > 0:  # Don't include origin
                        routes.append((dest_id, dest_name, jumps + 1, dest_wealth, dest_type, x1, y1))
                    
                    if jumps + 1 < max_jumps:
                        queue.append((dest_id, jumps + 1))
        
        return routes

    async def _generate_jobs_for_location(self, location_id: int):
        """Create jobs with heavy emphasis on travel between locations and shift-aware generation."""
        # 1) Remove all untaken jobs here
        self.db.execute_query(
            "DELETE FROM jobs WHERE location_id = %s AND is_taken = false",
            (location_id,)
        )

        # 2) Get this location's info
        row = self.db.execute_query(
            "SELECT name, x_coordinate, y_coordinate, wealth_level, location_type FROM locations WHERE location_id = %s",
            (location_id,),
            fetch='one'
        )
        if not row:
            return
        loc_name, x0, y0, wealth, loc_type = row

        # 3) Find all available destinations (direct and multi-jump)
        direct_destinations = self.db.execute_query(
            """SELECT DISTINCT l.location_id, l.name, l.x_coordinate, l.y_coordinate, l.location_type, l.wealth_level
               FROM corridors c 
               JOIN locations l ON c.destination_location = l.location_id
               WHERE c.origin_location = %s AND c.is_active = true""",
            (location_id,),
            fetch='all'
        )
        
        # Get multi-jump destinations
        multi_jump_destinations = await self._find_multi_jump_destinations(location_id, max_jumps=4)
        
        if not direct_destinations and not multi_jump_destinations:
            return

        # Get shift multiplier for job generation
        shift_multiplier = self.get_shift_job_multiplier()
        
        expire_time = datetime.now() + timedelta(hours=random.randint(3, 8))

        # 4) Generate travel jobs with shift-aware counts
        base_travel_jobs = random.randint(8, 14)
        num_travel_jobs = max(2, int(base_travel_jobs * shift_multiplier))  # Apply shift multiplier
        
        print(f"🕐 Generating {num_travel_jobs} travel jobs (shift multiplier: {shift_multiplier:.1f})")
        
        for _ in range(num_travel_jobs):
            # Select destination based on jump probability: 60% single, 30% double, 10% triple+
            jump_type = random.random()
            jumps = 1
            
            if jump_type < 0.6 and direct_destinations:
                # 60% chance for single jump (direct)
                dest_id, dest_name, x1, y1, dest_type, dest_wealth = random.choice(direct_destinations)
                jumps = 1
            elif jump_type < 0.9 and multi_jump_destinations:
                # 30% chance for double jump
                multi_jump_2 = [d for d in multi_jump_destinations if d[2] == 2]
                if multi_jump_2:
                    dest_id, dest_name, jumps, dest_wealth, dest_type, x1, y1 = random.choice(multi_jump_2)
                else:
                    # Fallback to direct if no 2-jump destinations
                    dest_id, dest_name, x1, y1, dest_type, dest_wealth = random.choice(direct_destinations)
                    jumps = 1
            else:
                # 10% chance for triple+ jump
                multi_jump_3plus = [d for d in multi_jump_destinations if d[2] >= 3]
                if multi_jump_3plus:
                    dest_id, dest_name, jumps, dest_wealth, dest_type, x1, y1 = random.choice(multi_jump_3plus)
                else:
                    # Fallback to direct if no 3+ jump destinations
                    dest_id, dest_name, x1, y1, dest_type, dest_wealth = random.choice(direct_destinations)
                    jumps = 1
            
            # Calculate distance-based rewards (travel jobs pay well!)
            dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            base_reward = max(100, int(dist * random.uniform(8, 15)))  # Much better pay
            
            # Jump bonus - additional reward for multi-jump jobs
            jump_bonus = (jumps - 1) * 100  # +100 credits per additional jump
            
            # Wealth bonus for wealthy destinations
            wealth_bonus = (dest_wealth + wealth) * 5
            final_reward = base_reward + jump_bonus + wealth_bonus + random.randint(-20, 50)
            
            # Duration based on distance and jumps
            duration = max(10, int(dist * random.uniform(1.0, 2.0)) + (jumps - 1) * 5)
            danger = min(5, max(1, int(dist / 25) + jumps + random.randint(0, 2)))
            
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
            
            # Level restrictions: Only 33% of jobs get level restrictions
            min_skill_level = 0
            if random.random() < 0.33:
                # Level restrictions range from 5 to 25
                min_skill_level = random.randint(5, 25)
                # Higher level jobs get better rewards
                level_multiplier = 1.0 + (min_skill_level * 0.03)
                final_reward = int(final_reward * level_multiplier)
            
            # Higher rewards for dangerous/long routes
            if danger >= 4:
                final_reward = int(final_reward * 1.5)
                title = f"HAZARD PAY: {title}"
            
            self.db.execute_query(
                '''INSERT INTO jobs
                   (location_id, title, description, reward_money, required_skill, min_skill_level,
                    danger_level, duration_minutes, expires_at, is_taken, destination_location_id)
                   VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, 0, %s)''',
                (location_id, title, desc, final_reward, min_skill_level, danger, duration, expire_time, dest_id)
            )

        # 5) Add fewer stationary jobs with shift multiplier
        base_stationary = random.randint(6, 10)
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
                reward = random.randint(40, 100)  # Lower pay for local work
                duration = random.randint(2, 8)  
                danger = random.randint(0, 2)
                
                # Level restrictions: Only 33% of stationary jobs get level restrictions
                min_skill_level = 0
                if random.random() < 0.33:
                    # Level restrictions range from 5 to 25
                    min_skill_level = random.randint(5, 25)
                    # Higher level jobs get better rewards
                    level_multiplier = 1.0 + (min_skill_level * 0.03)
                    reward = int(reward * level_multiplier)
                
                self.db.execute_query(
                    '''INSERT INTO jobs
                       (location_id, title, description, reward_money, required_skill, min_skill_level,
                        danger_level, duration_minutes, expires_at, is_taken)
                       VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, 0)''',
                    (location_id, title, desc, reward, min_skill_level, danger, duration, expire_time)
                )

    @job_group.command(name="accept", description="Accept a job by title or ID number")
    @app_commands.describe(job_identifier="Job title/partial title OR job ID number")
    async def job_accept(self, interaction: discord.Interaction, job_identifier: str):
        # Check if player has a character and is not in transit
        char_info = self.db.execute_query(
            "SELECT current_location, hp, money, group_id FROM characters WHERE user_id = %s",
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
            "SELECT job_id FROM jobs WHERE taken_by = %s AND is_taken = true",
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
            "SELECT current_location FROM characters WHERE user_id = %s",
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
                   WHERE location_id = %s AND job_id = %s AND is_taken = false AND expires_at > NOW()''',
                (current_location, int(job_identifier)),
                fetch='one'
            )
        
        # If not found by ID or not numeric, search by title
        if not job:
            job = self.db.execute_query(
                '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, danger_level, duration_minutes
                   FROM jobs
                   WHERE location_id = %s AND LOWER(title) LIKE LOWER(%s) 
                         AND is_taken = false AND expires_at > NOW()
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
               WHERE j.job_id = %s AND j.location_id = %s AND j.is_taken = false''',
            (job_id, current_location),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("This job is not available or already taken.", ephemeral=True)
            return
        
        job_id, title, description, reward, danger, duration, is_taken, location_name = job_info
        
        # Get group info
        group_info = self.db.execute_query(
            "SELECT name, leader_id FROM groups WHERE group_id = %s",
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
               WHERE group_id = %s AND vote_type = 'job' AND expires_at > NOW()''',
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
               VALUES (%s, %s, %s, %s, %s)''',
            (group_id, 'job', json.dumps(vote_data), interaction.channel.id, expire_time.isoformat())
        )
        
        # Get group members
        members = self.db.execute_query(
            "SELECT user_id, name FROM characters WHERE group_id = %s",
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
               SET is_taken = true, taken_by = %s, taken_at = NOW()
               WHERE job_id = %s''',
            (interaction.user.id, job_id)
        )

        # Determine if this is a stationary job that needs tracking
        title_lower = title.lower()
        desc_lower = desc.lower()

        # Get destination_location_id from the job info
        job_destination = self.db.execute_query(
            "SELECT destination_location_id, location_id FROM jobs WHERE job_id = %s",
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
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # For transport jobs, use 0 duration so they don't need location tracking
        tracking_duration = 0 if is_transport_job else duration

        self.db.execute_query(
            '''INSERT INTO job_tracking
               (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
               VALUES (%s, %s, %s, %s, 0.0, NOW())''',
            (job_id, interaction.user.id, current_location, tracking_duration)
        )
        embed = discord.Embed(
            title="✅ Job Accepted & Started",
            description=f"You have taken: **{title}** (ID: {job_id})\n🔄 **Job is now active** - work in progress!",
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
            "SELECT job_id, title FROM jobs WHERE taken_by = %s AND is_taken = true",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("You don't have an active job to abandon.", ephemeral=True)
            return
        
        job_id, title = job_info
        
        # Remove the job assignment (make it available again)
        self.db.execute_query(
            "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL WHERE job_id = %s",
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
               WHERE j.taken_by = %s AND j.is_taken = true''',
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

        taken_time = safe_datetime_parse(taken_at)
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
                unloading_time = safe_datetime_parse(unloading_started_at)
                unloading_elapsed = (current_time - unloading_time).total_seconds()
                unloading_duration = 120  # 2 minutes in seconds
                unloading_remaining = max(0, unloading_duration - unloading_elapsed)
                
                status_text = f"🚛 **Unloading Cargo** - {unloading_remaining:.0f}s remaining"
                progress_pct = min(100, (unloading_elapsed / unloading_duration) * 100)
                bars = int(progress_pct // 10)
                progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
                
                if unloading_remaining > 0:
                    status_text += "\n💡 Use the 'Complete Job' button to rush (10% penalty)"
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
                    "SELECT name FROM locations WHERE location_id = %s",
                    (destination_location_id,),
                    fetch='one'
                )
                dest_name = dest_name[0] if dest_name else "Unknown Location"
                
                # Check if player is at destination
                player_location = self.db.execute_query(
                    "SELECT current_location FROM characters WHERE user_id = %s",
                    (interaction.user.id,),
                    fetch='one'
                )[0]
                
                if player_location == destination_location_id:
                    status_text = f"📍 **At Destination** - {dest_name}\n✅ Use the 'Complete Job' button to start unloading"
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
                    status_text = "✅ **Ready for delivery** - Use the 'Complete Job' button at any location"
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
                embed.add_field(name="🎯 Destination", value=location_name[:1020], inline=True)
                
            embed.add_field(name="Status", value=status_text[:1020], inline=False)
            embed.add_field(name="Progress", value=progress_text[:1020], inline=False)
            
            # Skip the default fields since we added them above
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
            
        else:
            # Stationary job - check tracking
            tracking = self.db.execute_query(
                "SELECT time_at_location, required_duration FROM job_tracking WHERE job_id = %s AND user_id = %s",
                (job_id, interaction.user.id),
                fetch='one'
            )
            
            if tracking:
                time_at_location, required_duration = tracking
                # FIX: Ensure values are treated as floats and handle edge cases
                time_at_location = float(time_at_location) if time_at_location else 0.0
                required_duration = float(required_duration) if required_duration else 1.0
                
                if time_at_location >= required_duration:
                    status_text = "✅ **Ready for completion** - Use the 'Complete Job' button"
                    progress_text = "Required time at location completed"
                else:
                    remaining = max(0, required_duration - time_at_location)  # Prevent negative values
                    status_text = f"📍 **Working on-site** - {remaining:.1f} minutes remaining"
                    progress_pct = min(100, (time_at_location / required_duration) * 100)  # Cap at 100%
                    bars = int(progress_pct // 10)
                    progress_text = "🟩" * bars + "⬜" * (10 - bars) + f" {progress_pct:.0f}%"
            else:
                status_text = "📍 **Needs location tracking** - Use the 'Complete Job' button to start"
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
                   WHERE jt.user_id = %s AND j.is_taken = true''',
                (user_id,),
                fetch='one'
            )
            
            if tracking:
                tracking_id, job_id, start_location, required_duration, time_at_location, last_check = tracking
                
                # Check current location
                current_location = self.db.execute_query(
                    "SELECT current_location FROM characters WHERE user_id = %s",
                    (user_id,),
                    fetch='one'
                )
                
                if current_location and current_location[0] == start_location:
                    # Force add 1 minute to the tracking
                    new_time = float(time_at_location or 0) + 1.0
                    self.db.execute_query(
                        '''UPDATE job_tracking
                           SET time_at_location = %s, last_location_check = NOW()
                           WHERE tracking_id = %s''',
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
            WHERE j.is_taken = true
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
               WHERE location_id = %s AND (stock > 0 OR stock = -1)
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
               WHERE owner_id = %s AND quantity > 0
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
                
                # Format category name
                category_name = self._format_category_name(item_type)
                
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
                        description=f"[{category_name}] {description[:65]}{'...' if len(description) > 65 else ''} {stock_text}{status_emoji}"[:100],
                        value=item_name
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose an item to buy...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    def _format_category_name(self, item_type: str) -> str:
        """Convert item_type to user-friendly category name."""
        if not item_type:
            return "General"
        return item_type.replace('_', ' ').title()
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your shop interface!", ephemeral=True)
            return
        
        item_name = interaction.data['values'][0]
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_name, price, stock, description, item_type
               FROM shop_items 
               WHERE location_id = %s AND item_name = %s''',
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
            "SELECT current_location, money FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Find item in shop
        item = econ_cog.db.execute_query(
            '''SELECT item_id, item_name, price, stock, description, item_type, metadata
               FROM shop_items 
               WHERE location_id = %s AND item_name = %s
               AND (stock >= %s OR stock = -1)''',
            (current_location, self.item_name, self.quantity),
            fetch='one'
        )
        
        if not item:
            await interaction.followup.send(f"Item '{self.item_name}' not available or insufficient stock.", ephemeral=True)
            return
        
        item_id, actual_name, price, stock, description, item_type, metadata = item

        # Ensure metadata exists using helper function
        from utils.item_config import ItemConfig
        metadata = ItemConfig.ensure_item_metadata(actual_name, metadata)

        total_cost = price * self.quantity
        
        if current_money < total_cost:
            await interaction.followup.send(
                f"Insufficient credits! Need {total_cost:,}, have {current_money:,}.",
                ephemeral=True
            )
            return
        
        # Process purchase (same logic as shop_buy)
        econ_cog.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (total_cost, interaction.user.id)
        )
        
        # Update shop stock
        if stock != -1:
            econ_cog.db.execute_query(
                "UPDATE shop_items SET stock = stock - %s WHERE item_id = %s",
                (self.quantity, item_id)
            )
        
        # Add to inventory
        existing_item = econ_cog.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (interaction.user.id, actual_name),
            fetch='one'
        )
        
        if existing_item:
            econ_cog.db.execute_query(
                "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                (self.quantity, existing_item[0])
            )
        else:
            econ_cog.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                (interaction.user.id, actual_name, item_type, self.quantity, description, price, metadata)
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
               WHERE owner_id = %s AND item_id = %s''',
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
                "SELECT wealth_level FROM locations WHERE location_id = %s",
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
                "SELECT wealth_level FROM locations WHERE location_id = %s",
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
            "SELECT current_location, money FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send("Character not found!", ephemeral=True)
            return
        
        current_location, current_money = char_info
        
        # Check if location has shops
        has_shops = econ_cog.db.execute_query(
            "SELECT has_shops, wealth_level FROM locations WHERE location_id = %s",
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
               WHERE owner_id = %s AND item_name = %s AND quantity >= %s''',
            (interaction.user.id, self.item_name, self.quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.followup.send(f"You don't have enough '{self.item_name}' to sell.", ephemeral=True)
            return
        
        inv_id, actual_name, current_qty, base_value, item_type, description = inventory_item
        
        total_earnings = self.sell_price * self.quantity
        
        # Check if item is equipped and unequip it before selling
        equipped_check = econ_cog.db.execute_query(
            "SELECT equipment_id FROM character_equipment WHERE item_id = %s AND user_id = %s",
            (inv_id, interaction.user.id),
            fetch='all'
        )
        
        if equipped_check:
            # Item is equipped, remove from equipment slots
            econ_cog.db.execute_query(
                "DELETE FROM character_equipment WHERE item_id = %s AND user_id = %s",
                (inv_id, interaction.user.id)
            )
        
        # Update inventory
        if current_qty == self.quantity:
            econ_cog.db.execute_query("DELETE FROM inventory WHERE item_id = %s", (inv_id,))
        else:
            econ_cog.db.execute_query(
                "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                (self.quantity, inv_id)
            )
        
        # Add money to character
        econ_cog.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (total_earnings, interaction.user.id)
        )
        
        # Add sold items to shop (same logic as existing shop_sell)
        markup_price = max(self.sell_price + 1, int(self.sell_price * 1.2))
        
        existing = econ_cog.db.execute_query(
            "SELECT item_id, stock, price FROM shop_items WHERE location_id = %s AND LOWER(item_name) = LOWER(%s)",
            (current_location, actual_name),
            fetch='one'
        )
        
        if existing:
            shop_id, shop_stock, shop_price = existing
            new_stock = shop_stock + self.quantity if shop_stock != -1 else -1
            new_price = max(shop_price, markup_price)
            econ_cog.db.execute_query(
                "UPDATE shop_items SET stock = %s, price = %s WHERE item_id = %s",
                (new_stock, new_price, shop_id)
            )
        else:
            from utils.item_config import ItemConfig
            metadata = ItemConfig.create_item_metadata(actual_name)
            econ_cog.db.execute_query(
                '''INSERT INTO shop_items
                   (location_id, item_name, item_type, price, stock, description, metadata, sold_by_player)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (current_location, actual_name, item_type, markup_price, self.quantity, description, metadata, True)
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
        
        # Check if this is a quest first
        quest_cog = self.bot.get_cog('QuestsCog')
        if quest_cog:
            quest_info = self.bot.db.execute_query(
                '''SELECT quest_id, title, description, reward_money, danger_level, 
                          estimated_duration, required_level
                   FROM quests WHERE quest_id = %s''',
                (job_id,),
                fetch='one'
            )
            
            if quest_info:
                # This is a quest, handle it differently
                view = QuestDetailView(self.bot, self.user_id, quest_info)
                embed = await view.create_embed()
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
        
        # Get job details (regular job)
        job_info = self.bot.db.execute_query(
            '''SELECT job_id, title, description, reward_money, required_skill, min_skill_level, 
                      danger_level, duration_minutes, destination_location_id
               FROM jobs WHERE job_id = %s''',
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
                "SELECT name FROM locations WHERE location_id = %s",
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
            "SELECT job_id FROM jobs WHERE taken_by = %s AND is_taken = true",
            (interaction.user.id,),
            fetch='one'
        )
        
        if has_job:
            await interaction.followup.send("You already have an active job. Complete or abandon it first.", ephemeral=True)
            return
        
        # Get character info
        char = econ_cog.db.execute_query(
            "SELECT current_location, group_id FROM characters WHERE user_id = %s",
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
               WHERE location_id = %s AND job_id = %s AND is_taken = false AND expires_at > NOW()''',
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
                f"SELECT {skill} FROM characters WHERE user_id = %s",
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
               SET is_taken = true, taken_by = %s, taken_at = NOW()
               WHERE job_id = %s''',
            (interaction.user.id, job_id)
        )

        # Determine if this is a stationary job that needs tracking
        title_lower = title.lower()
        desc_lower = desc.lower()

        # Get destination_location_id from the job info
        job_destination = econ_cog.db.execute_query(
            "SELECT destination_location_id, location_id FROM jobs WHERE job_id = %s",
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
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # For transport jobs, use 0 duration so they don't need location tracking
        tracking_duration = 0 if is_transport_job else duration

        econ_cog.db.execute_query(
            '''INSERT INTO job_tracking
               (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
               VALUES (%s, %s, %s, %s, 0.0, NOW())''',
            (job_id, interaction.user.id, current_location, tracking_duration)
        )
        
        # Build success embed
        embed = discord.Embed(
            title="✅ Job Accepted & Started",
            description=f"You have taken: **{title}** (ID: {job_id})\n🔄 **Job is now active** - work in progress!",
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

class QuestDetailView(discord.ui.View):
    def __init__(self, bot, user_id: int, quest_info: tuple):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.quest_info = quest_info
    
    async def create_embed(self):
        """Create the quest detail embed"""
        quest_id, title, description, reward_money, danger_level, estimated_duration, required_level = self.quest_info
        
        # Get quest objectives
        objectives = self.bot.db.execute_query(
            '''SELECT objective_order, objective_type, description, target_location_id, 
                      target_item, target_quantity
               FROM quest_objectives
               WHERE quest_id = %s
               ORDER BY objective_order''',
            (quest_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"🏆 {title}",
            description=description,
            color=0x9b59b6
        )
        
        embed.add_field(name="💰 Reward", value=f"{reward_money:,} credits", inline=True)
        embed.add_field(name="⚠️ Danger Level", value="⚠️" * danger_level, inline=True)
        embed.add_field(name="🎯 Required Level", value=str(required_level), inline=True)
        
        if estimated_duration:
            embed.add_field(name="⏱️ Estimated Duration", value=estimated_duration, inline=True)
        
        # Add objectives
        if objectives:
            obj_text = []
            for order, obj_type, desc, location_id, item, quantity in objectives:
                if obj_type == 'travel':
                    location_name = self.bot.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = %s",
                        (location_id,), fetch='one'
                    )
                    location_name = location_name[0] if location_name else f"Location {location_id}"
                    obj_text.append(f"{order}. Travel to {location_name}")
                elif obj_type == 'obtain_item':
                    obj_text.append(f"{order}. Obtain {quantity}x {item}")
                elif obj_type == 'deliver_item':
                    location_name = self.bot.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = %s",
                        (location_id,), fetch='one'
                    )
                    location_name = location_name[0] if location_name else f"Location {location_id}"
                    obj_text.append(f"{order}. Deliver {quantity}x {item} to {location_name}")
                else:
                    obj_text.append(f"{order}. {desc}")
            
            embed.add_field(
                name="📋 Objectives",
                value="\n".join(obj_text[:10]),  # Limit to prevent embed overflow
                inline=False
            )
        
        embed.set_footer(text=f"Quest ID: {quest_id} | This is a multi-step quest")
        return embed
    
    @discord.ui.button(label="Accept Quest", style=discord.ButtonStyle.success, emoji="🏆")
    async def accept_quest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your quest interface!", ephemeral=True)
            return
        
        quest_id = self.quest_info[0]
        
        # Get quest cog for acceptance logic
        quest_cog = self.bot.get_cog('QuestsCog')
        if not quest_cog:
            await interaction.response.send_message("Quest system unavailable.", ephemeral=True)
            return
        
        # Check if user can accept the quest
        can_accept, reason = quest_cog.can_accept_quest(self.user_id, quest_id)
        if not can_accept:
            await interaction.response.send_message(reason, ephemeral=True)
            return
        
        # Accept the quest
        success = quest_cog.accept_quest(self.user_id, quest_id)
        if not success:
            await interaction.response.send_message("Failed to accept quest. Please try again.", ephemeral=True)
            return
        
        quest_title = self.quest_info[1]
        embed = discord.Embed(
            title="✅ Quest Accepted!",
            description=f"You have accepted: **{quest_title}**\n🏆 **Quest is now active** - begin your journey!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📊 Next Steps",
            value="Use `/tqe` to check your progress and objectives.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_quest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your quest interface!", ephemeral=True)
            return
        
        await interaction.response.send_message("Quest viewing cancelled.", ephemeral=True)

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
            "SELECT reputation FROM character_reputation WHERE user_id = %s AND location_id = %s",
            (self.user_id, self.location_id),
            fetch='one'
        )
        current_reputation = reputation_data[0] if reputation_data else 0
        
        # Get available items based on reputation - THIS IS THE FIX
        items = self.bot.db.execute_query(
            '''SELECT item_name, item_type, price, stock, description, clearance_level
               FROM federal_supply_items 
               WHERE location_id = %s AND (stock > 0 OR stock = -1) AND %s >= clearance_level
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
               WHERE bm.location_id = %s AND (bmi.stock > 0 OR bmi.stock = -1)
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
                
                # Format category name
                category_name = self._format_category_name(item_type)
                
                options.append(
                    discord.SelectOption(
                        label=f"{item_name} - {price:,} credits",
                        description=f"[{category_name}] {description[:55]}{'...' if len(description) > 55 else ''} {stock_text}{rep_text}"[:100],
                        value=item_name,
                        emoji="🏛️"
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose federal equipment to purchase...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    def _format_category_name(self, item_type: str) -> str:
        """Convert item_type to user-friendly category name."""
        if not item_type:
            return "General"
        return item_type.replace('_', ' ').title()
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your federal depot interface!", ephemeral=True)
            return
        
        item_name = interaction.data['values'][0]
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_name, price, stock, description, item_type, required_reputation
               FROM federal_supply_items 
               WHERE location_id = %s AND item_name = %s''',
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
                
                # Format category name
                category_name = self._format_category_name(item_type)
                
                options.append(
                    discord.SelectOption(
                        label=f"{item_name} - {price:,} credits",
                        description=f"[{category_name}] {description[:65]}{'...' if len(description) > 65 else ''} {stock_text}"[:100],
                        value=item_name,
                        emoji="💀"
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose contraband to purchase...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    def _format_category_name(self, item_type: str) -> str:
        """Convert item_type to user-friendly category name."""
        if not item_type:
            return "General"
        return item_type.replace('_', ' ').title()
    
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
               WHERE bm.location_id = %s AND bmi.item_name = %s''',
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
            "SELECT money FROM characters WHERE user_id = %s",
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
            "SELECT reputation FROM character_reputation WHERE user_id = %s AND location_id = %s",
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
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (total_cost, interaction.user.id)
        )
        
        # Add item to inventory
        existing_item = self.bot.db.execute_query(
            "SELECT quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (interaction.user.id, self.item_name),
            fetch='one'
        )
        
        item_data = ItemConfig.get_item_definition(self.item_name)
        item_value = item_data.get("base_value", self.price) if item_data else self.price
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + %s WHERE owner_id = %s AND item_name = %s",
                (self.quantity, interaction.user.id, self.item_name)
            )
        else:
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, value, description)
                   VALUES (%s, %s, %s, %s, %s, %s)''',
                (interaction.user.id, self.item_name, self.item_type, self.quantity, item_value, self.description)
            )
        
        # Update stock if not unlimited
        if self.stock != -1:
            self.bot.db.execute_query(
                "UPDATE federal_supply_items SET stock = stock - %s WHERE location_id = %s AND item_name = %s",
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
            "SELECT money FROM characters WHERE user_id = %s",
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
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (total_cost, interaction.user.id)
        )
        
        # Add item to inventory
        existing_item = self.bot.db.execute_query(
            "SELECT quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (interaction.user.id, self.item_name),
            fetch='one'
        )
        
        item_data = ItemConfig.get_item_definition(self.item_name)
        item_value = item_data.get("base_value", self.price) if item_data else self.price
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + %s WHERE owner_id = %s AND item_name = %s",
                (self.quantity, interaction.user.id, self.item_name)
            )
        else:
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, value, description)
                   VALUES (%s, %s, %s, %s, %s, %s)''',
                (interaction.user.id, self.item_name, self.item_type, self.quantity, item_value, self.description)
            )
        
        # Update stock if not unlimited
        if self.stock != -1:
            self.bot.db.execute_query(
                "UPDATE black_market_items SET stock = stock - %s WHERE location_id = %s AND item_name = %s",
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