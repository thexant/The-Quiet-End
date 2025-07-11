# main.py
import discord
from discord.ext import commands
import asyncio
import os
from database import Database
import logging
from utils.activity_tracker import ActivityTracker
import random
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
        self.db = Database()
        activity = discord.Activity(type=discord.ActivityType.playing, name=ACTIVITY_NAME)
        super().__init__(
            command_prefix=COMMAND_PREFIX, 
            intents=intents,
            activity=activity,
            help_command=None  # We'll use slash commands primarily
        )
        self.logger = logging.getLogger('RPGBot')
        # Don't initialize activity tracker here - move to setup_hook
        self.activity_tracker = None
        self.income_task = None
    async def setup_hook(self):
        """This function is called when the bot is preparing to start."""
        try:
            print("📊 Initializing activity tracker...")
            # Initialize the activity tracker BEFORE trying to use it
            self.activity_tracker = ActivityTracker(self)
            print("✅ Activity tracker initialized")
            
            # Cancel existing tasks if they exist
            if hasattr(self, 'monitor_task') and self.monitor_task and not self.monitor_task.done():
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            
            if hasattr(self, 'income_task') and self.income_task and not self.income_task.done():
                self.income_task.cancel()
                try:
                    await self.income_task
                except asyncio.CancelledError:
                    pass
            
            print("🧩 Loading cogs...")
            # Load all cogs from the 'cogs' directory
            loaded_cogs = 0
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py') and not filename.startswith('_'):
                    cog_name = filename[:-3]  # Remove .py extension
                    try:
                        print(f"  Loading {cog_name}...")
                        await self.load_extension(f'cogs.{cog_name}')
                        loaded_cogs += 1
                        print(f"  ✅ {cog_name} loaded")
                    except Exception as e:
                        print(f"  ❌ Failed to load {cog_name}: {e}")
                        import traceback
                        traceback.print_exc()
            
            print(f"✅ Loaded {loaded_cogs} cogs successfully")
            
            # Start background monitoring tasks AFTER cogs are loaded
            print("🔄 Starting background tasks...")
            self.monitor_task = self.loop.create_task(self.activity_tracker.monitor_activity())
            self.income_task = self.loop.create_task(self.generate_location_income())
            print("✅ Background tasks started")
            
            print("🎮 Bot setup complete!")
            
        except Exception as e:
            print(f"❌ Error in setup_hook: {e}")
            import traceback
            traceback.print_exc()
            raise
        
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
            
            # Don't start auto corridor shifts here - let the cog handle it
            galaxy_cog = self.get_cog('GalaxyGeneratorCog')
            if galaxy_cog:
                print("🌌 Galaxy cog loaded, auto corridor shifts handled by cog")
        
        # Sync slash commands
        try:
            print("🔄 Syncing slash commands...")
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")    
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
        """Generate passive income for locations every hour."""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                await asyncio.sleep(3600)  # Wait 1 hour
                
                owned_locations = self.db.execute_query(
                    '''SELECT lo.location_id, l.wealth_level, l.population
                       FROM location_ownership lo
                       JOIN locations l ON lo.location_id = l.location_id''',
                    fetch='all'
                )
                
                for location_id, wealth_level, population in owned_locations:
                    base_income = (wealth_level * 10) + (population // 100)
                    income_multiplier = 1.0  # Placeholder for upgrades
                    final_income = int(base_income * income_multiplier)
                    
                    if final_income > 0:
                        self.db.execute_query(
                            '''UPDATE locations 
                               SET generated_income = generated_income + ? 
                               WHERE location_id = ?''',
                            (final_income, location_id)
                        )
                
                print("💰 Generated passive income for owned locations.")
                
            except Exception as e:
                print(f"Error generating location income: {e}")
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
            # Import asyncio for proper cleanup
            import asyncio
            
            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the bot
            bot.run(BOT_TOKEN)
        except discord.LoginFailure:
            print("❌ Invalid bot token!")
            print("🔗 Please check your token at: https://discord.com/developers/applications")
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            import traceback
            traceback.print_exc()