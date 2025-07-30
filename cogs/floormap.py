# cogs/floormap.py
import discord
from discord.ext import commands
from discord import app_commands
from utils.holographic_floorplan_generator import HolographicFloorplanGenerator
from config import ALLOWED_GUILD_ID
import os

class FloormapCog(commands.Cog):
    """Commands for generating and displaying location floormaps"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.holo_generator = HolographicFloorplanGenerator(bot)
    
    @app_commands.command(name="floormap", description="View the floormap of your current location")
    async def floormap(self, interaction: discord.Interaction):
        """Display the floormap for the user's current location"""
        
        # Check guild restriction
        if ALLOWED_GUILD_ID and interaction.guild_id != ALLOWED_GUILD_ID:
            await interaction.response.send_message("This command is not available in this server.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send(
                "❌ You need a character to view floormaps! Use `/character create` first.",
                ephemeral=True
            )
            return
        
        current_location_id, char_name = char_info
        
        if not current_location_id:
            await interaction.followup.send(
                "❌ You must be at a location to view its floormap! Use `/travel` to go somewhere first.",
                ephemeral=True
            )
            return
        
        # Generate holographic floormap
        try:
            image_path = self.holo_generator.generate_holographic_floormap(current_location_id)
            
            if not image_path or not os.path.exists(image_path):
                await interaction.followup.send(
                    "❌ Unable to generate floormap for this location.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="LOCATION LAYOUT",
                color=0x00FFFF,  # Cyan color matching holographic theme
                timestamp=discord.utils.utcnow()
            )
            
            embed.set_footer(text=f"Requested by {char_name}")
            
            # Add usage instructions
            embed.add_field(
                name="🔹 Location Map Interface",
                value="Facility blueprint generated with advanced scanning protocols. Use the sub-locations sub-menu to access rooms.",
                inline=False
            )
            
            # Send with holographic blueprint attachment
            with open(image_path, 'rb') as f:
                file = discord.File(f, filename="holographic_blueprint.png")
                embed.set_image(url="attachment://holographic_blueprint.png")
                await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error generating floormap for location {current_location_id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the floormap. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="regenerate_floormap", description="Force regenerate the floormap for your current location")
    async def regenerate_floormap(self, interaction: discord.Interaction):
        """Force regenerate the floormap by deleting cached version"""
        
        # Check guild restriction
        if ALLOWED_GUILD_ID and interaction.guild_id != ALLOWED_GUILD_ID:
            await interaction.response.send_message("This command is not available in this server.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has a character
        char_info = self.db.execute_query(
            "SELECT current_location, name FROM characters WHERE user_id = ?",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.followup.send(
                "❌ You need a character to regenerate floormaps!",
                ephemeral=True
            )
            return
        
        current_location_id, char_name = char_info
        
        if not current_location_id:
            await interaction.followup.send(
                "❌ You must be at a location to regenerate its floormap!",
                ephemeral=True
            )
            return
        
        try:
            # Delete cached holographic floormap to force regeneration
            filepath = self.holo_generator.get_floormap_path(current_location_id)
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Generate new holographic floormap
            image_path = self.holo_generator.generate_holographic_floormap(current_location_id)
            
            if not image_path or not os.path.exists(image_path):
                await interaction.followup.send(
                    "❌ Unable to regenerate floormap for this location.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="🛸 Holographic Blueprint (Regenerated)",
                color=0x00ff00,  # Green for regenerated
                timestamp=discord.utils.utcnow()
            )
            
            embed.set_footer(text=f"Regenerated by {char_name}")
            
            embed.add_field(
                name="✅ Regeneration Complete",
                value="New holographic blueprint generated with updated facility data.",
                inline=False
            )
            
            # Send with holographic blueprint attachment
            with open(image_path, 'rb') as f:
                file = discord.File(f, filename="holographic_blueprint_regen.png")
                embed.set_image(url="attachment://holographic_blueprint_regen.png")
                await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error regenerating floormap for location {current_location_id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while regenerating the floormap. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(FloormapCog(bot))