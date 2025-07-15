# bot.py - Fixed version with proper shutdown handling
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
        self._closing = False  # Add this at the very beginning
        self.db = Database()
        activity = discord.Activity(type=discord.ActivityType.watching, name=ACTIVITY_NAME)
        super().__init__(
            command_prefix=COMMAND_PREFIX, 
            intents=intents,
            activity=activity,
            help_command=None
        )
        self.logger = logging.getLogger('RPGBot')
        self.activity_tracker = None
        self.income_task = None
        self._background_tasks = []
        
    def start_background_tasks(self):
        """Starts the background tasks if they are not already running."""
        if self._closing:
            print("⚠️ Bot is shutting down, not starting background tasks")
            return
            
        print("🔄 Starting background tasks...")
        
        # Cancel any existing tasks first
        self._cancel_background_tasks()
        
        # Start new tasks
        if not hasattr(self, 'income_task') or self.income_task is None or self.income_task.done():
            self.income_task = self.loop.create_task(self.generate_location_income())
            self._background_tasks.append(self.income_task)
        
        galaxy_cog = self.get_cog('GalaxyGeneratorCog')
        if galaxy_cog:
            galaxy_cog.start_auto_shift_task()
            
        print("✅ Background tasks started.")

    def stop_background_tasks(self):
        """Stops/Cancels the background tasks."""
        print("⏸️ Stopping background tasks...")
        self._cancel_background_tasks()
        
        galaxy_cog = self.get_cog('GalaxyGeneratorCog')
        if galaxy_cog:
            galaxy_cog.stop_auto_shift_task()
            
        print("🛑 Background tasks stopped.")
    
    def _cancel_background_tasks(self):
        """Cancel all tracked background tasks"""
        for task in self._background_tasks:
            if task and not task.done():
                task.cancel()
        self._background_tasks.clear()
        
        if hasattr(self, 'income_task') and self.income_task and not self.income_task.done():
            self.income_task.cancel()
            self.income_task = None
    
    async def close(self):
        """Properly close the bot and cleanup resources"""
        if self._closing:
            return
            
        self._closing = True
        print("\n🔄 Bot shutdown initiated...")
        
        # Stop all background tasks first
        self.stop_background_tasks()
        
        # Give tasks a moment to cancel
        await asyncio.sleep(0.5)
        
        # Database cleanup
        if hasattr(self, 'db'):
            print("🔄 Closing database connections...")
            # Don't run async cleanup here, just mark for shutdown
            self.db._shutdown = True
        
        # Call parent close
        try:
            await super().close()
        except:
            pass  # Ignore errors during Discord.py's close
            
        print("✅ Bot shutdown complete")
        
    async def setup_hook(self):
        """This function is called when the bot is preparing to start."""
        try:
            # Check database integrity first
            if not self.db.check_integrity():
                print("❌ Database integrity check failed! Attempting to repair...")
                self.db.vacuum_database()
                if not self.db.check_integrity():
                    raise Exception("Database is corrupted and cannot be repaired")
            
            print("📊 Initializing activity tracker...")
            self.activity_tracker = ActivityTracker(self)
            print("✅ Activity tracker initialized")
            
            print("🧩 Loading cogs...")
            loaded_cogs = 0
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py') and not filename.startswith('_'):
                    cog_name = filename[:-3]
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
            
            # Start background tasks
            self.start_background_tasks()
            
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
            return
        
        print(f"Command error in {ctx.command}: {error}")
        
        if hasattr(ctx, 'send'):
            try:
                await ctx.send(f"An error occurred: {str(error)}", ephemeral=True)
            except: pass
    
    async def on_application_command_error(self, interaction, error):
        """Handle slash command errors"""
        print(f"Slash command error: {error}")
        
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    f"An error occurred: {str(error)}", 
                    ephemeral=True
                )
            except: pass

    async def on_interaction(self, interaction: discord.Interaction):
        """Track user activity on any interaction"""
        if interaction.user and not interaction.user.bot:
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = ? AND is_logged_in = 1",
                (interaction.user.id,),
                fetch='one'
            )
            if char_check:
                self.activity_tracker.update_activity(interaction.user.id)
                
    async def update_nickname(self, member: discord.Member):
        """Checks a user's auto_rename setting and updates their nickname accordingly."""
        # Ensure we have a member object and the necessary permissions
        if not member or not member.guild or not member.guild.me.guild_permissions.manage_nicknames:
            return

        char_data = self.db.execute_query(
            "SELECT name, auto_rename FROM characters WHERE user_id = ?",
            (member.id,),
            fetch='one'
        )

        # Case 1: Character exists and auto-rename is ON
        if char_data and char_data[1] == 1:  # char_data[1] is auto_rename
            char_name = char_data[0]
            if member.nick != char_name:
                try:
                    await member.edit(nick=char_name, reason="Character auto-rename enabled.")
                except discord.Forbidden:
                    print(f"Lacked permissions to set nickname for {member.display_name} in {member.guild.name}")
                except Exception as e:
                    print(f"An error occurred while setting nickname for {member.display_name}: {e}")
        # Case 2: Auto-rename is OFF or character doesn't exist
        else:
            # We should only clear the nickname if the current nickname was likely set by the bot.
            # We'll check if the current nickname matches their character name.
            character_name_if_exists = None
            if char_data:
                character_name_if_exists = char_data[0]
            
            # If the user's nickname is their character name, clear it.
            # This handles turning the setting OFF.
            if member.nick and member.nick == character_name_if_exists:
                try:
                    await member.edit(nick=None, reason="Character auto-rename disabled.")
                except discord.Forbidden:
                    print(f"Lacked permissions to clear nickname for {member.display_name} in {member.guild.name}")
                except Exception as e:
                    print(f"An error occurred while clearing nickname for {member.display_name}: {e}")

    async def on_message(self, message):
        """Track user activity on messages"""
        if message.author and not message.author.bot:
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
        
        while not self.is_closed() and not self._closing:
            try:
                # Wait 1 hour, but check for shutdown every 10 seconds
                for _ in range(360):  # 3600 seconds / 10 = 360 checks
                    if self._closing:
                        return
                    await asyncio.sleep(10)
                
                if self._closing:
                    return
                
                owned_locations = self.db.execute_query(
                    '''SELECT lo.location_id, l.wealth_level, l.population
                       FROM location_ownership lo
                       JOIN locations l ON lo.location_id = l.location_id''',
                    fetch='all'
                )
                
                if not owned_locations:
                    continue

                for location_id, wealth_level, population in owned_locations:
                    if self._closing:
                        return
                        
                    base_income = (wealth_level * 10) + (population // 100)
                    income_multiplier = 1.0
                    final_income = int(base_income * income_multiplier)
                    
                    if final_income > 0:
                        self.db.execute_query(
                            '''UPDATE locations 
                               SET generated_income = generated_income + ? 
                               WHERE location_id = ?''',
                            (final_income, location_id)
                        )
                
                print("💰 Generated passive income for owned locations.")
                
            except asyncio.CancelledError:
                print("💰 Income generation task cancelled.")
                break
            except Exception as e:
                if not self._closing:
                    print(f"Error generating location income: {e}")

# Global bot instance
# Global bot instance
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
            # Run the bot - Discord.py will handle CTRL+C internally
            bot.run(BOT_TOKEN)
        except discord.LoginFailure:
            print("❌ Invalid bot token!")
            print("🔗 Please check your token at: https://discord.com/developers/applications")
        except KeyboardInterrupt:
            # Discord.py catches KeyboardInterrupt internally, but just in case
            print("\n🛑 Received interrupt signal, shutting down...")
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            import traceback
            traceback.print_exc()
        
        # This code runs after bot.run() completes (including after CTRL+C)
        print("\n🔄 Bot has stopped, performing cleanup...")
        
        # Ensure bot is closed
        if hasattr(bot, '_closing') and not bot._closing:
            # Run the close method synchronously
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(bot.close())
                loop.close()
            except:
                pass
        
        # Database cleanup
        if hasattr(bot, 'db') and hasattr(bot.db, '_shutdown') and not bot.db._shutdown:
            bot.db.cleanup()
        
        # Final WAL checkpoint
        try:
            import sqlite3
            db_path = bot.db.db_path if hasattr(bot, 'db') else "thequietendDEV.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
                print("✅ Final WAL checkpoint complete")
        except Exception as e:
            print(f"⚠️ Final checkpoint error: {e}")
        
        print("✅ Cleanup complete, exiting...")