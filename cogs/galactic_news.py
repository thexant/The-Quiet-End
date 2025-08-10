# cogs/galactic_news.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from utils.datetime_utils import safe_datetime_parse

class GalacticNewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.news_delivery_loop.start()
        self.shift_change_monitor.start()
        self.fluff_news_generation.start()
        
    def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        self.news_delivery_loop.cancel()
        self.shift_change_monitor.cancel()
        self.fluff_news_generation.cancel()
        
    @tasks.loop(seconds=30)  # Check every 30 seconds for news to deliver
    async def news_delivery_loop(self):
        """Deliver scheduled news that has reached its delivery time"""
        try:
            # Get news ready to deliver
            pending_news = self.db.execute_query(
                """SELECT news_id, guild_id, news_type, title, description, 
                          location_id, delay_hours, event_data
                   FROM news_queue 
                   WHERE is_delivered = false AND scheduled_delivery <= NOW() + INTERVAL '1 second'
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
                    "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = %s",
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
                        "UPDATE news_queue SET is_delivered = true WHERE news_id = %s",
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
            'admin_announcement': 0x14F4FF,  # Earth Blue
            'bounty': 0xff6600,
            'location_establishment': 0x228B22  # Forest green
        }
        
        color = colors.get(news_type, 0x2F4F4F)
        
        embed = discord.Embed(
            title=f"📰 {title}",
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
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
            'economic': '📈 Economic',
            'admin_announcement': '🌐 Earth Government',
            'location_establishment': '🏗️ New Facility'
        }
        
        embed.set_author(name=news_type_names.get(news_type, '📰 News'))
        
        # Add location context if available
        if location_id:
            location_info = self.db.execute_query(
                "SELECT name, location_type, system_name, x_coord, y_coord FROM locations WHERE location_id = %s",
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
                value="Real-time from Central News Hub",
                inline=True
            )
        
        # Add timestamp
        embed.set_footer(text="Galactic News Network • Inter-Solar Standard Time")
        
        return embed

    def _format_news_delay(self, delay_hours: float) -> str:
        """Format news delay in an immersive way"""
        if delay_hours < 1:
            minutes = int(delay_hours * 60)
            return f"Signal Age: {minutes} minute{'s' if minutes != 1 else ''} old."
        elif delay_hours < 24:
            hours = int(delay_hours)
            return f"Signal Age: {hours} hour{'s' if hours != 1 else ''} old. Sent via deep-space relay"
        else:
            days = int(delay_hours / 24)
            return f"Transmitted {days} day{'s' if days != 1 else ''} old. Sent via deep-space relay"

    def calculate_news_delay(self, location_id: Optional[int]) -> float:
        """Calculate news delay based on distance from galactic center"""
        if not location_id:
            return 0.0
            
        # Get location coordinates
        location_info = self.db.execute_query(
            "SELECT x_coord, y_coord FROM locations WHERE location_id = %s",
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
        delivery_time = datetime.now(timezone.utc) + timedelta(hours=delay_hours)
        
        event_data_json = json.dumps(event_data) if event_data else None
        
        self.db.execute_query(
            """INSERT INTO news_queue 
               (guild_id, news_type, title, description, location_id, 
                scheduled_delivery, delay_hours, event_data)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (guild_id, news_type, title, description, location_id, 
             delivery_time, delay_hours, event_data_json)
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
            
            # Enhanced thematic news generation with destination shuffling
            destinations_changed = results.get('destinations_changed', 0)
            
            if results.get('activated', 0) > 0 and results.get('deactivated', 0) > 0:
                title = "🌌 GALACTIC INFRASTRUCTURE ALERT"
                description = (
                    f"**CORRIDOR NETWORK RECONFIGURATION IN PROGRESS**\n\n"
                    f"Hyperspace monitoring stations report major shifts in the corridor network. "
                    f"Navigation computers across the galaxy are updating their databases as {results['activated']} "
                    f"new corridors have stabilized while {results['deactivated']} existing routes "
                    f"have collapsed into atomic instability."
                )
                if destinations_changed > 0:
                    description += (
                        f" Additionally, {destinations_changed} active corridor{'s' if destinations_changed != 1 else ''} "
                        f"have been redirected to entirely different destinations."
                    )
                description += "\n\nAll vessels are advised to verify route availability before departure."
            elif destinations_changed > 0 and results.get('activated', 0) == 0 and results.get('deactivated', 0) == 0:
                title = "🔀 CORRIDOR DESTINATION SHUFFLE"
                description = (
                    f"**NAVIGATION SYSTEM UPDATE REQUIRED**\n\n"
                    f"Quantum hyperspace fluctuations have caused {destinations_changed} active corridor{'s' if destinations_changed != 1 else ''} "
                    f"to redirect to entirely different destinations. While the corridors remain stable and traversable, "
                    f"they now lead to completely different locations than before.\n\n"
                    f"All pilots must update their navigation computers immediately before attempting travel."
                )
            elif results.get('activated', 0) > 0:
                title = "📡 NEW HYPERSPACE ROUTES DETECTED"
                description = (
                    f"**EXPLORATION OPPORTUNITY ANNOUNCEMENT**\n\n"
                    f"Deep space survey teams confirm the stabilization of {results['activated']} previously "
                    f"unmapped corridor{'s' if results['activated'] != 1 else ''}. These newly accessible "
                    f"routes are now cleared for civilian traffic following successful probe deployments."
                )
                if destinations_changed > 0:
                    description += (
                        f" Simultaneously, {destinations_changed} existing corridor{'s' if destinations_changed != 1 else ''} "
                        f"have been redirected to new endpoints."
                    )
                description += "\n\nAdventurous pilots may find new opportunities in previously unreachable sectors."
            elif results.get('deactivated', 0) > 0:
                title = "⚠️ HYPERSPACE DISRUPTION WARNING"
                description = (
                    f"**CRITICAL NAVIGATION ADVISORY**\n\n"
                    f"Catastrophic corridor destabilization has rendered {results['deactivated']} "
                    f"corridor{'s' if results['deactivated'] != 1 else ''} impassable. Emergency beacons have been "
                    f"deployed to warn approaching vessels."
                )
                if destinations_changed > 0:
                    description += (
                        f" Additionally, {destinations_changed} surviving corridor{'s' if destinations_changed != 1 else ''} "
                        f"have been redirected to different destinations."
                    )
                description += (
                    f" Navigation systems galaxy-wide are recalculating optimal routes.\n\n"
                    f"Pilots are urged to check alternate paths before attempting travel."
                )
            else:
                title = "🌊 HYPERSPACE FLUCTUATION REPORT"
                description = (
                    "**ROUTINE MONITORING UPDATE**\n\n"
                    "Minor variations detected in the corridor network. No immediate major impact "
                    "on established trade routes. Continue normal operations while monitoring for updates."
                )
            
            # Add intensity-based urgency
            urgency_tags = {
                1: "\n\n`Classification: Routine Maintenance`",
                2: "\n\n`Classification: Standard Infrastructure Update`",
                3: "\n\n`Classification: Significant Network Event`",
                4: "\n\n`Classification: Major Infrastructure Alert`",
                5: "\n\n`Classification: CRITICAL NETWORK EMERGENCY`"
            }
            
            description += urgency_tags.get(intensity, "\n\n`Classification: Unspecified`")
            
            # Add timestamp
            timestamp = datetime.now(timezone.utc).strftime("%H:%M IST")
            description += f"\n\n*Broadcast Time: {timestamp}*"
            
            # Find a central location for delay calculation
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
            
    @tasks.loop(minutes=5)  # Check every 5 minutes for shift changes
    async def shift_change_monitor(self):
        """Monitor for galactic shift changes"""
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            
            # Get last shift check time from database
            last_check = self.db.execute_query(
                "SELECT last_shift_check, current_shift FROM galaxy_info WHERE galaxy_id = 1",
                fetch='one'
            )
            
            if last_check:
                last_check_time_str, current_stored_shift = last_check
                if last_check_time_str and isinstance(last_check_time_str, str) and last_check_time_str.strip():
                    try:
                        last_check_time = safe_datetime_parse(last_check_time_str)
                    except (ValueError, TypeError):
                        last_check_time = None
                else:
                    last_check_time = None
            else:
                last_check_time = None
                current_stored_shift = None
            
            # Check for shift change
            current_time = time_system.calculate_current_ingame_time()
            if current_time:
                shift_name, shift_period = time_system.get_current_shift()
                
                if current_stored_shift != shift_period:
                    # Shift change detected!
                    print(f"🔄 Shift change detected: {current_stored_shift} → {shift_period}")
                    
                    # Post shift change news
                    await self.post_shift_change_news(shift_period, shift_name, current_time)
                    
                    # Update stored shift
                    self.db.execute_query(
                        "UPDATE galaxy_info SET last_shift_check = %s, current_shift = %s WHERE galaxy_id = 1",
                        (current_time.isoformat(), shift_period)
                    )
                    
                    print(f"📰 Posted shift change announcement: {shift_name}")
                else:
                    # Just update check time
                    self.db.execute_query(
                        "UPDATE galaxy_info SET last_shift_check = %s WHERE galaxy_id = 1",
                        (current_time.isoformat(),)
                    )
            
        except Exception as e:
            print(f"❌ Error in shift change monitor: {e}")

    @shift_change_monitor.before_loop
    async def before_shift_change_monitor(self):
        await self.bot.wait_until_ready()

    async def post_shift_change_news(self, new_shift: str, shift_name: str, current_time: datetime):
            """Post news about galactic shift changes"""
            
            # Get all guilds with galactic updates channels
            guilds_with_updates = self.db.execute_query(
                "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
                fetch='all'
            )
            
            for guild_tuple in guilds_with_updates:
                guild_id = guild_tuple[0]
                
                # Format date for announcement
                today_date = current_time.strftime("%d-%m-%Y")

                # Create shift-specific announcements
                shift_announcements = {
                    "morning": {
                        "title": "🌅 Morning Shift Begins",
                        "description": f"**Today's Date:** {today_date} ISST\n\nColony work shifts are beginning across human space. Facility operations are transitioning to day protocols. Increased activity expected on major trade routes."
                    },
                    "day": {
                        "title": "☀️ Day Shift Active",
                        "description": "Peak operational hours are now in effect. Maximum traffic reported on all corridor networks. Commercial and industrial activities at full capacity across the galaxy."
                    },
                    "evening": {
                        "title": "🌆 Evening Shift Transition",
                        "description": "Systems are transitioning to night operations. Reduced traffic expected as colonies shift to evening protocols. Non-essential services moving to standby."
                    },
                    "night": {
                        "title": "🌙 Night Shift Operations",
                        "description": "Minimal activity period now in effect. Most colonies operating on standby protocols. Emergency services remain active. Reduced corridor monitoring in low population areas."
                    }
                }
                
                announcement = shift_announcements.get(new_shift, {
                    "title": "⏰ Shift Change",
                    "description": "Galactic operations shift change in progress."
                })
                
                title = announcement["title"]
                description = announcement["description"]
                
                # Add operational impacts
                if new_shift == "day":
                    description += " Job opportunities and trade activities are at peak availability."
                elif new_shift == "night":
                    description += " Limited job postings and reduced commercial activity during this period."
                else:
                    description += " Moderate levels of commercial and employment opportunities available."
                
                await self.queue_news(guild_id, 'admin_announcement', title, description, None)
    async def post_obituary_news(self, character_name: str, location_id: int, cause: str = "unknown"):
        """Post obituary news for character deaths"""
        
        # Get location info
        location_info = self.db.execute_query(
            "SELECT name, location_type, system_name FROM locations WHERE location_id = %s",
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
                f"We regret to report the recovery of remains belonging to {character_name} near {location_name} in {system_name} system. The remains were identified by genetic analysis, as other means of identification were determined impossible.",
            ]
            
            description = random.choice(obituary_templates)
            
            if cause and cause != "unknown":
                description += f" Preliminary reports suggest {cause} may have been a factor."
            
            await self.queue_news(guild_id, 'obituary', title, description, location_id)

    async def post_character_obituary(self, character_name: str, location_id: int, cause: str = "unknown"):
        """Compatibility method for NPC death calls - redirects to post_obituary_news"""
        await self.post_obituary_news(character_name, location_id, cause)

    async def post_location_destruction_news(self, location_name: str, casualty_count: int, nearest_location_id: int):
        """Post news about location destruction events"""
        
        # Get all guilds with galactic updates channels
        guilds_with_updates = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE galactic_updates_channel_id IS NOT NULL",
            fetch='all'
        )
        
        for guild_tuple in guilds_with_updates:
            guild_id = guild_tuple[0]
            
            # Create different news variants for variety
            import random
            
            news_variants = [
                {
                    "title": f"BREAKING: {location_name} Completely Destroyed",
                    "description": f"In a catastrophic event, {location_name} has been completely annihilated. "
                                  f"All {casualty_count:,} inhabitants are confirmed lost. "
                                  f"The cause of the destruction remains unknown. Rescue operations are impossible."
                },
                {
                    "title": f"DISASTER: {location_name} Wiped From Galaxy Maps",
                    "description": f"Tragic news reaches us as {location_name} has been utterly destroyed in what appears to be "
                                  f"a total structural collapse. Emergency services report {casualty_count:,} casualties. "
                                  f"The location has been removed from all navigation systems."
                },
                {
                    "title": f"CATASTROPHE: {location_name} Lost With All Hands",
                    "description": f"We regret to report the complete destruction of {location_name}. "
                                  f"No survivors have been found among the {casualty_count:,} registered inhabitants. "
                                  f"Space traffic controllers have marked the coordinates as a no-fly zone."
                }
            ]
            
            selected_news = random.choice(news_variants)
            
            await self.queue_news(guild_id, 'major_event', selected_news['title'], 
                                selected_news['description'], nearest_location_id)

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

    @tasks.loop(hours=3)  # Generate fluff news every 6 hours
    async def fluff_news_generation(self):
        """Periodically generate fluff news"""
        if random.random() < 0.25:  # 30% chance every 2 hours
            await self.generate_fluff_news()

    @fluff_news_generation.before_loop
    async def before_fluff_news_generation(self):
        await self.bot.wait_until_ready()

    # Test/Verification Commands
    @app_commands.command(name="test_news", description="Test galactic news system (Admin only)")
    @app_commands.describe(
        news_type="Type of news to test",
        test_data="Test data for the news event"
    )
    async def test_news_system(self, interaction: discord.Interaction, 
                              news_type: str, test_data: str = "Test data"):
        """Test the galactic news system with different event types"""
        
        # Check if user is admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            if news_type.lower() == "npc_death":
                # Test NPC death news
                test_location = self.db.execute_query(
                    "SELECT location_id FROM locations ORDER BY RANDOM() LIMIT 1",
                    fetch='one'
                )
                if test_location:
                    await self.post_character_obituary("Test NPC", test_location[0], "system test")
                    await interaction.followup.send("✅ NPC death news queued successfully", ephemeral=True)
                else:
                    await interaction.followup.send("❌ No locations found for testing", ephemeral=True)
                    
            elif news_type.lower() == "location_creation":
                # Test location establishment news
                test_location = self.db.execute_query(
                    "SELECT location_id, name FROM locations ORDER BY RANDOM() LIMIT 1",
                    fetch='one'
                )
                if test_location:
                    location_id, location_name = test_location
                    await self.queue_news(
                        interaction.guild.id, 
                        'location_establishment',
                        f"New Facility: Test {location_name}",
                        f"A new test facility has been established near {location_name}. This is a system verification test.",
                        location_id
                    )
                    await interaction.followup.send("✅ Location creation news queued successfully", ephemeral=True)
                else:
                    await interaction.followup.send("❌ No locations found for testing", ephemeral=True)
                    
            elif news_type.lower() == "location_destruction":
                # Test location destruction news
                test_location = self.db.execute_query(
                    "SELECT location_id FROM locations ORDER BY RANDOM() LIMIT 1",
                    fetch='one'
                )
                if test_location:
                    await self.post_location_destruction_news(
                        "Test Location", 1000, test_location[0]
                    )
                    await interaction.followup.send("✅ Location destruction news queued successfully", ephemeral=True)
                else:
                    await interaction.followup.send("❌ No locations found for testing", ephemeral=True)
                    
            else:
                await interaction.followup.send(
                    "❌ Invalid news type. Use: npc_death, location_creation, or location_destruction", 
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(f"❌ Test failed: {str(e)}", ephemeral=True)

    @app_commands.command(name="news_queue_status", description="Check news queue status (Admin only)")
    async def check_news_queue(self, interaction: discord.Interaction):
        """Check the current status of the news queue"""
        
        # Check if user is admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
            
        # Get queue statistics
        pending_count = self.db.execute_query(
            "SELECT COUNT(*) FROM news_queue WHERE guild_id = %s AND is_delivered = false",
            (interaction.guild.id,),
            fetch='one'
        )[0]
        
        delivered_count = self.db.execute_query(
            "SELECT COUNT(*) FROM news_queue WHERE guild_id = %s AND is_delivered = true",  
            (interaction.guild.id,),
            fetch='one'
        )[0]
        
        # Get recent news by type
        recent_by_type = self.db.execute_query(
            """SELECT news_type, COUNT(*) 
               FROM news_queue 
               WHERE guild_id = %s AND created_at > NOW() - INTERVAL '24 hours'
               GROUP BY news_type""",
            (interaction.guild.id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title="📰 News Queue Status",
            description="Current status of the galactic news system",
            color=0x00BFFF
        )
        
        embed.add_field(
            name="📋 Queue Status",
            value=f"Pending: {pending_count}\nDelivered: {delivered_count}",
            inline=True
        )
        
        if recent_by_type:
            type_summary = "\n".join([f"{news_type}: {count}" for news_type, count in recent_by_type])
            embed.add_field(
                name="📊 Last 24 Hours by Type",
                value=type_summary,
                inline=True
            )
        
        embed.add_field(
            name="🔧 System Status",
            value=f"News Loop: {'✅ Running' if not self.news_delivery_loop.is_being_cancelled() else '❌ Stopped'}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear_news_queue", description="Clear all pending news from the queue (Admin only)")
    async def clear_news_queue(self, interaction: discord.Interaction):
        """Clear all pending news from the queue"""
        
        # Check if user is admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get count of pending news before clearing
            pending_count = self.db.execute_query(
                "SELECT COUNT(*) FROM news_queue WHERE guild_id = %s AND is_delivered = false",
                (interaction.guild.id,),
                fetch='one'
            )[0]
            
            if pending_count == 0:
                await interaction.followup.send("ℹ️ No pending news in queue to clear.", ephemeral=True)
                return
            
            # Clear all pending news for this guild
            self.db.execute_query(
                "DELETE FROM news_queue WHERE guild_id = %s AND is_delivered = false",
                (interaction.guild.id,)
            )
            
            await interaction.followup.send(
                f"✅ Successfully cleared {pending_count} pending news item{'s' if pending_count != 1 else ''} from the queue.",
                ephemeral=True
            )
            
            print(f"🗑️ Admin {interaction.user.name} cleared {pending_count} pending news items for guild {interaction.guild.name}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to clear news queue: {str(e)}", ephemeral=True)
            print(f"❌ Error clearing news queue: {e}")

async def setup(bot):
    await bot.add_cog(GalacticNewsCog(bot))