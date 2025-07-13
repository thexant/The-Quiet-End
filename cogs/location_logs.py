# cogs/location_logs.py
import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta
from utils.npc_data import generate_npc_name, get_occupation

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
        """Generate initial log entries for a location using dynamic NPCs with location-specific content"""
        
        # Generate 3-7 initial entries
        num_entries = random.randint(3, 7)
        
        # Location-specific message templates
        location_messages = {
            'colony': [
                "Agricultural output exceeding projections this quarter.",
                "Population growth steady. Housing expansion approved.",
                "Mining operations proceeding on schedule.",
                "Trade relations with neighboring systems improving.",
                "Colonial infrastructure upgrade project initiated.",
                "Atmospheric processors maintaining optimal conditions.",
                "New settlers orientation program completed successfully.",
                "Local star radiation levels fluctuated today.",
                "Large planetary storm hit the colony.",
                "Resource extraction quotas met ahead of deadline."
            ],
            'space_station': [
                "Docking bay efficiency improved with new traffic protocols.",
                "Station rotation mechanics functioning within normal parameters.",
                "Merchant traffic up 15% compared to last cycle.",
                "Artificial gravity generators running smoothly.",
                "Recycling systems processing waste at maximum efficiency.",
                "How much further to Earth?",
                "Tourist accommodation bookings at capacity.",
                "Station-wide maintenance inspection scheduled for next week.",
                "Emergency response drill conducted successfully."
            ],
            'outpost': [
                "Long-range communications restored after equipment failure.",
                "Supply cache inventory updated and secured.",
                "Mineral survey scan detected ores.",
                "Perimeter sensors detecting normal background activity only.",
                "Generator fuel reserves adequate for six months operation.",
                "Weather monitoring equipment requires minor calibration.",
                "Emergency beacon tested and confirmed operational.",
                "Staff rotation schedule updated for next assignment period.",
                "Isolation protocols reviewed and updated."
            ],
            'gate': [
                "Corridor stability measurements within acceptable variance.",
                "Transit queue processing efficiently during peak hours.",
                "Gate energy consumption optimized for cost savings.",
                "Safety protocols updated following recent navigation incidents.",
                "Decontamination procedures enhanced per Federal directives.",
                "Navigation beacon alignment verified and corrected.",
                "Traffic control systems upgraded to latest specification.",
                "Emergency transit procedures drilled with all staff."
            ]
        }
        
        # Generic messages that work for any location
        generic_messages = [
            "Completed daily inspection rounds. All systems nominal.",
            "Shift report: No incidents to report. Operations running smoothly.",
            "Updated safety protocols as per latest regulations.",
            "Monthly evaluation complete. Performance metrics within acceptable range.",
            "Routine maintenance scheduled for next cycle.",
            "Quality control checks passed. Standards maintained.",
            "Staff briefing conducted. New procedures implemented.",
            "Equipment calibration complete. Ready for continued operations.",
            "Inventory audit finished. Supplies adequate for current needs.",
            "Training session completed for new personnel.",
            "All systems green. No anomalies detected.",
            "Environmental conditions stable.",
            "Security sweep complete. Perimeter secure.",
            "Communications array functioning normally.",
            "Power grid operating at optimal efficiency.",
            "Life support systems within normal parameters.",
            "Navigation beacons updated and verified.",
            "Emergency systems tested and confirmed operational.",
            "Radiation levels remain within safe limits.",
            "Structural integrity checks completed successfully.",
            "Another quiet day. Good for getting caught up on paperwork.",
            "Coffee supply running low. Need to add that to the next order.",
            "Met some interesting travelers today. Always enjoy hearing their stories.",
            "Long shift, but someone has to keep things running.",
            "Received a message from family today. Always brightens the mood.",
            "Weather patterns have been unusual lately. Hope it doesn't affect operations.",
            "New arrival seemed nervous. First time this far from home, I'd guess.",
            "Reminder to self: check the backup generators tomorrow.",
            "Quiet night shift. Perfect time for reading technical manuals.",
            "Looking forward to my next leave. Could use a change of scenery.",
            "Cargo manifests reviewed and approved for processing.",
            "Price negotiations concluded. Fair deal reached.",
            "Supply shipment arrived on schedule. Quality goods as usual.",
            "Market analysis complete. Prices holding steady.",
            "New trade agreement signed. Should improve local economy.",
            "Customs inspection finished. All documentation in order.",
            "Freight scheduling updated. Traffic flow optimized.",
            "Quality assessment of incoming goods complete. Standards met.",
            "Export permits processed. Shipments cleared for departure.",
            "Trade route security briefing attended. Safety first.",
            "Diagnostic complete. Minor adjustments made to improve efficiency.",
            "Software update installed. No compatibility issues detected.",
            "Preventive maintenance performed on critical systems.",
            "Backup systems tested. Failsafes functioning properly.",
            "Network connectivity stable. Data transmission normal.",
            "Sensor array recalibrated for optimal performance.",
            "Firmware update applied successfully. System restart completed.",
            "Performance metrics analyzed. Operating within design parameters.",
            "Component replacement scheduled for next maintenance window.",
            "System logs reviewed. No error conditions found."
        ]
        
        # Combine location-specific and generic messages
        specific_messages = location_messages.get(location_type, [])
        all_messages = specific_messages + generic_messages
        
        # Generate entries with random NPCs
        for _ in range(num_entries):
            # Generate NPC
            first_name, last_name = generate_npc_name()
            full_name = f"{first_name} {last_name}"
            
            # Determine wealth level (weighted toward middle values for more variety)
            wealth_level = random.choices(
                range(1, 11), 
                weights=[1, 2, 3, 4, 5, 5, 4, 3, 2, 1]  # Bell curve distribution
            )[0]
            
            # Get occupation based on location type and wealth
            occupation = get_occupation(location_type, wealth_level)
            
            # Create author name format variety
            name_format = random.choice([
                f"{full_name}, {occupation}",  # Full formal
                f"{first_name} {last_name}",   # Just name
                f"{occupation} {last_name}",   # Title + surname
                f"{first_name}, {occupation}"  # First name + title
            ])
            
            # Select message (favor location-specific if available)
            if specific_messages and random.random() < 0.6:  # 60% chance for location-specific
                message = random.choice(specific_messages)
            else:
                message = random.choice(generic_messages)
            
            # Random time in past 30 days
            days_ago = random.randint(1, 30)
            hours_ago = random.randint(0, 23)
            entry_time = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
            
            self.db.execute_query(
                '''INSERT INTO location_logs 
                   (location_id, author_id, author_name, message, posted_at, is_generated)
                   VALUES (?, ?, ?, ?, ?, 1)''',
                (location_id, 0, name_format, message, entry_time.isoformat())
            )

async def setup(bot):
    await bot.add_cog(LocationLogsCog(bot))