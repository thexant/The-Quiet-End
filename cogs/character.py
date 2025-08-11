# cogs/character.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from utils.location_utils import get_character_location_status
from datetime import datetime
import asyncio
from utils.item_effects import ItemEffectChecker
from utils.views import ObserveModal, RadioModal, GiveItemSelectView, SellItemSelectView, LogoutConfirmView
from utils.datetime_utils import safe_datetime_parse
















class CharacterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self._galaxy_info_cache = None
        self._galaxy_info_cache_time = 0

    async def _safe_db_query(self, query, params=None, fetch='one', timeout_seconds=5, user_id=None):
        """Execute database query with timeout and error handling"""
        import asyncio
        
        def run_query():
            return self.db.execute_query(query, params, fetch=fetch)
        
        try:
            # Run the query with a timeout
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, run_query),
                timeout=timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            print(f"🚨 TQE: Database query timeout ({timeout_seconds}s) for user {user_id}: {query[:100]}...")
            return None
        except Exception as e:
            print(f"❌ TQE: Database query error for user {user_id}: {e}")
            return None
    
    



# Add this to your character.py cog

    def _get_galaxy_info(self):
        """Get galaxy information including time, shift, players online, and galaxy name"""
        import time
        
        # Cache galaxy info for 30 seconds to reduce database load
        current_time = time.time()
        if (self._galaxy_info_cache and 
            current_time - self._galaxy_info_cache_time < 30):
            return self._galaxy_info_cache
        
        try:
            # Get current galaxy time using TimeSystem
            try:
                from utils.time_system import TimeSystem
                time_system = TimeSystem(self.bot)
                current_datetime = time_system.calculate_current_ingame_time()
                if current_datetime:
                    current_date = time_system.format_ingame_datetime(current_datetime)
                    # Get the current shift
                    shift_name, shift_period = time_system.get_current_shift()
                else:
                    current_date = "Unknown Date"
                    shift_name = "Unknown Shift"
                    shift_period = "unknown"
            except:
                # Fallback if TimeSystem is not available
                current_date = "Unknown Date"
                shift_name = "Unknown Shift"
                shift_period = "unknown"

            # Get logged in players count and galaxy name in a single optimized query
            combined_info = self.bot.db.execute_query(
                """SELECT 
                    (SELECT COUNT(*) FROM characters WHERE is_logged_in = true) as logged_in_count,
                    (SELECT name FROM galaxy_info WHERE galaxy_id = 1) as galaxy_name""",
                fetch='one'
            )

            if combined_info:
                logged_in_count, galaxy_name = combined_info
            else:
                logged_in_count = 0
                galaxy_name = "Unknown Galaxy"

            # Add shift emoji based on period
            shift_emojis = {
                "morning": "🌅",
                "day": "☀️",
                "evening": "🌆",
                "night": "🌙"
            }
            shift_emoji = shift_emojis.get(shift_period, "🌐")

            result = {
                'galaxy_name': galaxy_name or "Unknown Galaxy",
                'current_date': current_date,
                'shift_name': shift_name,
                'shift_emoji': shift_emoji,
                'logged_in_count': logged_in_count or 0
            }
            
            # Cache the result
            self._galaxy_info_cache = result
            self._galaxy_info_cache_time = current_time
            
            return result
            
        except Exception as e:
            print(f"⚠️ Error getting galaxy info: {e}")
            # Return fallback data
            return {
                'galaxy_name': "The Quiet End",
                'current_date': "Unknown Date",
                'shift_name': "Unknown Shift",
                'shift_emoji': "🌐",
                'logged_in_count': 0
            }

    @app_commands.command(name="tqe", description="The Quiet End - View game overview panel")
    async def tqe_overview(self, interaction: discord.Interaction):
        """Display The Quiet End overview panel with character, location, and galaxy info"""
        
        # Defer response to prevent Discord timeout during database operations
        await interaction.response.defer(ephemeral=True)
        
        import time
        start_time = time.time()
        
        try:
            # Check if user has a character
            char_data = self.db.execute_query(
                """SELECT name, is_logged_in, current_location, current_ship_id, 
                   location_status, money
                   FROM characters WHERE user_id = %s""",
                (interaction.user.id,),
                fetch='one'
            )
        
            # Check if this command is being run in a location channel
            from utils.channel_manager import ChannelManager
            channel_manager = ChannelManager(self.bot)
            location_channel_check = channel_manager.get_location_from_channel_id(
                interaction.guild.id, 
                interaction.channel.id
            )
            
            # Check if this command is being run in a home interior channel
            home_channel_check = self.db.execute_query(
                "SELECT home_id FROM home_interiors WHERE channel_id = %s",
                (interaction.channel.id,),
                fetch='one'
            )
            
            # Check if this command is being run in a ship interior channel
            ship_channel_check = self.db.execute_query(
                "SELECT ship_id FROM ships WHERE channel_id = %s",
                (interaction.channel.id,),
                fetch='one'
            )
            
            # Check if this command is being run in a transit channel
            # Transit channels have names starting with "transit-" and are typically in the transit category
            transit_channel_check = (
                interaction.channel.name.startswith("transit-") and 
                interaction.channel.category and 
                interaction.channel.category.name == "🚀 IN TRANSIT"
            )
            
            # Show basic panel unless user is logged in AND in a recognized channel (location, home, ship, or transit)
            # Basic panel conditions: (no character) OR (not logged in) OR (not in any recognized channel)
            show_basic_panel = (
                not char_data or 
                (char_data and not char_data[1]) or  # char_data[1] is is_logged_in
                (not location_channel_check and not home_channel_check and not ship_channel_check and not transit_channel_check)
            )
            
            if show_basic_panel:
                galaxy_info = self._get_galaxy_info()
                
                # Create basic embed with galaxy info only
                embed = discord.Embed(
                    title="🌌 The Quiet End - Galaxy Overview",
                    description="Current galaxy status and information",
                    color=0x1a1a2e
                )
                
                embed.add_field(
                    name="🌍 Galaxy",
                    value=f"**Name:** {galaxy_info['galaxy_name']}\n"
                          f"**Date:** {galaxy_info['current_date']}\n"
                          f"**Shift:** {galaxy_info['shift_emoji']} {galaxy_info['shift_name']}\n"
                          f"**Players Online:** {galaxy_info['logged_in_count']}",
                    inline=False
                )
                
                # Customize message based on whether user has a character
                if char_data:
                    getting_started_text = "• Click **Login** to connect to your character\n• Use `/tqe` in a location channel after logging in for full features"
                else:
                    getting_started_text = "• Click **Login** to connect to your character\n• Use the game panel to create a character if you don't have a character yet"
                
                embed.add_field(
                    name="🚀 Getting Started",
                    value=getting_started_text,
                    inline=False
                )
                
                embed.set_footer(text="The Quiet End • Use Login to access full features")
                
                # Import BasicTQEView from utils.views
                from utils.views import BasicTQEView
                view = BasicTQEView(self.bot)
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                return
            
            # Original behavior for no character in location channels or other scenarios
            if not char_data:
                await interaction.followup.send(
                    "You don't have a character! Use the game panel to create a character first.",
                    ephemeral=True
                )
                return
            
            char_name, is_logged_in, current_location, current_ship_id, location_status, money = char_data
            
            # Get age from character_identity table
            age_data = self.db.execute_query(
                "SELECT age FROM character_identity WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            age = age_data[0] if age_data else "Unknown"
            
            # Create the main embed
            embed = discord.Embed(
                title="🌌 The Quiet End - Overview",
                description=f"**{char_name}**'s Status Overview",
                color=0x1a1a2e
            )
            
            # Character Information Section
            status_emoji = "🟢" if is_logged_in else "⚫"
            status_text = "Online" if is_logged_in else "Offline"
            embed.add_field(
                name="👤 Character",
                value=f"**Status:** {status_emoji} {status_text}\n"
                      f"**Age:** {age} years\n"
                      f"**Credits:** {money:,}",
                inline=True
            )
            
            # Location/Transit Information Section
            if location_status == "traveling" or not current_location:
                # Get travel session info using separated queries to avoid JOIN hangs
                print(f"🚨 TQE: User {interaction.user.id} in travel state - checking for corruption (location_status='{location_status}', current_location={current_location})")
                
                # Step 1: Get basic travel session data first with timeout
                travel_session = await self._safe_db_query(
                    """SELECT origin_location, destination_location, corridor_id,
                              end_time, temp_channel_id,
                              EXTRACT(EPOCH FROM (end_time - NOW())) / 86400.0 as time_remaining
                       FROM travel_sessions 
                       WHERE user_id = %s AND status = 'traveling'""",
                    (interaction.user.id,),
                    fetch='one',
                    timeout_seconds=3,
                    user_id=interaction.user.id
                )
                
                if travel_session:
                    origin_id, dest_id, corridor_id, end_time, temp_channel_id, time_remaining = travel_session
                    print(f"📍 TQE: Travel session found for user {interaction.user.id} - origin:{origin_id}, dest:{dest_id}, corridor:{corridor_id}")
                    
                    # Step 2: Get location names separately (safer than JOINs)
                    origin_name = "Unknown Origin"
                    dest_name = "Unknown Destination"
                    corridor_name = "Unknown Corridor"
                    
                    # Step 2: Get location names with individual timeouts
                    if origin_id:
                        origin_data = await self._safe_db_query("SELECT name FROM locations WHERE location_id = %s", (origin_id,), timeout_seconds=2, user_id=interaction.user.id)
                        origin_name = origin_data[0] if origin_data else f"Location #{origin_id}"
                    
                    if dest_id:
                        dest_data = await self._safe_db_query("SELECT name FROM locations WHERE location_id = %s", (dest_id,), timeout_seconds=2, user_id=interaction.user.id)
                        dest_name = dest_data[0] if dest_data else f"Location #{dest_id}"
                    
                    if corridor_id:
                        corridor_data = await self._safe_db_query("SELECT name FROM corridors WHERE corridor_id = %s", (corridor_id,), timeout_seconds=2, user_id=interaction.user.id)
                        corridor_name = corridor_data[0] if corridor_data else f"Corridor #{corridor_id}"
                    
                    travel_info = (origin_id, dest_id, corridor_id, end_time, temp_channel_id, 
                                 origin_name, dest_name, corridor_name, time_remaining)
                else:
                    travel_info = None
                    print(f"❌ TQE: No travel session found for user {interaction.user.id} despite traveling status!")
                
                if travel_info:
                    origin_id, dest_id, corridor_id, end_time, temp_channel_id, \
                    origin_name, dest_name, corridor_name, time_remaining = travel_info
                    
                    # Convert time remaining to hours and minutes
                    if time_remaining and time_remaining > 0:
                        hours_remaining = int(time_remaining * 24)
                        minutes_remaining = int((time_remaining * 24 - hours_remaining) * 60)
                        time_str = f"{hours_remaining}h {minutes_remaining}m"
                    else:
                        time_str = "Arriving soon..."
                    
                    # Build transit status with corridor info
                    transit_value = f"**From:** {origin_name}\n"
                    transit_value += f"**To:** {dest_name}\n"
                    transit_value += f"**Via:** {corridor_name}\n"
                    transit_value += f"**ETA:** {time_str}"
                    
                    embed.add_field(
                        name="🚀 Transit Status",
                        value=transit_value,
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="📍 Location",
                        value="**Status:** In Transit\n**Destination:** Unknown",
                        inline=True
                    )
            else:
                # Get current location info
                location_name = "Unknown Location"
                location_type = ""
                if current_location:
                    location_info = self.db.execute_query(
                        "SELECT name, location_type FROM locations WHERE location_id = %s",
                        (current_location,),
                        fetch='one'
                    )
                    if location_info:
                        location_name = location_info[0]
                        location_type = location_info[1]
                
                status_emoji = "🛬" if location_status == "docked" else "🚀"
                embed.add_field(
                    name="📍 Location",
                    value=f"**Current:** {location_name}\n"
                          f"**Type:** {location_type.replace('_', ' ').title()}\n"
                          f"**Status:** {status_emoji} {location_status.replace('_', ' ').title()}",
                    inline=True
                )
            
            # Galaxy Information Section
            galaxy_info = self._get_galaxy_info()
            
            embed.add_field(
                name="🌍 Galaxy",
                value=f"**Name:** {galaxy_info['galaxy_name']}\n"
                      f"**Date:** {galaxy_info['current_date']}\n"
                      f"**Shift:** {galaxy_info['shift_emoji']} {galaxy_info['shift_name']}\n"
                      f"**Players Online:** {galaxy_info['logged_in_count']}",
                inline=True
            )
            
            # Add instructions
            embed.add_field(
                name="📱 Quick Access",
                value="Use the buttons below to access detailed panels:",
                inline=False
            )
            
            embed.set_footer(text="The Quiet End • Use the buttons to navigate")
            
            # Create the view with buttons - use fallback if view creation fails
            view = None
            try:
                from utils.views import TQEOverviewView
                view = TQEOverviewView(self.bot, interaction.user.id)
            except Exception as view_error:
                print(f"⚠️ TQE: View creation failed for user {interaction.user.id}: {view_error}")
                # Continue without interactive buttons
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # Log successful completion time
            total_time = time.time() - start_time
            if total_time > 2.0:  # Log if takes longer than 2 seconds
                print(f"⚠️ TQE command took {total_time:.2f}s for user {interaction.user.id}")
            elif total_time > 5.0:  # Alert if extremely slow
                print(f"🚨 TQE command SLOW: {total_time:.2f}s for user {interaction.user.id}")
            
        except Exception as e:
            # Log the error for debugging
            print(f"❌ TQE Command Error for user {interaction.user.id}: {e}")
            
            # Create fallback embed
            embed = discord.Embed(
                title="🌌 The Quiet End - Service Temporarily Unavailable",
                description="The game servers are experiencing temporary issues. Please try again in a moment.",
                color=0xff6b6b
            )
            embed.add_field(
                name="ℹ️ Status",
                value="Our technical team has been notified and is working to resolve this issue.",
                inline=False
            )
            embed.set_footer(text="The Quiet End • Sorry for the inconvenience")
            
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                # If even the fallback fails, try basic text response
                try:
                    await interaction.followup.send(
                        "🚫 The Quiet End is temporarily unavailable. Please try again in a moment.",
                        ephemeral=True
                    )
                except:
                    # Last resort - at least log that we tried
                    print(f"❌ Failed to send any response to user {interaction.user.id} for /tqe command")

    @app_commands.command(name="db_health", description="[Admin] Check database connection health")
    @app_commands.default_permissions(administrator=True)
    async def db_health(self, interaction: discord.Interaction):
        """Check database connection pool health"""
        import time
        try:
            # Get pool status
            pool_status = self.bot.db.get_pool_status()
            
            # Test a simple query
            test_start = time.time()
            test_result = self.bot.db.execute_query("SELECT 1", fetch='one')
            test_time = time.time() - test_start
            
            embed = discord.Embed(
                title="🔍 Database Health Check",
                color=0x00ff00 if pool_status["status"] == "healthy" else 0xff0000
            )
            
            embed.add_field(
                name="Connection Pool",
                value=f"**Status:** {pool_status['status']}\n"
                      f"**Min Connections:** {pool_status.get('minconn', 'unknown')}\n"
                      f"**Max Connections:** {pool_status.get('maxconn', 'unknown')}",
                inline=False
            )
            
            embed.add_field(
                name="Query Test",
                value=f"**Response Time:** {test_time:.3f}s\n"
                      f"**Result:** {'✅ Success' if test_result else '❌ Failed'}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Database Health Check Failed",
                description=f"Error: {e}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="check_travel_corruption", description="[Admin] Check for corrupted travel session data")
    @app_commands.default_permissions(administrator=True)
    async def check_travel_corruption(self, interaction: discord.Interaction):
        """Check for users with corrupted travel session data that could cause /tqe timeouts"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Find travel sessions with invalid location/corridor references
            corrupt_sessions = self.bot.db.execute_query(
                """SELECT ts.user_id, ts.origin_location, ts.destination_location, ts.corridor_id,
                          c.name as char_name,
                          CASE WHEN ol.location_id IS NULL THEN 'Missing Origin' ELSE '' END as origin_issue,
                          CASE WHEN dl.location_id IS NULL THEN 'Missing Destination' ELSE '' END as dest_issue,
                          CASE WHEN cor.corridor_id IS NULL THEN 'Missing Corridor' ELSE '' END as corridor_issue
                   FROM travel_sessions ts
                   JOIN characters c ON ts.user_id = c.user_id
                   LEFT JOIN locations ol ON ts.origin_location = ol.location_id
                   LEFT JOIN locations dl ON ts.destination_location = dl.location_id  
                   LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                   WHERE ts.status = 'traveling'
                   AND (ol.location_id IS NULL OR dl.location_id IS NULL OR cor.corridor_id IS NULL)""",
                fetch='all'
            )
            
            # Find characters in traveling state without travel sessions
            orphaned_travelers = self.bot.db.execute_query(
                """SELECT c.user_id, c.name, c.location_status
                   FROM characters c
                   LEFT JOIN travel_sessions ts ON c.user_id = ts.user_id AND ts.status = 'traveling'
                   WHERE c.location_status = 'traveling' AND ts.user_id IS NULL""",
                fetch='all'
            )
            
            embed = discord.Embed(
                title="🔍 Travel Data Corruption Report",
                color=0xff6600 if corrupt_sessions or orphaned_travelers else 0x00ff00
            )
            
            if corrupt_sessions:
                corrupt_list = []
                for session in corrupt_sessions[:10]:  # Limit to first 10
                    user_id, origin_id, dest_id, corridor_id, char_name, origin_issue, dest_issue, corridor_issue = session
                    issues = [i for i in [origin_issue, dest_issue, corridor_issue] if i]
                    corrupt_list.append(f"• **{char_name}** (ID: {user_id}): {', '.join(issues)}")
                
                embed.add_field(
                    name=f"❌ Corrupted Travel Sessions ({len(corrupt_sessions)})",
                    value='\n'.join(corrupt_list) + (f"\n... and {len(corrupt_sessions)-10} more" if len(corrupt_sessions) > 10 else ""),
                    inline=False
                )
            
            if orphaned_travelers:
                orphan_list = []
                for traveler in orphaned_travelers[:10]:
                    user_id, char_name, status = traveler
                    orphan_list.append(f"• **{char_name}** (ID: {user_id})")
                
                embed.add_field(
                    name=f"👻 Orphaned Travelers ({len(orphaned_travelers)})",
                    value='\n'.join(orphan_list) + (f"\n... and {len(orphaned_travelers)-10} more" if len(orphaned_travelers) > 10 else ""),
                    inline=False
                )
            
            if not corrupt_sessions and not orphaned_travelers:
                embed.add_field(
                    name="✅ All Clear",
                    value="No corrupted travel session data found.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🔧 Recommended Action",
                    value="Use `/fix_travel_corruption` to clean up corrupted data, or manually reset affected users' location_status to 'docked'.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Corruption Check Failed",
                description=f"Error checking travel data: {e}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="fix_travel_corruption", description="[Admin] Clean up corrupted travel session data")
    @app_commands.default_permissions(administrator=True)
    async def fix_travel_corruption(self, interaction: discord.Interaction, confirm: bool = False):
        """Clean up corrupted travel session data that causes /tqe timeouts"""
        
        if not confirm:
            embed = discord.Embed(
                title="⚠️ Travel Data Cleanup Confirmation",
                description="This will clean up corrupted travel session data. **This action cannot be undone.**",
                color=0xff6600
            )
            embed.add_field(
                name="What this will do:",
                value="• Delete travel sessions with invalid location/corridor references\n"
                      "• Reset characters stuck in 'traveling' status to 'docked'\n"
                      "• Clean up orphaned travel session records",
                inline=False
            )
            embed.add_field(
                name="To proceed:",
                value="Run `/fix_travel_corruption confirm:True`",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            fixed_count = 0
            
            # Step 1: Find and delete travel sessions with invalid references
            print("🔧 Starting travel session cleanup...")
            
            # Get corrupted sessions before deleting them
            corrupt_sessions = self.bot.db.execute_query(
                """SELECT ts.user_id, c.name as char_name
                   FROM travel_sessions ts
                   JOIN characters c ON ts.user_id = c.user_id
                   LEFT JOIN locations ol ON ts.origin_location = ol.location_id
                   LEFT JOIN locations dl ON ts.destination_location = dl.location_id  
                   LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                   WHERE ts.status = 'traveling'
                   AND (ol.location_id IS NULL OR dl.location_id IS NULL OR cor.corridor_id IS NULL)""",
                fetch='all'
            )
            
            if corrupt_sessions:
                # Delete corrupted travel sessions
                deleted_sessions = self.bot.db.execute_query(
                    """DELETE FROM travel_sessions 
                       WHERE travel_session_id IN (
                           SELECT ts.travel_session_id
                           FROM travel_sessions ts
                           LEFT JOIN locations ol ON ts.origin_location = ol.location_id
                           LEFT JOIN locations dl ON ts.destination_location = dl.location_id  
                           LEFT JOIN corridors cor ON ts.corridor_id = cor.corridor_id
                           WHERE ts.status = 'traveling'
                           AND (ol.location_id IS NULL OR dl.location_id IS NULL OR cor.corridor_id IS NULL)
                       )"""
                )
                fixed_count += len(corrupt_sessions)
                print(f"✅ Deleted {len(corrupt_sessions)} corrupted travel sessions")
            
            # Step 2: Reset orphaned travelers to docked status
            orphaned_travelers = self.bot.db.execute_query(
                """SELECT c.user_id, c.name
                   FROM characters c
                   LEFT JOIN travel_sessions ts ON c.user_id = ts.user_id AND ts.status = 'traveling'
                   WHERE c.location_status = 'traveling' AND ts.user_id IS NULL""",
                fetch='all'
            )
            
            if orphaned_travelers:
                # Reset their status to docked
                for user_id, char_name in orphaned_travelers:
                    self.bot.db.execute_query(
                        "UPDATE characters SET location_status = 'docked' WHERE user_id = %s",
                        (user_id,)
                    )
                    print(f"🔧 Reset {char_name} (ID: {user_id}) from traveling to docked")
                
                fixed_count += len(orphaned_travelers)
            
            # Step 3: Clean up any completed/cancelled travel sessions that are lingering
            old_sessions = self.bot.db.execute_query(
                """DELETE FROM travel_sessions 
                   WHERE status IN ('completed', 'cancelled') 
                   AND end_time < NOW() - INTERVAL '24 hours'"""
            )
            
            # Step 4: Delete any transit channels that are no longer needed
            # (Optional - might want to keep this separate)
            
            embed = discord.Embed(
                title="✅ Travel Data Cleanup Complete",
                color=0x00ff00
            )
            
            if corrupt_sessions:
                char_names = [session[1] for session in corrupt_sessions]
                embed.add_field(
                    name=f"🗑️ Deleted Corrupted Sessions ({len(corrupt_sessions)})",
                    value=', '.join(char_names[:10]) + ('...' if len(char_names) > 10 else ''),
                    inline=False
                )
            
            if orphaned_travelers:
                char_names = [traveler[1] for traveler in orphaned_travelers]
                embed.add_field(
                    name=f"🚢 Reset to Docked ({len(orphaned_travelers)})",
                    value=', '.join(char_names[:10]) + ('...' if len(char_names) > 10 else ''),
                    inline=False
                )
            
            if not corrupt_sessions and not orphaned_travelers:
                embed.add_field(
                    name="🎯 No Issues Found",
                    value="No corrupted travel data needed cleanup.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 Summary",
                    value=f"Fixed **{fixed_count}** travel data issues.\n"
                          f"/tqe command should now work properly for all users.",
                    inline=False
                )
            
            embed.set_footer(text="Affected users should try /tqe again - it should work now!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Travel cleanup error: {e}")
            embed = discord.Embed(
                title="❌ Cleanup Failed",
                description=f"Error during travel data cleanup: {e}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="think", description="Share your character's internal thoughts")
    @app_commands.describe(thought="What your character is thinking")
    async def think(self, interaction: discord.Interaction, thought: str):
        char_data = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet! Use the game panel to create a character first.",
                ephemeral=True
            )
            return
        
        char_name = char_data[0]
        
        embed = discord.Embed(
            title="💭 Internal Thoughts",
            description=f"**{char_name}** thinks to themselves:",
            color=0x9370DB
        )
        embed.add_field(name="💭", value=f"*{thought}*", inline=False)
        
        # Try to award passive XP
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "think")
        if xp_awarded:
            embed.add_field(name="✨ Introspection", value="Deep thinking has expanded your awareness. (+5 XP)", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="observe", description="Describe what your character observes around them")
    @app_commands.describe(observation="What you observe in your surroundings")
    async def observe(self, interaction: discord.Interaction, observation: str):
        char_data = self.db.execute_query(
            "SELECT name, current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet! Use the game panel to create a character first.",
                ephemeral=True
            )
            return
        
        char_name, current_location = char_data
        
        # Get location name for context
        location_name = "Unknown Location"
        if current_location:
            loc_info = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = %s",
                (current_location,),
                fetch='one'
            )
            if loc_info:
                location_name = loc_info[0]
        
        embed = discord.Embed(
            title="👁️ Observation",
            description=f"**{char_name}** carefully observes their surroundings at **{location_name}**:",
            color=0x4682B4
        )
        embed.add_field(name="🔍 Noticed", value=observation, inline=False)
        
        # Try to award passive XP
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "observe")
        if xp_awarded:
            embed.add_field(name="✨ Awareness", value="You learn from your observations. (+5 XP)", inline=False)
        
        await interaction.response.send_message(embed=embed)

    
    character_group = app_commands.Group(name="character", description="Character management commands")

    @app_commands.command(name="status", description="Quick access to character information and management")
    async def status_shorthand(self, interaction: discord.Interaction):
        # Check if user has a character and get HP info
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in, hp, max_hp FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character! Use the game panel to create a character first.",
                ephemeral=True
            )
            return
        
        char_name, is_logged_in, hp, max_hp = char_data
        
        # Get ship fuel and hull info
        ship_data = self.db.execute_query(
            """SELECT s.current_fuel, s.fuel_capacity, s.hull_integrity, s.max_hull, s.name
               FROM ships s 
               INNER JOIN player_ships ps ON s.ship_id = ps.ship_id 
               WHERE ps.owner_id = %s AND ps.is_active = true""",
            (interaction.user.id,),
            fetch='one'
        )
        
        # Create the character panel embed
        embed = discord.Embed(
            title=f"📋 Character Panel: {char_name}",
            description="Quick access to your character information",
            color=0x4169E1
        )
        
        # Add status indicator
        status_emoji = "🟢" if is_logged_in else "⚫"
        status_text = "Online" if is_logged_in else "Offline"
        embed.add_field(name="Status", value=f"{status_emoji} {status_text}", inline=True)
        
        # Add HP info with modifiers
        from utils.stat_system import StatSystem
        stat_system = StatSystem(self.db)
        base_stats, effective_stats = stat_system.calculate_effective_stats(interaction.user.id)
        
        if base_stats and effective_stats:
            effective_max_hp = effective_stats.get('max_hp', max_hp)
            effective_hp = min(hp, effective_max_hp)
            hp_percent = (effective_hp / effective_max_hp) * 100 if effective_max_hp > 0 else 0
            hp_display = f"{effective_hp}/{stat_system.format_stat_display(base_stats.get('max_hp', max_hp), effective_max_hp)}"
        else:
            hp_percent = (hp / max_hp) * 100 if max_hp > 0 else 0
            hp_display = f"{hp}/{max_hp}"
        
        hp_emoji = "🟢" if hp_percent > 70 else "🟡" if hp_percent > 30 else "🔴"
        embed.add_field(name="Health", value=f"{hp_emoji} {hp_display}", inline=True)
        
        # Add defense if > 0
        if base_stats and effective_stats:
            defense_value = effective_stats.get('defense', 0)
            if defense_value > 0:
                base_defense = base_stats.get('defense', 0)
                defense_display = stat_system.format_stat_display(base_defense, defense_value)
                embed.add_field(name="Defense", value=f"🛡️ {defense_display}%", inline=True)
        
        # Add ship info if available
        if ship_data:
            current_fuel, fuel_capacity, hull_integrity, max_hull, ship_name = ship_data
            
            # Fuel status
            fuel_percent = (current_fuel / fuel_capacity) * 100 if fuel_capacity > 0 else 0
            fuel_emoji = "🟢" if fuel_percent > 70 else "🟡" if fuel_percent > 30 else "🔴"
            embed.add_field(name="Fuel", value=f"{fuel_emoji} {current_fuel}/{fuel_capacity}", inline=True)
            
            # Hull status  
            hull_percent = (hull_integrity / max_hull) * 100 if max_hull > 0 else 0
            hull_emoji = "🟢" if hull_percent > 70 else "🟡" if hull_percent > 30 else "🔴"
            embed.add_field(name="Hull", value=f"{hull_emoji} {hull_integrity}/{max_hull}", inline=True)
        else:
            embed.add_field(name="Ship", value="❌ No active ship", inline=True)
        
        embed.add_field(
            name="Available Actions",
            value="Use the buttons below to access different aspects of your character:",
            inline=False
        )
        
        embed.set_footer(text="Click the buttons below to view detailed information")
        
        view = CharacterPanelView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="here", description="Quick access to location panel and interactions")
    async def here_shorthand(self, interaction: discord.Interaction):
        # Check if this command is being run in a ship interior channel
        ship_channel_check = self.db.execute_query(
            "SELECT ship_id, name, ship_type, interior_description, owner_id FROM ships WHERE channel_id = %s",
            (interaction.channel.id,),
            fetch='one'
        )
        
        if ship_channel_check:
            # User is running command in a ship interior channel, use ShipInteriorView
            from utils.views import ShipInteriorView
            view = ShipInteriorView(self.bot, interaction.user.id)
            
            ship_id, ship_name, ship_type, interior_desc, owner_id = ship_channel_check
            
            embed = discord.Embed(
                title="🚀 Ship Interior Panel",
                description=f"**{ship_name}** ({ship_type}) - Ship Control Panel",
                color=0x1f2937
            )
            
            if interior_desc:
                embed.add_field(
                    name="Interior Description",
                    value=interior_desc[:1000] + ("..." if len(interior_desc) > 1000 else ""),
                    inline=False
                )
            
            # Show if user is owner or visitor
            status = "Owner" if owner_id == interaction.user.id else "Visitor"
            embed.add_field(
                name="Status",
                value=f"⚡ {status}",
                inline=True
            )
            
            embed.add_field(
                name="Available Actions",
                value="Use the buttons below to interact with the ship",
                inline=False
            )
            
            embed.set_footer(text="Use the buttons to control ship functions!")
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Check if this command is being run in a home interior channel
        home_channel_check = self.db.execute_query(
            """SELECT lh.home_id, lh.home_name, lh.owner_id, lh.interior_description 
               FROM location_homes lh 
               JOIN home_interiors hi ON lh.home_id = hi.home_id 
               WHERE hi.channel_id = %s""",
            (interaction.channel.id,),
            fetch='one'
        )
        
        if home_channel_check:
            # User is running command in a home interior channel, use HomeInteriorView
            from utils.views import HomeInteriorView
            view = HomeInteriorView(self.bot, interaction.user.id)
            
            home_id, home_name, owner_id, interior_desc = home_channel_check
            
            embed = discord.Embed(
                title="🏠 Home Interior Panel",
                description=f"**{home_name}** - Home Control Panel",
                color=0x8B4513
            )
            
            if interior_desc:
                embed.add_field(
                    name="Interior Description",
                    value=interior_desc[:1000] + ("..." if len(interior_desc) > 1000 else ""),
                    inline=False
                )
            
            # Show if user is owner or visitor
            status = "Owner" if owner_id == interaction.user.id else "Visitor"
            embed.add_field(
                name="Status",
                value=f"🏡 {status}",
                inline=True
            )
            
            embed.add_field(
                name="Available Actions",
                value="Use the buttons below to interact with your home",
                inline=False
            )
            
            embed.set_footer(text="Use the buttons to control home functions!")
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Check if this command is being run in a location channel
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        location_channel_check = channel_manager.get_location_from_channel_id(
            interaction.guild.id, 
            interaction.channel.id
        )
        
        if location_channel_check:
            # User is running command in a location channel, use normal location panel
            await self.location_info.callback(self, interaction)
            return
        
        # Fall back to normal location panel for other channels
        await self.location_info.callback(self, interaction)
    

    
    @app_commands.command(
    name="act",
    description="Perform a roleplay action"
    )
    @app_commands.describe(
        action="Describe your character’s action"
    )
    async def act(self, interaction: discord.Interaction, action: str):
        # fetch character name from your DB
        row = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch="one"
        )
        if not row:
            await interaction.response.send_message(
                "You don’t have a character yet! Use the game panel to create a character first.",
                ephemeral=True
            )
            return

        char_name = row[0]
        # send publicly in the channel
        await interaction.response.send_message(f"{char_name} *{action}*")
        
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "act")
        if xp_awarded:
            try:
                await interaction.followup.send("✨ *You feel slightly more experienced from that action.* (+5 XP)", ephemeral=True)
            except:
                pass  # Ignore if follow-up fails

    @app_commands.command(
        name="say", 
        description="Speak as your character"
    )
    @app_commands.describe(
        message="What your character says"
    )
    async def say(self, interaction: discord.Interaction, message: str):
        # Check if user has a logged-in character
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = %s AND is_logged_in = true",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet or your character isn't logged in! Use the game panel to create a character first and make sure to log in.",
                ephemeral=True
            )
            return

        char_name = char_data[0]
        # Use the same format as the automatic message replacement system
        speech_content = f"**{char_name}** says: {message}"
        
        await interaction.response.send_message(speech_content)
        
        # Award passive XP like other roleplay commands
        xp_awarded = await self.try_award_passive_xp(interaction.user.id, "say")
        if xp_awarded:
            try:
                await interaction.followup.send("✨ *Your words resonate with newfound understanding.* (+5 XP)", ephemeral=True)
            except:
                pass  # Ignore if follow-up fails
                
    @character_group.command(name="create", description="Create a new character")
    async def create_character(self, interaction: discord.Interaction):
        existing = self.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        current_year = 2751  # fallback default
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            current_time = time_system.calculate_current_ingame_time()
            if current_time:
                current_year = current_time.year
        except:
            pass  # Use fallback if time system unavailable
        if existing:
            await interaction.response.send_message(
                "You already have a character! Use the game panel to create a character to see your stats.",
                ephemeral=True
            )
            return
        
        from utils.views import CharacterCreationView
        view = CharacterCreationView(self.bot)
        embed = discord.Embed(
            title="Welcome to the Galaxy",
            description=f"The year is {current_year}. Humanity is scattered across failing colonies connected by unstable Corridors. Click below to create your character and begin your journey.",
            color=0x8B4513
        )
        embed.add_field(
            name="Starting Equipment",
            value="• Basic ship with 100 fuel capacity\n• 500 credits\n• Basic stats in all skills",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @character_group.command(name="dock", description="Dock your ship at the current location")
    async def dock_ship(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, location_status = char_data
                # This is the only combat check needed.
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog and combat_cog.check_any_combat_status(interaction.user.id):
            await interaction.response.send_message(
                "❌ You cannot dock while in combat!",
                ephemeral=True
            )
            return
        
        if location_status == "docked":
            await interaction.response.send_message("You're already docked at this location!", ephemeral=True)
            return
        
        # Dock the ship
        self.db.execute_query(
            "UPDATE characters SET location_status = 'docked' WHERE user_id = %s",
            (interaction.user.id,)
        )
        
        # Get character name and location name for roleplay message
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (current_location,),
            fetch='one'
        )[0]
        
        # Send visible roleplay message with embed
        embed = discord.Embed(
            title="🛬 Docked",
            description=f"**{char_name}** has docked their ship at **{location_name}**",
            color=0x00aa00
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @character_group.command(name="undock", description="Undock and move to space near the location")
    async def undock_ship(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT current_location, location_status, current_ship_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        # This is the only combat check needed.
        combat_cog = self.bot.get_cog('CombatCog')
        if combat_cog and combat_cog.check_any_combat_status(interaction.user.id):
            await interaction.response.send_message(
                "❌ You cannot undock while in combat!",
                ephemeral=True
            )
            return
        current_location, location_status, current_ship_id = char_data
        
        # block if inside ship interior
        if current_ship_id:
            await interaction.response.send_message(
                "❌ You cannot undock while inside your ship interior! Use `/tqe` to leave your ship first.",
                ephemeral=True
            )
            return
        
        # Check for active jobs that need to be completed at this location
        # Only block undocking for stationary jobs or transport jobs without a different destination
        blocking_jobs = self.db.execute_query(
            '''SELECT COUNT(*) FROM jobs j 
               LEFT JOIN job_tracking jt ON j.job_id = jt.job_id
               WHERE j.taken_by = %s AND j.job_status = 'active' 
               AND (jt.start_location = %s OR (jt.start_location IS NULL AND j.location_id = %s))
               AND (j.destination_location_id IS NULL OR j.destination_location_id = %s)''',
            (interaction.user.id, current_location, current_location, current_location),
            fetch='one'
        )[0]
        
        if blocking_jobs > 0:
            embed = discord.Embed(
                title="⚠️ Active Job Warning",
                description=f"You have {blocking_jobs} active job(s) that must be completed at this location. Undocking will cancel them!",
                color=0xff9900
            )
            embed.add_field(
                name="Confirm Undocking%s",
                value="This will cancel your active jobs without reward.",
                inline=False
            )
            
            view = UndockJobConfirmView(self.bot, interaction.user.id, current_location)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        if not current_location:
            await interaction.response.send_message("You're in deep space!", ephemeral=True)
            return
        
        if location_status == "in_space":
            await interaction.response.send_message("You're already in space near this location!", ephemeral=True)
            return
        
        # Undock the ship
        self.db.execute_query(
            "UPDATE characters SET location_status = 'in_space' WHERE user_id = %s",
            (interaction.user.id,)
        )
        
        # Get character name and location name for roleplay message
        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (current_location,),
            fetch='one'
        )[0]
        
        # Send visible roleplay message with embed
        embed = discord.Embed(
            title="🚀 Undocked",
            description=f"**{char_name}** has undocked their ship and entered space near **{location_name}**",
            color=0x4169e1
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
    @character_group.command(name="view", description="View your character information")
    async def view_character(self, interaction: discord.Interaction):
        result = self.bot.db.execute_query(
            '''
            SELECT 
              c.name,
              c.callsign,
              c.appearance,
              c.hp,
              c.max_hp,
              c.money,
              c.engineering,
              c.navigation,
              c.combat,
              c.medical,
              c.current_location,
              c.location_status,
              l.name    AS location_name,
              s.name    AS ship_name,
              s.current_fuel,
              s.fuel_capacity,
              s.ship_type,
              c.experience,
              c.level,
              c.is_logged_in,
              c.current_ship_id,
              c.image_url
            FROM characters c
            LEFT JOIN locations l ON c.current_location = l.location_id
            LEFT JOIN ships     s ON c.ship_id       = s.ship_id
            WHERE c.user_id = %s
            ''',
            (interaction.user.id,),
            fetch='one'
        )

        if not result:
            await interaction.response.send_message(
                "You don't have a character! Use the game panel to create a character first.",
                ephemeral=True
            )
            return

        # Show full character info (with stats) to the owner
        (name, callsign, appearance, hp, max_hp, credits,
         eng, nav, combat_skill, medical_skill,
         current_location, location_status, location_name,
         ship_name, current_fuel, fuel_capacity, ship_type,
         experience, level, is_logged_in, current_ship_id, image_url) = result

        embed = discord.Embed(title=name, color=0x0099ff)
        # Add character image if available
        if image_url:
            embed.set_thumbnail(url=image_url)
        if callsign:
            embed.add_field(name="Radio Callsign", value=callsign, inline=True)
        # Health with modifiers
        from utils.stat_system import StatSystem
        stat_system = StatSystem(self.db)
        base_stats, effective_stats = stat_system.calculate_effective_stats(interaction.user.id)
        
        if base_stats and effective_stats:
            effective_max_hp = effective_stats.get('max_hp', max_hp)
            effective_hp = min(hp, effective_max_hp)  # Cap current HP to effective max
            hp_display = f"{effective_hp}/{stat_system.format_stat_display(base_stats.get('max_hp', max_hp), effective_max_hp)}"
        else:
            hp_display = f"{hp}/{max_hp}"
        
        embed.add_field(name="Health", value=hp_display, inline=True)
        embed.add_field(name="Credits", value=f"{credits:,}", inline=True)
        
        # Login status
        login_emoji = "🟢" if is_logged_in else "⚫"
        login_status_text = "Online" if is_logged_in else "Offline"
        embed.add_field(name="Status", value=f"{login_emoji} {login_status_text}", inline=True)
        
        # Get accurate location status including ship context
        location_status_text, location_data = get_character_location_status(self.bot.db, interaction.user.id)

        if location_data and location_data['type'] == 'location':
            # Character is at a location (possibly in ship interior)
            if 'ship_context' in location_data:
                # In ship interior
                emoji = "🚀"
                embed.add_field(name="Location", value=f"{emoji} {location_status_text}", inline=True)
            else:
                # Directly at location
                emoji = "🛬" if location_status == "docked" else "🚀"
                embed.add_field(name="Location", value=f"{emoji} {location_name} ({location_status})", inline=True)
        elif location_data and location_data['type'] == 'transit':
            # Character is in transit
            embed.add_field(name="Location", value=f"🚀 {location_status_text}", inline=True)
        else:
            # Character is truly lost in space
            embed.add_field(name="Location", value="💀 Lost in Deep Space", inline=True)

        # Skills with modifiers
        from utils.stat_system import StatSystem
        stat_system = StatSystem(self.db)
        base_stats, effective_stats = stat_system.calculate_effective_stats(interaction.user.id)
        
        if base_stats and effective_stats:
            # Show modified stats
            embed.add_field(
                name="Engineering", 
                value=stat_system.format_stat_display(base_stats.get('engineering', eng), effective_stats.get('engineering', eng)), 
                inline=True
            )
            embed.add_field(
                name="Navigation", 
                value=stat_system.format_stat_display(base_stats.get('navigation', nav), effective_stats.get('navigation', nav)), 
                inline=True
            )
            embed.add_field(
                name="Combat", 
                value=stat_system.format_stat_display(base_stats.get('combat', combat_skill), effective_stats.get('combat', combat_skill)), 
                inline=True
            )
            embed.add_field(
                name="Medical", 
                value=stat_system.format_stat_display(base_stats.get('medical', medical_skill), effective_stats.get('medical', medical_skill)), 
                inline=True
            )
            
            # Add defense if > 0
            defense_value = effective_stats.get('defense', 0)
            if defense_value > 0:
                embed.add_field(
                    name="Defense",
                    value=f"{stat_system.format_stat_display(base_stats.get('defense', 0), defense_value)}%",
                    inline=True
                )
        else:
            # Fallback to original display
            embed.add_field(name="Engineering", value=str(eng), inline=True)
            embed.add_field(name="Navigation", value=str(nav), inline=True)
            embed.add_field(name="Combat", value=str(combat_skill), inline=True)
            embed.add_field(name="Medical", value=str(medical_skill), inline=True)
        embed.add_field(name="⚖️ Reputation", value="Use `/tqe` and access the 'Extras > Bounties and Reputation' menu to view your standings.", inline=True)
        # Level & Experience
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Experience", value=f"{experience:,} EXP", inline=True)

        # Ship info
        if ship_name:
            embed.add_field(name="Ship", value=f"{ship_name} ({ship_type})", inline=True)
            embed.add_field(name="Fuel", value=f"{current_fuel}/{fuel_capacity}", inline=True)
        else:
            embed.add_field(name="Ship", value="No Ship", inline=True)

        # Location context hints
        if current_ship_id:
            embed.add_field(
                name="🚀 Ship Interior Status",
                value="• Inside your ship\n• Radio uses ship's docking location\n• Use `/tqe` to exit",
                inline=False
            )
        elif location_name:
            if location_status == "docked":
                embed.add_field(
                    name="🛬 Docked Status",
                    value="• Full location access\n• Personal combat available\n• Use `/tqe` to move to space",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🚀 In-Space Status",
                    value="• Ship combat available\n• Limited location services\n• Use `/tqe` to dock",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character_group.command(name="location", description="View current location and available actions")
    async def location_info(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT user_id, current_location, location_status FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character! Use the game panel to create a character first.",
                ephemeral=True
            )
            return
        
        user_id, current_location, location_status = char_data
        
        if not current_location:
            # Check if user is in transit
            travel_data = self.db.execute_query(
                """SELECT ts.origin_location, ts.destination_location, ts.corridor_id, 
                          ts.start_time, ts.end_time, ts.temp_channel_id,
                          ol.name as origin_name, dl.name as dest_name, 
                          c.name as corridor_name, c.travel_time
                   FROM travel_sessions ts
                   JOIN locations ol ON ts.origin_location = ol.location_id
                   JOIN locations dl ON ts.destination_location = dl.location_id
                   JOIN corridors c ON ts.corridor_id = c.corridor_id
                   WHERE ts.user_id = %s AND ts.status = 'traveling'""",
                (interaction.user.id,),
                fetch='one'
            )
            
            if travel_data:
                # User is in transit - show transit information
                origin_id, dest_id, corridor_id, start_time, end_time, temp_channel_id, \
                origin_name, dest_name, corridor_name, travel_time = travel_data
                
                # Calculate time remaining
                from datetime import datetime
                try:
                    end_dt = safe_datetime_parse(end_time)
                    now = datetime.utcnow()
                    time_remaining = (end_dt - now).total_seconds()
                    
                    if time_remaining > 0:
                        hours, remainder = divmod(int(time_remaining), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
                    else:
                        time_str = "Arriving soon..."
                except:
                    time_str = "Unknown"
                
                # Create transit embed
                embed = discord.Embed(
                    title="🚀 In Transit",
                    description=f"You are currently traveling through space.",
                    color=0x4169E1
                )
                
                embed.add_field(name="Corridor", value=corridor_name, inline=False)
                embed.add_field(name="Origin", value=origin_name, inline=True)
                embed.add_field(name="Destination", value=dest_name, inline=True)
                embed.add_field(name="Time Remaining", value=time_str, inline=True)
                
                # Add travel channel link if available
                if temp_channel_id:
                    embed.add_field(
                        name="Travel Channel",
                        value=f"<#{temp_channel_id}>",
                        inline=False
                    )
                
                embed.set_footer(text="Use /travel status for more details")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else:
                # Not in transit and no location - show original message
                await interaction.response.send_message(
                    "You're not at a location!",
                    ephemeral=True
                )
                return
        
        # Get location info using guild-specific system
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        channel_info = channel_manager.get_channel_id_from_location(
            interaction.guild.id, 
            current_location
        )
        
        # Get location name separately
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (current_location,),
            fetch='one'
        )
        
        location_info = None
        if channel_info and location_name:
            location_info = (location_name[0], channel_info[0])  # (name, channel_id)
        
        if not location_info:
            await interaction.response.send_message(
                "Location not found!",
                ephemeral=True
            )
            return
        
        location_name, channel_id = location_info
        
        # Create ephemeral location panel
        from utils.views import EphemeralLocationView
        view = EphemeralLocationView(self.bot, user_id)
        
        embed = discord.Embed(
            title="📍 Location Panel",
            description=f"**{location_name}** - Interactive Control Panel",
            color=0x4169E1
        )
        
        # Add status indicator
        status_emoji = "🛬" if location_status == "docked" else "🚀"
        embed.add_field(
            name="Status",
            value=f"{status_emoji} {location_status.replace('_', ' ').title()}",
            inline=True
        )
        
        embed.add_field(
            name="Available Actions",
            value="Use the buttons below to interact with this location",
            inline=False
        )
        
        embed.set_footer(text="Use the buttons to interact with the location!")
        
        # Send ephemeral response
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    @character_group.command(name="inventory", description="View your inventory")
    async def view_inventory(self, interaction: discord.Interaction):
        char_check = self.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_check:
            await interaction.response.send_message(
                "You don't have a character! Use the game panel to create a character first.",
                ephemeral=True
            )
            return
        
        items = self.db.execute_query(
            '''SELECT i.item_name, i.item_type, i.quantity, i.description, i.value, 
                      i.item_id, CASE WHEN ce.equipment_id IS NOT NULL THEN 1 ELSE 0 END as is_equipped
               FROM inventory i
               LEFT JOIN character_equipment ce ON i.item_id = ce.item_id AND ce.user_id = i.owner_id
               WHERE i.owner_id = %s
               ORDER BY is_equipped DESC, i.item_type, i.item_name''',
            (interaction.user.id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🎒 Interactive Inventory",
            description="Your current items and equipment",
            color=0x8B4513
        )
        
        if not items:
            embed.add_field(name="Empty", value="Your inventory is empty.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Group by item type for display
            item_types = {}
            total_value = 0
            
            for name, item_type, quantity, description, value, item_id, is_equipped in items:
                if item_type not in item_types:
                    item_types[item_type] = []
                
                item_types[item_type].append((name, quantity, value, is_equipped))
                total_value += value * quantity
            
            # Add summary of items by type
            for item_type, type_items in item_types.items():
                items_text = []
                for name, quantity, value, is_equipped in type_items[:5]:  # Limit display
                    qty_text = f" x{quantity}" if quantity > 1 else ""
                    value_text = f" ({value * quantity} credits)" if value > 0 else ""
                    equipped_text = " ⚡" if is_equipped else ""
                    items_text.append(f"{name}{qty_text}{value_text}{equipped_text}")
                
                if len(type_items) > 5:
                    items_text.append(f"...and {len(type_items) - 5} more")
                
                embed.add_field(
                    name=item_type.replace('_', ' ').title(),
                    value="\n".join(items_text) or "None",
                    inline=True
                )
            
            embed.add_field(name="Total Value", value=f"{total_value:,} credits", inline=False)
            embed.add_field(
                name="📋 Instructions", 
                value="Use the dropdown menu below to select and use an item from your inventory.",
                inline=False
            )
            
            # Create the interactive view
            from utils.views import InteractiveInventoryView
            view = InteractiveInventoryView(self.bot, interaction.user.id, items)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @character_group.command(name="id", description="View character ID information")
    @app_commands.describe(target="View another character's ID (if not scrubbed)")
    async def view_character_id(self, interaction: discord.Interaction, target: discord.Member = None):
        target_user = target or interaction.user
        
        # Get character and identity info
        char_result = self.bot.db.execute_query(
            '''SELECT c.name, c.callsign, c.appearance, ci.birth_month, ci.birth_day, 
                      ci.birth_year, ci.age, ci.biography, ci.id_scrubbed, l.name as birthplace,
                      c.image_url
               FROM characters c
               LEFT JOIN character_identity ci ON c.user_id = ci.user_id
               LEFT JOIN locations l ON ci.birthplace_id = l.location_id
               WHERE c.user_id = %s''',
            (target_user.id,),
            fetch='one'
        )        
        if not char_result:
            no_char_msg = "You don't" if target is None else f"{target.display_name} doesn't"
            await interaction.response.send_message(
                f"{no_char_msg} have a character!",
                ephemeral=True
            )
            return
        
        (name, callsign, appearance, birth_month, birth_day, birth_year, 
         age, biography, id_scrubbed, birthplace, image_url) = char_result
        
        # Check if ID is scrubbed and viewing someone else's ID
        if id_scrubbed and target_user.id != interaction.user.id:
            error_messages = [
                "❌ **ID LOOKUP ERROR**\n`ERR_ID_NOT_FOUND: Record corrupted or deleted`",
                "❌ **ACCESS DENIED**\n`ERR_DATABASE_CORRUPTED: Identity records unavailable`",
                "❌ **QUERY FAILED**\n`ERR_CONNECTION_TIMEOUT: Unable to retrieve identity data`",
                "❌ **ID SCRUBBED**\n`ERR_RECORD_PURGED: Identity information has been permanently removed`"
            ]
            await interaction.response.send_message(random.choice(error_messages), ephemeral=True)
            return
        
        # Show identity information
        embed = discord.Embed(
            title=f"📋 Character Identity: {name}",
            color=0x4169E1 if not id_scrubbed else 0x888888
        )

        if image_url and not id_scrubbed:
            embed.set_thumbnail(url=image_url)
        elif image_url and id_scrubbed and target_user.id == interaction.user.id:
            # Show image to owner even if ID is scrubbed
            embed.set_thumbnail(url=image_url)
        
        if id_scrubbed and target_user.id == interaction.user.id:
            embed.add_field(
                name="⚠️ ID Status",
                value="Your identity has been scrubbed. Others will see an error when viewing your ID.",
                inline=False
            )
        
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Callsign", value=callsign or "Unknown", inline=True)
        embed.add_field(name="Age", value=f"{age} years", inline=True)
        
        if birth_month and birth_day and birth_year:
            embed.add_field(name="Born", value=f"{birth_month:02d}/{birth_day:02d}/{birth_year}", inline=True)
        
        if birthplace:
            embed.add_field(name="Birthplace", value=birthplace, inline=True)
        
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        if appearance:
            embed.add_field(name="Physical Description", value=appearance, inline=False)
        
        if biography:
            embed.add_field(name="Biography", value=biography[:1000], inline=False)
        
        # Add scrubbing option for own character
        if target_user.id == interaction.user.id and not id_scrubbed:
            view = IDScrubView(self.bot, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="ship", description="View detailed ship information")
    async def view_ship(self, interaction: discord.Interaction):
        # Modified query to explicitly select the needed columns
        ship_data = self.db.execute_query(
            '''SELECT 
               s.ship_id,
               s.owner_id,
               s.name,
               s.ship_type,
               s.fuel_capacity,
               s.current_fuel,
               s.fuel_efficiency,
               s.combat_rating,
               s.hull_integrity,
               s.max_hull,
               s.cargo_capacity,
               s.cargo_used,
               s.ship_hp,
               s.max_ship_hp,
               s.created_at,
               s.ship_class,
               s.upgrade_slots,
               s.used_upgrade_slots,
               s.exterior_description,
               s.interior_description,
               s.channel_id,
               s.docked_at_location,
               c.name as owner_name
               FROM ships s
               JOIN characters c ON s.owner_id = c.user_id
               WHERE s.owner_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not ship_data:
            await interaction.response.send_message(
                "You don't have a ship! Create a character first.",
                ephemeral=True
            )
            return
        
        # FIX: The unpacking now includes the `docked_at_location` column to match the database schema.
        (ship_id,
         owner_id,
         name,
         ship_type,
         fuel_capacity,
         current_fuel,
         fuel_efficiency,
         combat_rating,
         hull_integrity,
         max_hull,
         cargo_capacity,
         cargo_used,
         ship_hp,
         max_ship_hp,
         created_at,
         ship_class,
         upgrade_slots,
         used_upgrade_slots,
         exterior_description,
         interior_description,
         channel_id,
         docked_at_location, # This was the missing column
         owner_name
        ) = ship_data
        
        embed = discord.Embed(
            title=name,
            description=f"Class: {ship_type}",
            color=0x2F4F4F
        )
        
        # Status indicators
        fuel_percent = (current_fuel / fuel_capacity) * 100 if fuel_capacity > 0 else 0
        hull_percent = (hull_integrity / max_hull) * 100 if max_hull > 0 else 0
        hp_percent = (ship_hp / max_ship_hp) * 100 if max_ship_hp > 0 else 0
        cargo_percent = (cargo_used / cargo_capacity) * 100 if cargo_capacity > 0 else 0
        
        # Fuel status
        fuel_emoji = "🟢" if fuel_percent > 70 else "🟡" if fuel_percent > 30 else "🔴"
        embed.add_field(
            name="Fuel",
            value=f"{fuel_emoji} {current_fuel}/{fuel_capacity} ({fuel_percent:.0f}%)",
            inline=True
        )
        
        # Hull status
        hull_emoji = "🟢" if hull_percent > 70 else "🟡" if hull_percent > 30 else "🔴"
        embed.add_field(
            name="Hull Integrity",
            value=f"{hull_emoji} {hull_integrity}/{max_hull} ({hull_percent:.0f}%)",
            inline=True
        )
        
        # Ship HP
        hp_emoji = "🟢" if hp_percent > 70 else "🟡" if hp_percent > 30 else "🔴"
        embed.add_field(
            name="Ship Health",
            value=f"{hp_emoji} {ship_hp}/{max_ship_hp} ({hp_percent:.0f}%)",
            inline=True
        )
        
        # Cargo
        cargo_emoji = "🟢" if cargo_percent < 70 else "🟡" if cargo_percent < 90 else "🔴"
        embed.add_field(
            name="Cargo",
            value=f"{cargo_emoji} {cargo_used}/{cargo_capacity} ({cargo_percent:.0f}% full)",
            inline=True
        )
        
        # Performance stats
        embed.add_field(name="Fuel Efficiency", value=f"{fuel_efficiency}/10", inline=True)
        embed.add_field(name="Combat Rating", value=f"{combat_rating}/10", inline=True)
        
        # Add warning if ship needs attention
        warnings = []
        if fuel_percent < 30:
            warnings.append("⚠️ Low fuel")
        if hull_percent < 50:
            warnings.append("⚠️ Hull damage")
        if hp_percent < 50:
            warnings.append("⚠️ Systems damaged")
        if cargo_percent > 90:
            warnings.append("⚠️ Cargo hold full")
        
        if warnings:
            embed.add_field(name="Alerts", value="\n".join(warnings), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="search", description="Search your current location for items")
    async def search_location(self, interaction: discord.Interaction):
        # Check character exists and get location
        char_data = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data or not char_data[0]:
            await interaction.response.send_message("You need to be at a location to search!", ephemeral=True)
            return
        
        current_location = char_data[0]
        
        # Check location type (no searching on ships or travel channels)
        location_info = self.db.execute_query(
            "SELECT name, location_type, wealth_level FROM locations WHERE location_id = %s",
            (current_location,),
            fetch='one'
        )
        
        if not location_info:
            await interaction.response.send_message("Invalid location!", ephemeral=True)
            return
        
        location_name, location_type, wealth_level = location_info
        
        # Check if location allows searching
        if location_type in ['ship', 'travel']:
            await interaction.response.send_message("You cannot search here!", ephemeral=True)
            return
        
        # Check cooldown
        cooldown_data = self.db.execute_query(
            "SELECT last_search_time FROM search_cooldowns WHERE user_id = %s AND location_id = %s",
            (interaction.user.id, current_location),
            fetch='one'
        )
        
        current_time = datetime.now()
        
        if cooldown_data:
            # Handle both datetime objects (PostgreSQL) and strings (SQLite)
            if isinstance(cooldown_data[0], datetime):
                last_search = cooldown_data[0]
            else:
                last_search = safe_datetime_parse(cooldown_data[0])
            time_diff = current_time - last_search
            
            # 15 minute cooldown
            if time_diff.total_seconds() < 900:  # 15 minutes
                remaining = 900 - time_diff.total_seconds()
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                await interaction.response.send_message(
                    f"You must wait {minutes}m {seconds}s before searching again.", 
                    ephemeral=True
                )
                return
        
        # Start search
        search_duration = random.randint(15, 60)  # 15-60 seconds
        
        embed = discord.Embed(
            title="🔍 Searching...",
            description=f"Searching **{location_name}** for items...",
            color=0xffff00
        )
        embed.add_field(name="Time Remaining", value=f"{search_duration} seconds", inline=True)
        embed.add_field(name="Location Type", value=location_type.replace('_', ' ').title(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Update search progress every 10-15 seconds
        updates = []
        if search_duration >= 30:
            updates.append(search_duration // 2)
        if search_duration >= 45:
            updates.append(search_duration // 3)
        
        for update_time in updates:
            await asyncio.sleep(update_time)
            remaining = search_duration - update_time
            search_duration = remaining
            
            # Random search progress message
            progress_messages = [
                "Examining debris and containers...",
                "Checking hidden compartments...", 
                "Scanning for valuable materials...",
                "Searching through scattered equipment...",
                "Looking in overlooked areas..."
            ]
            
            embed = discord.Embed(
                title="🔍 Searching...",
                description=f"Searching **{location_name}** for items...\n\n*{random.choice(progress_messages)}*",
                color=0xffff00
            )
            embed.add_field(name="Time Remaining", value=f"{remaining} seconds", inline=True)
            
            try:
                await interaction.edit_original_response(embed=embed)
            except:
                pass  # Message might be deleted
        
        # Final wait
        await asyncio.sleep(search_duration - sum(updates) if updates else search_duration)
        
        # Update cooldown
        self.db.execute_query(
            """INSERT INTO search_cooldowns (user_id, last_search_time, location_id) VALUES (%s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET 
               last_search_time = EXCLUDED.last_search_time, location_id = EXCLUDED.location_id""",
            (interaction.user.id, current_time, current_location)
        )
        
        # Generate search results
        # Check for dropped items at this location FIRST
        dropped_items = self.db.execute_query(
            '''SELECT item_name, item_type, SUM(quantity) as total_quantity, 
                      MAX(description) as description
               FROM location_items 
               WHERE location_id = %s
               GROUP BY item_name, item_type
               LIMIT 5''',
            (current_location,),
            fetch='all'
        )

        # Generate random search results
        from utils.item_config import ItemConfig
        random_items = ItemConfig.generate_search_loot(location_type, wealth_level)

        # Combine dropped items and random items
        found_items = []

        # Add dropped items first (guaranteed finds)
        for item_name, item_type, quantity, description in dropped_items:
            found_items.append((item_name, quantity))
            
            # Remove the dropped items from the location
            self.db.execute_query(
                "DELETE FROM location_items WHERE location_id = %s AND item_name = %s LIMIT %s",
                (current_location, item_name, quantity)
            )

        # Add random items if we haven't found too many already
        if len(found_items) < 3:
            for item in random_items[:3-len(found_items)]:
                found_items.append(item)

        # NOW CREATE THE RESULT EMBED - This happens regardless of finding items or not
        if not found_items:
            embed = discord.Embed(
                title="🔍 Search Complete",
                description=f"You thoroughly searched **{location_name}** but found nothing of value.",
                color=0x808080
            )
            embed.add_field(name="Better Luck Next Time", value="Try searching other locations or wait for the area to refresh.", inline=False)
        else:
            # Process found items and add to inventory
            items_added = []
            for item_name, quantity in found_items:
                # For dropped items, we already have the full item data
                # For random items, we need to get the item definition
                if isinstance(item_name, tuple):
                    # This is from ItemConfig.generate_search_loot() which returns (name, quantity)
                    actual_name = item_name[0]
                    actual_quantity = item_name[1]
                else:
                    actual_name = item_name
                    actual_quantity = quantity
                
                # Get item definition from ItemConfig
                from utils.item_config import ItemConfig
                item_def = ItemConfig.get_item_definition(actual_name)
                
                if item_def:
                    # Check if player already has this item
                    existing_item = self.db.execute_query(
                        "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
                        (interaction.user.id, actual_name),
                        fetch='one'
                    )
                    
                    if existing_item:
                        # Update existing stack
                        self.db.execute_query(
                            "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                            (actual_quantity, existing_item[0])
                        )
                    else:
                        # Create new inventory entry
                        metadata = ItemConfig.create_item_metadata(actual_name)
                        self.db.execute_query(
                            '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, 
                               description, value, metadata, equippable, equipment_slot, stat_modifiers)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                            (interaction.user.id, actual_name, item_def["type"], actual_quantity,
                             item_def["description"], item_def["base_value"], metadata, False, None, None)
                        )
                    
                    items_added.append(f"{actual_quantity}x **{actual_name}**")
                else:
                    # Fallback for items without definitions (like dropped items)
                    # Try to get info from dropped items data
                    for dropped in dropped_items:
                        if dropped[0] == actual_name:  # item_name matches
                            existing_item = self.db.execute_query(
                                "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
                                (interaction.user.id, actual_name),
                                fetch='one'
                            )
                            
                            if existing_item:
                                self.db.execute_query(
                                    "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                                    (actual_quantity, existing_item[0])
                                )
                            else:
                                # Ensure proper metadata using helper function
                                existing_metadata = dropped[6] if len(dropped) > 6 else None
                                metadata = ItemConfig.ensure_item_metadata(actual_name, existing_metadata)
                                
                                self.db.execute_query(
                                    '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, 
                                       description, value, metadata, equippable, equipment_slot, stat_modifiers)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                                    (interaction.user.id, actual_name, dropped[1], actual_quantity,
                                     dropped[3], dropped[4], metadata, False, None, None)
                                )
                            
                            items_added.append(f"{actual_quantity}x **{actual_name}**")
                            break
            
            embed = discord.Embed(
                title="🔍 Search Complete",
                description=f"You found items while searching **{location_name}**!",
                color=0x00ff00
            )
            embed.add_field(name="Items Found", value="\n".join(items_added), inline=False)
            embed.add_field(name="Next Search", value="You can search again in 15 minutes.", inline=False)

        # ALWAYS UPDATE THE MESSAGE - This is the key fix
        try:
            await interaction.edit_original_response(embed=embed)
        except discord.HTTPException:
            # If edit fails, try sending a followup
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                # If all else fails, at least log it
                print(f"Failed to send search results for user {interaction.user.id}")
            
    @character_group.command(name="look", description="Look around to see dropped items")
    async def look_around(self, interaction: discord.Interaction):
        # Get character location
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[0]:
            await interaction.response.send_message("You cannot look around while in transit!", ephemeral=True)
            return
        
        current_location = char_info[0]
        
        # Get location name
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (current_location,),
            fetch='one'
        )[0]
        
        # Get dropped items
        items = self.db.execute_query(
            '''SELECT item_name, quantity, dropped_by, dropped_at 
               FROM location_items 
               WHERE location_id = %s
               ORDER BY dropped_at DESC
               LIMIT 10''',
            (current_location,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"👀 Looking Around {location_name}",
            description="Items scattered around this location:",
            color=0x4169E1
        )
        
        if not items:
            embed.add_field(name="Nothing Here", value="The area appears to be clear of any dropped items.", inline=False)
        else:
            items_text = []
            for item_name, quantity, dropped_by, dropped_at in items:
                qty_text = f"x{quantity}" if quantity > 1 else ""
                items_text.append(f"• {item_name} {qty_text}")
            
            embed.add_field(
                name="Visible Items",
                value="\n".join(items_text[:10]),
                inline=False
            )
            embed.add_field(
                name="💡 Tip",
                value="Use `/character search` to find these items, or the game panel to create a character to grab a specific one!",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)        
            
         
    @character_group.command(name="delete", description="Permanently delete your character (cannot be undone!)")
    async def delete_character(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT name, money, hp FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character to delete.",
                ephemeral=True
            )
            return
        
        char_name, money, hp = char_data
        
        # Don't allow deletion if character is dead (HP = 0)
        if hp <= 0:
            await interaction.response.send_message(
                "Your character is dead and will be automatically removed. You cannot manually delete a dead character.",
                ephemeral=True
            )
            return
        
        # Import the view class from channel_manager
        from utils.channel_manager import CharacterDeleteConfirmView
        view = CharacterDeleteConfirmView(self.bot, interaction.user.id, char_name)
        
        embed = discord.Embed(
            title="⚠️ PERMANENT CHARACTER DELETION",
            description=f"You are about to **permanently delete** your character **{char_name}**.",
            color=0xff0000
        )
        
        embed.add_field(
            name="⚠️ WARNING",
            value="This action **CANNOT BE UNDONE**!\n\n• Your character will be completely removed\n• Your ship will be deleted\n• All inventory will be lost\n• All progress will be erased",
            inline=False
        )
        
        embed.add_field(
            name="💰 Current Assets",
            value=f"Credits: {money:,}\nHP: {hp}/100\nThese will be permanently lost!",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Confirmation Required",
            value="Click the button below to confirm permanent deletion.",
            inline=False
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    async def try_award_passive_xp(self, user_id: int, action_type: str = "roleplay"):
        """Award passive XP with 25% chance for roleplay actions"""
        import random
        
        # 25% chance to gain XP
        if random.random() > 0.25:
            return False
        
        # Check if character exists and is logged in
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_data or not char_data[1]:  # Character doesn't exist or not logged in
            return False
        
        char_name = char_data[0]
        xp_gained = 5
        
        # Award XP
        self.db.execute_query(
            "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
            (xp_gained, user_id)
        )
        
        # Check for level up
        await self.level_up_check(user_id)
        
        return True
        
    async def cleanup_character_homes(self, user_id: int):
        """Release all homes owned by a character when they die or are deleted"""
        
        # Get all owned homes
        owned_homes = self.db.execute_query(
            '''SELECT home_id, home_name, location_id FROM location_homes 
               WHERE owner_id = %s''',
            (user_id,),
            fetch='all'
        )
        
        if owned_homes:
            # Make all homes available again
            self.db.execute_query(
                '''UPDATE location_homes 
                   SET owner_id = NULL, is_available = true, purchase_date = NULL
                   WHERE owner_id = %s''',
                (user_id,)
            )
            
            # Remove any market listings
            self.db.execute_query(
                '''UPDATE home_market_listings 
                   SET is_active = false
                   WHERE seller_id = %s''',
                (user_id,)
            )
            
            # Clean up home interior threads
            for home_id, home_name, location_id in owned_homes:
                interior_info = self.db.execute_query(
                    "SELECT channel_id FROM home_interiors WHERE home_id = %s",
                    (home_id,),
                    fetch='one'
                )
                
                if interior_info and interior_info[0]:
                    try:
                        thread = self.bot.get_channel(interior_info[0])
                        if thread and isinstance(thread, discord.Thread):
                            await thread.edit(archived=True, reason="Owner character deleted")
                    except:
                        pass
            
            print(f"Released {len(owned_homes)} homes from character {user_id}")
    
    async def _handle_ship_exchange_death_cleanup(self, user_id: int):
        """Handle ship exchange listings when a player dies - transfer ships to location inventory"""
        
        # Get all active ship exchange listings owned by the deceased player
        listings = self.db.execute_query(
            '''SELECT sel.listing_id, sel.ship_id, sel.listed_at_location, sel.asking_price,
                      s.name, s.ship_type, s.tier, s.condition_rating, s.market_value,
                      s.cargo_capacity, s.speed_rating, s.combat_rating, s.fuel_efficiency
               FROM ship_exchange_listings sel
               JOIN ships s ON sel.ship_id = s.ship_id
               WHERE sel.owner_id = %s AND sel.is_active = true''',
            (user_id,),
            fetch='all'
        )
        
        if not listings:
            return
        
        print(f"Processing {len(listings)} ship exchange listings for deceased player {user_id}")
        
        for listing in listings:
            (listing_id, ship_id, location_id, asking_price, ship_name, ship_type, 
             tier, condition, market_value, cargo_capacity, speed_rating, 
             combat_rating, fuel_efficiency) = listing
            
            # Calculate reduced price (75% of asking price, minimum 50% of market value)
            reduced_price = max(int(asking_price * 0.75), int(market_value * 0.5))
            
            # Transfer ship to location's shipyard inventory
            try:
                self.db.execute_query(
                    '''INSERT INTO shipyard_inventory 
                       (location_id, ship_name, ship_type, ship_class, tier, price, 
                        cargo_capacity, speed_rating, combat_rating, fuel_efficiency, 
                        condition_rating, market_value, is_player_sold, original_owner_id)
                       VALUES (%s, %s, %s, 'civilian', %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)''',
                    (location_id, ship_name, ship_type, tier, reduced_price, 
                     cargo_capacity, speed_rating, combat_rating, fuel_efficiency, 
                     condition, market_value, user_id)
                )
                
                print(f"Transferred {ship_name} to location {location_id} inventory at {reduced_price:,} credits")
                
            except Exception as e:
                print(f"Failed to transfer ship {ship_name} to location inventory: {e}")
        
        # Deactivate all ship exchange listings from this player
        self.db.execute_query(
            "UPDATE ship_exchange_listings SET is_active = false WHERE owner_id = %s",
            (user_id,)
        )
        
        # Cancel all pending offers made by this player
        self.db.execute_query(
            "UPDATE ship_exchange_offers SET status = 'expired' WHERE offerer_id = %s",
            (user_id,)
        )
        
        # Cancel all pending offers on this player's ships
        offer_listings = [listing[0] for listing in listings]
        if offer_listings:
            placeholders = ','.join(['%s' for _ in offer_listings])
            self.db.execute_query(
                f"UPDATE ship_exchange_offers SET status = 'expired' WHERE listing_id IN ({placeholders})",
                offer_listings
            )
    
    async def check_character_death(self, user_id: int, guild: discord.Guild, reason: str = "unknown"):
        """Check if character has died (HP <= 0) and execute death if needed"""
        char_data = self.db.execute_query(
            "SELECT name, hp FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return False
        
        char_name, hp = char_data
        
        if hp <= 0:
            # Character is dead
            await self._execute_character_death(user_id, char_name, guild, reason)
            return True
        
        return False

    async def check_ship_death(self, user_id: int, guild: discord.Guild, reason: str = "ship destruction"):
        """Check if ship has been destroyed (hull <= 0) and execute character death if needed"""
        ship_data = self.db.execute_query(
            "SELECT hull_integrity FROM ships WHERE owner_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not ship_data:
            return False
        
        hull_integrity = ship_data[0]
        
        if hull_integrity <= 0:
            # Ship is destroyed - this kills the character
            char_name = self.db.execute_query(
                "SELECT name FROM characters WHERE user_id = %s",
                (user_id,),
                fetch='one'
            )
            
            if char_name:
                await self._execute_character_death(user_id, char_name[0], guild, reason)
                return True
        
        return False
    
    async def _execute_character_death(self, user_id: int, char_name: str, guild: discord.Guild, reason: str = "unknown"):
        """Execute automatic character death with enhanced descriptions."""
        member = guild.get_member(user_id)
        if member and guild.me.guild_permissions.manage_nicknames:
            # We only clear the nickname if it matches the character who is dying.
            # This avoids clearing a custom nickname the user may have set.
            if member.nick == char_name:
                try:
                    await member.edit(nick=None, reason="Character has died.")
                except Exception as e:
                    print(f"Failed to clear nickname on death for {member}: {e}")
        # Get detailed character info for the obituary and death message
        char_data = self.db.execute_query(
            "SELECT c.current_location, c.current_ship_id, l.name as loc_name "
            "FROM characters c "
            "LEFT JOIN locations l ON c.current_location = l.location_id "
            "WHERE c.user_id = %s",
            (user_id,),
            fetch='one'
        )

        location_id = None
        ship_id = None
        location_name = "Deep Space"
        if char_data:
            location_id, ship_id, location_name = char_data
            if ship_id and not location_id:
                ship_loc = self.db.execute_query(
                    "SELECT docked_at_location FROM ships WHERE ship_id = %s",
                    (ship_id,), fetch='one'
                )
                if ship_loc and ship_loc[0]:
                    location_id = ship_loc[0]
                    loc_name_result = self.db.execute_query(
                        "SELECT name FROM locations WHERE location_id = %s",
                        (location_id,), fetch='one'
                    )
                    if loc_name_result:
                        location_name = loc_name_result[0]


        # Post obituary FIRST, before deleting character data
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog and location_id:
            await news_cog.post_obituary_news(char_name, location_id, reason)

        # Delete character and associated data
        self.db.execute_query("DELETE FROM characters WHERE user_id = %s", (user_id,))
        self.db.execute_query("DELETE FROM character_identity WHERE user_id = %s", (user_id,))
        self.db.execute_query("DELETE FROM character_inventory WHERE user_id = %s", (user_id,))
        self.db.execute_query("DELETE FROM inventory WHERE owner_id = %s", (user_id,))
        
        # Handle ship exchange listings - transfer to location inventory before deleting ships
        await self._handle_ship_exchange_death_cleanup(user_id)
        
        # Comprehensive ship cleanup - delete ALL ships owned by the user
        self.db.execute_query("DELETE FROM ships WHERE owner_id = %s", (user_id,))
        self.db.execute_query("DELETE FROM player_ships WHERE owner_id = %s", (user_id,))
        
        # Clean up ship-related data
        if ship_id:
            self.db.execute_query("DELETE FROM ship_upgrades WHERE ship_id = %s", (ship_id,))
            self.db.execute_query("DELETE FROM ship_customizations WHERE ship_id = %s", (ship_id,))
            self.db.execute_query("DELETE FROM ship_activities WHERE ship_id = %s", (ship_id,))
            self.db.execute_query("DELETE FROM ship_interiors WHERE ship_id = %s", (ship_id,))
        self.db.execute_query(
            "UPDATE travel_sessions SET status = 'character_death' WHERE user_id = %s AND status = 'traveling'",
            (user_id,)
        )
        self.db.execute_query(
            "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL WHERE taken_by = %s",
            (user_id,)
        )
        await self.cleanup_character_homes(user_id)
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        member = guild.get_member(user_id)
        if member and location_id:
            await channel_manager.remove_user_location_access(member, location_id)


        # Create death announcement with gruesome descriptions
        death_descriptions = [
            f"The last transmission from **{char_name}** was a burst of static and a final, choked scream. Their vessel was later found vented to space, the crew lost to the cold vacuum.",
            f"An emergency beacon from **{char_name}'s** ship was detected, but rescue crews arrived too late. The ship's log detailed a catastrophic life support failure. There were no survivors.",
            f"**{char_name}**'s ship was found adrift, its hull breached by pirate munitions. The interior was a scene of violence and desperation. No one was left alive.",
            f"A critical engine malfunction caused **{char_name}**'s vessel to explode during transit. Debris was scattered across several kilometers of space. The crew was lost instantly.",
            f"After a hull breach during a firefight, **{char_name}** was exposed to hard vacuum. The body was later recovered, a frozen monument to the brutality of space.",
        ]
        obituary_text = random.choice(death_descriptions)

        embed = discord.Embed(
            title="💀 CHARACTER DEATH",
            description=obituary_text,
            color=0x000000
        )

        embed.add_field(
            name="⚰️ Final Rest",
            value=f"**{char_name}**'s journey has come to a violent end. Their story is now a cautionary tale whispered in station bars across the sector.",
            inline=False
        )

        embed.add_field(
            name="🔄 Starting Over",
            value="You can create a new character with `/character create` to begin a new journey.",
            inline=False
        )

        # Send DM to the deceased player with detailed death information
        if member:
            try:
                death_dm_embed = discord.Embed(
                    title="💀 Your Character Has Died",
                    description=f"**{char_name}** has met their end in the harsh void of space.",
                    color=0x8b0000
                )
                
                death_dm_embed.add_field(
                    name="📍 Location of Death",
                    value=location_name if location_name else "Deep Space",
                    inline=True
                )
                
                death_dm_embed.add_field(
                    name="⚰️ Cause of Death", 
                    value=reason.title() if reason != "unknown" else "Unknown Circumstances",
                    inline=True
                )
                
                death_dm_embed.add_field(
                    name="💫 What Happened",
                    value=obituary_text,
                    inline=False
                )
                
                death_dm_embed.add_field(
                    name="🔄 Next Steps",
                    value="Your character's journey has ended, but yours continues. Use the game panel to create a character to forge a new path among the stars.",
                    inline=False
                )
                
                death_dm_embed.set_footer(text="The void claims another soul. Your location channel access has been removed.")
                
                await member.send(embed=death_dm_embed)
            except discord.Forbidden:
                print(f"Could not send death DM to {member.display_name} - DMs disabled")
            except Exception as e:
                print(f"Error sending death DM to {member.display_name}: {e}")

        # Announce in all location channels using cross-guild broadcast
        if location_id:
            try:
                from utils.channel_manager import ChannelManager
                channel_manager = ChannelManager(self.bot)
                cross_guild_channels = await channel_manager.get_cross_guild_location_channels(location_id)
                
                death_announcement = discord.Embed(
                    title="💀 Tragedy Strikes",
                    description=f"A grim discovery has been made at {location_name}. **{char_name}** is dead.",
                    color=0x8b0000
                )
                death_announcement.add_field(
                    name="Cause of Death",
                    value=reason.title(),
                    inline=False
                )
                death_announcement.set_footer(text="Another soul lost to the void.")
                
                for guild_channel, channel in cross_guild_channels:
                    try:
                        await channel.send(embed=death_announcement)
                    except Exception as e:
                        print(f"Error sending death announcement to channel: {e}")
            except Exception as e:
                print(f"Error sending death announcement to location channels: {e}")

        print(f"💀 Character death (automatic): {char_name} (ID: {user_id}) - {reason}")

    async def update_character_hp(self, user_id: int, hp_change: int, guild: discord.Guild, reason: str = ""):
        """Update character HP and check for death"""
        # Handle healing (positive hp_change) normally
        if hp_change >= 0:
            self.db.execute_query(
                "UPDATE characters SET hp = GREATEST(0::bigint, hp + %s) WHERE user_id = %s",
                (hp_change, user_id)
            )
            return await self.check_character_death(user_id, guild, reason)
        
        # Handle damage (negative hp_change) with defense reduction
        from utils.stat_system import StatSystem
        stat_system = StatSystem(self.db)
        
        # Calculate damage reduction (convert to positive for calculation)
        damage_amount = abs(hp_change)
        final_damage, damage_reduced = stat_system.calculate_damage_reduction(user_id, damage_amount)
        
        # Apply the final damage (convert back to negative)
        final_hp_change = -final_damage
        
        self.db.execute_query(
            "UPDATE characters SET hp = GREATEST(0::bigint, hp + %s) WHERE user_id = %s",
            (final_hp_change, user_id)
        )
        
        # Send damage reduction notification if damage was reduced
        if damage_reduced > 0:
            try:
                # Get character's current location for notification
                char_data = self.db.execute_query(
                    "SELECT current_location FROM characters WHERE user_id = %s",
                    (user_id,),
                    fetch='one'
                )
                
                if char_data and char_data[0]:
                    location_id = char_data[0]
                    # Use cross-guild broadcasting for armor protection notifications
                    from utils.channel_manager import ChannelManager
                    channel_manager = ChannelManager(self.bot)
                    cross_guild_channels = await channel_manager.get_cross_guild_location_channels(location_id)
                    
                    user = guild.get_member(user_id)
                    if user and cross_guild_channels:
                        embed = discord.Embed(
                            title="🛡️ Armor Protection",
                            description=f"Damage reduced by: **{damage_reduced}** due to armor",
                            color=0x4169E1
                        )
                        for guild_channel, channel in cross_guild_channels:
                            try:
                                await channel.send(embed=embed, delete_after=10)
                            except:
                                pass  # Skip if can't send to this guild
            except Exception as e:
                # Don't let notification failures stop damage processing
                print(f"Failed to send damage reduction notification: {e}")
        
        return await self.check_character_death(user_id, guild, reason)
        
    async def update_ship_hull(self, user_id: int, hull_change: int, guild: discord.Guild, reason: str = ""):
        """Update ship hull and check for death"""
        self.db.execute_query(
            "UPDATE ships SET hull_integrity = GREATEST(0::bigint, hull_integrity + %s) WHERE owner_id = %s",
            (hull_change, user_id)
        )
        return await self.check_ship_death(user_id, guild, reason)    
    @character_group.command(name="login", description="Log into the game and restore your character")
    async def login_character(self, interaction: discord.Interaction):
        # Defer response to prevent timeout during database operations and channel management
        await interaction.response.defer(ephemeral=True)
        
        try:
            char_data = self.db.execute_query(
                "SELECT name, current_location, is_logged_in, current_ship_id FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_data:
                await interaction.followup.send(
                    "You don't have a character! Use the game panel to create a character first.",
                    ephemeral=True
                )
                return
            
            char_name, current_location, is_logged_in, current_ship_id = char_data
            
            if is_logged_in:
                await interaction.followup.send(
                    f"**{char_name}** is already logged in!",
                    ephemeral=True
                )
                return
            
            # Log in the character
            self.db.execute_query(
                "UPDATE characters SET is_logged_in = true, guild_id = %s, login_time = CURRENT_TIMESTAMP, last_activity = CURRENT_TIMESTAMP WHERE user_id = %s",
                (interaction.guild.id, interaction.user.id)
            )
            
            # Restore location access
            from utils.channel_manager import ChannelManager
            channel_manager = ChannelManager(self.bot)
            location_name = "Deep Space"

            if current_ship_id:
                ship_info_raw = self.db.execute_query(
                    "SELECT ship_id, name, ship_type, interior_description, channel_id, owner_id FROM ships WHERE ship_id = %s",
                    (current_ship_id,), fetch='one'
                )
                if ship_info_raw:
                    ship_id, ship_name, s_type, s_int, s_chan, owner_id = ship_info_raw
                    owner = interaction.guild.get_member(owner_id)
                    if owner:
                        ship_tuple = (ship_id, ship_name, s_type, s_int, s_chan)
                        await channel_manager.get_or_create_ship_channel(interaction.guild, ship_tuple, owner)
                        await channel_manager.give_user_ship_access(interaction.user, current_ship_id)
                        location_name = f"Aboard '{ship_name}'"
                    else:
                        self.db.execute_query("UPDATE characters SET current_ship_id = NULL, current_location = NULL WHERE user_id = %s", (interaction.user.id,))
                        location_name = "Lost in Space (Ship's owner not found)"
                else:
                    self.db.execute_query("UPDATE characters SET current_ship_id = NULL, current_location = NULL WHERE user_id = %s", (interaction.user.id,))
                    location_name = "Lost in Space (Ship was destroyed)"

            elif current_location:
                success = await channel_manager.restore_user_location_on_login(interaction.user, current_location)
                location_name = self.db.execute_query(
                    "SELECT name FROM locations WHERE location_id = %s",
                    (current_location,),
                    fetch='one'
                )[0]
            
            else:
                # Character has no location (likely from galaxy reset) - spawn at random colony
                colony_locations = self.db.execute_query(
                    """SELECT location_id, name FROM locations 
                       WHERE location_type = 'colony' 
                       ORDER BY RANDOM() LIMIT 1""", 
                    fetch='one'
                )
                
                if colony_locations:
                    colony_id, colony_name = colony_locations
                    # Set character location to the colony
                    self.db.execute_query(
                        "UPDATE characters SET current_location = %s WHERE user_id = %s",
                        (colony_id, interaction.user.id)
                    )
                    # Grant access to the colony
                    await channel_manager.restore_user_location_on_login(interaction.user, colony_id)
                    location_name = f"{colony_name} (Auto-spawned after galaxy reset)"
                else:
                    location_name = "Deep Space (No colonies available)"
            
            # Group functionality removed
            group_status = ""
            
            # Check for pending faction payouts
            await self.check_faction_payouts(interaction, interaction.user.id)
            
            # Update activity tracker
            if hasattr(self.bot, 'activity_tracker'):
                self.bot.activity_tracker.update_activity(interaction.user.id)
            
            embed = discord.Embed(
                title="✅ Login Successful",
                description=f"Welcome back, **{char_name}**!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📍 Current Location",
                value=location_name,
                inline=True
            )
            
            embed.add_field(
                name="🕐 Session Started",
                value=f"<t:{int(datetime.now().timestamp())}:T>",
                inline=True
            )
            
            if group_status:
                embed.add_field(
                    name="👥 Group Status",
                    value=group_status.strip(),
                    inline=False
                )
            
            embed.add_field(
                name="💡 Tip",
                value="Use `/tqe` to interact with your current location.",
                inline=False
            )
            
            # Auto-resume time system if this is the first player to log in
            try:
                from utils.time_system import TimeSystem
                time_system = TimeSystem(self.bot)
                # This will check conditions and only resume if appropriate
                time_system.auto_resume_time()
            except Exception as e:
                print(f"⚠️ LOGIN: Failed to check auto-resume time system: {e}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ LOGIN: Error during login process: {e}")
            embed = discord.Embed(
                title="❌ Login Failed",
                description="An error occurred during login. Please try again in a moment.",
                color=0xff0000
            )
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                # Fallback if followup also fails
                print(f"❌ LOGIN: Could not send error message to user {interaction.user.id}")
        
    async def check_faction_payouts(self, interaction: discord.Interaction, user_id: int):
        pending_payouts = self.db.execute_query(
            '''SELECT p.amount, f.name, f.emoji
               FROM faction_payouts p
               JOIN factions f ON p.faction_id = f.faction_id
               WHERE p.user_id = %s AND p.collected = 0''',
            (user_id,),
            fetch='all'
        )
        
        if pending_payouts:
            total_payout = sum(payout[0] for payout in pending_payouts)
            
            # Add to character's money
            self.db.execute_query(
                "UPDATE characters SET money = money + %s WHERE user_id = %s",
                (total_payout, user_id)
            )
            
            # Mark as collected
            self.db.execute_query(
                "UPDATE faction_payouts SET collected = 1 WHERE user_id = %s AND collected = 0",
                (user_id,)
            )
            
            # Send notification
            payout_text = "\n".join([f"{p[2]} {p[1]}: {p[0]:,} credits" for p in pending_payouts])
            embed = discord.Embed(
                title="💰 Faction Payout Received!",
                description=f"You received faction payouts while you were away:\n\n{payout_text}\n\nTotal: {total_payout:,} credits",
                color=0x00ff00
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)

    @character_group.command(name="logout", description="Log out of the game (saves your progress)")
    async def logout_character(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character!",
                ephemeral=True
            )
            return
        
        char_name, is_logged_in = char_data
        
        if not is_logged_in:
            await interaction.response.send_message(
                f"**{char_name}** is not currently logged in.",
                ephemeral=True
            )
            return
        
        # Check for active jobs
        active_jobs = self.db.execute_query(
            "SELECT COUNT(*) FROM jobs WHERE taken_by = %s AND job_status = 'active'",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if active_jobs > 0:
            view = LogoutConfirmView(self.bot, interaction.user.id, char_name, active_jobs)
            
            embed = discord.Embed(
                title="⚠️ Active Jobs Warning",
                description=f"**{char_name}** has {active_jobs} active job(s).",
                color=0xff9900
            )
            embed.add_field(
                name="Logout Effect",
                value="Logging out will **cancel** all active jobs and you won't receive payment.",
                inline=False
            )
            embed.add_field(
                name="Confirm Logout%s",
                value="Choose below to proceed or cancel.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # No active jobs, proceed with logout
            await self._execute_logout(interaction.user.id, char_name, interaction)

    async def _execute_logout(self, user_id: int, char_name: str, interaction: discord.Interaction):
        """Execute the logout process"""
        member = interaction.guild.get_member(user_id)
        if member and interaction.guild.me.guild_permissions.manage_nicknames:
            # We only clear the nickname if it matches the character name and auto-rename is on.
            auto_rename_setting = self.db.execute_query(
                "SELECT auto_rename FROM characters WHERE user_id = %s",
                (user_id,),
                fetch='one'
            )
            if auto_rename_setting and auto_rename_setting[0] == 1 and member.nick == char_name:
                try:
                    await member.edit(nick=None, reason="Character logged out.")
                except Exception as e:
                    print(f"Failed to clear nickname on logout for {member}: {e}")
        # Cancel any active jobs
        self.db.execute_query(
            "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = %s",
            (user_id,)
        )
        # Group functionality removed
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = %s",
            (user_id,)
        )
        
        # Get current location, ship, and home for cleanup
        char_state = self.db.execute_query(
            "SELECT current_location, current_ship_id, current_home_id FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        current_location, current_ship_id, current_home_id = char_state if char_state else (None, None, None)

        # Log out the character
        self.db.execute_query(
            "UPDATE characters SET is_logged_in = false WHERE user_id = %s",
            (user_id,)
        )

        # Remove access and cleanup
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)

        if current_location:
            await channel_manager.remove_user_location_access(interaction.user, current_location)
            await channel_manager.immediate_logout_cleanup(interaction.guild, current_location, current_ship_id, current_home_id)
        elif current_ship_id:
            await channel_manager.remove_user_ship_access(interaction.user, current_ship_id)
            await channel_manager.immediate_logout_cleanup(interaction.guild, None, current_ship_id, current_home_id)
        elif current_home_id:
            await channel_manager.remove_user_home_access(interaction.user, current_home_id)
            await channel_manager.immediate_logout_cleanup(interaction.guild, None, None, current_home_id)
        
        # Clean up activity tracker
        if hasattr(self.bot, 'activity_tracker'):
            self.bot.activity_tracker.cleanup_user_tasks(user_id)
        
        embed = discord.Embed(
            title="👋 Logout Successful",
            description=f"**{char_name}** has been logged out safely.",
            color=0xff9900
        )
        
        embed.add_field(
            name="💾 Progress Saved",
            value="• Character data preserved\n• Inventory saved\n• Location remembered\n• Group membership maintained",
            inline=False
        )
        
        embed.add_field(
            name="🔄 Next Login",
            value="Use the game panel to login and resume your journey exactly where you left off.",
            inline=False
        )
        
        # Auto-pause time system if this was the last player to log out
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            # This will check conditions and only pause if no players remain
            time_system.auto_pause_time()
        except Exception as e:
            print(f"⚠️ LOGOUT: Failed to check auto-pause time system: {e}")
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _execute_auto_logout(self, user_id: int, reason: str):
        """Execute automatic logout (called by activity tracker)"""
        char_data = self.db.execute_query(
            "SELECT name, current_location, current_ship_id, current_home_id FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return
        
        char_name, current_location, current_ship_id, current_home_id = char_data
        
        # Cancel any active jobs
        self.db.execute_query(
            "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = %s",
            (user_id,)
        )
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = %s",
            (user_id,)
        )
        # Group functionality removed
        # Log out the character
        self.db.execute_query(
            "UPDATE characters SET is_logged_in = false WHERE user_id = %s",
            (user_id,)
        )
        
        # Remove access and cleanup
        user = self.bot.get_user(user_id)
        if user:
            # Find the guild where this user is
            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    from utils.channel_manager import ChannelManager
                    channel_manager = ChannelManager(self.bot)
                    
                    if current_location:
                        await channel_manager.remove_user_location_access(member, current_location)
                        await channel_manager.immediate_logout_cleanup(guild, current_location, current_ship_id, current_home_id)
                    elif current_ship_id:
                        await channel_manager.remove_user_ship_access(member, current_ship_id)
                        await channel_manager.immediate_logout_cleanup(guild, None, current_ship_id, current_home_id)
                    elif current_home_id:
                        await channel_manager.remove_user_home_access(member, current_home_id)
                        await channel_manager.immediate_logout_cleanup(guild, None, None, current_home_id)
                    
                    break
        
        # Notify user
        if user:
            embed = discord.Embed(
                title="😴 Automatic Logout",
                description=f"**{char_name}** has been logged out due to inactivity.",
                color=0xff9900
            )
            embed.add_field(
                name="🔄 Log Back In",
                value="You can log back in with the login button or `/character login`",
                inline=False
            )
            
            try:
                await user.send(embed=embed)
            except:
                pass  # Failed to DM user
        
        # Auto-pause time system if this was the last player to log out
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            # This will check conditions and only pause if no players remain
            time_system.auto_pause_time()
        except Exception as e:
            print(f"⚠️ AUTO-LOGOUT: Failed to check auto-pause time system: {e}")
        
        print(f"🚪 Auto-logout: {char_name} (ID: {user_id}) - {reason}")
        
    
    @character_group.command(name="drop", description="Drop an item at your current location")
    @app_commands.describe(
        item_name="Name of the item to drop",
        quantity="Number of items to drop (default: 1)"
    )
    async def drop_item(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        if quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than 0.", ephemeral=True)
            return
        
        # Get character info
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[0]:
            await interaction.response.send_message("You cannot drop items while in transit!", ephemeral=True)
            return
        
        current_location = char_info[0]
        
        # Find item in inventory
        inventory_item = self.db.execute_query(
            '''SELECT item_id, item_name, quantity, item_type, description, value
               FROM inventory 
               WHERE owner_id = %s AND LOWER(item_name) LIKE LOWER(%s) AND quantity >= %s''',
            (interaction.user.id, f"%{item_name}%", quantity),
            fetch='one'
        )
        
        if not inventory_item:
            await interaction.response.send_message(f"You don't have enough '{item_name}' to drop.", ephemeral=True)
            return
        
        inv_id, actual_name, current_qty, item_type, description, value = inventory_item
        
        # Remove from inventory
        if current_qty == quantity:
            self.db.execute_query("DELETE FROM inventory WHERE item_id = %s", (inv_id,))
        else:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                (quantity, inv_id)
            )
        
        # Add to location items
        self.db.execute_query(
            '''INSERT INTO location_items 
               (location_id, item_name, item_type, quantity, description, value, dropped_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s)''',
            (current_location, actual_name, item_type, quantity, description, value, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="📦 Item Dropped",
            description=f"Dropped {quantity}x **{actual_name}** at this location",
            color=0x8B4513
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character_group.command(name="pickup", description="Pick up an item from your current location")
    @app_commands.describe(item_name="Name of the item to pick up")
    async def pickup_item(self, interaction: discord.Interaction, item_name: str):
        # Get character info
        char_info = self.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[0]:
            await interaction.response.send_message("You cannot pick up items while in transit!", ephemeral=True)
            return
        
        current_location = char_info[0]
        
        # Find item at location
        location_item = self.db.execute_query(
            '''SELECT item_id, item_name, item_type, quantity, description, value
               FROM location_items 
               WHERE location_id = %s AND LOWER(item_name) LIKE LOWER(%s)
               ORDER BY dropped_at ASC LIMIT 1''',
            (current_location, f"%{item_name}%"),
            fetch='one'
        )
        
        if not location_item:
            await interaction.response.send_message(f"No '{item_name}' found at this location.", ephemeral=True)
            return
        
        item_id, actual_name, item_type, quantity, description, value = location_item
        
        # Remove from location
        self.db.execute_query("DELETE FROM location_items WHERE item_id = %s", (item_id,))
        
        # Add to inventory
        existing_item = self.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (interaction.user.id, actual_name),
            fetch='one'
        )
        
        if existing_item:
            self.db.execute_query(
                "UPDATE inventory SET quantity = quantity + %s WHERE item_id = %s",
                (quantity, existing_item[0])
            )
        else:
            from utils.item_config import ItemConfig
            metadata = ItemConfig.create_item_metadata(actual_name)
            self.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, value, metadata, equippable, equipment_slot, stat_modifiers)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (interaction.user.id, actual_name, item_type, quantity, description, value, metadata, False, None, None)
            )
        
        embed = discord.Embed(
            title="📦 Item Picked Up",
            description=f"Picked up {quantity}x **{actual_name}**",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @character_group.command(name="skills", description="View and manage your character skills")
    async def view_skills(self, interaction: discord.Interaction):
        char_data = self.db.execute_query(
            '''SELECT name, level, experience, skill_points, engineering, navigation, 
                      combat, medical
               FROM characters WHERE user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        name, level, exp, skill_points, eng, nav, combat, medical = char_data
        
        # Calculate experience needed for next level
        exp_needed = self._calculate_exp_for_level(level + 1)
        exp_current_level = self._calculate_exp_for_level(level)
        exp_progress = exp - exp_current_level
        exp_to_next = exp_needed - exp
        
        embed = discord.Embed(
            title=f"📊 {name} - Character Skills",
            description=f"Level {level} Character",
            color=0x4169e1
        )
        
        # Level and experience info
        progress_bar = self._create_progress_bar(exp_progress, exp_needed - exp_current_level)
        embed.add_field(
            name="📈 Level Progress",
            value=f"Level {level} ({exp:,} EXP)\n{progress_bar}\n{exp_to_next:,} EXP to level {level + 1}",
            inline=False
        )
        
        # Skills display
        skills_text = []
        skills = [
            ("🔧 Engineering", eng, "Ship repairs, system efficiency"),
            ("🧭 Navigation", nav, "Travel time, route finding"), 
            ("⚔️ Combat", combat, "Attack power, damage resistance"),
            ("⚕️ Medical", medical, "Healing, radiation treatment")
        ]
        
        for skill_name, skill_value, skill_desc in skills:
            skill_tier = self._get_skill_tier(skill_value)
            skills_text.append(f"{skill_name}: **{skill_value}** {skill_tier}")
            skills_text.append(f"  _{skill_desc}_")
        
        embed.add_field(
            name="🎯 Skills",
            value="\n".join(skills_text),
            inline=False
        )
        
        if skill_points > 0:
            embed.add_field(
                name="💡 Available Skill Points",
                value=f"You have **{skill_points}** unspent skill points!",
                inline=False
            )
            
            view = SkillUpgradeView(self.bot, interaction.user.id, skill_points)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    def _calculate_exp_for_level(self, level):
        """Calculate total experience needed for a given level"""
        if level <= 1:
            return 0
        base_exp = 150  # Increased from 100
        return int(base_exp * ((level - 1) ** 2.2))  # Exponential growth
    def _create_progress_bar(self, current, total, length=10):
        """Create a visual progress bar"""
        if total == 0:
            filled = length
        else:
            filled = int((current / total) * length)
        
        bar = "🟩" * filled + "⬜" * (length - filled)
        percentage = (current / total * 100) if total > 0 else 100
        return f"{bar} {percentage:.1f}%"

    def _get_skill_tier(self, skill_value):
        """Get skill tier description"""
        if skill_value >= 80:  # Increased from 50
            return "(Master)"
        elif skill_value >= 60:  # Increased from 35
            return "(Expert)"
        elif skill_value >= 40:  # Increased from 25
            return "(Advanced)"
        elif skill_value >= 25:  # Increased from 15
            return "(Skilled)"
        elif skill_value >= 15:  # Same
            return "(Competent)"
        else:
            return "(Novice)"

    async def level_up_check(self, user_id: int):
        """Check if character should level up and handle the process"""
        char_data = self.db.execute_query(
            "SELECT level, experience FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            return False
        
        current_level, current_exp = char_data
        
        while True:
            exp_needed = self._calculate_exp_for_level(current_level + 1)
            
            if current_exp >= exp_needed:
                # Level up!
                current_level += 1
                skill_points_gained = 1  # 2 skill points per level
                
                self.db.execute_query(
                    "UPDATE characters SET level = %s, skill_points = skill_points + %s WHERE user_id = %s",
                    (current_level, skill_points_gained, user_id)
                )
                
                # Notify user
                # Notify user in their location channel
                user = self.bot.get_user(user_id)
                if user:
                    try:
                        # Get user's current location
                        user_location = self.db.execute_query(
                            "SELECT current_location FROM characters WHERE user_id = %s",
                            (user_id,),
                            fetch='one'
                        )
                        
                        if user_location and user_location[0]:
                            # Use cross-guild broadcasting for level up notifications
                            from utils.channel_manager import ChannelManager
                            channel_manager = ChannelManager(self.bot)
                            cross_guild_channels = await channel_manager.get_cross_guild_location_channels(user_location[0])
                            
                            if cross_guild_channels:
                                embed.set_color(0xffd700)
                                embed.add_field(name="Rewards", value=f"• +{skill_points_gained} skill points\n• +10 max HP", inline=False)
                                embed.add_field(name="💡 Tip", value="Use the 'Character > Skills' menu in `/tqe` to spend your skill points!", inline=False)
                                
                                for guild_channel, channel in cross_guild_channels:
                                    try:
                                        await channel.send(f"{user.mention}", embed=embed)
                                    except:
                                        pass  # Skip if can't send to this guild
                    except Exception as e:
                        print(f"Failed to send level up notification to location channel: {e}")
                
                # Increase max HP
                self.db.execute_query(
                    "UPDATE characters SET max_hp = max_hp + 10, hp = hp + 10 WHERE user_id = %s",
                    (user_id,)
                )
                
            else:
                break
        
        return True

    @character_group.command(name="train", description="Train skills at certain locations")
    @app_commands.describe(skill="Skill to train")
    @app_commands.choices(skill=[
        app_commands.Choice(name="Engineering", value="engineering"),
        app_commands.Choice(name="Navigation", value="navigation"),
        app_commands.Choice(name="Combat", value="combat"),
        app_commands.Choice(name="Medical", value="medical")
    ])
    async def train_skill(self, interaction: discord.Interaction, skill: str):
        # Check location capabilities
        char_location = self.db.execute_query(
            '''SELECT l.name, l.location_type, l.wealth_level, l.has_medical
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = %s''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Character or location not found!", ephemeral=True)
            return
        
        location_name, location_type, wealth, has_medical = char_location
        
        # Check if location supports training
        training_available = {
            'engineering': location_type in ['space_station', 'colony'] and wealth >= 5,
            'navigation': location_type in ['space_station', 'gate'] and wealth >= 4,
            'combat': location_type in ['space_station'] and wealth >= 6,
            'medical': has_medical and wealth >= 5
        }
        
        if not training_available.get(skill, False):
            await interaction.response.send_message(
                f"{location_name} doesn't offer {skill} training. Try a different location or skill.",
                ephemeral=True
            )
            return
        
        # Get character info
        char_info = self.db.execute_query(
            f"SELECT money, {skill} FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        money, current_skill = char_info
        
        # Calculate training cost (more expensive for higher skills)
        base_cost = 200
        skill_multiplier = 1 + (current_skill * 0.1)
        training_cost = int(base_cost * skill_multiplier)
        
        if money < training_cost:
            await interaction.response.send_message(
                f"Training costs {training_cost:,} credits. You only have {money:,}.",
                ephemeral=True
            )
            return
        
        # Training success chance based on location wealth
        success_chance = 0.6 + (wealth * 0.05)  # 60% base + 5% per wealth level
        
        view = TrainingConfirmView(self.bot, interaction.user.id, skill, training_cost, success_chance)
        
        embed = discord.Embed(
            title=f"🎓 {skill.title()} Training Available",
            description=f"Train your {skill} skill at {location_name}",
            color=0x4169e1
        )
        
        embed.add_field(name="Current Skill Level", value=str(current_skill), inline=True)
        embed.add_field(name="Training Cost", value=f"{training_cost:,} credits", inline=True)
        embed.add_field(name="Success Chance", value=f"{int(success_chance * 100)}%", inline=True)
        
        embed.add_field(
            name="Training Benefits",
            value=f"• +1 to {skill} skill on success\n• Experience points\n• Potential for breakthrough (+2 skill)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    # Add admin command for emergency revival
    @character_group.command(name="admin_revive", description="Admin: Revive a dead player or restore HP")
    @app_commands.describe(
        target_user="User to revive",
        hp_amount="HP to restore (default: full heal)"
    )
    async def admin_revive(self, interaction: discord.Interaction, target_user: discord.Member, hp_amount: int = 100):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        char_data = self.db.execute_query(
            "SELECT name, hp, max_hp FROM characters WHERE user_id = %s",
            (target_user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(f"{target_user.mention} does not have a character.", ephemeral=True)
            return
        
        char_name, current_hp, max_hp = char_data
        
        # Restore HP
        new_hp = min(hp_amount, max_hp)
        self.db.execute_query(
            "UPDATE characters SET hp = %s WHERE user_id = %s",
            (new_hp, target_user.id)
        )
        
        embed = discord.Embed(
            title="⚕️ Administrative Healing",
            description=f"**{char_name}** has been healed by an administrator.",
            color=0x00ff00
        )
        
        embed.add_field(name="HP Restored", value=f"{current_hp} → {new_hp}", inline=True)
        embed.add_field(name="Healed By", value=interaction.user.mention, inline=True)
        
        # Notify the player
        try:
            await target_user.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class SkillUpgradeView(discord.ui.View):
    def __init__(self, bot, user_id: int, skill_points: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.skill_points = skill_points
    
    @discord.ui.button(label="Engineering", style=discord.ButtonStyle.secondary, emoji="🔧")
    async def upgrade_engineering(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "engineering")
    
    @discord.ui.button(label="Navigation", style=discord.ButtonStyle.secondary, emoji="🧭")
    async def upgrade_navigation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "navigation")
    
    @discord.ui.button(label="Combat", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def upgrade_combat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "combat")
    
    @discord.ui.button(label="Medical", style=discord.ButtonStyle.secondary, emoji="⚕️")
    async def upgrade_medical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade_skill(interaction, "medical")
    
    async def _upgrade_skill(self, interaction: discord.Interaction, skill: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your skill panel!", ephemeral=True)
            return
        
        # Check skill points
        current_points = self.bot.db.execute_query(
            "SELECT skill_points FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        if current_points < 1:
            await interaction.response.send_message("No skill points available!", ephemeral=True)
            return
        
        # Upgrade skill
        self.bot.db.execute_query(
            f"UPDATE characters SET {skill} = {skill} + 1, skill_points = skill_points - 1 WHERE user_id = %s",
            (interaction.user.id,)
        )
        
        # Get new skill level
        new_skill = self.bot.db.execute_query(
            f"SELECT {skill} FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="✅ Skill Upgraded",
            description=f"Your {skill} skill has been upgraded to level {new_skill}!",
            color=0x00ff00
        )
        
        embed.add_field(name="Skill Points Remaining", value=str(current_points - 1), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class TrainingConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, skill: str, cost: int, success_chance: float):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.skill = skill
        self.cost = cost
        self.success_chance = success_chance
    
    @discord.ui.button(label="Begin Training", style=discord.ButtonStyle.primary, emoji="🎓")
    async def begin_training(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your training session!", ephemeral=True)
            return
        
        # Check if user still has enough money
        current_money = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not current_money or current_money[0] < self.cost:
            await interaction.response.send_message(
                f"Training costs {self.cost:,} credits. You only have {current_money[0] if current_money else 0:,}.",
                ephemeral=True
            )
            return
        
        # Deduct cost
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - %s WHERE user_id = %s",
            (self.cost, interaction.user.id)
        )
        
        # Roll for success
        import random
        roll = random.random()
        
        if roll < self.success_chance:
            # Success!
            skill_gain = 2 if roll < 0.1 else 1  # 10% chance for breakthrough (+2 skill)
            exp_gain = random.randint(15, 30)
            
            self.bot.db.execute_query(
                f"UPDATE characters SET {self.skill} = {self.skill} + %s, experience = experience + %s WHERE user_id = %s",
                (skill_gain, exp_gain, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="🎉 Training Successful!",
                description=f"Your {self.skill} training was successful!",
                color=0x00ff00
            )
            embed.add_field(name="Skill Gained", value=f"+{skill_gain} {self.skill}", inline=True)
            embed.add_field(name="Experience Gained", value=f"+{exp_gain} EXP", inline=True)
            
            if skill_gain == 2:
                embed.add_field(name="🌟 Breakthrough!", value="Exceptional progress made!", inline=False)
            
            # Check for level up
            char_cog = self.bot.get_cog('CharacterCog')
            if char_cog:
                await char_cog.level_up_check(interaction.user.id)
        
        else:
            # Failure
            exp_gain = random.randint(5, 10)  # Small consolation experience
            
            self.bot.db.execute_query(
                "UPDATE characters SET experience = experience + %s WHERE user_id = %s",
                (exp_gain, interaction.user.id)
            )
            
            embed = discord.Embed(
                title="❌ Training Failed",
                description=f"The {self.skill} training session didn't go as planned.",
                color=0xff4500
            )
            embed.add_field(name="Experience Gained", value=f"+{exp_gain} EXP", inline=True)
            embed.add_field(name="💡 Try Again", value="Training can be repeated for another chance.", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_training(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your training session!", ephemeral=True)
            return
        
        await interaction.response.send_message("Training cancelled.", ephemeral=True)


class IDScrubView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
    
    @discord.ui.button(label="Scrub Identity Records", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def scrub_identity(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your ID panel!", ephemeral=True)
            return
        
        # Check if character has enough money (expensive service)
        char_money = self.bot.db.execute_query(
            "SELECT money FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_money or char_money[0] < 15000:
            await interaction.response.send_message(
                "Identity scrubbing costs 15,000 credits. You don't have enough money!",
                ephemeral=True
            )
            return
        
        # Deduct money and scrub identity
        self.bot.db.execute_query(
            "UPDATE characters SET money = money - 15000 WHERE user_id = %s",
            (interaction.user.id,)
        )
        
        self.bot.db.execute_query(
            "UPDATE character_identity SET id_scrubbed = 1, scrubbed_at = NOW() WHERE user_id = %s",
            (interaction.user.id,)
        )
        
        embed = discord.Embed(
            title="🗑️ Identity Scrubbed",
            description="Your identity records have been permanently scrubbed from official databases.",
            color=0x888888
        )
        
        embed.add_field(
            name="💰 Cost",
            value="15,000 credits deducted",
            inline=True
        )
        
        embed.add_field(
            name="🔒 Effect",
            value="Other players will see an error when viewing your ID",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def _execute_undock(self, interaction: discord.Interaction, user_id: int):
        """Execute the actual undocking process after job confirmation"""
        # Cancel any active jobs first
        self.db.execute_query(
            "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE taken_by = %s",
            (user_id,)
        )
        
        # Remove from job tracking
        self.db.execute_query(
            "DELETE FROM job_tracking WHERE user_id = %s",
            (user_id,)
        )
        
        char_data = self.db.execute_query(
            "SELECT current_location, location_status FROM characters WHERE user_id = %s",
            (user_id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message("Character not found!", ephemeral=True)
            return
        
        current_location, location_status = char_data
        
        if not current_location:
            await interaction.response.send_message("You're in deep space!", ephemeral=True)
            return
        
        if location_status == "in_space":
            await interaction.response.send_message("You're already in space near this location!", ephemeral=True)
            return
        
        # Undock the ship
        self.db.execute_query(
            "UPDATE characters SET location_status = 'in_space' WHERE user_id = %s",
            (user_id,)
        )
        
        location_name = self.db.execute_query(
            "SELECT name FROM locations WHERE location_id = %s",
            (current_location,),
            fetch='one'
        )[0]
        
        embed = discord.Embed(
            title="🚀 Ship Undocked (Jobs Cancelled)",
            description=f"Your ship is now in space near **{location_name}**. All active jobs have been cancelled.",
            color=0x4169e1
        )
        
        embed.add_field(
            name="Status Change",
            value="• You can now engage in ship combat\n• Limited access to location services\n• Full radio range available\n• All stationary jobs cancelled",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class UndockJobConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
    
    @discord.ui.button(label="Confirm Undock", style=discord.ButtonStyle.danger, emoji="🚀")
    async def confirm_undock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Cancel active jobs at this location
        active_jobs = self.bot.db.execute_query(
            '''SELECT j.job_id FROM jobs j 
               LEFT JOIN job_tracking jt ON j.job_id = jt.job_id
               WHERE j.taken_by = %s AND j.job_status = 'active' 
               AND (jt.start_location = %s OR (jt.start_location IS NULL AND j.location_id = %s))''',
            (self.user_id, self.location_id, self.location_id),
            fetch='all'
        )
        
        for job_data in active_jobs:
            job_id = job_data[0]
            self.bot.db.execute_query(
                "UPDATE jobs SET is_taken = false, taken_by = NULL, taken_at = NULL, job_status = 'available' WHERE job_id = %s",
                (job_id,)
            )
            self.bot.db.execute_query(
                "DELETE FROM job_tracking WHERE job_id = %s AND user_id = %s",
                (job_id, self.user_id)
            )
        
        # Now execute the actual undock
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog._execute_undock(interaction, self.user_id)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_undock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.send_message("Undocking cancelled.", ephemeral=True)

class CharacterPanelView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        
        # Check for active quest and add quest button if needed
        self._add_quest_button_if_needed()
    
    def check_quest_status(self):
        """Check if user has active quest and if it's ready for completion"""
        # Get active quest info
        quest_info = self.bot.db.execute_query(
            '''SELECT qp.quest_id, q.title, q.description, qp.current_objective,
                      qp.objectives_completed, q.reward_money
               FROM quest_progress qp
               JOIN quests q ON qp.quest_id = q.quest_id
               WHERE qp.user_id = %s AND qp.quest_status = 'active' ''',
            (self.user_id,),
            fetch='one'
        )
        
        if not quest_info:
            return None, False  # No active quest
        
        quest_id, title, description, current_objective, completed_obj_json, reward = quest_info
        
        # Get total objectives for this quest
        total_objectives = self.bot.db.execute_query(
            "SELECT COUNT(*) FROM quest_objectives WHERE quest_id = %s",
            (quest_id,),
            fetch='one'
        )[0]
        
        # Parse completed objectives
        import json
        try:
            completed_objectives = json.loads(completed_obj_json) if completed_obj_json else []
        except:
            completed_objectives = []
        
        # Check if quest is ready for completion
        is_ready = len(completed_objectives) >= total_objectives
        
        return quest_info, is_ready
    
    def _add_quest_button_if_needed(self):
        """Add quest button if user has an active quest"""
        quest_info, is_ready = self.check_quest_status()
        
        if quest_info:
            # User has an active quest, add the appropriate button
            if is_ready:
                quest_button = discord.ui.Button(
                    label="Complete Quest",
                    style=discord.ButtonStyle.success,
                    emoji="🏆"
                )
                quest_button.callback = self.complete_quest
            else:
                # Quest is not ready yet
                quest_button = discord.ui.Button(
                    label="Quest Status",
                    style=discord.ButtonStyle.primary,
                    emoji="📜"
                )
                quest_button.callback = self.view_quest_status
            
            self.add_item(quest_button)
    
    async def complete_quest(self, interaction: discord.Interaction):
        """Handle quest completion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get the QuestCog and call its completion logic
        quest_cog = self.bot.get_cog('QuestCog')
        if quest_cog:
            # Check if quest is actually ready for completion
            quest_info, is_ready = self.check_quest_status()
            if not quest_info or not is_ready:
                await interaction.response.send_message("Your quest is not ready for completion yet.", ephemeral=True)
                return
            
            # Trigger quest completion directly
            quest_id = quest_info[0]
            await quest_cog._complete_quest(quest_id, self.user_id)
            await interaction.response.send_message("🏆 Quest completed! Check your location channel for rewards.", ephemeral=True)
        else:
            await interaction.response.send_message("Quest system is currently unavailable.", ephemeral=True)
    
    async def view_quest_status(self, interaction: discord.Interaction):
        """Handle viewing quest status"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get quest info
        quest_info, is_ready = self.check_quest_status()
        
        if not quest_info:
            await interaction.response.send_message("You don't have any active quests.", ephemeral=True)
            return
        
        quest_id, title, description, current_objective, completed_obj_json, reward = quest_info
        
        # Get all objectives for this quest
        objectives = self.bot.db.execute_query(
            '''SELECT objective_order, objective_type, description, target_location_id, 
                      target_item, target_quantity, target_amount
               FROM quest_objectives 
               WHERE quest_id = %s 
               ORDER BY objective_order''',
            (quest_id,),
            fetch='all'
        )
        
        # Parse completed objectives
        import json
        try:
            completed_objectives = json.loads(completed_obj_json) if completed_obj_json else []
        except:
            completed_objectives = []
        
        # Create embed
        embed = discord.Embed(
            title="📜 Current Quest Status",
            description=f"**{title}**\n{description[:500]}{'...' if len(description) > 500 else ''}",
            color=0x6c5ce7
        )
        
        # Add objectives status
        objectives_text = ""
        for obj_order, obj_type, obj_desc, target_location_id, target_item, target_qty, target_amount in objectives:
            status_emoji = "✅" if obj_order in completed_objectives else "⏳"
            objectives_text += f"{status_emoji} **{obj_order}.** {obj_desc}\n"
        
        embed.add_field(
            name="Objectives Progress",
            value=objectives_text[:1024] if objectives_text else "No objectives found",
            inline=False
        )
        
        embed.add_field(name="Reward", value=f"{reward:,} credits", inline=True)
        embed.add_field(name="Status", value="🏆 Ready to Complete!" if is_ready else "⏳ In Progress", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Character Info", style=discord.ButtonStyle.primary, emoji="👤")
    async def view_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing character view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_character.callback(char_cog, interaction)
    
    @discord.ui.button(label="Ship Status", style=discord.ButtonStyle.secondary, emoji="🚀")
    async def view_ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing ship view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_ship.callback(char_cog, interaction)
    
    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.success, emoji="🎒")
    async def view_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing inventory view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_inventory.callback(char_cog, interaction)
    
    @discord.ui.button(label="Skills", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_skills(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Call the existing skills view logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.view_skills.callback(char_cog, interaction)
    
    @discord.ui.button(label="Equipment", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def view_equipment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        from utils.stat_system import StatSystem
        from utils.item_config import ItemConfig
        
        stat_system = StatSystem(self.bot.db)
        
        # Get equipped items
        equipped_items = stat_system.get_equipped_items(self.user_id)
        
        # Get base and effective stats
        base_stats, effective_stats = stat_system.calculate_effective_stats(self.user_id)
        
        # Create equipment embed
        embed = discord.Embed(
            title="⚔️ Equipment & Stat Modifiers",
            description="Your currently equipped items and their effects",
            color=0x8B4513
        )
        
        # Show equipment slots
        slot_display = {
            "head": "🎩 Head",
            "eyes": "👓 Eyes", 
            "torso": "👕 Torso",
            "arms_left": "💪 Left Arm",
            "arms_right": "💪 Right Arm",
            "hands_left": "🤚 Left Hand",
            "hands_right": "🤚 Right Hand",
            "legs_left": "🦵 Left Leg",
            "legs_right": "🦵 Right Leg",
            "feet_left": "👟 Left Foot",
            "feet_right": "👟 Right Foot"
        }
        
        equipment_text = ""
        for slot, display_name in slot_display.items():
            if slot in equipped_items:
                item = equipped_items[slot]
                modifiers = item['modifiers']
                mod_text = ""
                if modifiers:
                    mod_list = [f"{stat}+{val}" for stat, val in modifiers.items()]
                    mod_text = f" ({', '.join(mod_list)})"
                equipment_text += f"{display_name}: **{item['name']}**{mod_text}\n"
            else:
                equipment_text += f"{display_name}: *Empty*\n"
        
        embed.add_field(
            name="🎒 Equipment Slots",
            value=equipment_text[:1024] if equipment_text else "No equipment slots found",
            inline=False
        )
        
        # Show current stat effects
        if base_stats and effective_stats:
            stats_text = ""
            for stat_name in ['hp', 'max_hp', 'engineering', 'navigation', 'combat', 'medical', 'defense']:
                if stat_name in base_stats and stat_name in effective_stats:
                    # Only show defense if > 0
                    if stat_name == 'defense' and effective_stats[stat_name] <= 0:
                        continue
                    
                    display_text = stat_system.format_stat_display(
                        base_stats[stat_name], 
                        effective_stats[stat_name]
                    )
                    # Add % for defense
                    if stat_name == 'defense':
                        display_text += "%"
                    stats_text += f"**{stat_name.replace('_', ' ').title()}:** {display_text}\n"
            
            embed.add_field(
                name="📊 Current Stats (Base + Modifiers)",
                value=stats_text[:1024] if stats_text else "No stats available",
                inline=False
            )
        
        # Create equipment management view
        equipment_view = EquipmentManagementView(self.bot, self.user_id)
        await interaction.response.send_message(embed=embed, view=equipment_view, ephemeral=True)
    
    @discord.ui.button(label="Actions", style=discord.ButtonStyle.primary, emoji="⚡", row=1)
    async def actions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open character actions panel"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Create actions embed
        embed = discord.Embed(
            title="⚡ Character Actions",
            description="Use the buttons below to perform character actions:",
            color=0x4169E1
        )
        
        embed.add_field(
            name="Available Actions",
            value="• **Say** - Speak as your character\n• **Think** - Share internal thoughts\n• **Act** - Perform roleplay actions\n• **Drop Item** - Drop items from inventory\n• **Pickup Item** - Pick up items from location\n• **Give Item** - Give items to other players\n• **Sell Item** - Sell items to other players",
            inline=False
        )
        
        # Create the actions view
        actions_view = ActionsView(self.bot, self.user_id)
        await interaction.response.send_message(embed=embed, view=actions_view, ephemeral=True)
    
    @discord.ui.button(label="Enter Ship", style=discord.ButtonStyle.secondary, emoji="🚀", row=1)
    async def enter_ship_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enter your ship interior"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Check if already in a ship
        current_ship = self.bot.db.execute_query(
            "SELECT current_ship_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if current_ship and current_ship[0]:
            await interaction.followup.send("You are already inside a ship! Use the leave button in the ship interior first.", ephemeral=True)
            return
        
        # Get character location and status
        char_info = self.bot.db.execute_query(
            "SELECT current_location, location_status, active_ship_id FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or char_info[1] != 'docked':
            await interaction.followup.send("You must be docked at a location to enter your ship!", ephemeral=True)
            return
        
        location_id, location_status, active_ship_id = char_info
        
        if not active_ship_id:
            await interaction.followup.send("You don't have an active ship!", ephemeral=True)
            return
        
        # Get ship info
        ship_info = self.bot.db.execute_query(
            '''SELECT ship_id, name, ship_type, interior_description, channel_id
               FROM ships WHERE ship_id = %s''',
            (active_ship_id,),
            fetch='one'
        )
        
        if not ship_info:
            await interaction.followup.send("Ship not found!", ephemeral=True)
            return
        
        # Create ship interior channel and give access
        from utils.channel_manager import ChannelManager
        channel_manager = ChannelManager(self.bot)
        
        ship_channel = await channel_manager.get_or_create_ship_channel(
            interaction.guild,
            ship_info,
            interaction.user
        )
        
        if ship_channel:
            # Send area movement embed to location channel BEFORE removing access
            char_name = self.bot.db.execute_query(
                "SELECT name FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            # Ensure location channel exists and get it
            location_channel = await channel_manager.get_or_create_location_channel(
                interaction.guild, location_id
            )
            
            if location_channel:
                embed = discord.Embed(
                    title="🚪 Area Movement",
                    description=f"**{char_name}** enters the **{ship_info[1]}**.",
                    color=0x7289DA
                )
                try:
                    await self.bot.send_with_cross_guild_broadcast(location_channel, embed=embed)
                except Exception as e:
                    print(f"❌ Failed to send ship entry embed: {e}")
            
            # Update character to be inside ship
            self.bot.db.execute_query(
                "UPDATE characters SET current_ship_id = %s WHERE user_id = %s",
                (active_ship_id, interaction.user.id)
            )
            
            # Keep location channel access - users should retain access to both ship and location channels
            
            await interaction.followup.send(
                f"You've entered your ship. Head to {ship_channel.mention}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("Failed to create ship interior.", ephemeral=True)
    
    @discord.ui.button(label="Radio", style=discord.ButtonStyle.primary, emoji="📡", row=1)
    async def radio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open radio transmission modal"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Check if character is logged in
        char_data = self.bot.db.execute_query(
            "SELECT is_logged_in FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data or not char_data[0]:
            await interaction.response.send_message(
                "You must be logged in to use the radio!",
                ephemeral=True
            )
            return
        
        # Open the radio modal
        modal = RadioModal(self.bot)
        await interaction.response.send_modal(modal)

class ActionsView(discord.ui.View):
    """View for character actions: drop, pickup, think, say, and act"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, emoji="💬")
    async def say_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = SayModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Think", style=discord.ButtonStyle.secondary, emoji="💭")
    async def think_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = ThinkModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Act", style=discord.ButtonStyle.success, emoji="🎭")
    async def act_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = ActModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Drop Item", style=discord.ButtonStyle.danger, emoji="📦")
    async def drop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = DropModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Pickup Item", style=discord.ButtonStyle.primary, emoji="🔄")
    async def pickup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = PickupModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Give Item", style=discord.ButtonStyle.success, emoji="🤝", row=1)
    async def give_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Check if user has any items
        inventory = self.bot.db.execute_query(
            """SELECT item_name FROM inventory 
               WHERE owner_id = %s AND quantity > 0 
               LIMIT 1""",
            (self.user_id,),
            fetch='one'
        )
        
        if not inventory:
            await interaction.response.send_message("You don't have any items to give!", ephemeral=True)
            return
        
        # Check if there are other players at the same location
        char_data = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (self.user_id,),
            fetch='one'
        )
        
        if not char_data or not char_data[0]:
            await interaction.response.send_message("You must be at a location to give items!", ephemeral=True)
            return
        
        other_players = self.bot.db.execute_query(
            """SELECT c.user_id FROM characters c 
               WHERE c.current_location = %s AND c.user_id != %s AND c.is_logged_in = true
               LIMIT 1""",
            (char_data[0], self.user_id),
            fetch='one'
        )
        
        if not other_players:
            await interaction.response.send_message("No other players at this location!", ephemeral=True)
            return
        
        # Create the give item selection view
        view = GiveItemSelectView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🎁 Give Item",
            description="Select an item from your inventory to give to another player:",
            color=0x2ecc71
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Sell Item", style=discord.ButtonStyle.primary, emoji="💰", row=1)
    async def sell_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Check if user has any items
        inventory = self.bot.db.execute_query(
            """SELECT item_name FROM inventory 
               WHERE owner_id = %s AND quantity > 0 
               LIMIT 1""",
            (self.user_id,),
            fetch='one'
        )
        
        if not inventory:
            await interaction.response.send_message("You don't have any items to sell!", ephemeral=True)
            return
        
        # Check if there are other players at the same location
        char_data = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (self.user_id,),
            fetch='one'
        )
        
        if not char_data or not char_data[0]:
            await interaction.response.send_message("You must be at a location to sell items!", ephemeral=True)
            return
        
        other_players = self.bot.db.execute_query(
            """SELECT c.user_id FROM characters c 
               WHERE c.current_location = %s AND c.user_id != %s AND c.is_logged_in = true
               LIMIT 1""",
            (char_data[0], self.user_id),
            fetch='one'
        )
        
        if not other_players:
            await interaction.response.send_message("No other players at this location!", ephemeral=True)
            return
        
        # Create the sell item selection view
        view = SellItemSelectView(self.bot, self.user_id)
        embed = discord.Embed(
            title="💰 Sell Item",
            description="Select an item from your inventory to sell to another player:",
            color=0xf39c12
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Observe", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def observe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        modal = ObserveModal(self.bot)
        await interaction.response.send_modal(modal)

class SayModal(discord.ui.Modal, title="Speak as Character"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    message = discord.ui.TextInput(
        label="What does your character say?",
        placeholder="Enter your character's dialogue...",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Call the say command logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.say.callback(char_cog, interaction, self.message.value)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)

class ThinkModal(discord.ui.Modal, title="Character Thoughts"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    thought = discord.ui.TextInput(
        label="What is your character thinking?",
        placeholder="Enter your character's internal thoughts...",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Call the think command logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.think.callback(char_cog, interaction, self.thought.value)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)

class ActModal(discord.ui.Modal, title="Character Action"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    action = discord.ui.TextInput(
        label="What action does your character perform?",
        placeholder="Describe your character's action...",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Call the act command logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.act.callback(char_cog, interaction, self.action.value)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)

class DropModal(discord.ui.Modal, title="Drop Item"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    item_name = discord.ui.TextInput(
        label="Item Name",
        placeholder="Name of the item to drop...",
        max_length=200
    )
    
    quantity = discord.ui.TextInput(
        label="Quantity (default: 1)",
        placeholder="1",
        default="1",
        required=False,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse quantity
        try:
            qty = int(self.quantity.value) if self.quantity.value.strip() else 1
        except ValueError:
            qty = 1
        
        # Call the drop command logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.drop_item.callback(char_cog, interaction, self.item_name.value, qty)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)

class PickupModal(discord.ui.Modal, title="Pick Up Item"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    item_name = discord.ui.TextInput(
        label="Item Name",
        placeholder="Name of the item to pick up...",
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Call the pickup command logic
        char_cog = self.bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.pickup_item.callback(char_cog, interaction, self.item_name.value)
        else:
            await interaction.response.send_message("Character system unavailable.", ephemeral=True)


class EquipmentManagementView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    @discord.ui.button(label="Equip Item", style=discord.ButtonStyle.success, emoji="⚔️")
    async def equip_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Get equippable items from inventory
        from utils.item_config import ItemConfig
        
        equippable_items = self.bot.db.execute_query(
            '''SELECT item_id, item_name, description 
               FROM inventory 
               WHERE owner_id = %s AND quantity > 0''',
            (self.user_id,),
            fetch='all'
        )
        
        # Filter for equippable items
        available_items = []
        for item_id, item_name, description in equippable_items:
            if ItemConfig.is_equippable(item_name):
                available_items.append((item_id, item_name, description))
        
        if not available_items:
            await interaction.response.send_message("You don't have any equippable items!", ephemeral=True)
            return
        
        # Create select menu for equippable items
        select = EquipmentSelect(self.bot, self.user_id, available_items)
        view = discord.ui.View()
        view.add_item(select)
        
        embed = discord.Embed(
            title="⚔️ Equip Item",
            description="Select an item to equip:",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Unequip Item", style=discord.ButtonStyle.danger, emoji="❌")
    async def unequip_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        from utils.stat_system import StatSystem
        
        stat_system = StatSystem(self.bot.db)
        equipped_items = stat_system.get_equipped_items(self.user_id)
        
        if not equipped_items:
            await interaction.response.send_message("You don't have any items equipped!", ephemeral=True)
            return
        
        # Create select menu for equipped items
        select = UnequipmentSelect(self.bot, self.user_id, equipped_items)
        view = discord.ui.View()
        view.add_item(select)
        
        embed = discord.Embed(
            title="❌ Unequip Item", 
            description="Select an item to unequip:",
            color=0xff0000
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_equipment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your panel!", ephemeral=True)
            return
        
        # Refresh the equipment display by recreating the original detailed embed
        from utils.stat_system import StatSystem
        
        stat_system = StatSystem(self.bot.db)
        equipped_items = stat_system.get_equipped_items(self.user_id)
        
        # Get base and effective stats
        base_stats, effective_stats = stat_system.calculate_effective_stats(self.user_id)
        
        # Create equipment embed (matching original)
        embed = discord.Embed(
            title="⚔️ Equipment & Stat Modifiers",
            description="Your currently equipped items and their effects",
            color=0x8B4513
        )
        
        # Show equipment slots
        slot_display = {
            "head": "🎩 Head",
            "eyes": "👓 Eyes", 
            "torso": "👕 Torso",
            "arms_left": "💪 Left Arm",
            "arms_right": "💪 Right Arm",
            "hands_left": "🤚 Left Hand",
            "hands_right": "🤚 Right Hand",
            "legs_left": "🦵 Left Leg",
            "legs_right": "🦵 Right Leg",
            "feet_left": "👟 Left Foot",
            "feet_right": "👟 Right Foot"
        }
        
        equipment_text = ""
        for slot, display_name in slot_display.items():
            if slot in equipped_items:
                item = equipped_items[slot]
                modifiers = item['modifiers']
                mod_text = ""
                if modifiers:
                    mod_list = [f"{stat}+{val}" for stat, val in modifiers.items()]
                    mod_text = f" ({', '.join(mod_list)})"
                equipment_text += f"{display_name}: **{item['name']}**{mod_text}\n"
            else:
                equipment_text += f"{display_name}: *Empty*\n"
        
        embed.add_field(
            name="🎒 Equipment Slots",
            value=equipment_text[:1024] if equipment_text else "No equipment slots found",
            inline=False
        )
        
        # Show current stat effects
        if base_stats and effective_stats:
            stats_text = ""
            for stat_name in ['hp', 'max_hp', 'engineering', 'navigation', 'combat', 'medical', 'defense']:
                if stat_name in base_stats and stat_name in effective_stats:
                    # Only show defense if > 0
                    if stat_name == 'defense' and effective_stats[stat_name] <= 0:
                        continue
                    
                    display_text = stat_system.format_stat_display(
                        base_stats[stat_name], 
                        effective_stats[stat_name]
                    )
                    # Add % for defense
                    if stat_name == 'defense':
                        display_text += "%"
                    stats_text += f"**{stat_name.replace('_', ' ').title()}:** {display_text}\n"
            
            embed.add_field(
                name="📊 Current Stats (Base + Modifiers)",
                value=stats_text[:1024] if stats_text else "No stats available",
                inline=False
            )
        
        # Update the current view instead of creating a new one
        await interaction.response.edit_message(embed=embed, view=self)


class EquipmentSelect(discord.ui.Select):
    def __init__(self, bot, user_id: int, items: list):
        self.bot = bot
        self.user_id = user_id
        
        # Create options from items
        options = []
        for item_id, item_name, description in items[:25]:  # Discord limit
            from utils.item_config import ItemConfig
            slot = ItemConfig.get_equipment_slot(item_name)
            modifiers = ItemConfig.get_stat_modifiers(item_name)
            
            mod_text = ""
            if modifiers:
                mod_list = [f"{stat}+{val}" for stat, val in modifiers.items()]
                mod_text = f" ({', '.join(mod_list)})"
            
            options.append(discord.SelectOption(
                label=item_name[:100],
                value=str(item_id),
                description=f"Slot: {slot}{mod_text}"[:100]
            ))
        
        super().__init__(placeholder="Choose an item to equip...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your selection!", ephemeral=True)
            return
        
        from utils.stat_system import StatSystem
        
        item_id = int(self.values[0])
        
        # Get item name
        item_data = self.bot.db.execute_query(
            "SELECT item_name FROM inventory WHERE item_id = %s",
            (item_id,),
            fetch='one'
        )
        
        if not item_data:
            await interaction.response.send_message("Item not found!", ephemeral=True)
            return
        
        item_name = item_data[0]
        stat_system = StatSystem(self.bot.db)
        
        # Try to equip the item
        success = stat_system.equip_item(self.user_id, item_id, item_name)
        
        if success:
            await interaction.response.send_message(f"✅ Successfully equipped **{item_name}**!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Cannot equip **{item_name}** - slot may be occupied or item incompatible.", ephemeral=True)


class UnequipmentSelect(discord.ui.Select):
    def __init__(self, bot, user_id: int, equipped_items: dict):
        self.bot = bot
        self.user_id = user_id
        
        # Create options from equipped items
        options = []
        for slot_name, item_info in equipped_items.items():
            modifiers = item_info['modifiers']
            mod_text = ""
            if modifiers:
                mod_list = [f"{stat}+{val}" for stat, val in modifiers.items()]
                mod_text = f" ({', '.join(mod_list)})"
            
            options.append(discord.SelectOption(
                label=item_info['name'][:100],
                value=slot_name,
                description=f"Slot: {slot_name.replace('_', ' ').title()}{mod_text}"[:100]
            ))
        
        super().__init__(placeholder="Choose an item to unequip...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your selection!", ephemeral=True)
            return
        
        from utils.stat_system import StatSystem
        
        slot_name = self.values[0]
        stat_system = StatSystem(self.bot.db)
        
        # Get the item name for the response
        equipped_items = stat_system.get_equipped_items(self.user_id)
        item_name = equipped_items.get(slot_name, {}).get('name', 'Unknown Item')
        
        # Try to unequip the item
        success = stat_system.unequip_item(self.user_id, slot_name)
        
        if success:
            await interaction.response.send_message(f"✅ Successfully unequipped **{item_name}** from {slot_name.replace('_', ' ').title()}!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Failed to unequip item from {slot_name.replace('_', ' ').title()}.", ephemeral=True)

        
async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
