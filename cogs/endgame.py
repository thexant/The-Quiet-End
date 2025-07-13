# cogs/endgame.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

class EndgameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.endgame_task = None
        self.evacuation_warnings = {}  # Track pending evacuations
        
        # Apocalypse event types for variety
        self.apocalypse_events = [
            "stellar collapse", "quantum cascade failure", "dark energy surge",
            "dimensional rift", "cosmic storm", "gravitational anomaly",
            "spacetime fracture", "atomic decay cascade", "void incursion",
            "reality distortion", "entropy acceleration", "cosmic burnout"
        ]
        
        # Start background task if endgame is active
        self.bot.loop.create_task(self._initialize_endgame_on_startup())
    
    async def _initialize_endgame_on_startup(self):
        """Check if endgame should be running on startup"""
        await self.bot.wait_until_ready()
        
        # Check if there are any locations in the galaxy first
        location_count = self.db.execute_query(
            "SELECT COUNT(*) FROM locations",
            fetch='one'
        )[0]
        
        if location_count == 0:
            print("🌌 No locations found in galaxy - endgame system waiting for galaxy generation")
            return
        
        # Check if there's an active endgame
        endgame_config = self.db.execute_query(
            "SELECT * FROM endgame_config LIMIT 1",
            fetch='one'
        )
    
    def _parse_time_format(self, time_str: str) -> int:
        """Parse d/h/m format into minutes. Returns -1 if invalid."""
        try:
            if 'd' in time_str or 'h' in time_str or 'm' in time_str:
                # Parse d/h/m format
                days = hours = minutes = 0
                
                # Extract days
                if 'd' in time_str:
                    day_part = time_str.split('d')[0]
                    days = int(day_part) if day_part else 0
                    time_str = time_str.split('d', 1)[1] if len(time_str.split('d')) > 1 else ""
                
                # Extract hours  
                if 'h' in time_str:
                    hour_part = time_str.split('h')[0]
                    hours = int(hour_part) if hour_part else 0
                    time_str = time_str.split('h', 1)[1] if len(time_str.split('h')) > 1 else ""
                
                # Extract minutes
                if 'm' in time_str:
                    min_part = time_str.split('m')[0]
                    minutes = int(min_part) if min_part else 0
                
                total_minutes = (days * 24 * 60) + (hours * 60) + minutes
                return total_minutes if total_minutes >= 5 else -1  # Minimum 5 minutes
            else:
                # Try parsing as pure number (assume minutes)
                total_minutes = int(time_str)
                return total_minutes if total_minutes >= 5 else -1
        except (ValueError, IndexError):
            return -1
    
    # Admin command group
    endgame_group = app_commands.Group(name="endgame", description="Galactic apocalypse endgame system")
    
    @endgame_group.command(name="setup", description="Configure the galactic apocalypse endgame")
    @app_commands.describe(
        time_until="Time until endgame starts (format: XdYhZm, e.g., 1d2h30m)",
        length="Length of endgame (format: XdYhZm, default: 2d0h0m)"
    )
    async def setup_endgame(self, interaction: discord.Interaction, time_until: str, length: str = "2d0h0m"):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Parse time formats
        until_minutes = self._parse_time_format(time_until)
        length_minutes = self._parse_time_format(length)
        
        if until_minutes == -1:
            await interaction.response.send_message(
                "❌ Invalid 'time until' format. Use format like: 1d2h30m (minimum 5 minutes)",
                ephemeral=True
            )
            return
        
        if length_minutes == -1:
            await interaction.response.send_message(
                "❌ Invalid 'length' format. Use format like: 2d0h0m (minimum 5 minutes)",
                ephemeral=True
            )
            return
        
        # Calculate start time based on user's current time
        start_time = datetime.now() + timedelta(minutes=until_minutes)
        
        # Check if endgame already exists
        existing = self.db.execute_query("SELECT 1 FROM endgame_config LIMIT 1", fetch='one')
        if existing:
            await interaction.response.send_message(
                "❌ Endgame already configured. Use `/endgame cancel` first to reset.",
                ephemeral=True
            )
            return
        
        # Store configuration
        self.db.execute_query(
            """INSERT INTO endgame_config 
               (start_time, length_minutes, created_at, is_active) 
               VALUES (?, ?, ?, 1)""",
            (start_time.isoformat(), length_minutes, datetime.now().isoformat())
        )
        
        # Schedule endgame
        if self.endgame_task:
            self.endgame_task.cancel()
        
        self.endgame_task = self.bot.loop.create_task(
            self._wait_and_start_endgame(until_minutes * 60, length_minutes, start_time)
        )
        
        embed = discord.Embed(
            title="🌌 Galactic Apocalypse Configured",
            description="The countdown to galactic collapse has begun...",
            color=0xFF0000
        )
        embed.add_field(
            name="⏰ Starts At",
            value=f"<t:{int(start_time.timestamp())}:F>",
            inline=True
        )
        embed.add_field(
            name="⏳ Duration",
            value=f"{length_minutes // (24*60)}d {(length_minutes % (24*60)) // 60}h {length_minutes % 60}m",
            inline=True
        )
        embed.add_field(
            name="🎯 Countdown",
            value=f"<t:{int(start_time.timestamp())}:R>",
            inline=True
        )
        embed.set_footer(text="Use /endgame status to monitor the apocalypse countdown")
        
        await interaction.response.send_message(embed=embed)
        
        # Send initial warning to galactic news
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            await news_cog.queue_news(
                interaction.guild.id,
                'emergency_broadcast',
                'GALACTIC EMERGENCY PROTOCOL ACTIVATED',
                f'⚠️ **ATTENTION ALL CITIZENS** ⚠️\n\nThe Galactic Monitoring Authority has detected unprecedented cosmic anomalies throughout known space. All residents are advised to monitor emergency frequencies and prepare for potential system-wide disruptions.\n\n**Timeline:** Anomaly manifestation expected <t:{int(start_time.timestamp())}:R>\n**Advisory Level:** CRITICAL\n\nStay vigilant. Stay alive.',
                None
            )
    
    @endgame_group.command(name="status", description="Check endgame status")
    async def endgame_status(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        config = self.db.execute_query("SELECT * FROM endgame_config LIMIT 1", fetch='one')
        
        if not config:
            await interaction.response.send_message("No endgame configured.", ephemeral=True)
            return
        
        config_id, start_time_str, length_minutes, created_at, is_active = config
        start_time = datetime.fromisoformat(start_time_str)
        current_time = datetime.now()
        end_time = start_time + timedelta(minutes=length_minutes)
        
        embed = discord.Embed(title="🌌 Galactic Apocalypse Status", color=0xFF0000)
        
        if current_time < start_time:
            # Not started yet
            embed.add_field(name="📊 Status", value="⏰ Countdown Active", inline=True)
            embed.add_field(name="⏰ Starts", value=f"<t:{int(start_time.timestamp())}:R>", inline=True)
        elif current_time < end_time:
            # Active
            remaining = end_time - current_time
            embed.add_field(name="📊 Status", value="🔥 APOCALYPSE ACTIVE", inline=True)
            embed.add_field(name="⏳ Time Remaining", value=f"{remaining.days}d {remaining.seconds//3600}h {(remaining.seconds%3600)//60}m", inline=True)
            
            # Get location count
            location_count = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
            embed.add_field(name="🏠 Locations Remaining", value=str(location_count), inline=True)
        else:
            embed.add_field(name="📊 Status", value="💀 GAME OVER", inline=True)
        
        embed.add_field(name="⏱️ Duration", value=f"{length_minutes//(24*60)}d {(length_minutes%(24*60))//60}h {length_minutes%60}m", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @endgame_group.command(name="cancel", description="Cancel the endgame (emergency use only)")
    async def cancel_endgame(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Cancel running task
        if self.endgame_task:
            self.endgame_task.cancel()
            self.endgame_task = None
        
        # Clear configuration
        self.db.execute_query("DELETE FROM endgame_config")
        self.db.execute_query("DELETE FROM endgame_evacuations")
        
        embed = discord.Embed(
            title="🌌 Endgame Cancelled",
            description="The galactic apocalypse has been cancelled by administrative override.",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Send all-clear to galactic news
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            await news_cog.queue_news(
                interaction.guild.id,
                'admin_announcement',
                'EMERGENCY PROTOCOL DEACTIVATED',
                'The Galactic Monitoring Authority reports that cosmic anomalies have stabilized. Emergency protocols have been deactivated. Normal operations may resume.',
                None
            )
    
    async def _wait_and_start_endgame(self, delay_seconds: float, length_minutes: int, start_time: datetime):
        """Wait for the specified delay, then start endgame"""
        try:
            await asyncio.sleep(delay_seconds)
            await self._start_endgame_sequence(length_minutes, start_time)
        except asyncio.CancelledError:
            print("🌌 Endgame start cancelled")
    
    async def _start_endgame_sequence(self, length_minutes: int, start_time: datetime):
        """Begin the endgame apocalypse sequence"""
        print("🌌 GALACTIC APOCALYPSE BEGINNING...")
        
        # Send apocalypse start announcement
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            event_type = random.choice(self.apocalypse_events)
            await news_cog.queue_news(
                self.bot.guilds[0].id,  # Assume first guild for now
                'emergency_broadcast',
                'GALACTIC APOCALYPSE COMMENCED',
                f'🔥 **EMERGENCY BROADCAST** 🔥\n\nCatastrophic {event_type} detected across multiple sectors. Reality destabilization in progress. All locations experiencing critical system failures.\n\n**STATUS:** Galactic infrastructure collapse imminent\n**ADVISORY:** Seek immediate shelter and monitor emergency frequencies\n\nThis is not a drill. The end times have begun.',
                None
            )
        
        # Stop dynamic NPC spawning
        npc_cog = self.bot.get_cog('NPCCog')
        if npc_cog:
            # Set a flag to prevent new NPC spawns (we'll need to add this to NPCCog)
            npc_cog.endgame_active = True
        
        # Calculate destruction frequency
        total_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
        total_routes = self.db.execute_query("SELECT COUNT(*) FROM corridors", fetch='one')[0]
        
        if total_locations <= 1:
            print("🌌 Not enough locations for endgame")
            return
        
        # We want to leave 1 location at the end, so destroy (total_locations - 1)
        locations_to_destroy = total_locations - 1
        total_destruction_events = locations_to_destroy + total_routes
        
        # Calculate frequency: spread events across length_minutes
        if total_destruction_events > 0:
            frequency_minutes = length_minutes / total_destruction_events
            # Ensure minimum 2 minute spacing, maximum 30 minute spacing
            frequency_minutes = max(2, min(30, frequency_minutes))
        else:
            frequency_minutes = 10
        
        print(f"🌌 Endgame will destroy {total_destruction_events} elements over {length_minutes} minutes (every {frequency_minutes:.1f} min)")
        
        # Main destruction loop
        start_time_actual = datetime.now()
        end_time = start_time_actual + timedelta(minutes=length_minutes)
        last_destruction = start_time_actual
        
        while datetime.now() < end_time:
            try:
                current_time = datetime.now()
                
                # Check if it's time for next destruction
                if (current_time - last_destruction).total_seconds() >= (frequency_minutes * 60):
                    await self._execute_destruction_event()
                    last_destruction = current_time
                
                # Check remaining locations
                remaining_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
                if remaining_locations <= 1:
                    break
                
                # Sleep for 30 seconds before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                print(f"❌ Error in endgame sequence: {e}")
                await asyncio.sleep(60)
        
        # End the game
        await self._end_game()
    
    async def _execute_destruction_event(self):
        """Execute a single destruction event (route or location)"""
        # Check if there are any locations/corridors left
        location_count = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
        corridor_count = self.db.execute_query("SELECT COUNT(*) FROM corridors", fetch='one')[0]
        
        if location_count <= 1:
            print("🌌 Only one location remaining - ending endgame")
            await self._end_game()
            return
        
        # 60% chance to destroy route, 40% chance to destroy location
        if random.random() < 0.6 and corridor_count > 0:
            await self._destroy_random_route()
        elif location_count > 1:
            await self._destroy_random_location()
    
    async def _destroy_random_route(self):
        """Destroy a random corridor/route"""
        # Get a random active corridor
        corridors = self.db.execute_query(
            "SELECT corridor_id, name, origin_location, destination_location FROM corridors ORDER BY RANDOM() LIMIT 1",
            fetch='all'
        )
        
        if not corridors:
            return
        
        corridor_id, corridor_name, origin_id, dest_id = corridors[0]
        
        # Delete the corridor
        self.db.execute_query("DELETE FROM corridors WHERE corridor_id = ?", (corridor_id,))
        
        # Kill NPCs traveling through this corridor
        npc_cog = self.bot.get_cog('NPCCog')
        if npc_cog:
            await npc_cog.handle_corridor_collapse(corridor_id)
        
        # Get location names for news
        origin_name = self.db.execute_query("SELECT name FROM locations WHERE location_id = ?", (origin_id,), fetch='one')
        dest_name = self.db.execute_query("SELECT name FROM locations WHERE location_id = ?", (dest_id,), fetch='one')
        
        origin_name = origin_name[0] if origin_name else "Unknown"
        dest_name = dest_name[0] if dest_name else "Unknown"
        
        # 45% chance to broadcast news
        if random.random() < 0.45:
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                event_type = random.choice(self.apocalypse_events)
                await news_cog.queue_news(
                    self.bot.guilds[0].id,
                    'infrastructure_collapse',
                    'ROUTE COLLAPSE CONFIRMED',
                    f'💥 **INFRASTRUCTURE FAILURE**\n\nCatastrophic {event_type} has severed the {corridor_name} corridor linking {origin_name} and {dest_name}. The route is now permanently impassable.\n\n**STATUS:** Complete structural failure\n**CASUALTIES:** Multiple vessels reported missing\n**ADVISORY:** Seek alternate routes immediately',
                    origin_id
                )
        
        print(f"🌌 Destroyed corridor: {corridor_name} ({origin_name} <-> {dest_name})")
    
    async def _destroy_random_location(self):
        """Destroy a random location"""
        # Get all locations except the one we want to keep for the end
        # Prioritize non-colony locations first to keep colonies for last
        locations = self.db.execute_query(
            """SELECT location_id, name, location_type, channel_id 
               FROM locations 
               WHERE location_type != 'colony'
               ORDER BY RANDOM() LIMIT 1""",
            fetch='all'
        )
        
        # If no non-colony locations, get any location
        if not locations:
            total_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
            if total_locations <= 1:
                return  # Don't destroy the last location yet
            
            locations = self.db.execute_query(
                "SELECT location_id, name, location_type, channel_id FROM locations ORDER BY RANDOM() LIMIT 1",
                fetch='all'
            )
        
        if not locations:
            return
        
        location_id, location_name, location_type, channel_id = locations[0]
        
        # 5-minute evacuation warning
        await self._issue_evacuation_warning(location_id, location_name)
        
        # Wait 5 minutes
        await asyncio.sleep(300)
        
        # Check who's still in the location and kill them
        remaining_players = self.db.execute_query(
            "SELECT user_id, name FROM characters WHERE current_location = ?",
            (location_id,),
            fetch='all'
        )
        
        # Kill players who didn't evacuate
        for user_id, char_name in remaining_players:
            await self._kill_character(user_id, char_name, "atomic collapse")
        
        # Kill any dynamic NPCs at this location
        dynamic_npcs = self.db.execute_query(
            "SELECT npc_id, name, callsign FROM dynamic_npcs WHERE current_location = ? AND is_alive = 1",
            (location_id,),
            fetch='all'
        )
        
        for npc_id, npc_name, callsign in dynamic_npcs:
            self.db.execute_query("UPDATE dynamic_npcs SET is_alive = 0 WHERE npc_id = ?", (npc_id,))
            print(f"💀 NPC {npc_name} ({callsign}) died in location collapse")
        
        # Delete all related data with error handling
        try:
            self.db.execute_query("DELETE FROM corridors WHERE origin_location = ? OR destination_location = ?", 
                                 (location_id, location_id))
        except Exception as e:
            print(f"⚠️ Warning deleting corridors for location {location_id}: {e}")

        try:
            self.db.execute_query("DELETE FROM static_npcs WHERE location_id = ?", (location_id,))
        except Exception as e:
            print(f"⚠️ Warning deleting static NPCs for location {location_id}: {e}")

        try:
            self.db.execute_query("DELETE FROM shop_items WHERE location_id = ?", (location_id,))
        except Exception as e:
            print(f"⚠️ Warning deleting shop items for location {location_id}: {e}")

        try:
            self.db.execute_query("DELETE FROM jobs WHERE location_id = ?", (location_id,))
        except Exception as e:
            print(f"⚠️ Warning deleting jobs for location {location_id}: {e}")

        try:
            self.db.execute_query("DELETE FROM locations WHERE location_id = ?", (location_id,))
        except Exception as e:
            print(f"⚠️ Warning deleting location {location_id}: {e}")
        
        # Delete Discord channel
        if channel_id:
            guild = self.bot.guilds[0]  # Assume first guild
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.delete(reason="Galactic Apocalypse - Location destroyed")
                except:
                    pass
        
        # 45% chance to broadcast news
        if random.random() < 0.45:
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                event_type = random.choice(self.apocalypse_events)
                await news_cog.queue_news(
                    self.bot.guilds[0].id,
                    'location_destroyed',
                    'LOCATION ANNIHILATION CONFIRMED',
                    f'💀 **TOTAL SYSTEM FAILURE**\n\nThe {location_type.replace("_", " ")} {location_name} has been completely annihilated by {event_type}. All infrastructure, life support, and defensive systems have suffered catastrophic failure.\n\n**STATUS:** Total atomic collapse confirmed\n**SURVIVORS:** None detected\n**ADVISORY:** Location is permanently uninhabitable',
                    None
                )
        
        print(f"🌌 Destroyed location: {location_name} ({location_type})")
    
    async def _issue_evacuation_warning(self, location_id: int, location_name: str):
        """Issue evacuation warning to all players in a location"""
        # Get all players in this location
        players = self.db.execute_query(
            "SELECT user_id, name FROM characters WHERE current_location = ?",
            (location_id,),
            fetch='all'
        )
        
        if not players:
            return
        
        # Store evacuation warning
        evacuation_time = datetime.now() + timedelta(minutes=5)
        self.db.execute_query(
            """INSERT OR REPLACE INTO endgame_evacuations 
               (location_id, evacuation_deadline, warned_at) 
               VALUES (?, ?, ?)""",
            (location_id, evacuation_time.isoformat(), datetime.now().isoformat())
        )
        
        # Send warning to galactic news
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            await news_cog.queue_news(
                self.bot.guilds[0].id,
                'emergency_evacuation',
                f'IMMEDIATE EVACUATION - {location_name.upper()}',
                f'🚨 **IMMEDIATE EVACUATION REQUIRED** 🚨\n\n**LOCATION:** {location_name}\n**THREAT LEVEL:** CATASTROPHIC\n**TIME TO EVACUATION:** 5 MINUTES\n\nCritical system failure imminent. All personnel must evacuate immediately. Failure to comply will result in total loss of life.\n\n**THIS IS YOUR FINAL WARNING**',
                location_id
            )
        
        # Send direct warnings to players in the location channel
        guild = self.bot.guilds[0]
        location_info = self.db.execute_query("SELECT channel_id FROM locations WHERE location_id = ?", (location_id,), fetch='one')
        
        if location_info and location_info[0]:
            channel = guild.get_channel(location_info[0])
            if channel:
                embed = discord.Embed(
                    title="🚨 IMMEDIATE EVACUATION REQUIRED",
                    description=f"**{location_name.upper()}** - CRITICAL SYSTEM FAILURE IMMINENT",
                    color=0xFF0000
                )
                embed.add_field(name="⏰ Time to Evacuation", value="**5 MINUTES**", inline=True)
                embed.add_field(name="☠️ Threat Level", value="**FATAL**", inline=True)
                embed.add_field(name="🚀 Action Required", value="Use `/travel go` NOW", inline=False)
                embed.set_footer(text="Failure to evacuate will result in character death")
                
                try:
                    await channel.send("@everyone", embed=embed)
                except:
                    pass
        
        print(f"🚨 Issued evacuation warning for {location_name} ({len(players)} players)")
    
    async def _kill_character(self, user_id: int, char_name: str, cause: str):
        """Kill a character due to endgame event"""
        # Mark character as dead
        self.db.execute_query(
            "UPDATE characters SET hp = 0, status = 'dead', current_location = NULL WHERE user_id = ?",
            (user_id,)
        )
        
        # Send obituary to galactic news
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            await news_cog.post_character_obituary(char_name, None, cause)
        
        # Try to notify the player
        try:
            guild = self.bot.guilds[0]
            user = guild.get_member(user_id)
            if user:
                embed = discord.Embed(
                    title="💀 Character Death",
                    description=f"**{char_name}** has perished due to {cause}.",
                    color=0x000000
                )
                embed.add_field(
                    name="Cause of Death", 
                    value=cause.title(), 
                    inline=True
                )
                embed.add_field(
                    name="Game Status", 
                    value="Character permanently deceased", 
                    inline=True
                )
                embed.set_footer(text="A new galaxy awaits...")
                
                await user.send(embed=embed)
        except:
            pass
        
        print(f"💀 Killed character: {char_name} (cause: {cause})")
    
    async def _end_game(self):
        """End the game - final location destruction and game over"""
        # Get the last remaining location
        last_location = self.db.execute_query(
            "SELECT location_id, name, channel_id FROM locations LIMIT 1",
            fetch='one'
        )
        
        if last_location:
            location_id, location_name, channel_id = last_location
            
            # Send final broadcast
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                await news_cog.queue_news(
                    self.bot.guilds[0].id,
                    'final_broadcast',
                    'FINAL TRANSMISSION',
                    f'💀 **THIS IS THE END** 💀\n\nFrom the last beacon of civilization at {location_name}:\n\nThe cosmos has reclaimed what was once our domain. Reality itself unravels around us. To those who may find this message in whatever realm comes next - remember us. Remember our struggles, our triumphs, our hope.\n\nThe stars are going out.\n\nThis is our final transmission.\n\n...connection lost...',
                    location_id,
                    delay_hours=0  # Instant delivery
                )
            
            # Wait 1 minute
            await asyncio.sleep(60)
            
            # Kill anyone still there
            remaining_players = self.db.execute_query(
                "SELECT user_id, name FROM characters WHERE current_location = ?",
                (location_id,),
                fetch='all'
            )
            
            for user_id, char_name in remaining_players:
                await self._kill_character(user_id, char_name, "final cosmic collapse")
            
            # Delete the final location
            self.db.execute_query("DELETE FROM locations WHERE location_id = ?", (location_id,))
            
            # Delete the channel
            if channel_id:
                guild = self.bot.guilds[0]
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.delete(reason="Galactic Apocalypse - Final location destroyed")
                    except:
                        pass
        
        # Send GAME OVER message
        news_cog = self.bot.get_cog('GalacticNewsCog')
        if news_cog:
            # Get galactic news channel
            config = self.db.execute_query(
                "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = ?",
                (self.bot.guilds[0].id,),
                fetch='one'
            )
            
            if config and config[0]:
                news_channel = self.bot.guilds[0].get_channel(config[0])
                if news_channel:
                    embed = discord.Embed(
                        title="💀 GAME OVER 💀",
                        description="The galaxy has been consumed by cosmic forces beyond comprehension.",
                        color=0x000000
                    )
                    embed.add_field(
                        name="🌌 Final Status",
                        value="All locations destroyed\nAll life extinguished\nReality collapsed",
                        inline=True
                    )
                    embed.add_field(
                        name="🎮 Play Again",
                        value="Ready for a new beginning?\nUse `/galaxy generate` to create a new universe.",
                        inline=True
                    )
                    embed.set_footer(text="In the end, we are all stardust...")
                    
                    await news_channel.send(embed=embed)
        
        # Clean up endgame data
        self.db.execute_query("DELETE FROM endgame_config")
        self.db.execute_query("DELETE FROM endgame_evacuations")
        
        # Reset NPC spawning
        npc_cog = self.bot.get_cog('NPCCog')
        if npc_cog:
            npc_cog.endgame_active = False
        
        self.endgame_task = None
        print("🌌 GALACTIC APOCALYPSE COMPLETE - GAME OVER")

async def setup(bot):
    await bot.add_cog(EndgameCog(bot))