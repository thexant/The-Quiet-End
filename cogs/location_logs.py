# cogs/location_logs.py
import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta

class LocationLogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    logs_group = app_commands.Group(name="logs", description="Location logs and guestbooks")
    
    @logs_group.command(name="view", description="View the location's log/guestbook")
    async def view_logs(self, interaction: discord.Interaction):
        # Get current location
        char_location = self.db.execute_query(
            '''SELECT c.current_location, l.name, l.location_type
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_location:
            await interaction.response.send_message("Location not found!", ephemeral=True)
            return
        
        location_id, location_name, location_type = char_location
        
        # Check if this location has a log (25% chance if none exists)
        has_log = self.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0] > 0
        
        if not has_log:
            # 25% chance to generate log
            if random.random() < 0.25:
                await self._generate_initial_log(location_id, location_name, location_type)
                has_log = True
        
        if not has_log:
            await interaction.response.send_message(
                f"📜 No log or guestbook found at {location_name}.",
                ephemeral=True
            )
            return
        
        # Get log entries (most recent first)
        entries = self.db.execute_query(
            '''SELECT author_name, message, posted_at, is_generated
               FROM location_logs
               WHERE location_id = ?
               ORDER BY posted_at DESC
               LIMIT 10''',
            (location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"📜 {location_name} - Location Log",
            description=f"Messages and records from visitors to this {location_type.replace('_', ' ')}",
            color=0x8b4513
        )
        
        if entries:
            log_text = []
            for author, message, posted_at, is_generated in entries:
                # Format timestamp
                posted_time = datetime.fromisoformat(posted_at)
                time_str = posted_time.strftime("%Y-%m-%d")
                
                # Different formatting for generated vs player entries
                if is_generated:
                    log_text.append(f"**[{time_str}] {author}**")
                    log_text.append(f"*{message}*")
                else:
                    log_text.append(f"**[{time_str}] {author}**")
                    log_text.append(f'"{message}"')
                log_text.append("")
            
            # Split into multiple fields if too long
            full_text = "\n".join(log_text)
            if len(full_text) > 1024:
                # Split into chunks
                chunks = []
                current_chunk = ""
                for line in log_text:
                    if len(current_chunk + line + "\n") > 1000:
                        chunks.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                if current_chunk:
                    chunks.append(current_chunk)
                
                for i, chunk in enumerate(chunks[:3]):  # Max 3 fields
                    field_name = "📖 Log Entries" if i == 0 else f"📖 Log Entries (cont. {i+1})"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            else:
                embed.add_field(name="📖 Log Entries", value=full_text, inline=False)
        else:
            embed.add_field(name="📖 Empty Log", value="No entries found.", inline=False)
        
        embed.add_field(
            name="✍️ Add Entry",
            value="Use `/logs add <message>` to add your own entry to this log.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @logs_group.command(name="add", description="Add an entry to the location's log")
    @app_commands.describe(message="Your message to add to the log")
    async def add_log_entry(self, interaction: discord.Interaction, message: str):
        if len(message) > 500:
            await interaction.response.send_message("Log entries must be 500 characters or less.", ephemeral=True)
            return
        
        # Get character and location info
        char_info = self.db.execute_query(
            '''SELECT c.name, c.current_location, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character or location not found!", ephemeral=True)
            return
        
        char_name, location_id, location_name = char_info
        
        # Check if location has a log
        has_log = self.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0] > 0
        
        if not has_log:
            await interaction.response.send_message(
                "This location doesn't have a log or guestbook. Check back later!",
                ephemeral=True
            )
            return
        
        # Add entry
        self.db.execute_query(
            '''INSERT INTO location_logs (location_id, author_id, author_name, message)
               VALUES (?, ?, ?, ?)''',
            (location_id, interaction.user.id, char_name, message)
        )
        
        embed = discord.Embed(
            title="✍️ Log Entry Added",
            description=f"Your entry has been added to the {location_name} log.",
            color=0x00ff00
        )
        
        embed.add_field(name="Your Entry", value=f'"{message}"', inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _generate_initial_log(self, location_id: int, location_name: str, location_type: str):
        """Generate initial log entries for a location"""
        
        # Generate 3-7 initial entries
        num_entries = random.randint(3, 7)
        
        # Entry templates based on location type
        if location_type == 'colony':
            entry_templates = [
                ("Colonial Administrator", "New mining quotas established. Productivity up 12% this quarter."),
                ("Chief Engineer", "Atmospheric processors running at 94% efficiency. Recommend maintenance cycle next month."),
                ("Security Chief", "Perimeter patrol completed. No hostile contacts detected."),
                ("Medical Officer", "Radiation exposure levels within acceptable parameters. No health incidents reported."),
                ("Supply Coordinator", "Inbound cargo shipment delayed due to corridor instabilities. Expect 3-day delay."),
                ("Mining Foreman", "Rich ore vein discovered in Sector 7. Recommending immediate extraction."),
                ("Communications Tech", "Long-range communications restored. Contact with headquarters reestablished."),
                ("Unknown Trader", "Good rates here for processed materials. Fair dealing, would recommend."),
                ("Passing Pilot", "Safe harbor in this part of space. Fuel prices reasonable."),
                ("Maintenance Crew", "Life support systems overhauled. All green lights across the board.")
            ]
        
        elif location_type == 'space_station':
            entry_templates = [
                ("Station Commander", "Traffic control operating efficiently. 47 ships processed this cycle."),
                ("Docking Supervisor", "Bay 7 cleared for heavy freight operations. Reinforcement complete."),
                ("Trade Representative", "Market prices stable. Recommend bulk commodity trading."),
                ("Security Detail", "Contraband scan negative. All incoming cargo cleared."),
                ("Navigation Officer", "Updated stellar cartography data uploaded to public terminals."),
                ("Medical Bay", "Emergency medical supplies restocked. Ready for trauma cases."),
                ("Merchant Captain", "Excellent trading post. Wide selection, fair prices, good security."),
                ("Freelance Pilot", "Perfect stopover point. Everything a traveler needs."),
                ("Corporate Inspector", "Station meets all safety and operational standards. Certification renewed."),
                ("Visiting Diplomat", "Impressed by the professionalism and efficiency of station operations.")
            ]
        
        elif location_type == 'outpost':
            entry_templates = [
                ("Outpost Manager", "Supply drop successful. Should last us another 6 months."),
                ("Communications Op", "Long-range array repaired. Back in contact with the sector."),
                ("Mechanic", "Fixed the atmospheric recycler again. Really need replacement parts."),
                ("Patrol Leader", "Perimeter sensors functional. No anomalous readings."),
                ("Solo Trader", "Basic supplies available. Don't expect luxury here."),
                ("Explorer", "Good waypoint for deep space operations. Minimal but essential services."),
                ("Refugee", "Grateful for shelter. Small but welcoming community."),
                ("Surveyor", "Used this as base camp for sector mapping. Adequate facilities."),
                ("Maintenance Bot", "AUTO-LOG: Systems nominal. Efficiency at 67% of optimal."),
                ("Unknown Visitor", "Quiet place. Good for laying low and making repairs.")
            ]
        
        else:  # gate
            entry_templates = [
                ("Gate Operator", "Corridor stabilization parameters within normal range. Transit approved."),
                ("Transit Authority", "Safety inspection complete. Gate cleared for continued operation."),
                ("Navigation Beacon", "AUTO-LOG: Position verified. Stellar drift compensated."),
                ("Maintenance Crew", "Gate matrix realigned. Improved transit efficiency by 8%."),
                ("Corporate Transport", "Efficient gate operation. Transit time reduced significantly."),
                ("Independent Hauler", "Clean gate - no radiation spikes during transit. Recommend route."),
                ("Gate Engineer", "Upgraded decontamination systems online. Improved safety margins."),
                ("Safety Inspector", "All safety protocols in compliance. Operation authorized."),
                ("Freight Captain", "Smooth transit. Gate crew knows their business."),
                ("Research Team", "Collected valuable data on corridor mechanics. Fascinating phenomena.")
            ]
        
        # Select random entries
        selected_entries = random.sample(entry_templates, min(num_entries, len(entry_templates)))
        
        # Generate entries with random timestamps (past 30 days)
        for author, message in selected_entries:
            # Random time in past 30 days
            days_ago = random.randint(1, 30)
            hours_ago = random.randint(0, 23)
            entry_time = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
            
            self.db.execute_query(
                '''INSERT INTO location_logs 
                   (location_id, author_id, author_name, message, posted_at, is_generated)
                   VALUES (?, ?, ?, ?, ?, 1)''',
                (location_id, 0, author, message, entry_time.isoformat())
            )

async def setup(bot):
    await bot.add_cog(LocationLogsCog(bot))