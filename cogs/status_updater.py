# cogs/status_updater.py
import discord
from discord.ext import commands, tasks
from discord import app_commands # <--- 1. IMPORT app_commands
import asyncio
from datetime import datetime
from utils.time_system import TimeSystem

class StatusUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.time_system = TimeSystem(bot)
        
        self.update_status_channels.start()
    
    def cog_unload(self):
        self.update_status_channels.cancel()

    async def _execute_status_update(self):
        """
        The core logic for updating status voice channels.
        Returns: (number_of_channels_updated, reason_string)
        """
        try:
            servers_with_status = self.db.execute_query(
                "SELECT guild_id, status_voice_channel_id FROM server_config WHERE status_voice_channel_id IS NOT NULL",
                fetch='all'
            )
            
            if not servers_with_status:
                return (0, "No servers have a status channel configured.")
            
            current_ingame_time = self.time_system.calculate_current_ingame_time()
            if not current_ingame_time:
                print("❌ Could not calculate in-game time for status update")
                return (0, "Could not calculate in-game time.")
            
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
            
            active_players = self.db.execute_query(
                "SELECT COUNT(*) FROM characters WHERE is_logged_in = 1",
                fetch='one'
            )[0]
            
            dynamic_npcs = self.db.execute_query(
                "SELECT COUNT(*) FROM dynamic_npcs WHERE is_alive = 1",
                fetch='one'
            )[0]
            
            # Use the shortened name format
            new_channel_name = f"🌐{date_str}|⌚{approx_time}"
            
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
                
        except Exception as e:
            print(f"❌ Error in status channel update task: {e}")
            return (0, f"An unexpected error occurred: {e}")

    @tasks.loop(seconds=480)
    async def update_status_channels(self):
        await self._execute_status_update()
    
    @update_status_channels.before_loop
    async def before_status_update(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)
        print("🔄 Status voice channel updater started")

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


async def setup(bot):
    await bot.add_cog(StatusUpdaterCog(bot))