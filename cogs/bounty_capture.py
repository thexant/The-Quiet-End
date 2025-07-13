# cogs/bounty_capture.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import datetime
from typing import Optional, List

class RemoveAllBountiesView(discord.ui.View):
    def __init__(self, bot, user_id: int, bounties: list, total_refund: int, total_payments: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.bounties = bounties
        self.total_refund = total_refund
        self.total_payments = total_payments
    
    @discord.ui.button(label="Confirm Remove All", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_remove_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your confirmation!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        targets_notified = []
        
        # Process each bounty
        for bounty_id, target_id, target_name, amount, set_at in self.bounties:
            # Get payments for this bounty
            payments = self.bot.db.execute_query(
                '''SELECT COALESCE(SUM(payment_amount), 0) FROM bounty_payments 
                   WHERE bounty_id = ?''',
                (bounty_id,),
                fetch='one'
            )[0]
            
            # Return payments to target
            if payments > 0:
                self.bot.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (payments, target_id)
                )
            
            # Mark bounty as inactive
            self.bot.db.execute_query(
                "UPDATE personal_bounties SET is_active = 0 WHERE bounty_id = ?",
                (bounty_id,)
            )
            
            targets_notified.append((target_id, target_name, payments))
        
        # Return total refund to setter
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (self.total_refund, interaction.user.id)
        )
        
        # Notify all targets
        for target_id, target_name, payments_returned in targets_notified:
            target_member = interaction.guild.get_member(target_id)
            if target_member:
                try:
                    target_embed = discord.Embed(
                        title="✅ Bounty Cancelled",
                        description=f"**{interaction.user.display_name}** has cancelled their bounty on you!",
                        color=0x00ff00
                    )
                    
                    if payments_returned > 0:
                        target_embed.add_field(
                            name="💰 Refund", 
                            value=f"{payments_returned:,} credits returned",
                            inline=True
                        )
                    
                    await target_member.send(embed=target_embed)
                except:
                    pass
        
        # Final confirmation
        embed = discord.Embed(
            title="✅ All Bounties Removed",
            description=f"Successfully removed **{len(self.bounties)}** bounties.",
            color=0x00ff00
        )
        
        embed.add_field(name="Your Refund", value=f"{self.total_refund:,} credits", inline=True)
        embed.add_field(name="Targets Notified", value=str(len(targets_notified)), inline=True)
        
        if self.total_payments > 0:
            embed.add_field(name="Payments Returned", value=f"{self.total_payments:,} credits", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your confirmation!", ephemeral=True)
            return
        
        await interaction.response.send_message("Bounty removal cancelled.", ephemeral=True)
        
class BountyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self._create_tables()

    def _create_tables(self):
        """Create necessary tables for the bounty system"""
        # Table to track capture attempt cooldowns
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS capture_cooldowns (
                attacker_id INTEGER,
                target_id INTEGER,
                attempt_time TEXT,
                PRIMARY KEY (attacker_id, target_id)
            )
        """)
        
        # Table to track travel bans after being captured
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS travel_bans (
                user_id INTEGER PRIMARY KEY,
                ban_until TEXT,
                reason TEXT
            )
        """)
            # Table to track personal bounties
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS personal_bounties (
                bounty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER NOT NULL,
                setter_id INTEGER NOT NULL,
                setter_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                set_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS bounty_payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bounty_id INTEGER NOT NULL,
                payment_amount INTEGER NOT NULL,
                paid_at TEXT NOT NULL,
                FOREIGN KEY (bounty_id) REFERENCES personal_bounties (bounty_id)
            )
        """)
    def get_reputation_alignment(self, reputation: int) -> str:
        """Get the alignment based on reputation"""
        if reputation >= 35:
            return "good"  # Good/Heroic
        elif reputation <= -35:
            return "evil"  # Bad/Evil
        else:
            return "neutral"

    def get_reputation_tier_name(self, reputation: int) -> str:
        """Get the tier name for display purposes"""
        if reputation >= 70:
            return "Heroic"
        elif reputation >= 35:
            return "Good"
        elif reputation <= -70:
            return "Evil"
        elif reputation <= -35:
            return "Bad"
        else:
            return "Neutral"

    async def check_travel_ban(self, user_id: int) -> Optional[str]:
        """Check if user is travel banned and return reason if banned"""
        ban_data = self.db.execute_query(
            "SELECT ban_until, reason FROM travel_bans WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not ban_data:
            return None
            
        ban_until_str, reason = ban_data
        ban_until = datetime.datetime.fromisoformat(ban_until_str)
        current_time = datetime.datetime.now()
        
        if current_time < ban_until:
            remaining = ban_until - current_time
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            return f"Travel banned for {minutes}m {seconds}s - {reason}"
        else:
            # Ban expired, remove it
            self.db.execute_query(
                "DELETE FROM travel_bans WHERE user_id = ?",
                (user_id,)
            )
            return None

    async def check_capture_cooldown(self, attacker_id: int, target_id: int) -> Optional[int]:
        """Check if there's a cooldown between attacker and target, returns seconds remaining"""
        cooldown_data = self.db.execute_query(
            "SELECT attempt_time FROM capture_cooldowns WHERE attacker_id = ? AND target_id = ?",
            (attacker_id, target_id),
            fetch='one'
        )
        
        if not cooldown_data:
            return None
            
        attempt_time = datetime.datetime.fromisoformat(cooldown_data[0])
        current_time = datetime.datetime.now()
        time_diff = current_time - attempt_time
        
        # 30 second cooldown
        if time_diff.total_seconds() < 30:
            return int(30 - time_diff.total_seconds())
        else:
            # Cooldown expired, remove it
            self.db.execute_query(
                "DELETE FROM capture_cooldowns WHERE attacker_id = ? AND target_id = ?",
                (attacker_id, target_id)
            )
            return None
    @app_commands.command(name="postbounty", description="Post a personal bounty on another player")
    @app_commands.describe(
        target="The player to put a bounty on",
        amount="Bounty amount in credits"
    )
    async def post_bounty(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        # Check if setter has a character
        setter_data = self.db.execute_query(
            "SELECT name, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not setter_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        setter_name, setter_money = setter_data
        
        # Check if target has a character
        target_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not target_data:
            await interaction.response.send_message(
                "❌ Target doesn't have a character!",
                ephemeral=True
            )
            return
        
        target_name = target_data[0]
        
        # Validate amount
        if amount < 100:
            await interaction.response.send_message(
                "❌ Minimum bounty amount is 100 credits!",
                ephemeral=True
            )
            return
        
        if amount > setter_money:
            await interaction.response.send_message(
                f"❌ You don't have enough credits! You have {setter_money:,}, need {amount:,}.",
                ephemeral=True
            )
            return
        
        # Check if target is yourself
        if interaction.user.id == target.id:
            await interaction.response.send_message(
                "❌ You cannot put a bounty on yourself!",
                ephemeral=True
            )
            return
        
        # Check if target already has an active bounty from this player
        existing_bounty = self.db.execute_query(
            "SELECT bounty_id FROM personal_bounties WHERE target_id = ? AND setter_id = ? AND is_active = 1",
            (target.id, interaction.user.id),
            fetch='one'
        )
        
        if existing_bounty:
            await interaction.response.send_message(
                f"❌ You already have an active bounty on **{target_name}**!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Deduct money
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (amount, interaction.user.id)
        )
        
        # Create bounty record
        current_time = datetime.datetime.now()
        self.db.execute_query(
            '''INSERT INTO personal_bounties 
               (target_id, setter_id, setter_name, target_name, amount, set_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (target.id, interaction.user.id, setter_name, target_name, amount, current_time.isoformat())
        )
        
        # Post galactic news - UPDATED
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            # Find the character's current location for news posting
            char_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            current_location_id = char_location[0] if char_location else None
            
            news_title = f"🎯 Bounty Notice"
            news_description = f"A bounty of {amount:,} credits has been authorized by {setter_name} for the apprehension of {target_name}."
            
            await news_cog.queue_news(
                interaction.guild.id, 
                'bounty', 
                news_title, 
                news_description, 
                current_location_id
            )
        
        embed = discord.Embed(
            title="🎯 Bounty Posted",
            description=f"Bounty successfully placed on **{target_name}**. A news broadcast has been sent.",
            color=0xff6600
        )

        embed.add_field(name="Target", value=target_name, inline=True)
        embed.add_field(name="Bounty Amount", value=f"{amount:,} credits", inline=True)
        embed.add_field(name="Your Remaining Credits", value=f"{setter_money - amount:,}", inline=True)

        embed.add_field(
            name="ℹ️ How It Works",
            value="• Other players can now attempt to capture the target using `/bounty`\n• Successful capture awards the full bounty amount\n• The bounty remains active until collected or paid off.",
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

        print(f"🎯 Bounty posted: {setter_name} → {target_name} for {amount:,} credits")
    @app_commands.command(name="removebounty", description="Remove a bounty you have set on another player")
    @app_commands.describe(target="The player whose bounty you want to remove")
    async def remove_bounty(self, interaction: discord.Interaction, target: discord.Member):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT name, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name, current_money = char_data
        
        # Check if target has a character
        target_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not target_data:
            await interaction.response.send_message(
                "❌ Target doesn't have a character!",
                ephemeral=True
            )
            return
        
        target_name = target_data[0]
        
        # Find active bounties set by this user on the target
        user_bounties = self.db.execute_query(
            '''SELECT bounty_id, amount, set_at FROM personal_bounties 
               WHERE setter_id = ? AND target_id = ? AND is_active = 1
               ORDER BY set_at DESC''',
            (interaction.user.id, target.id),
            fetch='all'
        )
        
        if not user_bounties:
            await interaction.response.send_message(
                f"❌ You don't have any active bounties on **{target_name}**!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        total_refund = 0
        total_target_refund = 0
        bounties_removed = []
        
        # Process each bounty
        for bounty_id, original_amount, set_at in user_bounties:
            # Check for payments made on this bounty
            payments_made = self.db.execute_query(
                '''SELECT COALESCE(SUM(payment_amount), 0) FROM bounty_payments 
                   WHERE bounty_id = ?''',
                (bounty_id,),
                fetch='one'
            )[0]
            
            # Return original amount to setter
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (original_amount, interaction.user.id)
            )
            total_refund += original_amount
            
            # Return any payments to target
            if payments_made > 0:
                self.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (payments_made, target.id)
                )
                total_target_refund += payments_made
            
            # Mark bounty as inactive (cancelled)
            self.db.execute_query(
                "UPDATE personal_bounties SET is_active = 0 WHERE bounty_id = ?",
                (bounty_id,)
            )
            
            bounties_removed.append((original_amount, payments_made))
        
        # Create response embed
        embed = discord.Embed(
            title="🗑️ Bounty Removed",
            description=f"Successfully removed {len(user_bounties)} bounty{'ies' if len(user_bounties) > 1 else ''} on **{target_name}**",
            color=0x00ff00
        )
        
        embed.add_field(name="Your Refund", value=f"{total_refund:,} credits", inline=True)
        embed.add_field(name="Your New Balance", value=f"{current_money + total_refund:,} credits", inline=True)
        
        if total_target_refund > 0:
            embed.add_field(
                name="Target Refund", 
                value=f"{total_target_refund:,} credits returned to {target_name}", 
                inline=True
            )
        
        # Show breakdown if multiple bounties
        if len(user_bounties) > 1:
            breakdown = []
            for original, payments in bounties_removed:
                if payments > 0:
                    breakdown.append(f"• {original:,} credits (+ {payments:,} payments returned to target)")
                else:
                    breakdown.append(f"• {original:,} credits")
            
            embed.add_field(
                name="Bounty Breakdown",
                value="\n".join(breakdown),
                inline=False
            )
        
        embed.add_field(
            name="ℹ️ Status",
            value="All specified bounties have been cancelled and funds returned.",
            inline=False
        )
        
        # Notify the target player
        try:
            target_embed = discord.Embed(
                title="✅ Bounty Cancelled",
                description=f"**{char_name}** has cancelled their bounty on you!",
                color=0x00ff00
            )
            
            if total_target_refund > 0:
                target_embed.add_field(
                    name="💰 Refund Received", 
                    value=f"{total_target_refund:,} credits (payments you made have been returned)",
                    inline=False
                )
            
            target_embed.add_field(
                name="🎉 Freedom",
                value="You are no longer being hunted by this bounty hunter!",
                inline=False
            )
            
            await target.send(embed=target_embed)
        except:
            pass  # Failed to notify target
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Post news about bounty cancellation if it was a significant amount
        if total_refund >= 1000:  # Only post news for bounties of 1000+ credits
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                char_location = self.db.execute_query(
                    "SELECT current_location FROM characters WHERE user_id = ?",
                    (interaction.user.id,),
                    fetch='one'
                )
                
                current_location_id = char_location[0] if char_location else None
                
                news_title = f"Bounty Cancelled"
                news_description = f"**{char_name}** has withdrawn their bounty on **{target_name}**. The target is no longer considered a priority for capture."
                
                await news_cog.queue_news(
                    interaction.guild.id, 
                    'bounty', 
                    news_title, 
                    news_description, 
                    current_location_id
                )
        
        print(f"🗑️ Bounty removed: {char_name} cancelled bounty on {target_name} (refund: {total_refund:,} credits)")
    @app_commands.command(name="removeallbounties", description="Remove ALL bounties you have set (requires confirmation)")
    async def remove_all_bounties(self, interaction: discord.Interaction):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT name, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name, current_money = char_data
        
        # Find all active bounties set by this user
        all_bounties = self.db.execute_query(
            '''SELECT pb.bounty_id, pb.target_id, pb.target_name, pb.amount, pb.set_at
               FROM personal_bounties pb
               WHERE pb.setter_id = ? AND pb.is_active = 1
               ORDER BY pb.set_at DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not all_bounties:
            await interaction.response.send_message(
                "❌ You don't have any active bounties to remove!",
                ephemeral=True
            )
            return
        
        # Calculate total refunds
        total_refund = 0
        total_payments_to_return = 0
        
        for bounty_id, target_id, target_name, amount, set_at in all_bounties:
            total_refund += amount
            
            # Check payments for this bounty
            payments = self.db.execute_query(
                '''SELECT COALESCE(SUM(payment_amount), 0) FROM bounty_payments 
                   WHERE bounty_id = ?''',
                (bounty_id,),
                fetch='one'
            )[0]
            total_payments_to_return += payments
        
        # Create confirmation view
        view = RemoveAllBountiesView(self.bot, interaction.user.id, all_bounties, total_refund, total_payments_to_return)
        
        embed = discord.Embed(
            title="⚠️ Remove All Bounties",
            description=f"You are about to remove **{len(all_bounties)}** active bounties.",
            color=0xff9900
        )
        
        embed.add_field(name="Total Refund", value=f"{total_refund:,} credits", inline=True)
        embed.add_field(name="Payments to Return", value=f"{total_payments_to_return:,} credits", inline=True)
        
        targets = [f"• **{target_name}** ({amount:,} credits)" for _, _, target_name, amount, _ in all_bounties[:5]]
        if len(all_bounties) > 5:
            targets.append(f"...and {len(all_bounties) - 5} more")
        
        embed.add_field(
            name="Bounties to Remove",
            value="\n".join(targets),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Confirmation Required",
            value="This action cannot be undone. Click below to confirm.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @app_commands.command(name="bounty", description="Attempt to capture a player with a bounty on their head")
    @app_commands.describe(target="The bountied player to attempt to capture")
    async def capture_bounty_target(self, interaction: discord.Interaction, target: discord.Member):
        # Check if attacker has a character
        attacker_data = self.db.execute_query(
            "SELECT current_location, hp, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not attacker_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        attacker_location, attacker_hp, attacker_name = attacker_data
        
        if not attacker_location:
            await interaction.response.send_message(
                "❌ You must be at a location to attempt bounty captures!",
                ephemeral=True
            )
            return
        
        if attacker_hp <= 0:
            await interaction.response.send_message(
                "❌ You cannot capture anyone while unconscious!",
                ephemeral=True
            )
            return
        
        # Check if target has a character
        target_data = self.db.execute_query(
            "SELECT current_location, hp, money, name FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not target_data:
            await interaction.response.send_message(
                "❌ Target doesn't have a character!",
                ephemeral=True
            )
            return
        
        target_location, target_hp, target_money, target_name = target_data
        
        if target_hp <= 0:
            await interaction.response.send_message(
                "❌ Target is already unconscious!",
                ephemeral=True
            )
            return
        
        # Check if both players are in the same location
        if attacker_location != target_location:
            await interaction.response.send_message(
                "❌ You must be in the same location as your target!",
                ephemeral=True
            )
            return
        
        # Check if target is yourself
        if interaction.user.id == target.id:
            await interaction.response.send_message(
                "❌ You cannot capture yourself!",
                ephemeral=True
            )
            return
        
        # Check if target has active bounties
        active_bounties = self.db.execute_query(
            '''SELECT SUM(amount), COUNT(*) FROM personal_bounties 
               WHERE target_id = ? AND is_active = 1''',
            (target.id,),
            fetch='one'
        )
        
        total_bounty, bounty_count = active_bounties if active_bounties[0] else (0, 0)
        
        if total_bounty == 0:
            await interaction.response.send_message(
                f"❌ **{target_name}** has no active bounties!",
                ephemeral=True
            )
            return
        
        # Check cooldown
        cooldown_remaining = await self.check_capture_cooldown(interaction.user.id, target.id)
        if cooldown_remaining is not None:
            await interaction.response.send_message(
                f"❌ You must wait {cooldown_remaining} seconds before attempting to capture this player again!",
                ephemeral=True
            )
            return
        
        # Check if target is travel banned (captured recently)
        travel_ban = await self.check_travel_ban(target.id)
        if travel_ban:
            await interaction.response.send_message(
                f"❌ Target is already captured and cannot be targeted again yet! ({travel_ban})",
                ephemeral=True
            )
            return
        
        # Get location info
        location_info = self.db.execute_query(
            "SELECT name, channel_id FROM locations WHERE location_id = ?",
            (attacker_location,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message("❌ Invalid location!", ephemeral=True)
            return
        
        location_name, location_channel_id = location_info
        
        await interaction.response.defer()
        
        # Balanced roll system
        attacker_roll = random.randint(1, 100)
        target_roll = random.randint(1, 100)
        
        capture_successful = attacker_roll > target_roll
        
        if capture_successful:
            await self._handle_successful_bounty_capture(
                interaction, target, location_name, location_channel_id,
                total_bounty, attacker_roll, target_roll
            )
        else:
            await self._handle_failed_bounty_capture(
                interaction, target, location_name, location_channel_id,
                attacker_roll, target_roll
            )

    async def _handle_successful_bounty_capture(self, interaction, target, location_name, location_channel_id, 
                                              total_bounty, attacker_roll, target_roll):
        """Handle a successful bounty capture attempt"""
        
        # Get all active bounties on target with payment details
        bounty_details = self.db.execute_query(
            '''SELECT pb.bounty_id, pb.setter_id, pb.setter_name, pb.amount
               FROM personal_bounties pb
               WHERE pb.target_id = ? AND pb.is_active = 1''',
            (target.id,),
            fetch='all'
        )
        
        # Calculate payments made for each bounty
        total_payments_to_distribute = 0
        bounty_payouts = []
        
        for bounty_id, setter_id, setter_name, bounty_amount in bounty_details:
            # Get total payments made for this bounty
            payments_made = self.db.execute_query(
                '''SELECT COALESCE(SUM(payment_amount), 0) FROM bounty_payments 
                   WHERE bounty_id = ?''',
                (bounty_id,),
                fetch='one'
            )[0]
            
            # Setter gets original bounty + any payments made
            payout = bounty_amount + payments_made
            bounty_payouts.append((setter_id, setter_name, bounty_amount, payments_made, payout))
            total_payments_to_distribute += payout
        
        # Distribute payouts to bounty setters
        for setter_id, setter_name, original_amount, payments_received, total_payout in bounty_payouts:
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (total_payout, setter_id)
            )
            
            # Notify bounty setter
            setter_member = interaction.guild.get_member(setter_id)
            if setter_member:
                try:
                    notify_embed = discord.Embed(
                        title="🎯 Bounty Captured!",
                        description=f"**{target.display_name}** has been captured by **{interaction.user.display_name}**!",
                        color=0xff6600
                    )
                    notify_embed.add_field(name="Original Bounty", value=f"{original_amount:,} credits", inline=True)
                    notify_embed.add_field(name="Payments Received", value=f"{payments_received:,} credits", inline=True)
                    notify_embed.add_field(name="Total Payout", value=f"{total_payout:,} credits", inline=True)
                    
                    await setter_member.send(embed=notify_embed)
                except:
                    pass
        
        # Give the ORIGINAL bounty amounts to the attacker (not including payments)
        original_bounty_total = sum(bounty[2] for bounty in bounty_details)  # bounty_amount from bounty_details
        
        self.db.execute_query(
            "UPDATE characters SET money = money + ? WHERE user_id = ?",
            (original_bounty_total, interaction.user.id)
        )
        
        # Reduce target's HP by 80%
        target_current_hp = self.db.execute_query(
            "SELECT hp FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )[0]
        
        hp_reduction = int(target_current_hp * 0.8)
        new_hp = max(1, target_current_hp - hp_reduction)
        
        self.db.execute_query(
            "UPDATE characters SET hp = ? WHERE user_id = ?",
            (new_hp, target.id)
        )
        
        # Mark all bounties as inactive (captured)
        self.db.execute_query(
            "UPDATE personal_bounties SET is_active = 0 WHERE target_id = ? AND is_active = 1",
            (target.id,)
        )
        
        # Apply 1-minute travel ban to target
        ban_until = datetime.datetime.now() + datetime.timedelta(minutes=1)
        self.db.execute_query(
            "INSERT OR REPLACE INTO travel_bans (user_id, ban_until, reason) VALUES (?, ?, ?)",
            (target.id, ban_until.isoformat(), "Captured for bounty")
        )
        
        # Create capture results embed for location channel
        capture_embed = discord.Embed(
            title="🎯 Bounty Captured!",
            description=f"**{interaction.user.display_name}** has successfully captured the bountied **{target.display_name}**!",
            color=0xff6600
        )
        
        capture_embed.add_field(
            name="🎯 Combat Results",
            value=f"**{interaction.user.display_name}** rolled: **{attacker_roll}**\n**{target.display_name}** rolled: **{target_roll}**",
            inline=True
        )
        
        # Show different rewards for attacker vs bounty setters
        capture_embed.add_field(
            name=f"💰 {interaction.user.display_name}'s Reward",
            value=f"• **{original_bounty_total:,}** credits (bounty collection)",
            inline=True
        )
        
        # Show bounty setter payouts if any had received payments
        total_extra_payments = sum(bounty[3] for bounty in bounty_payouts)  # payments_received
        if total_extra_payments > 0:
            capture_embed.add_field(
                name="💳 Bounty Setter Bonuses",
                value=f"• **{total_extra_payments:,}** credits in pre-payments returned to bounty setters",
                inline=True
            )
        
        capture_embed.add_field(
            name=f"💔 {target.display_name}'s Consequences",
            value=f"• **{hp_reduction}** HP damage ({target_current_hp} → {new_hp})\n• Cannot travel for **1 minute**",
            inline=True
        )
        
        capture_embed.add_field(
            name="📍 Location",
            value=f"**{location_name}**",
            inline=True
        )
        
        capture_embed.set_footer(text="Bounty capture complete - all bounties collected")
        
        # Send to location channel
        if location_channel_id:
            location_channel = self.bot.get_channel(location_channel_id)
            if location_channel:
                try:
                    await location_channel.send(embed=capture_embed)
                except:
                    pass
        
        await interaction.followup.send("✅ Bounty capture successful!", ephemeral=True)

    async def _handle_failed_bounty_capture(self, interaction, target, location_name, location_channel_id,
                                          attacker_roll, target_roll):
        """Handle a failed bounty capture attempt"""
        
        # Set cooldown for this attacker-target pair
        current_time = datetime.datetime.now()
        self.db.execute_query(
            "INSERT OR REPLACE INTO capture_cooldowns (attacker_id, target_id, attempt_time) VALUES (?, ?, ?)",
            (interaction.user.id, target.id, current_time.isoformat())
        )
        
        # Create public failed capture announcement
        failed_embed = discord.Embed(
            title="❌ Bounty Capture Failed",
            description=f"**{interaction.user.display_name}** attempted to capture the bountied **{target.display_name}** but failed!",
            color=0xff4444
        )
        
        failed_embed.add_field(
            name="🎯 Combat Results",
            value=f"**{interaction.user.display_name}** rolled: **{attacker_roll}**\n**{target.display_name}** rolled: **{target_roll}**",
            inline=True
        )
        
        failed_embed.add_field(
            name="⏱️ Cooldown",
            value=f"**{interaction.user.display_name}** cannot attempt to capture **{target.display_name}** again for **30 seconds**",
            inline=True
        )
        
        failed_embed.add_field(
            name="🛡️ Escape Window",
            value=f"**{target.display_name}** has **30 seconds** to escape before another attempt can be made!",
            inline=False
        )
        
        failed_embed.add_field(
            name="📍 Location",
            value=f"**{location_name}**",
            inline=True
        )
        
        failed_embed.set_footer(text="Bounty capture failed - 30 second cooldown active")
        
        # Send to location channel
        if location_channel_id:
            location_channel = self.bot.get_channel(location_channel_id)
            if location_channel:
                try:
                    await location_channel.send(embed=failed_embed)
                except:
                    pass
        
        # Simple ephemeral confirmation to attacker
        await interaction.followup.send("❌ Bounty capture failed! Results posted in location channel.", ephemeral=True)

    def has_active_bounty(self, user_id: int) -> bool:
        """Check if a user has any active bounties"""
        bounty_count = self.db.execute_query(
            "SELECT COUNT(*) FROM personal_bounties WHERE target_id = ? AND is_active = 1",
            (user_id,),
            fetch='one'
        )[0]
        return bounty_count > 0
    
    @app_commands.command(name="bounties", description="View active bounties within 3 locations of your position")
    async def view_local_bounties(self, interaction: discord.Interaction):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        current_location, char_name = char_data
        
        # Check if character is in transit
        transit_data = self.db.execute_query(
            '''SELECT ts.corridor_id, cor.name as corridor_name,
                      ol.location_id as origin_id, ol.name as origin_name,
                      dl.location_id as dest_id, dl.name as dest_name
               FROM travel_sessions ts
               JOIN corridors cor ON ts.corridor_id = cor.corridor_id
               JOIN locations ol ON ts.origin_location = ol.location_id
               JOIN locations dl ON ts.destination_location = dl.location_id
               WHERE ts.user_id = ? AND ts.status = 'traveling' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        search_locations = []
        search_description = ""
        
        if transit_data and "Ungated" not in transit_data[1]:  # In gated transit
            corridor_id, corridor_name, origin_id, origin_name, dest_id, dest_name = transit_data
            search_description = f"Scanning from corridor **{corridor_name}** (between {origin_name} and {dest_name})"
            
            # Use both ends of the corridor as starting points
            origin_reachable = await self._find_reachable_locations(origin_id, max_hops=3)
            dest_reachable = await self._find_reachable_locations(dest_id, max_hops=3)
            
            # Combine and deduplicate
            search_locations = list(set(origin_reachable + dest_reachable))
            
        elif current_location:  # At a normal location
            location_name = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (current_location,),
                fetch='one'
            )[0]
            
            search_description = f"Scanning from **{location_name}** and nearby locations"
            search_locations = await self._find_reachable_locations(current_location, max_hops=3)
            
        else:
            await interaction.response.send_message(
                "❌ Unable to scan for bounties from your current position!",
                ephemeral=True
            )
            return
        
        if not search_locations:
            await interaction.response.send_message(
                "❌ No reachable locations found for bounty scanning!",
                ephemeral=True
            )
            return
        
        # Find bountied players in reachable locations
        location_ids_str = ','.join(['?' for _ in search_locations])
        bountied_players = self.db.execute_query(
            f'''SELECT DISTINCT pb.target_name, SUM(pb.amount) as total_bounty, 
                      COUNT(*) as bounty_count, l.name as location_name,
                      c.user_id, pb.target_id
               FROM personal_bounties pb
               JOIN characters c ON pb.target_id = c.user_id
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.current_location IN ({location_ids_str}) 
               AND pb.is_active = 1 AND c.is_logged_in = 1
               GROUP BY pb.target_id, pb.target_name, l.name
               ORDER BY total_bounty DESC''',
            search_locations,
            fetch='all'
        )
        
        # Also check for bountied players in transit within our search area
        transit_bountied = self.db.execute_query(
            f'''SELECT DISTINCT pb.target_name, SUM(pb.amount) as total_bounty,
                      COUNT(*) as bounty_count, cor.name as corridor_name,
                      c.user_id, pb.target_id
               FROM personal_bounties pb
               JOIN characters c ON pb.target_id = c.user_id
               JOIN travel_sessions ts ON c.user_id = ts.user_id
               JOIN corridors cor ON ts.corridor_id = cor.corridor_id
               WHERE (ts.origin_location IN ({location_ids_str}) OR ts.destination_location IN ({location_ids_str}))
               AND pb.is_active = 1 AND c.is_logged_in = 1 
               AND ts.status = 'traveling'
               AND cor.name NOT LIKE '%Ungated%'
               GROUP BY pb.target_id, pb.target_name, cor.name
               ORDER BY total_bounty DESC''',
            search_locations + search_locations,  # Double the params for origin and dest
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🎯 Bounty Scan Results",
            description=search_description,
            color=0xff6600
        )
        
        total_targets = 0
        
        # Add stationary targets
        if bountied_players:
            location_text = []
            for target_name, total_bounty, bounty_count, location_name, user_id, target_id in bountied_players:
                location_text.append(f"🎯 **{target_name}** at **{location_name}**")
                location_text.append(f"   💰 {total_bounty:,} credits ({bounty_count} bounties)")
                total_targets += 1
            
            embed.add_field(
                name="📍 Stationary Targets",
                value="\n".join(location_text[:15]) + (f"\n*...and {len(location_text)-15} more*" if len(location_text) > 15 else ""),
                inline=False
            )
        
        # Add transit targets
        if transit_bountied:
            transit_text = []
            for target_name, total_bounty, bounty_count, corridor_name, user_id, target_id in transit_bountied:
                transit_text.append(f"🎯 **{target_name}** in transit via **{corridor_name}**")
                transit_text.append(f"   💰 {total_bounty:,} credits ({bounty_count} bounties)")
                total_targets += 1
            
            embed.add_field(
                name="🚀 Targets in Transit",
                value="\n".join(transit_text[:10]) + (f"\n*...and {len(transit_text)-10} more*" if len(transit_text) > 10 else ""),
                inline=False
            )
        
        if total_targets == 0:
            embed.add_field(
                name="No Active Bounties",
                value="No bountied players detected in the scan area.",
                inline=False
            )
            embed.color = 0x808080
        else:
            embed.add_field(
                name="💡 How to Collect",
                value=f"Found **{total_targets}** bountied target{'s' if total_targets != 1 else ''}. Travel to their location and use `/bounty [player]` to attempt capture.",
                inline=False
            )
            
            embed.add_field(
                name="📡 Scan Range",
                value=f"Searched {len(search_locations)} reachable location{'s' if len(search_locations) != 1 else ''} within 3 connection hops.",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _find_reachable_locations(self, start_location_id: int, max_hops: int = 3) -> List[int]:
        """Find all locations reachable within max_hops, excluding ungated corridors"""
        
        if max_hops <= 0:
            return [start_location_id]
        
        visited = set()
        current_level = {start_location_id}
        all_reachable = {start_location_id}
        
        for hop in range(max_hops):
            if not current_level:
                break
                
            next_level = set()
            
            for location_id in current_level:
                if location_id in visited:
                    continue
                visited.add(location_id)
                
                # Get connected locations via gated corridors only
                connected = self.db.execute_query(
                    '''SELECT destination_location FROM corridors 
                       WHERE origin_location = ? AND is_active = 1 
                       AND name NOT LIKE '%Ungated%' ''',
                    (location_id,),
                    fetch='all'
                )
                
                for (dest_id,) in connected:
                    if dest_id not in all_reachable:
                        next_level.add(dest_id)
                        all_reachable.add(dest_id)
            
            current_level = next_level
        
        return list(all_reachable)
    @app_commands.command(name="paybounty", description="Pay towards your active bounties")
    @app_commands.describe(amount="Amount to pay towards your bounties")
    async def pay_bounty(self, interaction: discord.Interaction, amount: int):
        # Check if user has a character
        char_data = self.db.execute_query(
            "SELECT name, money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        char_name, current_money = char_data
        
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Payment amount must be greater than 0!",
                ephemeral=True
            )
            return
        
        if amount > current_money:
            await interaction.response.send_message(
                f"❌ You don't have enough credits! You have {current_money:,}, trying to pay {amount:,}.",
                ephemeral=True
            )
            return
        
        # Get active bounties on this user
        active_bounties = self.db.execute_query(
            '''SELECT bounty_id, setter_id, setter_name, amount
               FROM personal_bounties 
               WHERE target_id = ? AND is_active = 1
               ORDER BY bounty_id ASC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not active_bounties:
            await interaction.response.send_message(
                "❌ You have no active bounties to pay!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Calculate total outstanding bounty amount
        total_bounty_amount = sum(bounty[3] for bounty in active_bounties)
        
        # Get existing payments for these bounties
        bounty_ids = [str(bounty[0]) for bounty in active_bounties]
        existing_payments = self.db.execute_query(
            f'''SELECT bounty_id, SUM(payment_amount) as total_paid
               FROM bounty_payments 
               WHERE bounty_id IN ({','.join(['?' for _ in bounty_ids])})
               GROUP BY bounty_id''',
            bounty_ids,
            fetch='all'
        )
        
        # Create a map of bounty_id -> total_paid
        payments_map = {payment[0]: payment[1] for payment in existing_payments}
        
        # Calculate remaining amount owed per bounty
        bounty_remainders = []
        total_remaining = 0
        
        for bounty_id, setter_id, setter_name, bounty_amount in active_bounties:
            paid_so_far = payments_map.get(bounty_id, 0)
            remaining = max(0, bounty_amount - paid_so_far)
            bounty_remainders.append((bounty_id, setter_id, setter_name, bounty_amount, remaining))
            total_remaining += remaining
        
        if total_remaining == 0:
            await interaction.followup.send(
                "✅ All your bounties have already been paid off! They will be processed shortly.",
                ephemeral=True
            )
            return
        
        # Cap payment to what's actually owed
        actual_payment = min(amount, total_remaining)
        
        # Deduct money from player
        self.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (actual_payment, interaction.user.id)
        )
        
        # Distribute payment proportionally across bounties
        remaining_to_distribute = actual_payment
        payments_made = []
        bounties_completed = []
        
        for bounty_id, setter_id, setter_name, bounty_amount, remaining_owed in bounty_remainders:
            if remaining_owed <= 0:
                continue
            
            # Calculate proportional payment for this bounty
            if total_remaining > 0:
                proportion = remaining_owed / total_remaining
                payment_for_bounty = min(remaining_owed, int(actual_payment * proportion))
                
                # Handle rounding - give any remainder to the last bounty
                if bounty_id == bounty_remainders[-1][0]:  # Last bounty
                    payment_for_bounty = min(remaining_owed, remaining_to_distribute)
            else:
                payment_for_bounty = 0
            
            if payment_for_bounty > 0:
                # Record the payment
                current_time = datetime.datetime.now()
                self.db.execute_query(
                    '''INSERT INTO bounty_payments (bounty_id, payment_amount, paid_at)
                       VALUES (?, ?, ?)''',
                    (bounty_id, payment_for_bounty, current_time.isoformat())
                )
                
                payments_made.append((setter_name, payment_for_bounty, bounty_amount))
                remaining_to_distribute -= payment_for_bounty
                
                # Check if this bounty is now fully paid
                total_paid_for_bounty = payments_map.get(bounty_id, 0) + payment_for_bounty
                if total_paid_for_bounty >= bounty_amount:
                    bounties_completed.append((bounty_id, setter_id, setter_name, bounty_amount, total_paid_for_bounty))
        
        # Process completed bounties
        for bounty_id, setter_id, setter_name, original_amount, total_paid in bounties_completed:
            # Transfer original bounty + overpayment to setter
            transfer_amount = original_amount + total_paid
            
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (transfer_amount, setter_id)
            )
            
            # Mark bounty as inactive (paid off)
            self.db.execute_query(
                "UPDATE personal_bounties SET is_active = 0 WHERE bounty_id = ?",
                (bounty_id,)
            )
            
            # Notify the bounty setter
            setter_member = interaction.guild.get_member(setter_id)
            if setter_member:
                try:
                    notify_embed = discord.Embed(
                        title="💰 Bounty Paid Off",
                        description=f"**{char_name}** has paid off your bounty!",
                        color=0x00ff00
                    )
                    notify_embed.add_field(name="Original Bounty", value=f"{original_amount:,} credits", inline=True)
                    notify_embed.add_field(name="Total Received", value=f"{transfer_amount:,} credits", inline=True)
                    notify_embed.add_field(name="Profit", value=f"{transfer_amount - original_amount:,} credits", inline=True)
                    
                    await setter_member.send(embed=notify_embed)
                except:
                    pass  # Failed to notify
        
        # Create response embed
        embed = discord.Embed(
            title="💳 Bounty Payment Processed",
            description=f"**{char_name}** has made a payment towards active bounties",
            color=0x00ff00 if bounties_completed else 0xffd700
        )
        
        embed.add_field(name="Payment Amount", value=f"{actual_payment:,} credits", inline=True)
        embed.add_field(name="Remaining Credits", value=f"{current_money - actual_payment:,}", inline=True)
        
        if payments_made:
            payment_details = []
            for setter_name, payment, bounty_amount in payments_made:
                payment_details.append(f"• **{setter_name}**: {payment:,} credits")
            
            embed.add_field(
                name="💰 Payments Distributed",
                value="\n".join(payment_details),
                inline=False
            )
        
        if bounties_completed:
            completed_details = []
            for _, _, setter_name, amount, total_paid in bounties_completed:
                profit = total_paid - amount
                completed_details.append(f"• **{setter_name}**: {amount:,} credits + {profit:,} profit")
    @app_commands.command(name="capture", description="Attempt to capture an enemy player for bounty")
    @app_commands.describe(target="The player to attempt to capture")
    async def capture_bounty(self, interaction: discord.Interaction, target: discord.Member):
        # Check if attacker has a character
        attacker_data = self.db.execute_query(
            "SELECT current_location, hp FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not attacker_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
            
        attacker_location, attacker_hp = attacker_data
        
        if not attacker_location:
            await interaction.response.send_message(
                "❌ You must be at a location to attempt captures!",
                ephemeral=True
            )
            return
            
        if attacker_hp <= 0:
            await interaction.response.send_message(
                "❌ You cannot capture anyone while unconscious!",
                ephemeral=True
            )
            return

        # Check if target has a character
        target_data = self.db.execute_query(
            "SELECT current_location, hp, money FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )
        
        if not target_data:
            await interaction.response.send_message(
                "❌ Target doesn't have a character!",
                ephemeral=True
            )
            return
            
        target_location, target_hp, target_money = target_data
        
        if target_hp <= 0:
            await interaction.response.send_message(
                "❌ Target is already unconscious!",
                ephemeral=True
            )
            return

        # Check if both players are in the same location
        if attacker_location != target_location:
            await interaction.response.send_message(
                "❌ You must be in the same location as your target!",
                ephemeral=True
            )
            return

        # Check if target is yourself
        if interaction.user.id == target.id:
            await interaction.response.send_message(
                "❌ You cannot capture yourself!",
                ephemeral=True
            )
            return

        # Get location info
        location_info = self.db.execute_query(
            "SELECT name, channel_id FROM locations WHERE location_id = ?",
            (attacker_location,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message(
                "❌ Invalid location!",
                ephemeral=True
            )
            return
            
        location_name, location_channel_id = location_info

        # Get both players' reputations at current location
        attacker_rep = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (interaction.user.id, attacker_location),
            fetch='one'
        )
        attacker_reputation = attacker_rep[0] if attacker_rep else 0
        
        target_rep = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (target.id, attacker_location),
            fetch='one'
        )
        target_reputation = target_rep[0] if target_rep else 0

        # Check alignments
        attacker_alignment = self.get_reputation_alignment(attacker_reputation)
        target_alignment = self.get_reputation_alignment(target_reputation)
        
        # Check if either player is neutral
        if attacker_alignment == "neutral":
            await interaction.response.send_message(
                f"❌ Your reputation in **{location_name}** is neutral ({attacker_reputation}). You cannot capture players here!",
                ephemeral=True
            )
            return
            
        if target_alignment == "neutral":
            await interaction.response.send_message(
                f"❌ Target's reputation in **{location_name}** is neutral ({target_reputation}). They cannot be captured here!",
                ephemeral=True
            )
            return

        # Check if same alignment
        if attacker_alignment == target_alignment:
            await interaction.response.send_message(
                f"❌ You and your target are both {attacker_alignment}-aligned in **{location_name}**. You cannot capture allies!",
                ephemeral=True
            )
            return

        # Check cooldown
        cooldown_remaining = await self.check_capture_cooldown(interaction.user.id, target.id)
        if cooldown_remaining is not None:
            await interaction.response.send_message(
                f"❌ You must wait {cooldown_remaining} seconds before attempting to capture this player again!",
                ephemeral=True
            )
            return

        # Check if target is travel banned (captured recently)
        travel_ban = await self.check_travel_ban(target.id)
        if travel_ban:
            await interaction.response.send_message(
                f"❌ Target is already captured and cannot be targeted again yet! ({travel_ban})",
                ephemeral=True
            )
            return

        # All checks passed, proceed with capture attempt
        await interaction.response.defer()
        
        # Balanced roll system
        attacker_roll = random.randint(1, 100)
        target_roll = random.randint(1, 100)
        
        capture_successful = attacker_roll > target_roll
        
        if capture_successful:
            await self._handle_successful_capture(
                interaction, target, location_name, location_channel_id,
                attacker_reputation, target_reputation, target_money,
                attacker_roll, target_roll
            )
        else:
            await self._handle_failed_capture(
                interaction, target, location_name, location_channel_id,
                attacker_roll, target_roll
            )

    async def _handle_successful_capture(self, interaction, target, location_name, location_channel_id, 
                                       attacker_reputation, target_reputation, target_money,
                                       attacker_roll, target_roll):
        """Handle a successful capture attempt"""
        
        # Calculate currency reward (target's negative reputation x2)
        currency_reward = abs(target_reputation) * 5
            
        # Transfer target's money
        total_money_reward = currency_reward + target_money
        
        # Update attacker's money
        if total_money_reward > 0:
            self.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (total_money_reward, interaction.user.id)
            )
        
        # Remove target's money
        self.db.execute_query(
            "UPDATE characters SET money = 0 WHERE user_id = ?",
            (target.id,)
        )
        
        # Reduce target's HP by 50%
        target_current_hp = self.db.execute_query(
            "SELECT hp FROM characters WHERE user_id = ?",
            (target.id,),
            fetch='one'
        )[0]
        
        hp_reduction = target_current_hp // 2
        new_hp = max(1, target_current_hp - hp_reduction)  # Don't kill them
        
        self.db.execute_query(
            "UPDATE characters SET hp = ? WHERE user_id = ?",
            (new_hp, target.id)
        )
        
        # Apply reputation bonus to attacker
        reputation_cog = self.bot.get_cog('ReputationCog')
        attacker_alignment = self.get_reputation_alignment(attacker_reputation)
        reputation_change = 10 if attacker_alignment == "good" else -10
        
        if reputation_cog:
            await reputation_cog.update_reputation(
                interaction.user.id, 
                interaction.channel.id if hasattr(interaction.channel, 'id') else 1,  # fallback
                reputation_change
            )
        
        # Apply 1-minute travel ban to target
        ban_until = datetime.datetime.now() + datetime.timedelta(minutes=1)
        self.db.execute_query(
            "INSERT OR REPLACE INTO travel_bans (user_id, ban_until, reason) VALUES (?, ?, ?)",
            (target.id, ban_until.isoformat(), "Captured by opposing faction")
        )
        
        # Create comprehensive capture results embed for location channel
        attacker_alignment_name = "Hero" if attacker_alignment == "good" else "Villain"
        target_alignment_name = "Villain" if attacker_alignment == "good" else "Hero"

        if attacker_alignment == "good":
            embed_title = "⚖️ Justice Served!"
            embed_description = f"🛡️ **{interaction.user.display_name}** has brought the criminal **{target.display_name}** to justice!"
            embed_color = 0x4169E1
            justice_flavor = "The forces of justice have prevailed in this sector."
        else:
            embed_title = "💀 Criminal Victory!"
            embed_description = f"🔥 **{interaction.user.display_name}** has captured the so-called hero **{target.display_name}**!"
            embed_color = 0x8b0000
            justice_flavor = "The criminal underworld grows stronger in this sector."

        capture_embed = discord.Embed(
            title=embed_title,
            description=embed_description,
            color=embed_color
        )

        # Combat results
        capture_embed.add_field(
            name="🎯 Combat Results",
            value=f"**{interaction.user.display_name}** rolled: **{attacker_roll}**\n**{target.display_name}** rolled: **{target_roll}**",
            inline=True
        )

        # Attacker rewards
        capture_embed.add_field(
            name=f"💰 {interaction.user.display_name}'s Rewards",
            value=f"• **{currency_reward:,}** credits (bounty)\n• **{target_money:,}** credits (seized)\n• **Total: {total_money_reward:,}** credits\n• +10 reputation ({attacker_alignment_name} alignment)",
            inline=True
        )

        # Target consequences  
        capture_embed.add_field(
            name=f"💔 {target.display_name}'s Consequences",
            value=f"• Lost **{target_money:,}** credits\n• **{hp_reduction}** HP damage ({target_current_hp} → {new_hp})\n• Cannot travel for **1 minute**",
            inline=True
        )

        # Faction flavor
        capture_embed.add_field(
            name="🏛️ Sector Status",
            value=justice_flavor,
            inline=False
        )

        capture_embed.add_field(
            name="📍 Location",
            value=f"**{location_name}**",
            inline=True
        )

        capture_embed.set_footer(text="Bounty capture complete - all transactions processed")

        # Send to location channel
        if location_channel_id:
            location_channel = self.bot.get_channel(location_channel_id)
            if location_channel:
                try:
                    await location_channel.send(embed=capture_embed)
                except:
                    pass  # Channel send failed

        # Simple ephemeral confirmation to attacker
        await interaction.followup.send("✅ Capture successful!", ephemeral=True)
                
                

    async def _handle_failed_capture(self, interaction, target, location_name, location_channel_id,
                                   attacker_roll, target_roll):
        """Handle a failed capture attempt"""
        
        # Set cooldown for this attacker-target pair
        current_time = datetime.datetime.now()
        self.db.execute_query(
            "INSERT OR REPLACE INTO capture_cooldowns (attacker_id, target_id, attempt_time) VALUES (?, ?, ?)",
            (interaction.user.id, target.id, current_time.isoformat())
        )
        
        # Create public failed capture announcement
        failed_embed = discord.Embed(
            title="❌ Capture Attempt Failed",
            description=f"**{interaction.user.display_name}** attempted to capture **{target.display_name}** but failed!",
            color=0xff4444
        )

        failed_embed.add_field(
            name="🎯 Combat Results",
            value=f"**{interaction.user.display_name}** rolled: **{attacker_roll}**\n**{target.display_name}** rolled: **{target_roll}**",
            inline=True
        )

        failed_embed.add_field(
            name="⏱️ Cooldown",
            value=f"**{interaction.user.display_name}** cannot attempt to capture **{target.display_name}** again for **30 seconds**",
            inline=True
        )

        failed_embed.add_field(
            name="🛡️ Escape Window",
            value=f"**{target.display_name}** has **30 seconds** to escape before another attempt can be made!",
            inline=False
        )

        failed_embed.add_field(
            name="📍 Location",
            value=f"**{location_name}**",
            inline=True
        )

        failed_embed.set_footer(text="Capture attempt failed - 30 second cooldown active")

        # Send to location channel
        if location_channel_id:
            location_channel = self.bot.get_channel(location_channel_id)
            if location_channel:
                try:
                    await location_channel.send(embed=failed_embed)
                except:
                    pass

        # Simple ephemeral confirmation to attacker
        await interaction.followup.send("❌ Capture failed! Results posted in location channel.", ephemeral=True)

    # Replace the existing bounty_status command with this enhanced version:
    @app_commands.command(name="bounty_status", description="Check your bounty capture status and active bounties")
    async def bounty_status(self, interaction: discord.Interaction):
        # Check character exists
        char_data = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "❌ You don't have a character! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        current_location = char_data[0]
        
        embed = discord.Embed(
            title="🎯 Bounty Status Report",
            color=0x4169E1
        )
        
        # Check if user has bounties on them
        bounties_on_user = self.db.execute_query(
            '''SELECT setter_name, amount FROM personal_bounties 
               WHERE target_id = ? AND is_active = 1
               ORDER BY amount DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if bounties_on_user:
            bounty_details = []
            total_owed = 0
            total_paid = 0
            
            for setter_name, amount in bounties_on_user:
                # Get bounty ID to check payments
                bounty_id = self.db.execute_query(
                    '''SELECT bounty_id FROM personal_bounties 
                       WHERE target_id = ? AND setter_name = ? AND amount = ? AND is_active = 1
                       LIMIT 1''',
                    (interaction.user.id, setter_name, amount),
                    fetch='one'
                )
                
                if bounty_id:
                    payments_made = self.db.execute_query(
                        '''SELECT COALESCE(SUM(payment_amount), 0) FROM bounty_payments 
                           WHERE bounty_id = ?''',
                        (bounty_id[0],),
                        fetch='one'
                    )[0]
                    
                    remaining = max(0, amount - payments_made)
                    total_owed += remaining
                    total_paid += payments_made
                    
                    if payments_made > 0:
                        bounty_details.append(f"• **{setter_name}**: {remaining:,}/{amount:,} credits remaining")
                    else:
                        bounty_details.append(f"• **{setter_name}**: {amount:,} credits")
                else:
                    bounty_details.append(f"• **{setter_name}**: {amount:,} credits")
                    total_owed += amount
            
            status_text = f"**Total Owed: {total_owed:,} credits**"
            if total_paid > 0:
                status_text += f"\n*{total_paid:,} credits already paid*"
            
            status_text += "\n" + "\n".join(bounty_details)
            
            embed.add_field(
                name="🎯 Active Bounties",
                value=status_text,
                inline=False
            )
            
            if total_owed > 0:
                embed.add_field(
                    name="💳 Payment Options",
                    value="Use `/paybounty [amount]` to pay towards your bounties and reduce capture risk.",
                    inline=False
                )
        else:
            embed.add_field(
                name="🎯 Bounties On You",
                value="No active bounties",
                inline=False
            )
        
        # Check bounties set by user
        bounties_set = self.db.execute_query(
            '''SELECT target_name, amount FROM personal_bounties 
               WHERE setter_id = ? AND is_active = 1
               ORDER BY amount DESC''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if bounties_set:
            bounty_text = []
            for target_name, amount in bounties_set[:5]:
                bounty_text.append(f"• **{target_name}**: {amount:,} credits")
            
            if len(bounties_set) > 5:
                bounty_text.append(f"...and {len(bounties_set) - 5} more")
            
            embed.add_field(
                name="💰 Bounties You've Set",
                value="\n".join(bounty_text),
                inline=False
            )
        
        # Check travel ban
        travel_ban = await self.check_travel_ban(interaction.user.id)
        if travel_ban:
            embed.add_field(
                name="🚫 Travel Restriction",
                value=travel_ban,
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Travel Status",
                value="No travel restrictions",
                inline=False
            )
        
        # Check active cooldowns
        cooldowns = self.db.execute_query(
            """SELECT c.name, cc.attempt_time 
               FROM capture_cooldowns cd
               JOIN characters c ON cd.target_id = c.user_id
               WHERE cd.attacker_id = ?""",
            (interaction.user.id,),
            fetch='all'
        )
        
        if cooldowns:
            cooldown_text = []
            current_time = datetime.datetime.now()
            
            for target_name, attempt_time_str in cooldowns:
                attempt_time = datetime.datetime.fromisoformat(attempt_time_str)
                time_diff = current_time - attempt_time
                
                if time_diff.total_seconds() < 30:
                    remaining = int(30 - time_diff.total_seconds())
                    cooldown_text.append(f"• **{target_name}**: {remaining}s remaining")
            
            if cooldown_text:
                embed.add_field(
                    name="⏱️ Capture Cooldowns",
                    value="\n".join(cooldown_text),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Hook into travel commands to check travel bans
    async def cog_load(self):
        """Called when the cog is loaded"""
        # We'll need to modify the travel cog to check for travel bans
        print("🎯 Bounty Capture system loaded")

async def setup(bot):
    await bot.add_cog(BountyCog(bot))
    print("🎯 Bounty Capture cog loaded successfully")
    
