# cogs/status_updater.py
import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from utils.time_system import TimeSystem

class StatusUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.time_system = TimeSystem(bot)
        
        # Start the background task
        self.update_status_channels.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_status_channels.cancel()
    
    @tasks.loop(minutes=5)
    async def update_status_channels(self):
        """Update all status voice channels every 10 minutes"""
        try:
            # Get all servers with status voice channels configured
            servers_with_status = self.db.execute_query(
                "SELECT guild_id, status_voice_channel_id FROM server_config WHERE status_voice_channel_id IS NOT NULL",
                fetch='all'
            )
            
            if not servers_with_status:
                return
            
            # Get current in-game time
            current_ingame_time = self.time_system.calculate_current_ingame_time()
            if not current_ingame_time:
                print("❌ Could not calculate in-game time for status update")
                return
            
            # Format date and approximate time
            date_str = current_ingame_time.strftime("%d-%m-%Y")
            
            # Round to nearest 30 minutes
            minutes = current_ingame_time.minute
            if minutes < 15:
                approx_time = f"{current_ingame_time.hour:02d}:00"
            elif minutes < 45:
                approx_time = f"{current_ingame_time.hour:02d}:30"
            else:
                next_hour = (current_ingame_time.hour + 1) % 24
                approx_time = f"{next_hour:02d}:00"
            
            # Get global statistics (across all servers)
            active_players = self.db.execute_query(
                "SELECT COUNT(*) FROM characters WHERE is_logged_in = 1",
                fetch='one'
            )[0]
            
            dynamic_npcs = self.db.execute_query(
                "SELECT COUNT(*) FROM dynamic_npcs WHERE is_alive = 1",
                fetch='one'
            )[0]
            
            # Format the channel name
            new_channel_name = f"⏰ {date_str} - {approx_time} | 🟢 {active_players} | 🟠 {dynamic_npcs}"
            
            # Update all configured status channels
            updated_count = 0
            for guild_id, channel_id in servers_with_status:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                
                channel = guild.get_channel(channel_id)
                if not channel or not isinstance(channel, discord.VoiceChannel):
                    continue
                
                try:
                    # Only update if name is different (to avoid rate limits)
                    if channel.name != new_channel_name:
                        await channel.edit(name=new_channel_name, reason="Automated status update")
                        updated_count += 1
                        
                        # Small delay between updates to avoid rate limits
                        await asyncio.sleep(1)
                        
                except discord.HTTPException as e:
                    print(f"❌ Failed to update status channel in {guild.name}: {e}")
                except Exception as e:
                    print(f"❌ Unexpected error updating status channel in {guild.name}: {e}")
            
            if updated_count > 0:
                print(f"🔄 Updated {updated_count} status voice channel(s): {new_channel_name}")
                
        except Exception as e:
            print(f"❌ Error in status channel update task: {e}")
    
    @update_status_channels.before_loop
    async def before_status_update(self):
        """Wait for bot to be ready before starting the task"""
        await self.bot.wait_until_ready()
        
        # Initial delay to let everything settle
        await asyncio.sleep(30)
        
        print("🔄 Status voice channel updater started")

async def setup(bot):
    await bot.add_cog(StatusUpdaterCog(bot))