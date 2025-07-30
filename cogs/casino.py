# cogs/casino.py

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from datetime import datetime, timedelta


class CasinoRoleplayMessages:
    """Roleplay messages for casino games"""
    
    SLOT_WIN_MESSAGES = [
        "lights up the casino with a triumphant spin!",
        "hits the jackpot as credits rain down!",
        "celebrates as the reels align perfectly!",
        "strikes it rich on the slot machine!",
        "watches the symbols line up for a stellar win!",
        "scores big on the cosmic slots!",
        "hits pay dirt on the space station slots!"
    ]
    
    SLOT_LOSS_MESSAGES = [
        "watches the reels spin to a disappointing stop.",
        "sees their credits vanish into the machine's void.",
        "shakes their head as the symbols fail to align.",
        "experiences the harsh reality of space gambling.",
        "feeds more credits to the hungry slot machine.",
        "learns that the house always wins in the stars.",
        "watches their fortune slip away on the reels."
    ]
    
    BLACKJACK_WIN_MESSAGES = [
        "outplays the dealer in a tense hand!",
        "celebrates a perfect blackjack victory!",
        "beats the house with stellar card skills!",
        "emerges victorious from the card tables!",
        "shows the dealer who's boss!",
        "wins big with a masterful blackjack hand!",
        "proves their luck among the stars!"
    ]
    
    BLACKJACK_LOSS_MESSAGES = [
        "busts and loses their bet to the dealer.",
        "watches the dealer claim another victory.",
        "gets outplayed at the blackjack table.",
        "learns a costly lesson about card counting.",
        "falls victim to the house edge.",
        "sees their credits swept away by the dealer.",
        "discovers that luck wasn't on their side."
    ]
    
    BLACKJACK_PUSH_MESSAGES = [
        "ties with the dealer in a tense standoff!",
        "matches the dealer's hand perfectly!",
        "walks away even after a close hand.",
        "neither wins nor loses against the house.",
        "experiences the rare tie at blackjack!"
    ]
    
    DICE_WIN_MESSAGES = [
        "rolls the dice to victory!",
        "predicts the future and wins big!",
        "shows incredible intuition with the dice!",
        "beats the odds with a perfect prediction!",
        "demonstrates cosmic luck with the roll!",
        "calls it right and claims their prize!",
        "proves their gambling instincts are sharp!"
    ]
    
    DICE_LOSS_MESSAGES = [
        "watches their prediction crumble with the dice.",
        "learns that predicting dice is harder than it looks.",
        "sees their credits roll away with bad luck.",
        "discovers that fortune doesn't favor them today.",
        "makes the wrong call on the cosmic dice.",
        "experiences the cruel randomness of chance.",
        "finds out that the dice have their own plans."
    ]
    
    DICE_PUSH_MESSAGES = [
        "hits the lucky seven for a push!",
        "rolls exactly seven - neither win nor loss!",
        "experiences the mysterious power of seven!",
        "gets their bet back with a neutral roll!"
    ]


