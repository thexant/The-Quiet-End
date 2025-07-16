# cogs/admin_customize.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
from typing import Optional, Literal

class AdminCustomizeCog(commands.Cog):
    """Admin-only commands for customizing the bot's appearance and status"""
    
    def __init__(self, bot):
        self.bot = bot
        
    def is_admin():
        """Check if the user has administrator permissions"""
        async def predicate(interaction: discord.Interaction) -> bool:
            if interaction.guild is None:
                return False
            return interaction.user.guild_permissions.administrator
        return app_commands.check(predicate)
    
    customize_group = app_commands.Group(
        name="customize",
        description="Admin-only bot customization commands"
    )
    
    @customize_group.command(name="avatar")
    @is_admin()
    async def set_avatar(self, interaction: discord.Interaction, image_url: str):
        """Change the bot's profile picture/avatar
        
        Args:
            image_url: Direct URL to an image (jpg, png, gif)
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        await interaction.followup.send(
                            "❌ Failed to download image. Please provide a valid image URL.",
                            ephemeral=True
                        )
                        return
                    
                    # Check content type
                    content_type = response.headers.get('Content-Type', '')
                    if not content_type.startswith('image/'):
                        await interaction.followup.send(
                            "❌ The URL must point to an image file (jpg, png, gif).",
                            ephemeral=True
                        )
                        return
                    
                    # Read image data
                    image_data = await response.read()
                    
                    # Discord has a 10MB limit for avatars
                    if len(image_data) > 10 * 1024 * 1024:
                        await interaction.followup.send(
                            "❌ Image is too large. Maximum size is 10MB.",
                            ephemeral=True
                        )
                        return
                    
                    # Update avatar
                    await self.bot.user.edit(avatar=image_data)
                    
                    await interaction.followup.send(
                        "✅ Bot avatar updated successfully!",
                        ephemeral=True
                    )
                    
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to update avatar: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @customize_group.command(name="username")
    @is_admin()
    async def set_username(self, interaction: discord.Interaction, new_name: str):
        """Change the bot's username
        
        Args:
            new_name: The new username for the bot (2-32 characters)
        """
        await interaction.response.defer(ephemeral=True)
        
        # Validate username length
        if len(new_name) < 2 or len(new_name) > 32:
            await interaction.followup.send(
                "❌ Username must be between 2 and 32 characters long.",
                ephemeral=True
            )
            return
        
        try:
            old_name = self.bot.user.name
            await self.bot.user.edit(username=new_name)
            
            await interaction.followup.send(
                f"✅ Bot username changed from **{old_name}** to **{new_name}**!",
                ephemeral=True
            )
            
        except discord.HTTPException as e:
            if "You are changing your username or Discord Tag too fast" in str(e):
                await interaction.followup.send(
                    "❌ Username can only be changed twice per hour. Please try again later.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to update username: {str(e)}",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @customize_group.command(name="activity")
    @is_admin()
    async def set_activity(
        self, 
        interaction: discord.Interaction,
        activity_type: Literal["playing", "streaming", "listening", "watching", "competing"],
        activity_text: str,
        streaming_url: Optional[str] = None
    ):
        """Change the bot's activity/status
        
        Args:
            activity_type: Type of activity (playing, streaming, listening, watching, competing)
            activity_text: The text to display for the activity
            streaming_url: (Optional) Twitch or YouTube URL for streaming activity
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Map string to ActivityType
            activity_map = {
                "playing": discord.ActivityType.playing,
                "streaming": discord.ActivityType.streaming,
                "listening": discord.ActivityType.listening,
                "watching": discord.ActivityType.watching,
                "competing": discord.ActivityType.competing
            }
            
            activity_type_enum = activity_map[activity_type]
            
            # Create activity based on type
            if activity_type == "streaming":
                if not streaming_url:
                    await interaction.followup.send(
                        "❌ Streaming activity requires a Twitch or YouTube URL.",
                        ephemeral=True
                    )
                    return
                    
                # Validate streaming URL
                if not (streaming_url.startswith("https://twitch.tv/") or 
                        streaming_url.startswith("https://www.twitch.tv/") or
                        streaming_url.startswith("https://youtube.com/") or
                        streaming_url.startswith("https://www.youtube.com/")):
                    await interaction.followup.send(
                        "❌ Streaming URL must be a valid Twitch or YouTube URL.",
                        ephemeral=True
                    )
                    return
                
                activity = discord.Streaming(name=activity_text, url=streaming_url)
            else:
                activity = discord.Activity(type=activity_type_enum, name=activity_text)
            
            # Update bot's activity
            await self.bot.change_presence(activity=activity)
            
            # Save to config if possible (for persistence)
            try:
                import importlib
                import config
                
                # Update the config
                config.BOT_CONFIG['activity_type'] = activity_type
                config.BOT_CONFIG['activity_name'] = activity_text
                if streaming_url:
                    config.BOT_CONFIG['streaming_url'] = streaming_url
                
                # Try to save to file
                with open('config.py', 'r') as f:
                    lines = f.readlines()
                
                # Update activity_name in config
                for i, line in enumerate(lines):
                    if "'activity_name':" in line:
                        lines[i] = f"    'activity_name': '{activity_text}',\n"
                
                with open('config.py', 'w') as f:
                    f.writelines(lines)
                    
            except:
                # If we can't update config, that's okay - the change is still active
                pass
            
            await interaction.followup.send(
                f"✅ Bot activity updated to: **{activity_type.title()} {activity_text}**",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to update activity: {str(e)}",
                ephemeral=True
            )
    
    @customize_group.command(name="clear_activity")
    @is_admin()
    async def clear_activity(self, interaction: discord.Interaction):
        """Remove the bot's activity/status"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.bot.change_presence(activity=None)
            
            await interaction.followup.send(
                "✅ Bot activity cleared!",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to clear activity: {str(e)}",
                ephemeral=True
            )
    
    @customize_group.command(name="reset_avatar")
    @is_admin()
    async def reset_avatar(self, interaction: discord.Interaction):
        """Remove the bot's avatar (reset to default)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.bot.user.edit(avatar=None)
            
            await interaction.followup.send(
                "✅ Bot avatar reset to default!",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to reset avatar: {str(e)}",
                ephemeral=True
            )
    
    @customize_group.command(name="info")
    @is_admin()
    async def bot_info(self, interaction: discord.Interaction):
        """Display current bot customization info"""
        embed = discord.Embed(
            title="🤖 Bot Customization Info",
            color=discord.Color.blue()
        )
        
        # Bot avatar
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Username
        embed.add_field(name="Username", value=self.bot.user.name, inline=True)
        
        # Discriminator (if not pomelo username)
        if self.bot.user.discriminator != "0":
            embed.add_field(name="Discriminator", value=f"#{self.bot.user.discriminator}", inline=True)
        
        # Activity
        if self.bot.activity:
            activity_type = str(self.bot.activity.type).split('.')[-1].title()
            activity_name = self.bot.activity.name
            
            if isinstance(self.bot.activity, discord.Streaming):
                activity_info = f"{activity_type}: {activity_name}\nURL: {self.bot.activity.url}"
            else:
                activity_info = f"{activity_type}: {activity_name}"
                
            embed.add_field(name="Activity", value=activity_info, inline=False)
        else:
            embed.add_field(name="Activity", value="None", inline=False)
        
        # Bot ID
        embed.add_field(name="Bot ID", value=self.bot.user.id, inline=True)
        
        # Server count
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Error handlers for permission checks
    @set_avatar.error
    @set_username.error
    @set_activity.error
    @clear_activity.error
    @reset_avatar.error
    @bot_info.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminCustomizeCog(bot))