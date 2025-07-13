# cogs/reputation.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import sqlite3
class ReputationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    def get_reputation_tier(self, score: int) -> str:
        if score >= 70: return "Heroic"
        if score >= 35: return "Good"
        if score <= -70: return "Evil"
        if score <= -35: return "Bad"
        return "Neutral"

    async def update_reputation(self, user_id: int, source_location_id: int, karma_change: int):
        """
        Updates a user's reputation at the source location and propagates it
        to nearby locations with decay.
        """
        if karma_change == 0:
            return

        # Use a queue for BFS traversal
        queue = [(source_location_id, karma_change)]
        visited = {source_location_id}

        while queue:
            current_loc_id, current_karma_change = queue.pop(0)

            # Update reputation for the current location
            existing_rep = self.db.execute_query(
                "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
                (user_id, current_loc_id),
                fetch='one'
            )
            if existing_rep:
                new_rep = existing_rep[0] + current_karma_change
                self.db.execute_query(
                    "UPDATE character_reputation SET reputation = ? WHERE user_id = ? AND location_id = ?",
                    (new_rep, user_id, current_loc_id)
                )
            else:
                self.db.execute_query(
                    "INSERT INTO character_reputation (user_id, location_id, reputation) VALUES (?, ?, ?)",
                    (user_id, current_loc_id, current_karma_change)
                )
            
            # Stop propagation if karma change is too small
            if abs(current_karma_change) <= 2:
                continue

            # Find neighbors and add to queue for propagation
            neighbors = self.db.execute_query(
                "SELECT destination_location FROM corridors WHERE origin_location = ? AND is_active = 1",
                (current_loc_id,),
                fetch='all'
            )

            decayed_karma = (current_karma_change - 2) if current_karma_change > 0 else (current_karma_change + 2)

            for (neighbor_id,) in neighbors:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, decayed_karma))
        
        print(f"Reputation for {user_id} updated starting from {source_location_id} with change {karma_change}.")

    @app_commands.command(name="reputation", description="View your reputation standings across the galaxy")
    async def view_reputation(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            reputations = self.db.execute_query(
                """SELECT l.name, l.faction, cr.reputation
                   FROM character_reputation cr
                   JOIN locations l ON cr.location_id = l.location_id
                   WHERE cr.user_id = ?
                   ORDER BY cr.reputation DESC""",
                (interaction.user.id,),
                fetch='all'
            )
        except sqlite3.OperationalError as e:
            if "no such column: faction" in str(e):
                # Fallback query without faction
                reputations = self.db.execute_query(
                    """SELECT l.name, 'neutral' as faction, cr.reputation
                       FROM character_reputation cr
                       JOIN locations l ON cr.location_id = l.location_id
                       WHERE cr.user_id = ?
                       ORDER BY cr.reputation DESC""",
                    (interaction.user.id,),
                    fetch='all'
                )
                print("⚠️ Faction column missing in reputation query, using 'neutral' as default")
            else:
                raise e

        if not reputations:
            await interaction.followup.send("You have a neutral standing everywhere.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Reputation Report: {interaction.user.display_name}", color=0xCCCCCC)
        
        positive_rep = [rep for rep in reputations if rep[2] > 0]
        negative_rep = sorted([rep for rep in reputations if rep[2] < 0], key=lambda x: x[2])

        if positive_rep:
            pos_text = "\n".join([f"**{name}** ({faction}): **{rep}** ({self.get_reputation_tier(rep)})" for name, faction, rep in positive_rep[:5]])
            embed.add_field(name="👍 Positive Standings", value=pos_text, inline=False)

        if negative_rep:
            neg_text = "\n".join([f"**{name}** ({faction}): **{rep}** ({self.get_reputation_tier(rep)})" for name, faction, rep in negative_rep[:5]])
            embed.add_field(name="👎 Negative Standings", value=neg_text, inline=False)

        embed.set_footer(text="Reputation changes in one area can affect nearby locations.")
        await interaction.followup.send(embed=embed)
    @app_commands.command(name="setreputation", description="Admin: Set a user's reputation at a specific location")
    @app_commands.describe(
        user="The user to set reputation for",
        location="The location name (partial matches allowed)",
        reputation="The reputation value to set (-100 to 100 recommended)"
    )
    async def set_reputation(self, interaction: discord.Interaction, user: discord.Member, location: str, reputation: int):
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Administrator permissions required.",
                ephemeral=True
            )
            return
        
        # Validate reputation range (optional, but recommended)
        if reputation < -100 or reputation > 100:
            await interaction.response.send_message(
                "⚠️ Reputation values outside -100 to 100 may cause unexpected behavior.",
                ephemeral=True
            )
            return
        
        # Check if target user has a character
        char_check = self.db.execute_query(
            "SELECT user_id FROM characters WHERE user_id = ?",
            (user.id,),
            fetch='one'
        )
        
        if not char_check:
            await interaction.response.send_message(
                f"❌ {user.mention} doesn't have a character.",
                ephemeral=True
            )
            return
        
        # Find location by name (partial match)
        location_data = self.db.execute_query(
            "SELECT location_id, name FROM locations WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
            (f"%{location}%",),
            fetch='one'
        )
        
        if not location_data:
            await interaction.response.send_message(
                f"❌ Location '{location}' not found. Try a partial name match.",
                ephemeral=True
            )
            return
        
        location_id, location_name = location_data
        
        # Get current reputation at this location
        current_rep = self.db.execute_query(
            "SELECT reputation FROM character_reputation WHERE user_id = ? AND location_id = ?",
            (user.id, location_id),
            fetch='one'
        )
        
        current_reputation = current_rep[0] if current_rep else 0
        
        # Calculate the change needed
        reputation_change = reputation - current_reputation
        
        if reputation_change == 0:
            await interaction.response.send_message(
                f"ℹ️ {user.mention} already has {reputation} reputation at {location_name}.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Apply the reputation change (this will handle propagation automatically)
        await self.update_reputation(user.id, location_id, reputation_change)
        
        # Create response embed
        embed = discord.Embed(
            title="⚖️ Reputation Set",
            description=f"Set reputation for {user.mention} at **{location_name}**",
            color=0x4169E1
        )
        
        embed.add_field(
            name="Previous Reputation",
            value=f"{current_reputation} ({self.get_reputation_tier(current_reputation)})",
            inline=True
        )
        
        embed.add_field(
            name="New Reputation", 
            value=f"{reputation} ({self.get_reputation_tier(reputation)})",
            inline=True
        )
        
        embed.add_field(
            name="Change Applied",
            value=f"{'+' if reputation_change > 0 else ''}{reputation_change}",
            inline=True
        )
        
        embed.add_field(
            name="📡 Propagation",
            value="Reputation changes have been applied to nearby locations with decay.",
            inline=False
        )
        
        embed.set_footer(
            text=f"Set by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log the admin action
        print(f"⚖️ Admin reputation set: {user.display_name} at {location_name} = {reputation} (change: {reputation_change:+d}) by {interaction.user.display_name}")
async def setup(bot):
    await bot.add_cog(ReputationCog(bot))