# cogs/galactic_news.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import json
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class GalacticNewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.news_delivery_loop.start()
        
    def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        self.news_delivery_loop.cancel()

    @tasks.loop(minutes=5)  # Check every 5 minutes for news to deliver
    async def news_delivery_loop(self):
        """Deliver scheduled news that has reached its delivery time"""
        try:
            # Get news ready to deliver
            pending_news = self.db.execute_query(
                """SELECT news_id, guild_id, news_type, title, description, 
                          location_id, delay_hours, event_data
                   FROM news_queue 
                   WHERE is_delivered = 0 AND scheduled_delivery <= datetime('now')
                   ORDER BY scheduled_delivery ASC""",
                fetch='all'
            )
            
            if not pending_news:
                return
                
            for news_item in pending_news:
                news_id, guild_id, news_type, title, description, location_id, delay_hours, event_data = news_item
                
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                    
                # Get galactic updates channel
                updates_channel_id = self.db.execute_query(
                    "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = ?",
                    (guild_id,),
                    fetch='one'
                )
                
                if not updates_channel_id or not updates_channel_id[0]:
                    continue
                    
                channel = guild.get_channel(updates_channel_id[0])
                if not channel:
                    continue
                
                # Create and send news embed
                embed = await self._create_news_embed(news_type, title, description, location_id, delay_hours, event_data)
                
                try:
                    await channel.send(embed=embed)
                    
                    # Mark as delivered
                    self.db.execute_query(
                        "UPDATE news_queue SET is_delivered = 1 WHERE news_id = ?",
                        (news_id,)
                    )
                    
                    print(f"📰 Delivered {news_type} news to {guild.name}: {title}")
                    
                except Exception as e:
                    print(f"❌ Failed to deliver news to {guild.name}: {e}")
                    
        except Exception as e:
            print(f"❌ Error in news delivery loop: {e}")

    @news_delivery_loop.before_loop
    async def before_news_delivery_loop(self):
        await self.bot.wait_until_ready()

    async def _create_news_embed(self, news_type: str, title: str, description: str, 
                                location_id: Optional[int], delay_hours: float, event_data: Optional[str]) -> discord.Embed:
        """Create a news embed with appropriate styling"""
        
        # Color scheme based on news type
        colors = {
            'corridor_shift': 0x4B0082,  # Purple
            'obituary': 0x000000,       # Black
            'major_event': 0xFF6600,    # Orange
            'fluff_news': 0x00BFFF,     # Deep sky blue
            'pirate_activity': 0x8B0000, # Dark red
            'corporate_news': 0x4169E1,  # Royal blue
            'discovery': 0x32CD32,       # Lime green
            'economic': 0xFFD700,        # Gold
            'admin_announcement': 0x14F4FF  # Earth Blue
        }
        
        color = colors.get(news_type, 0x2F4F4F)
        
        embed = discord.Embed(
            title=f"📰 {title}",
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Add news type indicator
        news_type_names = {
            'corridor_shift': '🌌 Infrastructure',
            'obituary': '💀 Obituary',
            'major_event': '⚡ Breaking News',
            'fluff_news': '📰 General News',
            'pirate_activity': '☠️ Security Alert',
            'corporate_news': '🏢 Corporate',
            'discovery': '🔬 Discovery',
            'economic': '💰 Economic',
            'admin_announcement': '🌐 Earth Government'  # Add this line
        }
        
        embed.set_author(name=news_type_names.get(news_type, '📰 News'))
        
        # Add location context if available
        if location_id:
            location_info = self.db.execute_query(
                "SELECT name, location_type, system_name, x_coord, y_coord FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )
            
            if location_info:
                location_name, loc_type, system_name, x_coord, y_coord = location_info
                embed.add_field(
                    name="📍 Location",
                    value=f"{location_name} ({loc_type.replace('_', ' ').title()})\n{system_name} System",
                    inline=True
                )
        
        # Add news delay information with immersive flavor
        if delay_hours > 0:
            delay_text = self._format_news_delay(delay_hours)
            embed.add_field(
                name="📡 Information Relay",
                value=delay_text,
                inline=True
            )
        else:
            embed.add_field(
                name="📡 Information Relay",
                value="Real-time from Central Hub",
                inline=True
            )
        
        # Add timestamp
        embed.set_footer(text="Galactic News Network • Inter-Solar Standard Time")
        
        return embed

    def _format_news_delay(self, delay_hours: float) -> str:
        """Format news delay in an immersive way"""
        if delay_hours < 1:
            minutes = int(delay_hours * 60)
            return f"Transmitted {minutes} minute{'s' if minutes != 1 else ''} ago"
        elif delay_hours < 24:
            hours = int(delay_hours)
            return f"Transmitted {hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(delay_hours / 24)
            return f"Transmitted {days} day{'s' if days != 1 else ''} ago via deep-space relay"

    def calculate_news_delay(self, location_id: Optional[int]) -> float:
        """Calculate news delay based on distance from galactic center"""
        if not location_id:
            return 0.0
            
        # Get location coordinates
        location_info = self.db.execute_query(
            "SELECT x_coord, y_coord FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return 0.0
            
        x_coord, y_coord = location_info
        
        # Calculate distance from galactic center (0, 0)
        distance = math.sqrt(x_coord**2 + y_coord**2)
        
        # News delay formula: 1 hour per 50 units of distance + some randomness
        base_delay = distance / 50.0
        random_factor = random.uniform(0.8, 1.2)  # ±20% variation
        
        delay_hours = base_delay * random_factor
        
        # Cap maximum delay at 48 hours
        return min(delay_hours, 48.0)

    async def queue_news(self, guild_id: int, news_type: str, title: str, description: str, 
                        location_id: Optional[int] = None, event_data: Optional[Dict] = None):
        """Queue news for delivery with appropriate delay"""
        
        delay_hours = self.calculate_news_delay(location_id)
        delivery_time = datetime.utcnow() + timedelta(hours=delay_hours)
        
        event_data_json = json.dumps(event_data) if event_data else None
        
        self.db.execute_query(
            """INSERT INTO news_queue 
               (guild_id, news_type, title, description, location_id, 
                scheduled_delivery, delay_hours, event_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, news_type, title, description, location_id, 
             delivery_time.isoformat(), delay_hours, event_data_json)
        )
        
        print(f"📰 Queued {news_type} news for {guild_id}: {title} (delay: {delay_hours:.1f}h)")

    async def post_corridor_shift_news(self, results: Dict, intensity: int):
        """Post news about corridor shifts to all configured guilds"""
        
        # Get all guilds with galactic updates channels
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            
            # Create news title and description
            if results.get('activated', 0) > 0 and results.get('deactivated', 0) > 0:
                title = "Major Corridor Network Restructure"
                description = f"Galactic infrastructure has undergone significant changes. {results['activated']} new routes have opened while {results['deactivated']} routes have collapsed. Navigation systems are updating routing algorithms."
            elif results.get('activated', 0) > 0:
                title = "New Corridor Routes Discovered"
                description = f"Survey teams report {results['activated']} new stable corridor{'s' if results['activated'] != 1 else ''} have been mapped and are now available for transit. These routes may provide new trade opportunities."
            elif results.get('deactivated', 0) > 0:
                title = "Corridor Network Disruption"
                description = f"Space-time instabilities have caused {results['deactivated']} corridor{'s' if results['deactivated'] != 1 else ''} to become unstable and close to traffic. Alternate routes are being analyzed."
            else:
                title = "Hyperspace Fluctuations Detected"
                description = "Deep space monitoring stations report minor fluctuations in the corridor network. No immediate impact on travel routes expected."
            
            # Add intensity context
            intensity_descriptions = {
                1: "Minor adjustments to network topology.",
                2: "Routine infrastructure maintenance effects.",
                3: "Significant network reconfiguration.",
                4: "Major galactic infrastructure event.",
                5: "Critical network-wide restructuring."
            }
            
            description += f" {intensity_descriptions.get(intensity, 'Network status assessment ongoing.')}"
            
            # Find a central location for realistic delay calculation
            central_location = self.db.execute_query(
                """SELECT location_id FROM locations 
                   WHERE location_type = 'space_station' 
                   AND (x_coord*x_coord + y_coord*y_coord) < 900 
                   ORDER BY (x_coord*x_coord + y_coord*y_coord) ASC 
                   LIMIT 1""",
                fetch='one'
            )
            
            location_id = central_location[0] if central_location else None
            
            await self.queue_news(guild_id, 'corridor_shift', title, description, location_id)

    async def post_obituary_news(self, character_name: str, location_id: int, cause: str = "unknown"):
        """Post obituary news for character deaths"""
        
        # Get location info
        location_info = self.db.execute_query(
            "SELECT name, location_type, system_name FROM locations WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )
        
        if not location_info:
            return
            
        location_name, location_type, system_name = location_info
        
        # Get all guilds with galactic updates channels
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            
            title = f"Spacer Lost in {system_name} System"
            
            obituary_templates = [
                f"Independent pilot {character_name} was reported missing and presumed lost near {location_name}. Local authorities are investigating the circumstances. Next of kin have been notified.",
                f"The independent vessel registry confirms the loss of pilot {character_name} in the vicinity of {location_name}. Search and rescue operations have been suspended.",
                f"Tragic news from {system_name} System: spacer {character_name} has been confirmed lost near {location_name}. The pilot's family requests privacy during this difficult time.",
            ]
            
            description = random.choice(obituary_templates)
            
            if cause and cause != "unknown":
                description += f" Preliminary reports suggest {cause} may have been a factor."
            
            await self.queue_news(guild_id, 'obituary', title, description, location_id)
    async def post_shift_change_news(self, shift_name: str, description: str):
        """Post news about a galactic schedule shift change."""
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )

        title = f"Galactic Schedule Shift Change: {shift_name}"

        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            # Use a central location for system-wide announcements to ensure consistent, short delays
            central_location = self.db.execute_query(
                "SELECT location_id FROM locations ORDER BY location_id ASC LIMIT 1",
                fetch='one'
            )
            location_id = central_location[0] if central_location else None
            
            await self.queue_news(guild_id, 'admin_announcement', title, description, location_id)
    async def generate_fluff_news(self):
        """Generate random fluff news to make the universe feel alive"""
        
        # Get all guilds with galactic updates channels
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        if not guilds_with_updates:
            return
            
        # Get random location for the news
        random_location = self.db.execute_query(
            "SELECT location_id, name, location_type, system_name, wealth_level FROM locations ORDER BY RANDOM() LIMIT 1",
            fetch='one'
        )
        
        if not random_location:
            return
            
        location_id, location_name, location_type, system_name, wealth_level = random_location
        
        # Generate news based on location type and wealth
        news_templates = {
            'colony': [
                ("Agricultural Export Success", f"{location_name} reports record harvest yields this season. Agricultural exports are expected to increase by {random.randint(15, 40)}% over the next quarter."),
                ("Infrastructure Development", f"Construction crews on {location_name} have completed a major infrastructure upgrade. The colony's administrative council reports improved efficiency in all sectors."),
                ("Population Milestone", f"{location_name} celebrates reaching a new population milestone. Mayor's office announces expanded civic services to accommodate continued growth."),
                ("Cultural Festival", f"The annual cultural festival on {location_name} concluded with record attendance. Visitors from across {system_name} System participated in traditional celebrations."),
            ],
            'space_station': [
                ("Trade Volume Increase", f"{location_name} Station reports a {random.randint(10, 30)}% increase in docking traffic this month. Station administrators attribute growth to improved trade route efficiency."),
                ("Technology Upgrade", f"Systems upgrade completed at {location_name} Station. The new infrastructure promises faster cargo processing and enhanced passenger amenities."),
                ("Diplomatic Meeting", f"Representatives from multiple corporations held negotiations at {location_name} Station this week. Details of the discussions remain confidential."),
                ("Station Expansion", f"Construction of new docking bays at {location_name} Station is ahead of schedule. The expansion will increase station capacity by 25%."),
            ],
            'outpost': [
                ("Supply Chain Update", f"{location_name} Outpost receives critical supply delivery after extended isolation. Station personnel report all systems operating normally."),
                ("Research Discovery", f"Scientists at {location_name} Outpost publish findings from their ongoing research. The work may have implications for deep space exploration."),
                ("Security Patrol", f"Routine security patrol from {location_name} Outpost reports all nearby space lanes clear. No unusual activity detected in the sector."),
                ("Equipment Maintenance", f"{location_name} Outpost completes scheduled maintenance cycle. All critical systems have been inspected and certified operational."),
            ],
            'gate': [
                ("Traffic Control Update", f"{location_name} Gate reports optimal corridor stability readings. Transit Control confirms all routing algorithms operating within normal parameters."),
                ("Maintenance Complete", f"Scheduled maintenance at {location_name} Gate completed successfully. No disruption to corridor traffic reported during the service window."),
                ("Navigation Beacon", f"Enhanced navigation beacon installation at {location_name} Gate improves approach guidance for incoming vessels."),
                ("Efficiency Metrics", f"{location_name} Gate posts new efficiency record with {random.randint(95, 99)}% successful transits this period. Traffic control cites improved protocols."),
            ]
        }
        
        # Select appropriate template based on location type
        available_templates = news_templates.get(location_type, news_templates['outpost'])
        title, description = random.choice(available_templates)
        
        # Add wealth-based variations
        if wealth_level >= 8:
            description += " The facility's prosperity continues to attract investment from across the sector."
        elif wealth_level <= 3:
            description += " Despite economic challenges, the facility maintains essential operations."
        
        # Queue news for all guilds
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            await self.queue_news(guild_id, 'fluff_news', title, description, location_id)

    @tasks.loop(hours=6)  # Generate fluff news every 6 hours
    async def fluff_news_generation(self):
        """Periodically generate fluff news"""
        if random.random() < 0.3:  # 30% chance every 6 hours
            await self.generate_fluff_news()

    @fluff_news_generation.before_loop
    async def before_fluff_news_generation(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(GalacticNewsCog(bot))