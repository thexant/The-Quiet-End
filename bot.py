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
        # Multi-server support enabled - no guild restrictions
        
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
    
    async def on_guild_join(self, guild: discord.Guild):
        """Welcome message when joining a new guild"""
        print(f"🎉 Joined guild: {guild.name} ({guild.id})")
        
        # Send welcome message to the first available channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(
                        "🚀 **The Quiet End RPG Bot** has landed! "
                        "Use `/help` to get started with commands."
                    )
                    break
                except:
                    pass    
        
        
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
                print("❌ Database integrity check failed! Attempting to analyze...")
                # PostgreSQL equivalent to vacuum - analyze tables for query optimization
                try:
                    self.db.execute_query("ANALYZE")
                    print("✅ Database analysis complete")
                except Exception as analyze_error:
                    print(f"⚠️ Database analysis failed: {analyze_error}")
                if not self.db.check_integrity():
                    raise Exception("Database connection is not working properly")
            
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
        
        # Multi-server support enabled
        
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
        """Global interaction check - multi-server support enabled"""
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
                "SELECT user_id FROM characters WHERE user_id = %s AND is_logged_in = TRUE",
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
                "SELECT user_id FROM characters WHERE user_id = %s AND is_logged_in = TRUE",
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
            
        print(f"DEBUG: Processing message from {message.author.name}: {message.content[:50]}")
        
        # Skip if message starts with command prefix or is a slash command
        if message.content.startswith(COMMAND_PREFIX):
            return True
        
        # Check if user has a logged-in character
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = %s AND is_logged_in = TRUE",
            (message.author.id,),
            fetch='one'
        )
        
        if not char_data:
            print(f"DEBUG: No logged-in character found for {message.author.name}")
            return True
        
        char_name = char_data[0]
        
        # Check if this is a location-related channel
        channel = message.channel
        channel_id = channel.id
        
        print(f"DEBUG: Checking channel {channel.name} (ID: {channel_id}) for location association")
        
        # For threads, we need to check both the thread ID and parent channel ID
        is_location_channel = False
        
        # Check if it's a sub-location thread first
        if isinstance(channel, discord.Thread):
            print(f"DEBUG: Channel is a thread, checking sub-location association")
            sub_location_check = self.db.execute_query(
                "SELECT sub_location_id FROM sub_locations WHERE thread_id = %s",
                (channel.id,),
                fetch='one'
            )
            if sub_location_check:
                is_location_channel = True
                print(f"DEBUG: Found sub-location association: {sub_location_check[0]}")
            else:
                # For other threads, check the parent channel
                channel_id = channel.parent_id if channel.parent_id else channel_id
                print(f"DEBUG: No sub-location found, checking parent channel ID: {channel_id}")
        
        if not is_location_channel:
            # Primary Method: Check by exact channel name matching
            print(f"DEBUG: Using name-based location detection for channel: {channel.name}")
            
            # Get all locations and check if this channel name matches any location's expected name
            all_locations = self.db.execute_query(
                "SELECT location_id, name, location_type FROM locations",
                fetch='all'
            )
            
            location_id_found = None
            for loc_id, loc_name, loc_type in all_locations:
                # Import here to avoid circular imports
                from utils.channel_manager import ChannelManager
                # Create a temporary instance to access the naming method
                temp_manager = ChannelManager(self)
                expected_name = temp_manager._generate_channel_name(loc_name, loc_type)
                
                if channel.name == expected_name:
                    location_id_found = loc_id
                    print(f"DEBUG: Found location via EXACT name match: {loc_name} (ID: {loc_id})")
                    is_location_channel = True
                    break
            
            # Fallback Method: Check database channel_id if name matching fails
            if not is_location_channel:
                print(f"DEBUG: Name matching failed, trying database channel_id lookup for {channel_id}")
                from utils.channel_manager import ChannelManager
                channel_manager = ChannelManager(self)
                location_check = channel_manager.get_location_from_channel_id(
                    message.guild.id, 
                    channel_id
                )
                
                if location_check:
                    is_location_channel = True
                    location_id_found = location_check[0]
                    print(f"DEBUG: Found location via database lookup: location_id {location_check[0]}")
                else:
                    print(f"DEBUG: No location association found for channel_id {channel_id}")
                    
                    # Check if it's a home interior channel
                    home_check = self.db.execute_query(
                        "SELECT home_id FROM home_interiors WHERE channel_id = %s",
                        (channel_id,),
                        fetch='one'
                    )
                
                if home_check:
                    is_location_channel = True
                else:
                    # Check if it's a ship interior channel
                    ship_check = self.db.execute_query(
                        "SELECT ship_id FROM ships WHERE channel_id = %s",
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
            print(f"DEBUG: Not a location channel: {channel.name}")
            return True
            
        print(f"DEBUG: Found location channel, proceeding with speech conversion")
        
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
            print(f"DEBUG: Converting speech for {char_name}: {message.content[:30]}")
            # Delete the original message
            await message.delete()
            
            # Send the character speech to original channel first
            if reference:
                sent_message = await message.channel.send(speech_content, reference=reference)
            else:
                sent_message = await message.channel.send(speech_content)
            print(f"DEBUG: Sent speech message to original channel")
            
            # Then broadcast the converted speech to cross-guild channels
            await self.broadcast_cross_guild_message(
                original_channel=message.channel,
                message_content=speech_content,
                reference=reference
            )
            print(f"DEBUG: Broadcast speech message to cross-guild channels")
            
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

    async def broadcast_cross_guild_message(self, original_channel, message_content=None, embed=None, file=None, reference=None, **kwargs):
        """
        Broadcast a message to equivalent channels across all guilds where players are present.
        This is the core cross-guild synchronization system.
        """
        try:
            # Skip if no message content to broadcast
            if not message_content and not embed and not file:
                return
            
            # Identify what type of channel this is and get cross-guild equivalents
            cross_guild_channels = await self._get_cross_guild_channels_for_broadcast(original_channel)
            
            if not cross_guild_channels:
                print(f"DEBUG: No cross-guild channels found for {original_channel.name}")
                return
            
            print(f"DEBUG: Broadcasting to {len(cross_guild_channels)} cross-guild channels")
                
            # Broadcast to all equivalent channels using a direct method that bypasses message processing
            for guild, target_channel in cross_guild_channels:
                try:
                    # Use the direct Discord API send method to avoid triggering on_message processing
                    await target_channel.send(
                        content=message_content,
                        embed=embed,
                        file=file,
                        reference=reference,
                        **kwargs
                    )
                    print(f"DEBUG: Successfully broadcasted to {guild.name}#{target_channel.name}")
                except discord.HTTPException as e:
                    # Handle rate limits and permission errors gracefully
                    print(f"⚠️ Failed to broadcast to {guild.name}#{target_channel.name}: {e}")
                except Exception as e:
                    print(f"❌ Error broadcasting to {guild.name}: {e}")
                    
        except Exception as e:
            print(f"❌ Error in cross-guild broadcast: {e}")

    async def _get_cross_guild_channels_for_broadcast(self, original_channel):
        """
        Determine what type of channel this is and get equivalent channels across guilds.
        Returns list of (guild, channel) tuples for broadcasting.
        """
        from utils.channel_manager import ChannelManager
        
        # Get the first available ChannelManager instance from any cog
        channel_mgr = None
        for cog in self.cogs.values():
            if hasattr(cog, 'channel_mgr') and isinstance(cog.channel_mgr, ChannelManager):
                channel_mgr = cog.channel_mgr
                break
                
        if not channel_mgr:
            return []
            
        original_guild_id = original_channel.guild.id
        
        # Check if this is a main location channel using EXACT name matching first
        print(f"DEBUG: _get_cross_guild_channels_for_broadcast checking channel {original_channel.name}")
        
        # PRIMARY METHOD: Check by exact channel name matching (same logic as handle_character_speech)
        all_locations = self.db.execute_query(
            "SELECT location_id, name, location_type FROM locations",
            fetch='all'
        )
        
        location_id_found = None
        for loc_id, loc_name, loc_type in all_locations:
            temp_manager = ChannelManager(self)
            expected_name = temp_manager._generate_channel_name(loc_name, loc_type)
            
            if original_channel.name == expected_name:
                location_id_found = loc_id
                print(f"DEBUG: Found location via EXACT name match for broadcast: {loc_name} (ID: {loc_id})")
                break
        
        if location_id_found:
            return await channel_mgr.get_cross_guild_location_channels(location_id_found, exclude_guild_id=original_guild_id)
        
        # FALLBACK METHOD: Check database channel_id if name matching fails
        print(f"DEBUG: Name matching failed for broadcast, trying database channel_id lookup")
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self)
        location_check = channel_manager.get_location_from_channel_id(
            original_channel.guild.id, 
            original_channel.id
        )
        if location_check:
            location_id = location_check[0]
            print(f"DEBUG: Found location via database lookup for broadcast: location_id {location_id}")
            return await channel_mgr.get_cross_guild_location_channels(location_id, exclude_guild_id=original_guild_id)
        
        # Check if this is a sub-location thread
        if isinstance(original_channel, discord.Thread):
            sub_location_check = self.db.execute_query(
                "SELECT parent_location_id, name FROM sub_locations WHERE thread_id = %s",
                (original_channel.id,),
                fetch='one'
            )
            if sub_location_check:
                parent_location_id, sub_name = sub_location_check
                return await channel_mgr.get_cross_guild_sub_location_channels(parent_location_id, sub_name, exclude_guild_id=original_guild_id)
        
        # Check if this is a ship interior channel
        ship_check = self.db.execute_query(
            "SELECT ship_id FROM ships WHERE channel_id = %s",
            (original_channel.id,),
            fetch='one'
        )
        if ship_check:
            ship_id = ship_check[0]
            return await channel_mgr.get_cross_guild_ship_channels(ship_id, exclude_guild_id=original_guild_id)
        
        # Check if this is a home interior channel
        home_check = self.db.execute_query(
            "SELECT home_id FROM home_interiors WHERE channel_id = %s",
            (original_channel.id,),
            fetch='one'
        )
        if home_check:
            home_id = home_check[0]
            return await channel_mgr.get_cross_guild_home_channels(home_id, exclude_guild_id=original_guild_id)
        
        # Not a recognized location channel type
        return []

    async def send_with_cross_guild_broadcast(self, channel, content=None, **kwargs):
        """
        Send a message to a channel and automatically broadcast to cross-guild equivalents.
        This replaces direct channel.send() calls for location channels.
        """
        # Send to original channel first
        message = await channel.send(content=content, **kwargs)
        
        # Broadcast to cross-guild channels
        await self.broadcast_cross_guild_message(
            original_channel=channel,
            message_content=content,
            **kwargs
        )
        
        return message

    def get_cross_guild_send_method(self, channel):
        """
        Returns a send method that automatically broadcasts to cross-guild channels.
        This can be used by cogs to replace channel.send() calls.
        """
        async def cross_guild_send(content=None, **kwargs):
            return await self.send_with_cross_guild_broadcast(channel, content, **kwargs)
        return cross_guild_send
        
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
                               SET generated_income = generated_income + %s 
                               WHERE location_id = %s''',
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
        
        # PostgreSQL cleanup is already handled by the database cleanup method
        print("✅ PostgreSQL database cleanup handled by connection pool")
        
        print("✅ Cleanup complete, exiting...")