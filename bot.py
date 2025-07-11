# main.py
import discord
from discord.ext import commands
import asyncio
import os
from database import Database

# Try to load configuration
try:
    from config import BOT_CONFIG, DISCORD_CONFIG
    BOT_TOKEN = BOT_CONFIG.get('token', 'YOUR_BOT_TOKEN')
    COMMAND_PREFIX = BOT_CONFIG.get('command_prefix', '!')
    ACTIVITY_NAME = BOT_CONFIG.get('activity_name', 'in the void of space')
except ImportError:
    print("⚠️ config.py not found, using defaults")
    BOT_TOKEN = os.getenv('DISCORD_TOKEN', 'YOUR_BOT_TOKEN')
    COMMAND_PREFIX = '!'
    ACTIVITY_NAME = 'in the void of space'

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class RPGBot(commands.Bot):
    def __init__(self):
        activity = discord.Activity(type=discord.ActivityType.playing, name=ACTIVITY_NAME)
        super().__init__(
            command_prefix=COMMAND_PREFIX, 
            intents=intents,
            activity=activity,
            help_command=None  # We'll use slash commands primarily
        )
        self.db = Database()
        import logging
        self.logger = logging.getLogger('RPGBot')
        # Don't initialize activity tracker here - move to setup_hook
        self.activity_tracker = None
        self.income_task = None
    async def setup_hook(self):
        """Load all cogs"""
        # Initialize activity tracker here where async context is available
        from utils.activity_tracker import ActivityTracker
        self.activity_tracker = ActivityTracker(self)
        cogs = [
            'cogs.character',
            'cogs.travel', 
            'cogs.economy',
            'cogs.admin',
            'cogs.groups',
            'cogs.events',
            'cogs.galaxy_generator',
            'cogs.radio',
            'cogs.combat',
            'cogs.corridor_events',
            'cogs.enhanced_events',
            'cogs.location_logs',
            'cogs.ship_systems',
            'cogs.time_cog',
            'cogs.sub_locations',
            'cogs.help',
            'cogs.item_usage',
            'cogs.galactic_news',
            'cogs.location_ownership',
            'cogs.npcs',
            'cogs.npc_interactions',
            'cogs.web_map',
            'cogs.reputation',
        ]
        
        print("🔧 Loading cogs...")
        loaded_count = 0
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"  ✅ {cog}")
                loaded_count += 1
            except Exception as e:
                print(f"  ❌ {cog}: {e}")
        
        print(f"📦 Loaded {loaded_count}/{len(cogs)} cogs")
        self.income_task = self.loop.create_task(self.generate_location_income())
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            print(f"🔄 Synced {len(synced)} slash commands")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
    
    async def on_ready(self):
        print(f'🚀 {self.user} has landed in human space!')
        print(f'🌍 Connected to {len(self.guilds)} guild(s)')
        
        for guild in self.guilds:
            print(f"  - {guild.name} ({guild.id})")
        
        # Check if galaxy exists
        location_count = self.db.execute_query(
            "SELECT COUNT(*) FROM locations",
            fetch='one'
        )[0]
        
        if location_count == 0:
            print("🌌 No locations found - use `/galaxy generate` to create the galaxy")
        else:
            print(f"🗺️ Galaxy contains {location_count} locations")
            
            # Start automatic corridor shifts if galaxy exists
            galaxy_cog = self.get_cog('GalaxyGeneratorCog')
            if galaxy_cog and hasattr(galaxy_cog, '_auto_corridor_shift_loop'):
                if not hasattr(galaxy_cog, 'auto_shift_task') or galaxy_cog.auto_shift_task is None or galaxy_cog.auto_shift_task.done():
                    galaxy_cog.auto_shift_task = self.loop.create_task(galaxy_cog._auto_corridor_shift_loop())
                    print("🌌 Automatic corridor shift system initialized")
    
    async def on_command_error(self, ctx, error):
        """Handle command errors gracefully"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        print(f"Command error in {ctx.command}: {error}")
        
        if hasattr(ctx, 'send'):
            try:
                await ctx.send(f"An error occurred: {str(error)}", ephemeral=True)
            except:
                pass
    
    async def on_application_command_error(self, interaction, error):
        """Handle slash command errors"""
        print(f"Slash command error: {error}")
        
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    f"An error occurred: {str(error)}", 
                    ephemeral=True
                )
            except:
                pass
    async def on_interaction(self, interaction: discord.Interaction):
        """Track user activity on any interaction"""
        if interaction.user and not interaction.user.bot:
            # Check if user has a logged-in character
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = ? AND is_logged_in = 1",
                (interaction.user.id,),
                fetch='one'
            )
            if char_check:
                self.activity_tracker.update_activity(interaction.user.id)

    async def on_message(self, message):
        """Track user activity on messages"""
        if message.author and not message.author.bot:
            # Check if user has a logged-in character
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = ? AND is_logged_in = 1",
                (message.author.id,),
                fetch='one'
            )
            if char_check:
                self.activity_tracker.update_activity(message.author.id)
        
        await self.process_commands(message)
    async def generate_location_income(self):
        """Generate passive income for owned locations every hour"""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                # Get all owned locations with their upgrade data
                owned_locations = self.db.execute_query(
                    '''SELECT lo.location_id, lo.owner_id, l.wealth_level, l.population,
                              l.location_type, l.name
                       FROM location_ownership lo
                       JOIN locations l ON lo.location_id = l.location_id''',
                    fetch='all'
                )
                
                for location_data in owned_locations:
                    location_id, owner_id, wealth_level, population, location_type, name = location_data
                    
                    # Calculate base income
                    base_income = wealth_level * 10 + (population // 100)
                    
                    # Get upgrade bonuses
                    upgrades = self.db.execute_query(
                        "SELECT upgrade_type, upgrade_level FROM location_upgrades WHERE location_id = ?",
                        (location_id,),
                        fetch='all'
                    )
                    
                    income_multiplier = 1.0
                    for upgrade_type, level in upgrades:
                        if upgrade_type == 'wealth':
                            income_multiplier += level * 0.2
                        elif upgrade_type == 'population':
                            income_multiplier += level * 0.1
                    
                    final_income = int(base_income * income_multiplier)
                    
                    if final_income > 0:
                        # Record income
                        self.db.execute_query(
                            '''INSERT INTO location_income_log 
                               (location_id, income_type, amount)
                               VALUES (?, 'passive', ?)''',
                            (location_id, final_income)
                        )
                
            except Exception as e:
                print(f"Error generating location income: {e}")
            
            # Wait 1 hour
            await asyncio.sleep(3600)
# Run the bot
bot = RPGBot()

if __name__ == "__main__":
    # Check if token is configured
    if BOT_TOKEN == 'YOUR_BOT_TOKEN' or not BOT_TOKEN or BOT_TOKEN.strip() == '':
        print("❌ Bot token not configured!")
        print("📝 Please edit config.py or set DISCORD_TOKEN environment variable")
        print("🔗 Get a token from: https://discord.com/developers/applications")
    else:
        print("🎮 Starting Discord RPG Bot...")
        try:
            bot.run(BOT_TOKEN)
        except discord.LoginFailure:
            print("❌ Invalid bot token!")
            print("🔗 Please check your token at: https://discord.com/developers/applications")
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")