class SlotMachineView(discord.ui.View):
    """Slot machine gambling game"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.bet_amount = 50
        self.symbols = ['🍒', '🍋', '🍊', '💎', '🎰']
        self.payouts = {'🍒': 2, '🍋': 3, '🍊': 5, '💎': 10, '🎰': 20}
        self.update_buttons()
    
    async def send_roleplay_feedback(self, interaction: discord.Interaction, message_type: str, bet_amount: int, winnings: int = 0):
        """Send non-ephemeral roleplay feedback to the channel"""
        try:
            # Get character name
            char_info = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_info:
                return
            
            char_name = char_info[0]
            
            # Select appropriate message
            if message_type == "slot_win":
                action = random.choice(CasinoRoleplayMessages.SLOT_WIN_MESSAGES)
                description = f"**{char_name}** {action}\n💰 *Won {winnings:,} credits betting {bet_amount:,} on slots!*"
                color = 0x00FF00  # Green
            elif message_type == "slot_loss":
                action = random.choice(CasinoRoleplayMessages.SLOT_LOSS_MESSAGES)
                description = f"**{char_name}** {action}\n💸 *Lost {bet_amount:,} credits on the slot machine.*"
                color = 0xFF6B6B  # Soft red
            else:
                return
            
            # Create embed for roleplay feedback
            embed = discord.Embed(
                title="🎰 Casino Action",
                description=description,
                color=color
            )
            embed.set_footer(text="🎲 Live from the casino floor")
            
            # Send to channel (non-ephemeral)
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            # Silently fail to avoid breaking the game
            print(f"Failed to send casino roleplay feedback: {e}")
    
    def update_buttons(self):
        self.clear_items()
        
        # Bet amount controls
        decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.bet_amount <= 10))
        decrease_btn.callback = self.decrease_bet
        self.add_item(decrease_btn)
        
        bet_btn = discord.ui.Button(label=f"Bet: {self.bet_amount:,}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(bet_btn)
        
        increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.bet_amount >= 1000))
        increase_btn.callback = self.increase_bet
        self.add_item(increase_btn)
        
        # Spin button
        spin_btn = discord.ui.Button(label="🎰 SPIN!", style=discord.ButtonStyle.success, row=1)
        spin_btn.callback = self.spin_slots
        self.add_item(spin_btn)
        
        # Exit button
        exit_btn = discord.ui.Button(label="🚪 Exit Slots", style=discord.ButtonStyle.danger, row=1)
        exit_btn.callback = self.exit_game
        self.add_item(exit_btn)
    
    async def decrease_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.bet_amount = max(10, self.bet_amount - 10)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.bet_amount = min(1000, self.bet_amount + 10)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def spin_slots(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Check balance
        balance = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not balance or balance[0] < self.bet_amount:
            await interaction.response.send_message("❌ Insufficient credits!", ephemeral=True)
            return
        
        # Deduct bet
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.bet_amount, interaction.user.id)
        )
        
        # Spin the slots
        result = [random.choice(self.symbols) for _ in range(3)]
        
        # Check for win
        winnings = 0
        if result[0] == result[1] == result[2]:
            multiplier = self.payouts[result[0]]
            winnings = self.bet_amount * multiplier
            
            # Add winnings
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (winnings, interaction.user.id)
            )
        
        # Create result embed
        if winnings > 0:
            embed = discord.Embed(
                title="🎰 WINNER! 🎰",
                description=f"**Result:** {' '.join(result)}\n\n"
                           f"**Bet:** {self.bet_amount:,} credits\n"
                           f"**Won:** {winnings:,} credits\n"
                           f"**Profit:** +{winnings - self.bet_amount:,} credits",
                color=0x00FF00
            )
        else:
            embed = discord.Embed(
                title="🎰 Slot Machine",
                description=f"**Result:** {' '.join(result)}\n\n"
                           f"**Bet:** {self.bet_amount:,} credits\n"
                           f"**Won:** 0 credits\n"
                           f"**Loss:** -{self.bet_amount:,} credits",
                color=0xFF0000
            )
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send roleplay feedback to channel
        if winnings > 0:
            await self.send_roleplay_feedback(interaction, "slot_win", self.bet_amount, winnings)
        else:
            await self.send_roleplay_feedback(interaction, "slot_loss", self.bet_amount)
    
    async def exit_game(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎰 Slot Machine - Goodbye",
            description="Thanks for playing the slots! Your luck awaits you in the stars.",
            color=0x888888
        )
        await interaction.response.edit_message(embed=embed, view=None)

class BlackjackView(discord.ui.View):
    """Blackjack gambling game"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.bet_amount = 50
        self.player_cards = []
        self.dealer_cards = []
        self.game_active = False
        self.deck = self.create_deck()
        self.update_buttons()
    
    async def send_roleplay_feedback(self, interaction: discord.Interaction, message_type: str, bet_amount: int, winnings: int = 0):
        """Send non-ephemeral roleplay feedback to the channel"""
        try:
            # Get character name
            char_info = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_info:
                return
            
            char_name = char_info[0]
            
            # Select appropriate message
            if message_type == "blackjack_win":
                action = random.choice(CasinoRoleplayMessages.BLACKJACK_WIN_MESSAGES)
                description = f"**{char_name}** {action}\n💰 *Won {winnings:,} credits betting {bet_amount:,} at blackjack!*"
                color = 0x00FF00  # Green
            elif message_type == "blackjack_loss":
                action = random.choice(CasinoRoleplayMessages.BLACKJACK_LOSS_MESSAGES)
                description = f"**{char_name}** {action}\n💸 *Lost {bet_amount:,} credits at the blackjack table.*"
                color = 0xFF6B6B  # Soft red
            elif message_type == "blackjack_push":
                action = random.choice(CasinoRoleplayMessages.BLACKJACK_PUSH_MESSAGES)
                description = f"**{char_name}** {action}\n🤝 *Pushed {bet_amount:,} credits at blackjack.*"
                color = 0xFFD700  # Gold
            else:
                return
            
            # Create embed for roleplay feedback
            embed = discord.Embed(
                title="🃏 Casino Action",
                description=description,
                color=color
            )
            embed.set_footer(text="🎲 Live from the casino floor")
            
            # Send to channel (non-ephemeral)
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            # Silently fail to avoid breaking the game
            print(f"Failed to send casino roleplay feedback: {e}")
    
    def create_deck(self):
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        return [f"{rank}{suit}" for suit in suits for rank in ranks]
    
    def card_value(self, card):
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 11
        else:
            return int(rank)
    
    def hand_value(self, cards):
        value = sum(self.card_value(card) for card in cards)
        aces = sum(1 for card in cards if card[:-1] == 'A')
        
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        
        return value
    
    def update_buttons(self):
        self.clear_items()
        
        if not self.game_active:
            # Bet controls
            decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.bet_amount <= 10))
            decrease_btn.callback = self.decrease_bet
            self.add_item(decrease_btn)
            
            bet_btn = discord.ui.Button(label=f"Bet: {self.bet_amount:,}", style=discord.ButtonStyle.primary, disabled=True)
            self.add_item(bet_btn)
            
            increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.bet_amount >= 1000))
            increase_btn.callback = self.increase_bet
            self.add_item(increase_btn)
            
            # Deal button
            deal_btn = discord.ui.Button(label="🃏 Deal Cards", style=discord.ButtonStyle.success, row=1)
            deal_btn.callback = self.deal_cards
            self.add_item(deal_btn)
        else:
            # Game controls
            hit_btn = discord.ui.Button(label="🎯 Hit", style=discord.ButtonStyle.primary)
            hit_btn.callback = self.hit
            self.add_item(hit_btn)
            
            stand_btn = discord.ui.Button(label="🛑 Stand", style=discord.ButtonStyle.secondary)
            stand_btn.callback = self.stand
            self.add_item(stand_btn)
        
        # Exit button
        exit_btn = discord.ui.Button(label="🚪 Exit Blackjack", style=discord.ButtonStyle.danger, row=2)
        exit_btn.callback = self.exit_game
        self.add_item(exit_btn)
    
    async def decrease_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.bet_amount = max(10, self.bet_amount - 10)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.bet_amount = min(1000, self.bet_amount + 10)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def deal_cards(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Check balance
        balance = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not balance or balance[0] < self.bet_amount:
            await interaction.response.send_message("❌ Insufficient credits!", ephemeral=True)
            return
        
        # Deduct bet
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.bet_amount, interaction.user.id)
        )
        
        # Reset and shuffle deck
        self.deck = self.create_deck()
        random.shuffle(self.deck)
        
        # Deal initial cards
        self.player_cards = [self.deck.pop(), self.deck.pop()]
        self.dealer_cards = [self.deck.pop(), self.deck.pop()]
        self.game_active = True
        
        # Check for blackjack
        player_value = self.hand_value(self.player_cards)
        dealer_value = self.hand_value(self.dealer_cards)
        
        if player_value == 21:
            await self.end_game(interaction, "blackjack")
            return
        
        self.update_buttons()
        embed = self.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def hit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.player_cards.append(self.deck.pop())
        player_value = self.hand_value(self.player_cards)
        
        if player_value > 21:
            await self.end_game(interaction, "bust")
        else:
            embed = self.create_game_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def stand(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Dealer plays
        while self.hand_value(self.dealer_cards) < 17:
            self.dealer_cards.append(self.deck.pop())
        
        await self.end_game(interaction, "compare")
    
    async def end_game(self, interaction: discord.Interaction, result_type: str):
        self.game_active = False
        player_value = self.hand_value(self.player_cards)
        dealer_value = self.hand_value(self.dealer_cards)
        
        winnings = 0
        result_text = ""
        
        if result_type == "blackjack":
            winnings = int(self.bet_amount * 2.5)
            result_text = "🎉 BLACKJACK! 🎉"
        elif result_type == "bust":
            result_text = "💥 BUST! You went over 21!"
        elif result_type == "compare":
            if dealer_value > 21:
                winnings = self.bet_amount * 2
                result_text = "🎉 Dealer busted! You win!"
            elif player_value > dealer_value:
                winnings = self.bet_amount * 2
                result_text = "🎉 You win!"
            elif player_value == dealer_value:
                winnings = self.bet_amount
                result_text = "🤝 Push! It's a tie!"
            else:
                result_text = "😔 Dealer wins!"
        
        if winnings > 0:
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (winnings, interaction.user.id)
            )
        
        embed = self.create_final_embed(result_text, winnings)
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send roleplay feedback to channel
        if winnings > self.bet_amount:
            await self.send_roleplay_feedback(interaction, "blackjack_win", self.bet_amount, winnings)
        elif winnings == self.bet_amount:
            await self.send_roleplay_feedback(interaction, "blackjack_push", self.bet_amount, winnings)
        else:
            await self.send_roleplay_feedback(interaction, "blackjack_loss", self.bet_amount)
    
    def create_game_embed(self):
        player_value = self.hand_value(self.player_cards)
        dealer_shown = self.dealer_cards[0]
        
        embed = discord.Embed(
            title="🃏 Blackjack",
            description=f"**Your Cards:** {' '.join(self.player_cards)} (Value: {player_value})\n"
                       f"**Dealer Shows:** {dealer_shown}\n\n"
                       f"**Bet:** {self.bet_amount:,} credits",
            color=0x000000
        )
        return embed
    
    def create_final_embed(self, result_text: str, winnings: int):
        player_value = self.hand_value(self.player_cards)
        dealer_value = self.hand_value(self.dealer_cards)
        
        embed = discord.Embed(
            title="🃏 Blackjack - Game Over",
            description=f"**{result_text}**\n\n"
                       f"**Your Cards:** {' '.join(self.player_cards)} (Value: {player_value})\n"
                       f"**Dealer Cards:** {' '.join(self.dealer_cards)} (Value: {dealer_value})\n\n"
                       f"**Bet:** {self.bet_amount:,} credits\n"
                       f"**Won:** {winnings:,} credits\n"
                       f"**Net:** {'+' if winnings >= self.bet_amount else ''}{winnings - self.bet_amount:,} credits",
            color=0x00FF00 if winnings >= self.bet_amount else 0xFF0000
        )
        return embed
    
    async def exit_game(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🃏 Blackjack - Goodbye",
            description="Thanks for playing blackjack! May the cards be with you.",
            color=0x888888
        )
        await interaction.response.edit_message(embed=embed, view=None)

