# cogs/item_trading.py
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio

class ItemTradingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    item_group = app_commands.Group(name="item", description="Item trading commands")
    
    @item_group.command(name="give", description="Give an item to another player")
    @app_commands.describe(
        player="The player to give the item to",
        item="Name of the item to give",
        quantity="Number of items to give (default: 1)"
    )
    async def give_item(self, interaction: discord.Interaction, player: discord.Member, item: str, quantity: int = 1):
        if quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than 0.", ephemeral=True)
            return
        
        if player.id == interaction.user.id:
            await interaction.response.send_message("You cannot give items to yourself!", ephemeral=True)
            return
        
        if player.bot:
            await interaction.response.send_message("You cannot give items to bots!", ephemeral=True)
            return
        
        # Check if both players have characters
        giver_char = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not giver_char:
            await interaction.response.send_message("You don't have a character! Use the game panel to create a character first.", ephemeral=True)
            return
        
        receiver_char = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not receiver_char:
            await interaction.response.send_message(f"{player.mention} doesn't have a character!", ephemeral=True)
            return
        
        giver_location, giver_name = giver_char
        receiver_location, receiver_name = receiver_char
        
        # Check if both players are in the same location
        if not giver_location or not receiver_location:
            await interaction.response.send_message("Both players must be at a location (not in transit) to trade items.", ephemeral=True)
            return
        
        if giver_location != receiver_location:
            await interaction.response.send_message("You must be in the same location as the other player to give them items.", ephemeral=True)
            return
        
        # Find the item in giver's inventory
        inventory_item = self.db.execute_query(
            "SELECT item_id, item_name, quantity, item_type, description, value, metadata FROM inventory WHERE owner_id = %s AND LOWER(item_name) LIKE LOWER(%s) AND quantity >= %s",
            (interaction.user.id, f"%{item}%", quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.response.send_message(f"You don't have enough '{item}' to give. Check your inventory with `/character inventory`.", ephemeral=True)
            return
        
        item_id, actual_name, current_qty, item_type, description, value, metadata = inventory_item
        
        # Ensure metadata exists using helper function
        from utils.item_config import ItemConfig
        metadata = ItemConfig.ensure_item_metadata(actual_name, metadata)
        
        # Remove from giver's inventory
        if current_qty == quantity:
            self.db.execute_query("DELETE FROM inventory WHERE item_id = %s", (item_id,))
        else:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                (quantity, item_id)
            )
        
        # Add to receiver's inventory
        existing_item = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (player.id, actual_name),
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
                (player.id, actual_name, item_type, quantity, description, value, metadata)
            )
        
        # Send success message to location channels via cross-guild broadcast
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        cross_guild_channels = await channel_manager.get_cross_guild_location_channels(giver_location)
        
        embed = discord.Embed(
            title="🤝 Item Transfer",
            description=f"**{giver_name}** gave {quantity}x **{actual_name}** to **{receiver_name}**",
            color=0x00ff00
        )
        embed.add_field(name="Item Type", value=item_type.title(), inline=True)
        embed.add_field(name="Quantity", value=f"{quantity}", inline=True)
        embed.add_field(name="Value", value=f"{value * quantity:,} credits", inline=True)
        
        for guild_channel, channel in cross_guild_channels:
            try:
                await channel.send(embed=embed)
            except:
                pass  # Skip if can't send to this guild
        
        await interaction.response.send_message(f"✅ Successfully gave {quantity}x **{actual_name}** to {player.mention}!", ephemeral=True)
    
    @item_group.command(name="sell", description="Offer to sell an item to another player")
    @app_commands.describe(
        player="The player to offer the item to",
        item="Name of the item to sell",
        quantity="Number of items to sell (default: 1)",
        price="Price in credits (default: item's base value)"
    )
    async def sell_item(self, interaction: discord.Interaction, player: discord.Member, item: str, quantity: int = 1, price: int = None):
        if quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than 0.", ephemeral=True)
            return
        
        if player.id == interaction.user.id:
            await interaction.response.send_message("You cannot sell items to yourself!", ephemeral=True)
            return
        
        if player.bot:
            await interaction.response.send_message("You cannot sell items to bots!", ephemeral=True)
            return
        
        # Check if both players have characters
        seller_char = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not seller_char:
            await interaction.response.send_message("You don't have a character! Use the game panel to create a character first.", ephemeral=True)
            return
        
        buyer_char = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = %s",
            (player.id,),
            fetch='one'
        )
        
        if not buyer_char:
            await interaction.response.send_message(f"{player.mention} doesn't have a character!", ephemeral=True)
            return
        
        seller_location, seller_name = seller_char
        buyer_location, buyer_name = buyer_char
        
        # Check if both players are in the same location
        if not seller_location or not buyer_location:
            await interaction.response.send_message("Both players must be at a location (not in transit) to trade items.", ephemeral=True)
            return
        
        if seller_location != buyer_location:
            await interaction.response.send_message("You must be in the same location as the other player to sell them items.", ephemeral=True)
            return
        
        # Find the item in seller's inventory
        inventory_item = self.db.execute_query(
            "SELECT item_id, item_name, quantity, item_type, description, value FROM inventory WHERE owner_id = %s AND LOWER(item_name) LIKE LOWER(%s) AND quantity >= %s",
            (interaction.user.id, f"%{item}%", quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.response.send_message(f"You don't have enough '{item}' to sell. Check your inventory with `/character inventory`.", ephemeral=True)
            return
        
        item_id, actual_name, current_qty, item_type, description, value = inventory_item
        
        # Set default price if not provided
        if price is None:
            price = value * quantity
        elif price < 0:
            await interaction.response.send_message("Price cannot be negative.", ephemeral=True)
            return
        
        # Get location channels for cross-guild broadcasting
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        cross_guild_channels = await channel_manager.get_cross_guild_location_channels(seller_location)
        
        if not cross_guild_channels:
            await interaction.response.send_message("Unable to find location channels for this trade.", ephemeral=True)
            return
        
        # Create the trade offer view
        view = TradeOfferView(
            self.bot, 
            seller_id=interaction.user.id,
            buyer_id=player.id,
            item_id=item_id,
            item_name=actual_name,
            quantity=quantity,
            price=price,
            seller_name=seller_name,
            buyer_name=buyer_name
        )
        
        # Create embed for the offer
        embed = discord.Embed(
            title="💰 Item Sale Offer",
            description=f"**{seller_name}** is offering to sell items to **{buyer_name}**",
            color=0xffd700
        )
        embed.add_field(name="🎯 Item", value=f"{quantity}x **{actual_name}**", inline=True)
        embed.add_field(name="💵 Price", value=f"{price:,} credits", inline=True)
        embed.add_field(name="📝 Type", value=item_type.title(), inline=True)
        
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        
        embed.add_field(name="💡 Instructions", value=f"{player.mention} can accept or decline this offer using the buttons below.", inline=False)
        embed.set_footer(text="This offer will expire in 5 minutes")
        
        # Send to location channels via cross-guild broadcast
        offer_message = None
        for guild_channel, channel in cross_guild_channels:
            try:
                msg = await channel.send(embed=embed, view=view)
                if not offer_message:
                    offer_message = msg  # Store first successful message for view
            except:
                pass  # Skip if can't send to this guild
        
        if offer_message:
            view.message = offer_message
        
        await interaction.response.send_message(f"✅ Trade offer sent to {player.mention} in the location channel!", ephemeral=True)

    @item_group.command(name="slot_fix", description="Fix ghost equipment slots (admin only)")
    async def fix_equipment_slots(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Find all ghost equipment entries (equipment pointing to non-existent inventory items)
        ghost_equipment = self.db.execute_query(
            '''SELECT ce.equipment_id, ce.user_id, ce.slot_name, ce.item_id,
                      c.name as character_name
               FROM character_equipment ce
               JOIN characters c ON ce.user_id = c.user_id
               LEFT JOIN inventory i ON ce.item_id = i.item_id
               WHERE i.item_id IS NULL''',
            fetch='all'
        )
        
        if not ghost_equipment:
            embed = discord.Embed(
                title="✅ No Ghost Equipment Slots Found",
                description="All equipment slots are properly linked to existing inventory items.",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Group by character for display
        characters_affected = {}
        for equipment_id, user_id, slot_name, item_id, character_name in ghost_equipment:
            if user_id not in characters_affected:
                characters_affected[user_id] = {
                    'name': character_name,
                    'slots': []
                }
            characters_affected[user_id]['slots'].append({
                'equipment_id': equipment_id,
                'slot_name': slot_name,
                'item_id': item_id
            })
        
        # Clean up ghost equipment
        cleaned_count = 0
        for equipment_id, user_id, slot_name, item_id, character_name in ghost_equipment:
            self.db.execute_query(
                "DELETE FROM character_equipment WHERE equipment_id = %s",
                (equipment_id,)
            )
            cleaned_count += 1
        
        # Create result embed
        embed = discord.Embed(
            title="🔧 Equipment Slots Cleanup Complete",
            description=f"Removed {cleaned_count} ghost equipment entries from {len(characters_affected)} characters.",
            color=0x00ff00
        )
        
        # Show affected characters (up to 10)
        char_list = []
        for user_id, info in list(characters_affected.items())[:10]:
            member = interaction.guild.get_member(user_id)
            member_name = member.display_name if member else f"Unknown ({user_id})"
            slot_names = [slot['slot_name'] for slot in info['slots']]
            char_list.append(f"• **{info['name']}** ({member_name}): {', '.join(slot_names)}")
        
        if char_list:
            embed.add_field(
                name=f"🎭 Characters Fixed ({len(characters_affected)})",
                value="\n".join(char_list) + (f"\n... and {len(characters_affected)-10} more" if len(characters_affected) > 10 else ""),
                inline=False
            )
        
        embed.set_footer(text="Players can now properly equip items in previously 'occupied' slots.")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


class TradeOfferView(discord.ui.View):
    def __init__(self, bot, seller_id: int, buyer_id: int, item_id: int, item_name: str, quantity: int, price: int, seller_name: str, buyer_name: str):
        super().__init__(timeout=300)  # 5 minutes
        self.bot = bot
        self.seller_id = seller_id
        self.buyer_id = buyer_id
        self.item_id = item_id
        self.item_name = item_name
        self.quantity = quantity
        self.price = price
        self.seller_name = seller_name
        self.buyer_name = buyer_name
        self.message = None
        self.resolved = False
    
    async def on_timeout(self):
        """Handle timeout - offer expires"""
        if self.resolved:
            return
        
        self.resolved = True
        
        if self.message:
            embed = discord.Embed(
                title="⏰ Trade Offer Expired",
                description=f"The trade offer from **{self.seller_name}** to **{self.buyer_name}** has expired.",
                color=0x808080
            )
            embed.add_field(name="Item", value=f"{self.quantity}x **{self.item_name}**", inline=True)
            embed.add_field(name="Price", value=f"{self.price:,} credits", inline=True)
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            try:
                await self.message.edit(embed=embed, view=self)
            except:
                pass
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("Only the buyer can accept this offer!", ephemeral=True)
            return
        
        if self.resolved:
            await interaction.response.send_message("This offer has already been resolved!", ephemeral=True)
            return
        
        self.resolved = True
        
        # Check if buyer has enough money
        buyer_money = self.db.execute_query(
            "SELECT money FROM characters WHERE user_id = %s",
            (self.buyer_id,),
            fetch='one'
        )
        
        if not buyer_money or buyer_money[0] < self.price:
            have_money = buyer_money[0] if buyer_money else 0
            embed = discord.Embed(
                title="❌ Transaction Failed",
                description=f"**{self.buyer_name}** doesn't have enough credits to complete this purchase.",
                color=0xff0000
            )
            embed.add_field(name="Required", value=f"{self.price:,} credits", inline=True)
            embed.add_field(name="Available", value=f"{have_money:,} credits", inline=True)
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            return
        
        # Check if seller still has the item
        seller_item = self.db.execute_query(
            "SELECT quantity FROM inventory WHERE item_id = %s AND owner_id = %s",
            (self.item_id, self.seller_id),
            fetch='one'
        )
        
        if not seller_item or seller_item[0] < self.quantity:
            embed = discord.Embed(
                title="❌ Transaction Failed",
                description=f"**{self.seller_name}** no longer has enough of this item to complete the sale.",
                color=0xff0000
            )
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            return
        
        # Process the transaction
        try:
            # Transfer money from buyer to seller
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - %s WHERE user_id = %s",
                (self.price, self.buyer_id)
            )
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + %s WHERE user_id = %s",
                (self.price, self.seller_id)
            )
            
            # Get item details for transfer
            item_details = self.bot.db.execute_query(
                "SELECT item_name, item_type, description, value, metadata FROM inventory WHERE item_id = %s",
                (self.item_id,),
                fetch='one'
            )
            
            if not item_details:
                raise Exception("Item details not found")
            
            actual_name, item_type, description, value, metadata = item_details
            
            # Ensure metadata exists, create if missing
            if not metadata:
                from utils.item_config import ItemConfig
                try:
                    metadata = ItemConfig.create_item_metadata(actual_name)
                except:
                    # Fallback metadata for items without definitions
                    import json
                    metadata = json.dumps({
                        "usage_type": "consumable",
                        "effect_value": 10,
                        "single_use": True,
                        "uses_remaining": 1,
                        "rarity": "common"
                    })
            
            # Remove item from seller
            if seller_item[0] == self.quantity:
                self.bot.db.execute_query("DELETE FROM inventory WHERE item_id = %s", (self.item_id,))
            else:
                self.bot.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                    (self.quantity, self.item_id)
                )
            
            # Add item to buyer
            existing_item = self.bot.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
                (self.buyer_id, actual_name),
                fetch='one'
            )
            
            if existing_item:
                self.bot.db.execute_query(
                    "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                    (self.quantity, existing_item[0])
                )
            else:
                self.bot.db.execute_query(
                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                    (self.buyer_id, actual_name, item_type, self.quantity, description, value, metadata)
                )
            
            # Success embed
            embed = discord.Embed(
                title="✅ Transaction Complete",
                description=f"**{self.buyer_name}** successfully purchased items from **{self.seller_name}**",
                color=0x00ff00
            )
            embed.add_field(name="Item", value=f"{self.quantity}x **{actual_name}**", inline=True)
            embed.add_field(name="Price", value=f"{self.price:,} credits", inline=True)
            embed.add_field(name="Transaction", value=f"Credits: {self.seller_name} ← {self.buyer_name}", inline=False)
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Transaction Error",
                description="An error occurred while processing the transaction. Please try again.",
                color=0xff0000
            )
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            print(f"Trade error: {e}")
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message("Only the buyer can decline this offer!", ephemeral=True)
            return
        
        if self.resolved:
            await interaction.response.send_message("This offer has already been resolved!", ephemeral=True)
            return
        
        self.resolved = True
        
        embed = discord.Embed(
            title="❌ Trade Declined",
            description=f"**{self.buyer_name}** has declined **{self.seller_name}**'s offer.",
            color=0xff0000
        )
        embed.add_field(name="Item", value=f"{self.quantity}x **{self.item_name}**", inline=True)
        embed.add_field(name="Price", value=f"{self.price:,} credits", inline=True)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot):
    await bot.add_cog(ItemTradingCog(bot))