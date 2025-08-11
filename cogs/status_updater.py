# cogs/status_updater.py
import discord
from discord.ext import commands, tasks
from discord import app_commands # <--- 1. IMPORT app_commands
import asyncio
from datetime import datetime
from utils.time_system import TimeSystem
import psycopg2
import psycopg2.errors

class StatusUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.time_system = TimeSystem(bot)
        self.task_start_time = None
        self.task_failure_count = 0
        self.last_successful_update = None
        
        print("🔄 StatusUpdaterCog: Initializing...")
        try:
            self.update_status_channels.start()
            print("✅ StatusUpdaterCog: Background task started successfully")
        except Exception as e:
            print(f"❌ StatusUpdaterCog: Failed to start background task: {e}")
            import traceback
            traceback.print_exc()
    
    def cog_unload(self):
        print("🛑 StatusUpdaterCog: Unloading, cancelling background task...")
        self.update_status_channels.cancel()
        print("✅ StatusUpdaterCog: Background task cancelled")

    async def _execute_status_update(self):
        """
        The core logic for updating status voice channels.
        Returns: (number_of_channels_updated, reason_string)
        """
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Check if database is accessible before proceeding
                try:
                    # Simple test query with timeout
                    test_result = self.db.execute_query("SELECT 1", fetch='one')
                    if not test_result:
                        if attempt < max_retries - 1:
                            print(f"⚠️ Database test failed, retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        return (0, "Database is not accessible")
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Database connection issue during status update, retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return (0, "Database connection unavailable")
                except Exception as e:
                    raise e
                
                servers_with_status = self.db.execute_query(
                    "SELECT guild_id, status_voice_channel_id FROM server_config WHERE status_voice_channel_id IS NOT NULL",
                    fetch='all'
                )
                
                if not servers_with_status:
                    return (0, "No servers have a status channel configured.")
                
                current_ingame_time = self.time_system.calculate_current_ingame_time()
                if not current_ingame_time:
                    # No galaxy generated yet - show offline status
                    new_channel_name = "🌐|OFFLINE"
                else:
                    # Use the shortened date format
                    date_str = current_ingame_time.strftime("%d-%m-%Y")
                    
                    minutes = current_ingame_time.minute
                    if minutes < 15:
                        approx_time = f"{current_ingame_time.hour:02d}:00"
                    elif minutes < 45:
                        approx_time = f"{current_ingame_time.hour:02d}:30"
                    else:
                        next_hour = (current_ingame_time.hour + 1) % 24
                        approx_time = f"{next_hour:02d}:00"
                    
                    # Get player counts with error handling
                    try:
                        active_players = self.db.execute_query(
                            "SELECT COUNT(*) FROM characters WHERE is_logged_in = TRUE",
                            fetch='one'
                        )[0]
                        
                        dynamic_npcs = self.db.execute_query(
                            "SELECT COUNT(*) FROM dynamic_npcs WHERE is_alive = TRUE",
                            fetch='one'
                        )[0]
                    except psycopg2.errors.UndefinedTable as e:
                        # Table doesn't exist - galaxy not yet generated
                        new_channel_name = "🌐|OFFLINE"
                    except Exception as e:
                        raise e
                    else:
                        # Use the shortened name format
                        new_channel_name = f"🌐|{date_str}|⌚{approx_time}|🟢{active_players}"
                
                updated_count = 0
                for guild_id, channel_id in servers_with_status:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel or not isinstance(channel, discord.VoiceChannel):
                        continue
                    
                    try:
                        if channel.name != new_channel_name:
                            await channel.edit(name=new_channel_name, reason="Automated status update")
                            updated_count += 1
                            await asyncio.sleep(1)
                            
                    except discord.HTTPException as e:
                        print(f"❌ Failed to update status channel in {guild.name}: {e}")
                    except Exception as e:
                        print(f"❌ Unexpected error updating status channel in {guild.name}: {e}")
                
                if updated_count > 0:
                    print(f"🔄 Updated {updated_count} status voice channel(s): {new_channel_name}")
                    return (updated_count, f"Successfully updated channels with: {new_channel_name}")
                else:
                    return (0, "Channel names were already up-to-date.")
                
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Database connection issue during status update (attempt {attempt + 1}), retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    print(f"❌ Database connection remained unavailable after {max_retries} attempts")
                    return (0, "Database connection unavailable")
            except Exception as e:
                print(f"❌ Error in status channel update task: {e}")
                return (0, f"An unexpected error occurred: {e}")
        
        return (0, "Failed after maximum retries")

    @tasks.loop(seconds=480)
    async def update_status_channels(self):
        try:
            print("🔄 StatusUpdaterCog: Starting scheduled status update...")
            updated_count, reason = await self._execute_status_update()
            
            if updated_count > 0:
                self.last_successful_update = datetime.now()
                self.task_failure_count = 0
                print(f"✅ StatusUpdaterCog: Scheduled update successful - {updated_count} channels updated")
            else:
                print(f"ℹ️ StatusUpdaterCog: Scheduled update completed - {reason}")
                
        except Exception as e:
            self.task_failure_count += 1
            print(f"❌ StatusUpdaterCog: Task failed (failure #{self.task_failure_count}): {e}")
            import traceback
            traceback.print_exc()
            
            # Auto-restart after 3 consecutive failures
            if self.task_failure_count >= 3:
                print("⚠️ StatusUpdaterCog: Too many failures, restarting task...")
                await self._restart_task()
    
    @update_status_channels.before_loop
    async def before_status_update(self):
        print("⏳ StatusUpdaterCog: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()
        print("⏳ StatusUpdaterCog: Bot ready, waiting 30 seconds before first update...")
        await asyncio.sleep(30)
        self.task_start_time = datetime.now()
        print("🔄 StatusUpdaterCog: Background task fully initialized and ready")
        print(f"📅 StatusUpdaterCog: Next update scheduled in 8 minutes (480 seconds)")

    # -------------------------------------------------------------------------
    # 2. DECORATOR and FUNCTION SIGNATURE UPDATED for discord.py
    # -------------------------------------------------------------------------
    @app_commands.command(
        name="updatestatuscounter",
        description="Manually forces the status counters to update."
    )
    @app_commands.checks.has_permissions(administrator=True) # Use app_commands checks
    async def updatestatuscounter(self, interaction: discord.Interaction): # <--- Use discord.Interaction
        """Admin command to manually trigger a status update."""
        # 3. RESPONSE METHODS UPDATED for discord.py
        await interaction.response.defer(ephemeral=True)

        updated_count, reason = await self._execute_status_update()

        if updated_count > 0:
            embed = discord.Embed(
                title="✅ Status Update Forced",
                description=f"Successfully updated **{updated_count}** channel(s).",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="ℹ️ Status Update Result",
                description=f"No channels were updated. Reason: {reason}",
                color=0xff9900
            )
        
        await interaction.followup.send(embed=embed) # <--- Use interaction.followup

    async def _restart_task(self):
        """Restart the background task after failures"""
        try:
            print("🔄 StatusUpdaterCog: Stopping current task...")
            self.update_status_channels.cancel()
            await asyncio.sleep(2)  # Give it time to cancel
            
            print("🔄 StatusUpdaterCog: Starting fresh task...")
            self.task_failure_count = 0
            self.update_status_channels.restart()
            print("✅ StatusUpdaterCog: Task restarted successfully")
        except Exception as e:
            print(f"❌ StatusUpdaterCog: Failed to restart task: {e}")
            import traceback
            traceback.print_exc()

    @update_status_channels.error
    async def status_update_task_error(self, error):
        """Error handler for the task loop"""
        self.task_failure_count += 1
        print(f"❌ StatusUpdaterCog: Task error handler triggered (failure #{self.task_failure_count}): {error}")
        import traceback
        traceback.print_exc()
        
        # Auto-restart after 3 consecutive failures
        if self.task_failure_count >= 3:
            print("⚠️ StatusUpdaterCog: Too many failures in error handler, attempting restart...")
            await self._restart_task()

    @app_commands.command(
        name="statusupdaterdiagnostics", 
        description="Check the status of the background status updater task"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def statusupdaterdiagnostics(self, interaction: discord.Interaction):
        """Admin command to check the status updater task diagnostics"""
        await interaction.response.defer(ephemeral=True)
        
        # Gather diagnostic information
        is_running = self.update_status_channels.is_running()
        current_loop = self.update_status_channels.current_loop or 0
        next_iteration = self.update_status_channels.next_iteration
        
        embed = discord.Embed(title="📊 Status Updater Diagnostics", color=0x00ff00 if is_running else 0xff0000)
        embed.add_field(name="Task Running", value="✅ Yes" if is_running else "❌ No", inline=True)
        embed.add_field(name="Current Loop", value=str(current_loop), inline=True)
        embed.add_field(name="Failure Count", value=str(self.task_failure_count), inline=True)
        
        if self.task_start_time:
            embed.add_field(name="Started At", value=self.task_start_time.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        if self.last_successful_update:
            embed.add_field(name="Last Success", value=self.last_successful_update.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        else:
            embed.add_field(name="Last Success", value="Never", inline=True)
            
        if next_iteration:
            embed.add_field(name="Next Update", value=f"<t:{int(next_iteration.timestamp())}:R>", inline=True)
            
        # Test database connection
        try:
            test_result = self.db.execute_query("SELECT 1", fetch='one')
            db_status = "✅ Connected" if test_result else "❌ No Response"
        except Exception as e:
            db_status = f"❌ Error: {str(e)[:50]}"
        embed.add_field(name="Database", value=db_status, inline=True)
        
        # Check if there are servers with status channels configured
        try:
            servers_with_status = self.db.execute_query(
                "SELECT COUNT(*) FROM server_config WHERE status_voice_channel_id IS NOT NULL",
                fetch='one'
            )
            channel_count = servers_with_status[0] if servers_with_status else 0
            embed.add_field(name="Configured Servers", value=str(channel_count), inline=True)
        except Exception as e:
            embed.add_field(name="Configured Servers", value=f"Error: {str(e)[:30]}", inline=True)
            
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StatusUpdaterCog(bot))