class DiceGameView(discord.ui.View):
    """Dice gambling game"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.bet_amount = 50
        self.prediction = None
        self.update_buttons()
    
    async def send_roleplay_feedback(self, interaction: discord.Interaction, message_type: str, bet_amount: int, winnings: int = 0):
        """Send non-ephemeral roleplay feedback to the channel"""
        try:
            # Get character name
            char_info = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = ?",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_info:
                return
            
            char_name = char_info[0]
            
            # Select appropriate message
            if message_type == "dice_win":
                action = random.choice(CasinoRoleplayMessages.DICE_WIN_MESSAGES)
                description = f"**{char_name}** {action}\n💰 *Won {winnings:,} credits betting {bet_amount:,} on dice!*"
                color = 0x00FF00  # Green
            elif message_type == "dice_loss":
                action = random.choice(CasinoRoleplayMessages.DICE_LOSS_MESSAGES)
                description = f"**{char_name}** {action}\n💸 *Lost {bet_amount:,} credits on the dice table.*"
                color = 0xFF6B6B  # Soft red
            elif message_type == "dice_push":
                action = random.choice(CasinoRoleplayMessages.DICE_PUSH_MESSAGES)
                description = f"**{char_name}** {action}\n🎲 *Pushed {bet_amount:,} credits on dice.*"
                color = 0xFFD700  # Gold
            else:
                return
            
            # Create embed for roleplay feedback
            embed = discord.Embed(
                title="🎲 Casino Action",
                description=description,
                color=color
            )
            embed.set_footer(text="🎲 Live from the casino floor")
            
            # Send to channel (non-ephemeral)
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            # Silently fail to avoid breaking the game
            print(f"Failed to send casino roleplay feedback: {e}")
    
    def update_buttons(self):
        self.clear_items()
        
        # Bet controls
        decrease_btn = discord.ui.Button(label="-", style=discord.ButtonStyle.secondary, disabled=(self.bet_amount <= 10))
        decrease_btn.callback = self.decrease_bet
        self.add_item(decrease_btn)
        
        bet_btn = discord.ui.Button(label=f"Bet: {self.bet_amount:,}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(bet_btn)
        
        increase_btn = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, disabled=(self.bet_amount >= 1000))
        increase_btn.callback = self.increase_bet
        self.add_item(increase_btn)
        
        # Prediction buttons
        high_btn = discord.ui.Button(label="📈 HIGH (8-12)", style=discord.ButtonStyle.success, row=1)
        high_btn.callback = self.bet_high
        self.add_item(high_btn)
        
        low_btn = discord.ui.Button(label="📉 LOW (2-6)", style=discord.ButtonStyle.danger, row=1)
        low_btn.callback = self.bet_low
        self.add_item(low_btn)
        
        # Exit button
        exit_btn = discord.ui.Button(label="🚪 Exit Dice", style=discord.ButtonStyle.secondary, row=2)
        exit_btn.callback = self.exit_game
        self.add_item(exit_btn)
    
    async def decrease_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.bet_amount = max(10, self.bet_amount - 10)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.bet_amount = min(1000, self.bet_amount + 10)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def bet_high(self, interaction: discord.Interaction):
        await self.roll_dice(interaction, "high")
    
    async def bet_low(self, interaction: discord.Interaction):
        await self.roll_dice(interaction, "low")
    
    async def roll_dice(self, interaction: discord.Interaction, prediction: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Check balance
        balance = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not balance or balance[0] < self.bet_amount:
            await interaction.response.send_message("❌ Insufficient credits!", ephemeral=True)
            return
        
        # Deduct bet
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - ? WHERE user_id = ?",
            (self.bet_amount, interaction.user.id)
        )
        
        # Roll dice
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        total = die1 + die2
        
        # Determine result
        winnings = 0
        result_text = ""
        
        if total == 7:
            # Push - return bet
            winnings = self.bet_amount
            result_text = "🤝 Lucky 7! It's a push!"
            color = 0xFFFF00
        elif (prediction == "high" and total >= 8) or (prediction == "low" and total <= 6):
            # Win
            winnings = self.bet_amount * 2
            result_text = "🎉 You guessed correctly!"
            color = 0x00FF00
        else:
            # Lose
            result_text = "😔 Wrong guess!"
            color = 0xFF0000
        
        if winnings > 0:
            self.bot.db.execute_query(
                "UPDATE characters SET money = money + ? WHERE user_id = ?",
                (winnings, interaction.user.id)
            )
        
        # Create result embed
        embed = discord.Embed(
            title="🎲 Dice Roll Results",
            description=f"**Dice:** {die1} + {die2} = **{total}**\n"
                       f"**Your Guess:** {prediction.upper()}\n\n"
                       f"**{result_text}**\n\n"
                       f"**Bet:** {self.bet_amount:,} credits\n"
                       f"**Won:** {winnings:,} credits\n"
                       f"**Net:** {'+' if winnings >= self.bet_amount else ''}{winnings - self.bet_amount:,} credits",
            color=color
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send roleplay feedback to channel
        if total == 7:
            await self.send_roleplay_feedback(interaction, "dice_push", self.bet_amount, winnings)
        elif winnings > self.bet_amount:
            await self.send_roleplay_feedback(interaction, "dice_win", self.bet_amount, winnings)
        else:
            await self.send_roleplay_feedback(interaction, "dice_loss", self.bet_amount)
    
    async def exit_game(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎲 Dice Game - Goodbye",
            description="Thanks for rolling the dice! Fortune favors the bold.",
            color=0x888888
        )
        await interaction.response.edit_message(embed=embed, view=None)

class CasinoCog(commands.Cog):
    """Casino gambling functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    def create_slot_machine_view(self, user_id: int):
        """Create a slot machine view for sub-location integration"""
        return SlotMachineView(self.bot, user_id)
    
    def create_blackjack_view(self, user_id: int):
        """Create a blackjack view for sub-location integration"""
        return BlackjackView(self.bot, user_id)
    
    def create_dice_game_view(self, user_id: int):
        """Create a dice game view for sub-location integration"""
        return DiceGameView(self.bot, user_id)

async def setup(bot):
    await bot.add_cog(CasinoCog(bot))