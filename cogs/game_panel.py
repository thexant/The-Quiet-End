import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio
import time
import random

class GamePanelView(discord.ui.View):
    def __init__(self, bot, include_map_button=False):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.db = bot.db
        
        # Always add core buttons with explicit row assignments
        self.add_item(CreateCharacterButton(row=0))
        self.add_item(CreateRandomCharacterButton(row=0))
        self.add_item(LoginButton(row=1))
        self.add_item(LogoutButton(row=1))
        
        # Conditionally add map button on second row
        if include_map_button:
            self.add_item(ViewMapButton(row=1))
        
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            """Allow all users to use the panel"""
            return True

class CreateCharacterButton(discord.ui.Button):
    def __init__(self, row=None):
        super().__init__(
            label="Create Character",
            style=discord.ButtonStyle.primary,
            emoji="👤",
            custom_id="game_panel:create_character",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        db = bot.db
        
        # Check if user already has a character
        existing_char = db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if existing_char:
            await interaction.response.send_message(
                f"You already have a character named **{existing_char[0]}**! Use the Login button instead.",
                ephemeral=True
            )
            return
        
        # Import and use the existing character creation functionality
        char_cog = bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.create_character.callback(char_cog, interaction)
        else:
            await interaction.response.send_message(
                "Character system unavailable. Please try again later.",
                ephemeral=True
            )

class LoginButton(discord.ui.Button):
    def __init__(self, row=None):
        super().__init__(
            label="Login",
            style=discord.ButtonStyle.success,
            emoji="🔓",
            custom_id="game_panel:login",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        db = bot.db
        
        # Check if user has a character
        char_data = db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_data:
            await interaction.response.send_message(
                "You don't have a character yet! Use the **Create Character** button first.",
                ephemeral=True
            )
            return
        
        char_name, is_logged_in = char_data
        
        if is_logged_in:
            await interaction.response.send_message(
                f"You're already logged in as **{char_name}**!",
                ephemeral=True
            )
            return
        
        # Use the existing character login functionality
        char_cog = bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.login_character.callback(char_cog, interaction)
        else:
            await interaction.response.send_message(
                "Character system unavailable. Please try again later.",
                ephemeral=True
            )

class LogoutButton(discord.ui.Button):
    def __init__(self, row=None):
        super().__init__(
            label="Logout",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id="game_panel:logout",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        db = bot.db
        
        # Check if user has a character and is logged in
        char_data = db.execute_query(
            "SELECT name, is_logged_in FROM characters WHERE user_id = ?",
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
        
        # Use the existing character logout functionality
        char_cog = bot.get_cog('CharacterCog')
        if char_cog:
            await char_cog.logout_character.callback(char_cog, interaction)
        else:
            await interaction.response.send_message(
                "Character system unavailable. Please try again later.",
                ephemeral=True
            )

class ViewMapButton(discord.ui.Button):
    def __init__(self, row=None):
        super().__init__(
            label="View Map",
            style=discord.ButtonStyle.secondary,
            emoji="🗺️",
            custom_id=f"game_panel:view_map:{int(time.time())}",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        
        # Check if webmap is running
        webmap_cog = bot.get_cog('WebMapCog')
        if not webmap_cog or not webmap_cog.is_running:
            await interaction.response.send_message(
                "Interactive map is not currently available.",
                ephemeral=True
            )
            return
        
        # Get the final webmap URL
        final_url, _ = await webmap_cog.get_final_map_url()
        
        embed = discord.Embed(
            title="🗺️ Interactive Galaxy Map",
            description="Access the real-time galaxy map to see locations, players, and routes.",
            color=0x4169E1
        )
        
        embed.add_field(
            name="Map URL",
            value=f"[Click here to open the map]({final_url})",
            inline=False
        )
        
        # Only show a note if the IP address is not configured
        if "[SERVER_IP]" in final_url:
            embed.add_field(
                name="Note for Admins",
                value="The server's external IP could not be detected. Please use the `/webmap_set_ip` command so this link works for everyone.",
                inline=False
            )
        
        embed.add_field(
            name="Features",
            value="• Real-time player positions\n• Location details\n• Travel routes\n• Galaxy overview",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class CreateRandomCharacterButton(discord.ui.Button):
    def __init__(self, row=None):
        super().__init__(
            label="Create Random Character",
            style=discord.ButtonStyle.secondary,
            emoji="🎲",
            custom_id="game_panel:create_random_character",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        db = bot.db
        
        # Check if user already has a character
        existing_char = db.execute_query(
            "SELECT name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if existing_char:
            await interaction.response.send_message(
                f"You already have a character named **{existing_char[0]}**! Use the Login button instead.",
                ephemeral=True
            )
            return
        
        # Import the random character creation function
        from utils.views import create_random_character
        
        # Call the random character creation function
        await create_random_character(bot, interaction)
class GamePanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Start background task to update panels
        self.bot.loop.create_task(self.setup_persistent_views())
        self.bot.loop.create_task(self.panel_update_loop())
    
    async def setup_persistent_views(self):
        """Set up persistent views on bot startup"""
        await self.bot.wait_until_ready()
        
        # Check if webmap is running for initial setup
        webmap_cog = self.bot.get_cog('WebMapCog')
        include_map = webmap_cog and webmap_cog.is_running
        
        # Create and register a persistent view (Discord.py will handle the routing)
        view = GamePanelView(self.bot, include_map_button=include_map)
        self.bot.add_view(view)
        
        print("🎮 Game panel persistent views loaded")
    
    async def panel_update_loop(self):
        """Background task to update game panels periodically"""
        await self.bot.wait_until_ready()
        
        while True:
            try:
                await asyncio.sleep(30)  # Update every minute
                
                # Get all active panels
                panels = self.db.execute_query(
                    "SELECT guild_id, channel_id, message_id FROM game_panels",
                    fetch='all'
                )
                
                for guild_id, channel_id, message_id in panels:
                    try:
                        guild = self.bot.get_guild(guild_id)
                        if not guild:
                            continue
                        
                        channel = guild.get_channel(channel_id)
                        if not channel:
                            continue
                        
                        # Update the panel
                        embed = await self.create_panel_embed(guild)
                        view = await self.create_panel_view()
                        
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.edit(embed=embed, view=view)
                        except discord.NotFound:
                            # Message was deleted, remove from database
                            self.db.execute_query(
                                "DELETE FROM game_panels WHERE message_id = ?",
                                (message_id,)
                            )
                        except discord.Forbidden:
                            # No permission to edit
                            pass
                        
                    except Exception as e:
                        print(f"Error updating game panel {message_id}: {e}")
                
            except Exception as e:
                print(f"Error in panel update loop: {e}")
                await asyncio.sleep(60)
    @app_commands.command(name="panel_remove", description="Remove the game panel from this channel")
    async def remove_panel(self, interaction: discord.Interaction):
        """Remove game panel from current channel"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        # Check if there's a panel in this channel
        panel = self.db.execute_query(
            "SELECT message_id FROM game_panels WHERE guild_id = ? AND channel_id = ?",
            (interaction.guild.id, interaction.channel.id),
            fetch='one'
        )
        
        if not panel:
            await interaction.response.send_message(
                "❌ No game panel found in this channel.",
                ephemeral=True
            )
            return
        
        message_id = panel[0]
        
        # Try to delete the message
        try:
            message = await interaction.channel.fetch_message(message_id)
            await message.delete()
        except discord.NotFound:
            # Message already deleted, just clean up database
            pass
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ I don't have permission to delete the panel message. Removing from database only.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ Error deleting message: {e}. Removing from database.",
                ephemeral=True
            )
        
        # Remove from database
        self.db.execute_query(
            "DELETE FROM game_panels WHERE guild_id = ? AND channel_id = ?",
            (interaction.guild.id, interaction.channel.id)
        )
        
        embed = discord.Embed(
            title="🗑️ Game Panel Removed",
            description=f"Game panel has been removed from {interaction.channel.mention}",
            color=0xff6b6b
        )
        
        if not hasattr(interaction, 'response') or interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="panel_remove_channel", description="Remove game panel from a specific channel")
    @app_commands.describe(channel="The channel to remove the game panel from")
    async def remove_panel_from_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Remove game panel from specified channel"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        # Check if there's a panel in the specified channel
        panel = self.db.execute_query(
            "SELECT message_id FROM game_panels WHERE guild_id = ? AND channel_id = ?",
            (interaction.guild.id, channel.id),
            fetch='one'
        )
        
        if not panel:
            await interaction.response.send_message(
                f"❌ No game panel found in {channel.mention}.",
                ephemeral=True
            )
            return
        
        message_id = panel[0]
        
        # Try to delete the message
        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
        except discord.NotFound:
            # Message already deleted, just clean up database
            pass
        except discord.Forbidden:
            await interaction.response.send_message(
                f"⚠️ I don't have permission to delete the panel message in {channel.mention}. Removing from database only.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ Error deleting message in {channel.mention}: {e}. Removing from database.",
                ephemeral=True
            )
        
        # Remove from database
        self.db.execute_query(
            "DELETE FROM game_panels WHERE guild_id = ? AND channel_id = ?",
            (interaction.guild.id, channel.id)
        )
        
        embed = discord.Embed(
            title="🗑️ Game Panel Removed",
            description=f"Game panel has been removed from {channel.mention}",
            color=0xff6b6b
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="panel_list", description="List all game panels in this server")
    async def list_panels(self, interaction: discord.Interaction):
        """List all game panels in the server"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        panels = self.db.execute_query(
            "SELECT channel_id, message_id, created_at FROM game_panels WHERE guild_id = ?",
            (interaction.guild.id,),
            fetch='all'
        )
        
        if not panels:
            await interaction.response.send_message(
                "📝 No game panels found in this server.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 Game Panels in Server",
            description=f"Found {len(panels)} panel(s)",
            color=0x4169E1
        )
        
        for channel_id, message_id, created_at in panels:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                # Check if message still exists
                try:
                    await channel.fetch_message(message_id)
                    status = "✅ Active"
                except discord.NotFound:
                    status = "❌ Message Deleted"
                except discord.Forbidden:
                    status = "⚠️ No Access"
                except:
                    status = "❓ Unknown"
                
                embed.add_field(
                    name=f"#{channel.name}",
                    value=f"Status: {status}\nMessage ID: `{message_id}`\nCreated: {created_at}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Unknown Channel",
                    value=f"Channel ID: `{channel_id}` (deleted?)\nMessage ID: `{message_id}`\nCreated: {created_at}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="panel_cleanup", description="Clean up orphaned game panels (where messages no longer exist)")
    async def cleanup_panels(self, interaction: discord.Interaction):
        """Clean up orphaned game panels"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        panels = self.db.execute_query(
            "SELECT channel_id, message_id FROM game_panels WHERE guild_id = ?",
            (interaction.guild.id,),
            fetch='all'
        )
        
        if not panels:
            await interaction.followup.send("📝 No game panels found to clean up.")
            return
        
        orphaned_panels = []
        
        for channel_id, message_id in panels:
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                # Channel doesn't exist anymore
                orphaned_panels.append((channel_id, message_id, "Channel deleted"))
                continue
            
            try:
                await channel.fetch_message(message_id)
                # Message exists, panel is valid
            except discord.NotFound:
                # Message doesn't exist
                orphaned_panels.append((channel_id, message_id, "Message deleted"))
            except discord.Forbidden:
                # Can't access the message, assume it's still there
                pass
            except Exception as e:
                # Other error, log it but don't remove
                print(f"Error checking panel message {message_id}: {e}")
        
        if not orphaned_panels:
            embed = discord.Embed(
                title="✅ Cleanup Complete",
                description="No orphaned panels found. All panels are active.",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Remove orphaned panels
        for channel_id, message_id, reason in orphaned_panels:
            self.db.execute_query(
                "DELETE FROM game_panels WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
                (interaction.guild.id, channel_id, message_id)
            )
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=f"Removed {len(orphaned_panels)} orphaned panel(s)",
            color=0xff9500
        )
        
        cleanup_details = []
        for channel_id, message_id, reason in orphaned_panels:
            channel = interaction.guild.get_channel(channel_id)
            channel_name = f"#{channel.name}" if channel else f"Channel ID: {channel_id}"
            cleanup_details.append(f"• {channel_name}: {reason}")
        
        if cleanup_details:
            embed.add_field(
                name="Removed Panels",
                value="\n".join(cleanup_details[:10]),  # Limit to first 10 to avoid embed limits
                inline=False
            )
            
            if len(cleanup_details) > 10:
                embed.add_field(
                    name="Additional",
                    value=f"... and {len(cleanup_details) - 10} more",
                    inline=False
                )
        
        await interaction.followup.send(embed=embed)
    # No admin commands in this cog - they belong in admin.py
    async def refresh_all_panel_views(self):
        """Refresh all panel views with current webmap status"""
        try:
            # Check current webmap status
            webmap_cog = self.bot.get_cog('WebMapCog')
            include_map = webmap_cog and webmap_cog.is_running
            
            print(f"🔄 Webmap cog found: {webmap_cog is not None}")
            print(f"🔄 Webmap running status: {webmap_cog.is_running if webmap_cog else 'N/A'}")
            print(f"🔄 Include map button: {include_map}")
            
            # Create and register new persistent view
            view = GamePanelView(self.bot, include_map_button=include_map)
            self.bot.add_view(view)
            
            print(f"🔄 Refreshed persistent views with webmap status: {include_map}")
            
        except Exception as e:
            print(f"❌ Error refreshing panel views: {e}")
            import traceback
            traceback.print_exc()

    async def create_panel_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the embed for the game panel"""
        # Get galaxy info
        webmap_cog = self.bot.get_cog('WebMapCog')
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        galaxy_info = time_system.get_galaxy_info()
        
        if galaxy_info:
            galaxy_name = galaxy_info[0]
            current_time = time_system.format_ingame_datetime(time_system.calculate_current_ingame_time())
        else:
            galaxy_name = "Unknown Galaxy"
            current_time = "Time system not initialized"
        
        # Get active player count
        active_players = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE is_logged_in = 1",
            fetch='one'
        )[0]
        
        # Create the embed
        embed = discord.Embed(
            title=f"🌌 {galaxy_name}",
            description="Welcome to the galaxy! Use the buttons below to start your journey.",
            color=0x4169E1
        )
        
        embed.add_field(
            name="📅 Current Date",
            value=current_time,
            inline=True
        )
        
        embed.add_field(
            name="👥 Active Players",
            value=f"{active_players} pilots online",
            inline=True
        )
        
        embed.add_field(
            name="🌟 Galaxy Status",
            value="Operational",
            inline=True
        )
        
        # Check if webmap is running and add MAP field
        if webmap_cog and webmap_cog.is_running:
            try:
                final_url, _ = await webmap_cog.get_final_map_url()
                
                # Check if the fallback placeholder is being used
                if "[SERVER_IP]" in final_url:
                    value_text = "Map available (IP not set by admin)"
                else:
                    value_text = f"[Interactive Galaxy Map]({final_url})"
                
                embed.add_field(
                    name="🗺️ MAP",
                    value=f"{value_text}\nReal-time locations and routes",
                    inline=True
                )
            except Exception as e:
                print(f"Error getting webmap URL for game panel: {e}")
                embed.add_field(
                    name="🗺️ MAP", 
                    value="Interactive map available\n(URL unavailable)",
                    inline=True
                )
        
        embed.add_field(
            name="🚀 Getting Started",
            value="• **New pilots:** Create a character\n• **Returning pilots:** Login to continue\n• **Explore:** Use the map link above if available",
            inline=False
        )
        
        embed.set_footer(text="Panel updates automatically • Last update")
        embed.timestamp = datetime.now()
        
        return embed
    
    async def create_panel_view(self) -> discord.ui.View:
        """Create the view for the game panel with conditional map button"""
        # Check if webmap is running
        webmap_cog = self.bot.get_cog('WebMapCog')
        include_map = webmap_cog and webmap_cog.is_running
        
        return GamePanelView(self.bot, include_map_button=include_map)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Clean up orphaned panels on startup and setup views"""
        print("🎮 Game Panel Cog: Performing startup cleanup...")
        
        panels = self.db.execute_query(
            "SELECT guild_id, channel_id, message_id FROM game_panels",
            fetch='all'
        )
        
        orphaned_count = 0
        
        for guild_id, channel_id, message_id in panels:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                # Guild no longer exists, remove panel
                self.db.execute_query(
                    "DELETE FROM game_panels WHERE guild_id = ?",
                    (guild_id,)
                )
                orphaned_count += 1
                print(f"🗑️ Removed panel from non-existent guild {guild_id}")
                continue
            
            channel = guild.get_channel(channel_id)
            if not channel:
                # Channel no longer exists, remove panel
                self.db.execute_query(
                    "DELETE FROM game_panels WHERE channel_id = ?",
                    (channel_id,)
                )
                orphaned_count += 1
                print(f"🗑️ Removed panel from non-existent channel {channel_id} in {guild.name}")
                continue
            
            try:
                await channel.fetch_message(message_id)
            except discord.NotFound:
                # Message no longer exists, remove panel
                self.db.execute_query(
                    "DELETE FROM game_panels WHERE message_id = ?",
                    (message_id,)
                )
                orphaned_count += 1
                print(f"🗑️ Removed orphaned panel message {message_id} from #{channel.name} in {guild.name}")
            except Exception as e:
                print(f"⚠️ Could not verify panel message {message_id} in #{channel.name}: {e}")
        
        if orphaned_count > 0:
            print(f"🧹 Startup cleanup: Removed {orphaned_count} orphaned panel(s)")
        else:
            print("✅ Startup cleanup: No orphaned panels found")

async def setup(bot):
    await bot.add_cog(GamePanelCog(bot))
