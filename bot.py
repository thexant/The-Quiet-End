# bot.py - Fixed version with proper shutdown handling
import discord
from discord.ext import commands
import asyncio
import os
from database import Database
import logging
from utils.activity_tracker import ActivityTracker
import random
from utils.income_calculator import HomeIncomeCalculator
from config import ALLOWED_GUILD_ID
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
        self.add_check(self.guild_check)
        
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
        
        # Start activity monitoring and resume AFK warnings
        if hasattr(self, 'activity_tracker') and self.activity_tracker:
            # Start the monitoring task
            monitoring_task = self.activity_tracker.start_activity_monitoring()
            if monitoring_task:
                self._background_tasks.append(monitoring_task)
            
            # Resume any AFK warnings that were active before restart
            resume_task = self.loop.create_task(self.activity_tracker.resume_afk_warnings_on_startup())
            self._background_tasks.append(resume_task)
            
        print("✅ Background tasks started.")

    def stop_background_tasks(self):
        """Stops/Cancels the background tasks."""
        print("⏸️ Stopping background tasks...")
        self._cancel_background_tasks()
        
        # Cancel activity tracker tasks
        if hasattr(self, 'activity_tracker') and self.activity_tracker:
            self.activity_tracker.cancel_all_tasks()
        
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
    async def guild_check(self, ctx):
        """Global check that applies to EVERY command automatically"""
        # For slash commands
        if hasattr(ctx, 'interaction'):
            if not ctx.guild or ctx.guild.id != ALLOWED_GUILD_ID:
                await ctx.interaction.response.send_message(
                    "❌ This bot is private and only works in the official server.",
                    ephemeral=True
                )
                return False
        # For text commands
        else:
            if not ctx.guild or ctx.guild.id != ALLOWED_GUILD_ID:
                # Silently ignore or send message
                return False
        return True
    
    async def on_guild_join(self, guild: discord.Guild):
        """Leave immediately if joining unauthorized guild"""
        if guild.id != ALLOWED_GUILD_ID:
            print(f"⚠️ Attempted to join unauthorized guild: {guild.name} ({guild.id})")
            
            # Try to send a message before leaving
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        await channel.send(
                            "❌ This bot is private and only works in the official server. Leaving now."
                        )
                        break
                    except:
                        pass
            
            await guild.leave()
            print(f"✅ Left unauthorized guild: {guild.name}")    
        
        
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
            
            # Priority loading order - load important dependencies first
            priority_cogs = ['enhanced_events']  # Load enhanced_events before events/travel_micro_events
            
            # Load priority cogs first
            for cog_name in priority_cogs:
                if os.path.exists(f'./cogs/{cog_name}.py'):
                    try:
                        print(f"  Loading {cog_name} (priority)...")
                        await self.load_extension(f'cogs.{cog_name}')
                        loaded_cogs += 1
                        print(f"  ✅ {cog_name} loaded")
                    except Exception as e:
                        print(f"  ❌ Failed to load {cog_name}: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Load remaining cogs
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py') and not filename.startswith('_'):
                    cog_name = filename[:-3]
                    if cog_name not in priority_cogs:  # Skip already loaded priority cogs
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
        
        # Leave any unauthorized guilds on startup
        for guild in list(self.guilds):
            if guild.id != ALLOWED_GUILD_ID:
                print(f"⚠️ Leaving unauthorized guild: {guild.name} ({guild.id})")
                await guild.leave()
        
        # Continue with your existing on_ready code...
        print(f'🌍 Connected to {len(self.guilds)} guild(s)')
        
        for guild in self.guilds:
            print(f"  - {guild.name} ({guild.id})")
        
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
        income_calculator = HomeIncomeCalculator(bot)
        await income_calculator.start()
        
        # Start web map if configured for autostart
        web_map_cog = self.get_cog('WebMapCog')
        if web_map_cog:
            asyncio.create_task(web_map_cog.autostart_webmap())
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """This catches ALL slash command interactions globally"""
        if not interaction.guild or interaction.guild.id != ALLOWED_GUILD_ID:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ This bot is private and only works in the official server.",
                    ephemeral=True
                )
            return False
        return True    
        
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
        """DISABLED - No longer updates nicknames automatically."""
        # This feature has been disabled
        return

    async def on_message(self, message):
        """Track user activity on messages and handle character speech"""
        # Skip bot messages to avoid loops
        if message.author.bot:
            await self.process_commands(message)
            return
        
        # Track activity for logged-in characters
        if message.author and not message.author.bot:
            char_check = self.db.execute_query(
                "SELECT user_id FROM characters WHERE user_id = ? AND is_logged_in = 1",
                (message.author.id,),
                fetch='one'
            )
            if char_check:
                self.activity_tracker.update_activity(message.author.id)
        
        # Handle character speech in location channels BEFORE processing commands
        # This ensures the message is converted before command processing
        should_process_commands = await self.handle_character_speech(message)
        
        if should_process_commands:
            await self.process_commands(message)

    # Add this new method to the RPGBot class:

    async def handle_character_speech(self, message):
        """Convert player messages to character speech in location channels
        Returns True if commands should be processed, False otherwise"""
        
        # Skip if author is a bot
        if message.author.bot:
            return True
        
        # Skip if message starts with command prefix or is a slash command
        if message.content.startswith(COMMAND_PREFIX):
            return True
        
        # Check if user has a logged-in character
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = ? AND is_logged_in = 1",
            (message.author.id,),
            fetch='one'
        )
        
        if not char_data:
            return True
        
        char_name = char_data[0]
        
        # Check if this is a location-related channel
        channel = message.channel
        channel_id = channel.id
        
        # For threads, we need to check both the thread ID and parent channel ID
        is_location_channel = False
        
        # Check if it's a sub-location thread first
        if isinstance(channel, discord.Thread):
            sub_location_check = self.db.execute_query(
                "SELECT sub_location_id FROM sub_locations WHERE thread_id = ?",
                (channel.id,),
                fetch='one'
            )
            if sub_location_check:
                is_location_channel = True
            else:
                # For other threads, check the parent channel
                channel_id = channel.parent_id if channel.parent_id else channel_id
        
        if not is_location_channel:
            # Check if it's a location channel
            location_check = self.db.execute_query(
                "SELECT location_id FROM locations WHERE channel_id = ?",
                (channel_id,),
                fetch='one'
            )
            
            if location_check:
                is_location_channel = True
            else:
                # Check if it's a home interior channel
                home_check = self.db.execute_query(
                    "SELECT home_id FROM home_interiors WHERE channel_id = ?",
                    (channel_id,),
                    fetch='one'
                )
                
                if home_check:
                    is_location_channel = True
                else:
                    # Check if it's a ship interior channel
                    ship_check = self.db.execute_query(
                        "SELECT ship_id FROM ships WHERE channel_id = ?",
                        (channel_id,),
                        fetch='one'
                    )
                    
                    if ship_check:
                        is_location_channel = True
                    else:
                        # Check if it's a transit channel (by name pattern)
                        if channel.name and channel.name.startswith('transit-'):
                            is_location_channel = True
        
        # If not a location channel, process normally
        if not is_location_channel:
            return True
        
        # Special handling for certain message types that shouldn't be converted
        # Skip messages that are primarily embeds or have no text content
        if not message.content.strip() and not message.attachments:
            return True
        
        # Check if message is wrapped in asterisks for action format
        import re
        action_match = re.match(r'^\*(.+)\*$', message.content.strip())
        
        if action_match:
            # This is an action message
            action_text = action_match.group(1).strip()
            speech_content = f"{char_name} *{action_text}*"
        else:
            # Regular speech message
            speech_content = f"**{char_name}** says: {message.content}"
        
        # Handle attachments
        if message.attachments:
            # Add a note about attachments
            attachment_text = []
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    attachment_text.append("📷 *shows an image*")
                elif attachment.content_type and attachment.content_type.startswith('video/'):
                    attachment_text.append("📹 *shares a video*")
                elif attachment.content_type and attachment.content_type.startswith('audio/'):
                    attachment_text.append("🎵 *plays audio*")
                else:
                    attachment_text.append("📎 *shares a file*")
            
            if attachment_text:
                speech_content += "\n" + " ".join(attachment_text)
        
        # Handle message references (replies)
        reference = None
        if message.reference:
            try:
                # Try to fetch the referenced message
                ref_message = await message.channel.fetch_message(message.reference.message_id)
                reference = ref_message
            except:
                pass
        
        # Handle stickers
        if message.stickers:
            sticker_names = [sticker.name for sticker in message.stickers]
            speech_content += f"\n*uses sticker: {', '.join(sticker_names)}*"
        
        try:
            # Delete the original message
            await message.delete()
            
            # Send the character speech
            if reference:
                await message.channel.send(speech_content, reference=reference)
            else:
                await message.channel.send(speech_content)
            
            # Return False to indicate commands shouldn't be processed (message was deleted)
            return False
                
        except discord.Forbidden:
            # Bot lacks permissions, process message normally
            return True
        except discord.HTTPException:
            # Message too long or other HTTP error, process message normally
            return True
        except Exception:
            # Any other error, process message normally
            return True
        
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