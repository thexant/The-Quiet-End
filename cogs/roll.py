# cogs/roll.py
import discord
from discord.ext import commands
from discord import app_commands
import random

class RollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.command(name='roll')
    async def roll_prefix(self, ctx, stat: str = None):
        """Roll 1-100, optionally adding a character stat"""
        await self._handle_roll(ctx, stat, is_slash=False)

    @app_commands.command(name='roll', description='Roll 1-100, optionally adding a character stat')
    @app_commands.describe(stat='Optional stat to add: navigation, engineering, combat, or medical')
    @app_commands.choices(stat=[
        app_commands.Choice(name='Navigation', value='navigation'),
        app_commands.Choice(name='Engineering', value='engineering'),
        app_commands.Choice(name='Combat', value='combat'),
        app_commands.Choice(name='Medical', value='medical')
    ])
    async def roll_slash(self, interaction: discord.Interaction, stat: str = None):
        """Roll 1-100, optionally adding a character stat"""
        await self._handle_roll(interaction, stat, is_slash=True)

    async def _handle_roll(self, ctx_or_interaction, stat: str = None, is_slash: bool = True):
        """Handle both slash and prefix command logic"""
        user_id = ctx_or_interaction.user.id if is_slash else ctx_or_interaction.author.id
        
        # Base roll
        base_roll = random.randint(1, 100)
        total_roll = base_roll
        stat_bonus = 0
        
        # Get stat bonus if requested
        if stat and stat.lower() in ['navigation', 'engineering', 'combat', 'medical']:
            char_data = self.db.execute_query(
                "SELECT navigation, engineering, combat, medical FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            if char_data:
                # Map stat names to column indices
                stat_mapping = {
                    'navigation': 0,
                    'engineering': 1,
                    'combat': 2,
                    'medical': 3
                }
                stat_value = char_data[stat_mapping[stat.lower()]]
                stat_bonus = stat_value
                total_roll = base_roll + stat_bonus
            
        # Format the result
        if stat_bonus > 0:
            result_text = f"🎲 **{base_roll}** + {stat.title()} **{stat_bonus}** = **{total_roll}**"
        else:
            result_text = f"🎲 **{base_roll}**"
            
        if is_slash:
            await ctx_or_interaction.response.send_message(result_text, ephemeral=False)
        else:
            await ctx_or_interaction.send(result_text)

async def setup(bot):
    await bot.add_cog(RollCog(bot))