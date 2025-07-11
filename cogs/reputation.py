# cogs/reputation.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio

class ReputationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    def get_reputation_tier(self, score: int) -> str:
        if score >= 80: return "Heroic"
        if score >= 50: return "Good"
        if score <= -80: return "Evil"
        if score <= -50: return "Bad"
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

        reputations = self.db.execute_query(
            """SELECT l.name, l.faction, cr.reputation
               FROM character_reputation cr
               JOIN locations l ON cr.location_id = l.location_id
               WHERE cr.user_id = ?
               ORDER BY cr.reputation DESC""",
            (interaction.user.id,),
            fetch='all'
        )

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

async def setup(bot):
    await bot.add_cog(ReputationCog(bot))