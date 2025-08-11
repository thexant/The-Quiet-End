"""
Web Map Cog for Discord RPG Bot
Provides a dynamic web interface for the game map and wiki
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from aiohttp import web
import asyncio
import json
from datetime import datetime, timedelta
import os
from typing import Optional, Dict, Any, List
import socket
import traceback
from utils.time_system import TimeSystem
from config import WEBMAP_CONFIG


class WebMapCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.time_system = TimeSystem(bot)
        self.app = None
        self.runner = None
        self.site = None
        self.is_running = False
        self.host = '0.0.0.0'
        self.port = 8090
        self.external_ip = None
        self.domain = None
        self.https_proxy = False  # Force HTTPS URLs when behind proxy
        
        # Cache for performance
        self.cache = {
            'locations': {},
            'corridors': [],
            'players': {},
            'npcs': {},
            'news': [],
            'galaxy_info': {},
            'current_time': None,
            'last_update': None
        }
        
        # Update interval
        self.update_cache.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_cache.cancel()
        if self.is_running:
            asyncio.create_task(self.stop_webmap())
    
    async def autostart_webmap(self):
        """Auto-start the web map if configured to do so"""
        if not WEBMAP_CONFIG.get('auto_start', False):
            return
            
        # Wait for the configured delay
        delay = WEBMAP_CONFIG.get('auto_start_time', 30)
        await asyncio.sleep(delay)
        
        # Start the web map with configured settings
        host = WEBMAP_CONFIG.get('auto_start_host', '0.0.0.0')
        port = WEBMAP_CONFIG.get('auto_start_port', 8090)
        domain = WEBMAP_CONFIG.get('auto_start_domain', None)
        https_proxy = WEBMAP_CONFIG.get('auto_start_https_proxy', False)
        
        try:
            await self._start_webmap_internal(host, port, domain, https_proxy)
            print(f"✅ Web map auto-started on {host}:{port}")
            if domain:
                print(f"🌐 Domain: {domain}")
        except Exception as e:
            print(f"❌ Failed to auto-start web map: {e}")
            print(f"Web map auto-start error: {traceback.format_exc()}")
    
    @tasks.loop(seconds=5)  # Update cache every 5 seconds
    async def update_cache(self):
        """Update cached data for the web map"""
        try:
            await self._refresh_cache()
        except Exception as e:
            print(f"Error updating web map cache: {e}")
    
    @update_cache.before_loop
    async def before_update_cache(self):
        await self.bot.wait_until_ready()
    
    async def _refresh_cache(self):
        """Refresh all cached data"""
        # Get locations with explicit column names, ordered by type priority then by name for consistency
        locations_data = self.db.execute_webmap_query(
            """SELECT l.location_id, l.name, l.location_type, l.x_coordinate, l.y_coordinate,
                      l.system_name, l.wealth_level, l.population, l.description, l.faction,
                      lo.owner_id, lo.docking_fee, c.name as owner_name
               FROM locations l
               LEFT JOIN location_ownership lo ON l.location_id = lo.location_id
               LEFT JOIN characters c ON lo.owner_id = c.user_id
               ORDER BY 
                   CASE l.location_type 
                       WHEN 'corridor' THEN 1
                       WHEN 'gate' THEN 2
                       WHEN 'outpost' THEN 3
                       WHEN 'space_station' THEN 4
                       WHEN 'colony' THEN 5
                       ELSE 6
                   END,
                   l.name ASC""",
            fetch='all'
        )
        
        locations = {}
        for loc in locations_data:
            try:
                loc_id = loc.get('location_id') if loc.get('location_id') is not None else 0
                if loc_id == 0:  # Skip invalid location IDs
                    print(f"Skipping invalid location with ID 0: {loc}")
                    continue
                    
                locations[loc_id] = {
                    'id': loc_id,
                    'name': loc.get('name'),
                    'type': loc.get('location_type'),
                    'x': float(loc.get('x_coordinate')) if loc.get('x_coordinate') is not None else 0.0,
                    'y': float(loc.get('y_coordinate')) if loc.get('y_coordinate') is not None else 0.0,
                    'system': loc.get('system_name'),
                    'wealth': loc.get('wealth_level'),
                    'population': loc.get('population'),
                    'description': loc.get('description'),
                    'faction': loc.get('faction') if loc.get('faction') else 'Independent',
                    'owner_id': loc.get('owner_id'),
                    'owner_name': loc.get('owner_name'),
                    'docking_fee': loc.get('docking_fee') if loc.get('docking_fee') else 0,
                    'stability': 75
                }
            except Exception as e:
                print(f"Error processing location {loc_id if 'loc_id' in locals() else 'unknown'}: {e}")
                print(f"Location data: {loc}")
                continue
        
        # Get corridors
        corridors_data = self.db.execute_webmap_query(
            """SELECT corridor_id, origin_location, destination_location, 
                      name, travel_time, danger_level, corridor_type
               FROM corridors
               WHERE is_active = true""",
            fetch='all'
        )
        
        corridors = []
        for corr in corridors_data:
            corridors.append({
                'id': corr.get('corridor_id'),
                'origin': corr.get('origin_location'),
                'destination': corr.get('destination_location'),
                'name': corr.get('name'),
                'travel_time': corr.get('travel_time'),
                'danger_level': corr.get('danger_level'),
                'corridor_type': corr.get('corridor_type')
            })
        
        # Get active players - Only show currently logged in characters
        players_data = self.db.execute_webmap_query(
            """SELECT c.user_id, c.name, c.current_location, c.money,
                      t.corridor_id, t.start_time, t.end_time,
                      l.name as location_name, l.x_coordinate, l.y_coordinate,
                      c.level, c.experience
               FROM characters c
               LEFT JOIN travel_sessions t ON c.user_id = t.user_id AND t.status = 'traveling'
               LEFT JOIN locations l ON c.current_location = l.location_id
               WHERE c.is_logged_in = true""",
            fetch='all'
        )
        
        players = {}
        for player in players_data:
            try:
                user_id = player.get('user_id')
                players[user_id] = {
                    'id': user_id,
                    'name': player.get('name'),
                    'location': player.get('current_location'),
                    'location_name': player.get('location_name'),
                    'x': float(player.get('x_coordinate')) if player.get('x_coordinate') is not None else 0.0,
                    'y': float(player.get('y_coordinate')) if player.get('y_coordinate') is not None else 0.0,
                    'credits': player.get('money'),
                    'traveling': player.get('corridor_id') is not None,
                    'corridor_id': player.get('corridor_id'),
                    'travel_progress': self._calculate_travel_progress(player.get('start_time'), player.get('end_time')) if player.get('corridor_id') else 0,
                    'level': player.get('level') if player.get('level') else 1,
                    'experience': player.get('experience') if player.get('experience') else 0
                }
            except Exception as e:
                print(f"Error parsing player {user_id if 'user_id' in locals() else 'unknown'}: {e}")
                continue
        
        # Get dynamic NPCs
        npcs_data = self.db.execute_webmap_query(
            """SELECT n.npc_id, n.name, n.callsign, n.current_location,
                      n.destination_location, n.travel_start_time, n.travel_duration,
                      n.alignment, n.is_alive, l.name as location_name,
                      l.x_coordinate, l.y_coordinate
               FROM dynamic_npcs n
               LEFT JOIN locations l ON n.current_location = l.location_id
               WHERE n.is_alive = true""",
            fetch='all'
        )
        
        npcs = {}
        for npc in npcs_data:
            try:
                npc_id = npc.get('npc_id')
                npcs[npc_id] = {
                    'id': npc_id,
                    'name': npc.get('name'),
                    'callsign': npc.get('callsign'),
                    'location': npc.get('current_location'),
                    'location_name': npc.get('location_name'),
                    'x': float(npc.get('x_coordinate')) if npc.get('x_coordinate') is not None else 0.0,
                    'y': float(npc.get('y_coordinate')) if npc.get('y_coordinate') is not None else 0.0,
                    'destination': npc.get('destination_location'),
                    'traveling': npc.get('destination_location') is not None,
                    'travel_progress': self._calculate_npc_travel_progress(npc.get('travel_start_time'), npc.get('travel_duration')) if npc.get('destination_location') else 0,
                    'alignment': npc.get('alignment')
                }
            except Exception as e:
                print(f"Error parsing NPC {npc_id if 'npc_id' in locals() else 'unknown'}: {e}")
                continue
        
        # Get recent news from GalacticNewsCog's news_queue table
        news_data = self.db.execute_webmap_query(
            """SELECT title, description, location_id, scheduled_delivery, news_type
               FROM news_queue
               WHERE is_delivered = true
               ORDER BY scheduled_delivery DESC
               LIMIT 20""",
            fetch='all'
        )
        
        news = []
        for item in news_data:
            news.append({
                'title': item.get('title'),
                'content': item.get('description'),
                'location_id': item.get('location_id'),
                'timestamp': item.get('scheduled_delivery'),
                'news_type': item.get('news_type'),
                'game_date': self._convert_to_game_date(item.get('scheduled_delivery'))
            })
        
        # Get galaxy info and current time
        galaxy_info_data = self.time_system.get_galaxy_info()
        galaxy_info = {}
        current_time = None
        
        if galaxy_info_data:
            galaxy_name, start_date, time_scale, time_started_at, created_at, is_paused, time_paused_at, current_ingame, is_manually_paused = galaxy_info_data
            current_time_obj = self.time_system.calculate_current_ingame_time()
            
            galaxy_info = {
                'name': galaxy_name,
                'start_date': start_date,
                'time_scale': time_scale,
                'is_paused': is_paused
            }
            
            if current_time_obj:
                current_time = self.time_system.format_ingame_datetime(current_time_obj)
        
        # Update cache with timestamp
        self.cache = {
            'locations': locations,
            'corridors': corridors,
            'players': players,
            'npcs': npcs,
            'news': news,
            'galaxy_info': galaxy_info,
            'current_time': current_time,
            'last_update': datetime.now().isoformat()
        }
    
    def _calculate_travel_progress(self, start_time, end_time):
        """Calculate travel progress as percentage"""
        if not start_time or not end_time:
            return 0
        
        try:
            # Handle both string and datetime objects
            if isinstance(start_time, str):
                start = safe_datetime_parse(start_time.replace('Z', '+00:00'))
            else:
                start = start_time
                
            if isinstance(end_time, str):
                end = safe_datetime_parse(end_time.replace('Z', '+00:00'))
            else:
                end = end_time
                
            now = datetime.now()
            
            # If timezone-aware, make now timezone-aware too
            if start.tzinfo is not None:
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)
            
            total_duration = (end - start).total_seconds()
            elapsed = (now - start).total_seconds()
            
            if total_duration <= 0:
                return 100  # Already arrived
            
            progress = (elapsed / total_duration) * 100
            return min(max(progress, 0), 100)
        except Exception as e:
            print(f"Error calculating travel progress: {e}")
            return 0
    
    def _calculate_npc_travel_progress(self, start_time, duration):
        """Calculate NPC travel progress"""
        if not start_time or not duration:
            return 0
        
        try:
            if not isinstance(start_time, str):
                return 0
            start = safe_datetime_parse(start_time)
            now = datetime.now()
            elapsed = (now - start).total_seconds()
            
            progress = (elapsed / duration) * 100
            return min(max(progress, 0), 100)
        except:
            return 0
    
    def _convert_to_game_date(self, timestamp):
        """Convert timestamp to proper in-game date, handling mixed formats"""
        try:
            # Parse the provided timestamp
            if isinstance(timestamp, str):
                dt = safe_datetime_parse(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            
            # Check if this timestamp is already in game format or real format
            # Game years are typically 2500-4000, real years are 2020-2030
            if dt.year >= 2500 and dt.year <= 4000:
                # Already in game format, use as-is
                return dt.strftime("%d-%m-%Y %H:%M ISST")
            elif dt.year >= 2020 and dt.year <= 2030:
                # Real timestamp, convert to game time
                from utils.time_system import TimeSystem
                time_system = TimeSystem(self.bot)
                ingame_time = self._calculate_historical_ingame_time(time_system, dt)
                if ingame_time:
                    return ingame_time.strftime("%d-%m-%Y %H:%M ISST")
                else:
                    # Fallback if conversion fails
                    return dt.strftime("%d-%m-%Y %H:%M ISST")
            else:
                # Unknown year range, use as-is with ISST format
                return dt.strftime("%d-%m-%Y %H:%M ISST")
        except:
            return "Unknown Date"
    
    def _calculate_historical_ingame_time(self, time_system, historical_real_time):
        """Calculate what the in-game time was at a given historical real time"""
        galaxy_info = time_system.get_galaxy_info()
        if not galaxy_info:
            return None
            
        name, start_date_str, time_scale, time_started_at, created_at, is_paused, time_paused_at, current_ingame, is_manually_paused = galaxy_info
        
        # Parse start date
        start_date = time_system.parse_date_string(start_date_str)
        if not start_date:
            return None
        
        # Use time_started_at if available, otherwise use created_at
        if time_started_at and isinstance(time_started_at, str):
            real_start_time = safe_datetime_parse(time_started_at)
        elif created_at and isinstance(created_at, str):
            real_start_time = safe_datetime_parse(created_at)
        else:
            return None
        time_scale_factor = time_scale if time_scale else 4.0
        
        # If the historical time is before the galaxy started, return None
        if historical_real_time < real_start_time:
            return None
        
        # Calculate elapsed time from galaxy start to the historical timestamp
        elapsed_real_time = historical_real_time - real_start_time
        elapsed_ingame_time = elapsed_real_time * time_scale_factor
        historical_ingame_time = start_date + elapsed_ingame_time
        
        return historical_ingame_time
    
    webmap_group = app_commands.Group(name="webmap", description="Web map management commands")
    
    async def _start_webmap_internal(self, host: str, port: int, domain: str = None, https_proxy: bool = False):
        """Internal method to start the web map server"""
        if self.is_running:
            raise Exception("Web map is already running!")
        
        self.port = port
        self.host = host
        self.domain = domain
        self.https_proxy = https_proxy
        
        # Create web application
        self.app = web.Application()
        self.setup_routes()
        
        # Start the server
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        
        self.is_running = True
        
        # Update game panel
        panel_cog = self.bot.get_cog('GamePanelCog')
        if panel_cog:
            await panel_cog.refresh_all_panel_views()

    @webmap_group.command(name="start", description="Start the web map server")
    @app_commands.describe(
        port="Port to run the server on (default: 8090)",
        host="Host to bind to (default: 0.0.0.0)",
        domain="Domain name for the server (optional)",
        https_proxy="Force HTTPS URLs when behind proxy (default: False)"
    )
    async def start_webmap(self, interaction: discord.Interaction, port: int = 8090, host: str = '0.0.0.0', domain: str = None, https_proxy: bool = False):
        """Start the web map server"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if self.is_running:
            await interaction.response.send_message("Web map is already running!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            await self._start_webmap_internal(host, port, domain, https_proxy)
            
            # Get access URL
            final_url, _ = await self.get_final_map_url()
            
            embed = discord.Embed(
                title="✅ Web Map Started",
                description=f"The web map server is now running!",
                color=0x00ff00
            )
            embed.add_field(name="Host", value=self.host, inline=True)
            embed.add_field(name="Port", value=str(self.port), inline=True)
            embed.add_field(name="Status", value="🟢 Online", inline=True)
            embed.add_field(
                name="Access URLs",
                value=f"**Map:** {final_url}\\n**Wiki:** {final_url.replace('/map', '/wiki')}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.is_running = False
            await interaction.followup.send(f"Failed to start web map: {str(e)}", ephemeral=True)
            print(f"Web map start error: {traceback.format_exc()}")
    
    @webmap_group.command(name="stop", description="Stop the web map server")
    async def stop_webmap_command(self, interaction: discord.Interaction):
        """Stop the web map server"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not self.is_running:
            await interaction.response.send_message("Web map is not running!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            await self.stop_webmap()
            
            # Update game panel
            panel_cog = self.bot.get_cog('GamePanelCog')
            if panel_cog:
                await panel_cog.refresh_all_panel_views()
            
            embed = discord.Embed(
                title="🛑 Web Map Stopped",
                description="The web map server has been stopped.",
                color=0xff0000
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error stopping web map: {str(e)}", ephemeral=True)
    
    @webmap_group.command(name="set_ip", description="Set the external IP or domain for the web map")
    @app_commands.describe(address="External IP address or domain name")
    async def set_external_ip(self, interaction: discord.Interaction, address: str):
        """Set external IP or domain"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Check if it's a domain or IP
        if '.' in address and not address.replace('.', '').replace(':', '').isdigit():
            self.domain = address
            self.external_ip = None
            message = f"Domain set to: {address}"
        else:
            self.external_ip = address
            self.domain = None
            message = f"External IP set to: {address}"
        
        await interaction.response.send_message(message, ephemeral=True)
    
    async def stop_webmap(self):
        """Stop the web map server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        
        self.is_running = False
        self.app = None
        self.runner = None
        self.site = None
    
    async def get_final_map_url(self):
        """Get the final URL for the map"""
        if self.domain:
            protocol = "https" if (self.port == 443 or self.https_proxy) else "http"
            port_str = "" if (protocol == "https" and self.https_proxy) or self.port in [80, 443] else f":{self.port}"
            return f"{protocol}://{self.domain}{port_str}/map", self.domain
        elif self.external_ip:
            return f"http://{self.external_ip}:{self.port}/map", self.external_ip
        else:
            # Try to detect external IP
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('https://api.ipify.org?format=text', timeout=5) as resp:
                        detected_ip = await resp.text()
                        return f"http://{detected_ip}:{self.port}/map", detected_ip
            except:
                # Fallback
                return f"http://[SERVER_IP]:{self.port}/map", "[SERVER_IP]"
    
    def setup_routes(self):
        """Setup web routes"""
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/map', self.handle_map)
        self.app.router.add_get('/wiki', self.handle_wiki)
        self.app.router.add_get('/api/map-data', self.handle_api_map_data)
        self.app.router.add_get('/api/wiki-data', self.handle_api_wiki_data)
        self.app.router.add_get('/api/rich-presence/{user_id}', self.handle_api_rich_presence)
        self.app.router.add_static('/', path=os.path.dirname(__file__))
        self.app.router.add_static('/landing', path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'landing'))
    
    async def handle_index(self, request):
        """Serve the landing page"""
        try:
            html_content = self.get_landing_html()
            return web.Response(text=html_content, content_type='text/html')
        except Exception as e:
            print(f"❌ Error in handle_index: {e}")
            return web.Response(text=f"Error loading page: {str(e)}", status=500)
    
    async def handle_map(self, request):
        """Serve the map page"""
        try:
            html_content = self.get_map_html()
            return web.Response(text=html_content, content_type='text/html')
        except Exception as e:
            print(f"❌ Error in handle_map: {e}")
            return web.Response(text=f"Error loading map: {str(e)}", status=500)
    
    async def handle_wiki(self, request):
        """Serve the wiki page"""
        try:
            html_content = self.get_wiki_html()
            return web.Response(text=html_content, content_type='text/html')
        except Exception as e:
            print(f"❌ Error in handle_wiki: {e}")
            return web.Response(text=f"Error loading wiki: {str(e)}", status=500)
    
    async def handle_api_map_data(self, request):
        """API endpoint for map data"""
        try:
            return web.json_response(self.cache)
        except Exception as e:
            print(f"❌ Error in handle_api_map_data: {e}")
            return web.json_response({'error': 'Internal server error', 'message': str(e)}, status=500)
    
    async def handle_api_wiki_data(self, request):
        """API endpoint for wiki data"""
        try:
            wiki_data = await self._compile_wiki_data()
            return web.json_response(wiki_data)
        except Exception as e:
            print(f"❌ Error in handle_api_wiki_data: {e}")
            return web.json_response({'error': 'Internal server error', 'message': str(e)}, status=500)
    
    async def handle_api_rich_presence(self, request):
        """API endpoint for Rich Presence character data"""
        try:
            try:
                user_id = int(request.match_info['user_id'])
            except (ValueError, KeyError):
                return web.json_response({'error': 'Invalid user ID'}, status=400)
            
            # Get character data for Rich Presence
            char_data = self.db.execute_webmap_query(
                """SELECT c.name, c.current_location, c.is_logged_in, c.level, c.money,
                          c.location_status, c.login_time, l.name as location_name,
                          l.location_type, t.corridor_id, t.start_time, t.end_time,
                          dest_l.name as destination_name, dest_l.location_type as destination_type,
                          cor.travel_time, cor.fuel_cost, cor.danger_level,
                          j.title as current_job_title, j.description as current_job_description
                   FROM characters c
                   LEFT JOIN locations l ON c.current_location = l.location_id
                   LEFT JOIN travel_sessions t ON c.user_id = t.user_id AND t.status = 'traveling'
                   LEFT JOIN corridors cor ON t.corridor_id = cor.corridor_id
                   LEFT JOIN locations dest_l ON cor.destination_location = dest_l.location_id
                   LEFT JOIN job_tracking jt ON c.user_id = jt.user_id AND c.current_location = jt.start_location
                   LEFT JOIN jobs j ON jt.job_id = j.job_id
                   WHERE c.user_id = %s""",
                (user_id,),
                fetch='one'
            )
            
            if not char_data:
                return web.json_response({'error': 'Character not found'}, status=404)
            
            # Parse character data from dictionary
            name = char_data.get('name')
            current_location = char_data.get('current_location')
            is_logged_in = char_data.get('is_logged_in')
            level = char_data.get('level')
            money = char_data.get('money')
            location_status = char_data.get('location_status')
            login_time = char_data.get('login_time')
            location_name = char_data.get('location_name')
            location_type = char_data.get('location_type')
            corridor_id = char_data.get('corridor_id')
            travel_start = char_data.get('start_time')
            travel_end = char_data.get('end_time')
            destination_name = char_data.get('destination_name')
            destination_type = char_data.get('destination_type')
            travel_time_seconds = char_data.get('travel_time')
            fuel_cost = char_data.get('fuel_cost')
            danger_level = char_data.get('danger_level')
            current_job_title = char_data.get('current_job_title')
            current_job_description = char_data.get('current_job_description')
                
            # Define location type emojis and prefixes
            location_emojis = {
                'colony': '🏭',
                'space_station': '🛰️',
                'outpost': '🛤️',
                'gate': '🚪'
            }
            
            location_prefixes = {
                'colony': 'Colony',
                'space_station': 'Station',
                'outpost': 'Outpost',
                'gate': 'Gate'
            }
            
            # Determine current status for Rich Presence
            if not is_logged_in:
                status = "Offline"
                details = "Not currently playing"
                state = ""
            elif corridor_id:  # Currently traveling
                status = "Traveling"
                details = f"{name} - Level {level or 1}"
                
                # Enhanced travel state with destination emoji and route info
                if destination_name and destination_type:
                    dest_emoji = location_emojis.get(destination_type, '🌌')
                    state = f"🚀 Traveling to {dest_emoji} {destination_name}"
                elif destination_name:
                    state = f"🚀 Traveling to {destination_name}"
                else:
                    state = "🚀 In transit"
            else:  # At a location
                status = "Online"
                details = f"{name} - Level {level or 1}"
                
                # Enhanced location state with emoji and job info
                if location_name and location_type:
                    emoji = location_emojis.get(location_type, '🌌')
                    prefix = location_prefixes.get(location_type, '')
                    
                    if current_job_title:
                        state = f"💼 {current_job_title} at {emoji} {location_name}"
                    else:
                        state = f"At {emoji} {location_name}"
                elif location_name:
                    if current_job_title:
                        state = f"💼 {current_job_title} at {location_name}"
                    else:
                        state = f"At {location_name}"
                else:
                    state = "In space"
            
            # Calculate timestamp for Discord presence
            timestamp = None
            if login_time and is_logged_in:
                try:
                    from datetime import datetime
                    if isinstance(login_time, str) and login_time:
                        timestamp = int(safe_datetime_parse(login_time).timestamp())
                    elif hasattr(login_time, 'timestamp'):
                        timestamp = int(login_time.timestamp())
                except:
                    pass
            elif travel_start and corridor_id:
                try:
                    from datetime import datetime
                    if isinstance(travel_start, str) and travel_start:
                        timestamp = int(safe_datetime_parse(travel_start).timestamp())
                    elif hasattr(travel_start, 'timestamp'):
                        timestamp = int(travel_start.timestamp())
                except:
                    pass
            
            # Calculate travel progress if traveling
            travel_progress = None
            travel_time_remaining = None
            if corridor_id and travel_start and travel_time_seconds:
                from datetime import datetime, timedelta
                try:
                    if isinstance(travel_start, str) and travel_start:
                        start_time = safe_datetime_parse(travel_start)
                    elif hasattr(travel_start, 'strftime'):
                        start_time = travel_start
                    else:
                        return result
                    
                    current_time = datetime.utcnow()
                    elapsed_minutes = (current_time - start_time).total_seconds() / 60
                    travel_time_minutes = travel_time_seconds / 60  # Convert seconds to minutes
                    travel_time_remaining = max(0, travel_time_minutes - elapsed_minutes)
                    travel_progress = min(100, (elapsed_minutes / travel_time_minutes) * 100)
                except:
                    pass
            
            presence_data = {
                'status': status,
                'details': details,
                'state': state,
                'timestamp': timestamp,
                'is_online': bool(is_logged_in),
                'is_traveling': bool(corridor_id),
                'character_name': name,
                'level': level or 1,
                'credits': money or 0,
                'location': location_name,
                # Enhanced location information
                'location_type': location_type,
                'location_emoji': location_emojis.get(location_type, '🌌') if location_type else None,
                # Travel information
                'destination_name': destination_name,
                'destination_type': destination_type,
                'destination_emoji': location_emojis.get(destination_type, '🌌') if destination_type else None,
                'travel_time_minutes': travel_time_seconds / 60 if travel_time_seconds else None,
                'travel_time_remaining': travel_time_remaining,
                'travel_progress': travel_progress,
                'fuel_cost': fuel_cost,
                'danger_level': danger_level,
                # Job information
                'current_job_title': current_job_title,
                'current_job_description': current_job_description
            }
            
            return web.json_response(presence_data)
        
        except Exception as e:
            print(f"❌ Error in handle_api_rich_presence: {e}")
            return web.json_response({'error': 'Internal server error', 'message': str(e)}, status=500)
    
    async def _compile_wiki_data(self):
        """Compile comprehensive wiki data"""
        # Get galaxy info and current time
        galaxy_info_data = self.time_system.get_galaxy_info()
        galaxy_info = {}
        current_time = None
        
        if galaxy_info_data:
            galaxy_name, start_date, time_scale, time_started_at, created_at, is_paused, time_paused_at, current_ingame, is_manually_paused = galaxy_info_data
            current_time_obj = self.time_system.calculate_current_ingame_time()
            
            galaxy_info = {
                'name': galaxy_name,
                'start_date': start_date,
                'time_scale': time_scale,
                'is_paused': is_paused
            }
            
            if current_time_obj:
                current_time = self.time_system.format_ingame_datetime(current_time_obj)
        # Get detailed location information - removed tech_level and stability
        locations = self.db.execute_webmap_query(
            """SELECT l.location_id, l.name, l.location_type, l.x_coordinate, l.y_coordinate,
                      l.system_name, l.wealth_level, l.population, l.description, l.faction,
                      COUNT(DISTINCT c.user_id) as player_count,
                      COUNT(DISTINCT sn.npc_id) as static_npc_count,
                      COUNT(DISTINCT dn.npc_id) as dynamic_npc_count
               FROM locations l
               LEFT JOIN characters c ON l.location_id = c.current_location
               LEFT JOIN static_npcs sn ON l.location_id = sn.location_id
               LEFT JOIN dynamic_npcs dn ON l.location_id = dn.current_location AND dn.is_alive = true
               GROUP BY l.location_id""",
            fetch='all'
        )
        
        # Get route information - removed stability
        routes = self.db.execute_webmap_query(
            """SELECT c.corridor_id, c.origin_location, c.destination_location, c.name,
                      c.travel_time, c.danger_level,
                      ol.name as origin_name, dl.name as dest_name,
                      ol.system_name as origin_system, dl.system_name as dest_system
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.is_active = true
               ORDER BY ol.name, dl.name""",
            fetch='all'
        )
        
        # Get player information - only existing columns, only recent logins
        players = self.db.execute_webmap_query(
            """SELECT c.user_id, c.name, c.current_location, c.money,
                      c.level, c.experience, c.alignment,
                      l.name as location_name, s.name as ship_name
               FROM characters c
               LEFT JOIN locations l ON c.current_location = l.location_id
               LEFT JOIN ships s ON c.ship_id = s.ship_id
               WHERE c.is_logged_in = true
               ORDER BY c.name""",
            fetch='all'
        )
        
        # Get dynamic NPC information
        dynamic_npcs = self.db.execute_webmap_query(
            """SELECT n.npc_id, n.name, n.callsign, n.age, n.ship_name, n.ship_type,
                      n.current_location, n.credits, n.alignment, n.combat_rating,
                      l.name as location_name
               FROM dynamic_npcs n
               LEFT JOIN locations l ON n.current_location = l.location_id
               WHERE n.is_alive = true
               ORDER BY n.name""",
            fetch='all'
        )
        
        # Get location logs
        location_logs = self.db.execute_webmap_query(
            """SELECT ll.log_id, ll.location_id, ll.author_id, ll.author_name, 
                      ll.message, ll.posted_at, l.name as location_name
               FROM location_logs ll
               JOIN locations l ON ll.location_id = l.location_id
               ORDER BY ll.posted_at DESC
               LIMIT 100""",
            fetch='all'
        )
        
        return {
            'locations': self._format_wiki_locations(locations),
            'routes': self._format_wiki_routes(routes),
            'players': self._format_wiki_players(players),
            'npcs': self._format_wiki_npcs(dynamic_npcs),
            'logs': self._format_wiki_logs(location_logs),
            'news': self.cache['news'],
            'galaxy_info': galaxy_info,
            'current_time': current_time
        }
    
    def _format_wiki_locations(self, locations):
        """Format location data for wiki"""
        formatted = []
        for loc in locations:
            formatted.append({
                'id': loc.get('location_id'),
                'name': loc.get('name'),
                'type': loc.get('location_type'),
                'system': loc.get('system_name'),
                'wealth': loc.get('wealth_level'),
                'population': loc.get('population'),
                'description': loc.get('description'),
                'faction': loc.get('faction'),
                'stability': 75,  # Default since column doesn't exist
                'player_count': loc.get('player_count'),
                'static_npc_count': loc.get('static_npc_count'),
                'dynamic_npc_count': loc.get('dynamic_npc_count')
            })
        return formatted

    def _format_wiki_routes(self, routes):
        """Format route data for wiki"""
        formatted = []
        for route in routes:
            formatted.append({
                'id': route.get('corridor_id'),
                'origin': route.get('origin_location'),
                'destination': route.get('destination_location'),
                'name': route.get('name'),
                'travel_time': route.get('travel_time'),
                'danger_level': route.get('danger_level'),
                'stability': 90,  # Default since column doesn't exist
                'origin_name': route.get('origin_name'),
                'dest_name': route.get('dest_name'),
                'origin_system': route.get('origin_system'),
                'dest_system': route.get('dest_system')
            })
        return formatted

    def _format_wiki_players(self, players):
        """Format player data for wiki"""
        formatted = []
        for player in players:
            formatted.append({
                'id': player.get('user_id'),
                'name': player.get('name'),
                'location': player.get('current_location'),
                'credits': player.get('money'),
                'level': player.get('level') if player.get('level') else 1,
                'experience': player.get('experience') if player.get('experience') else 0,
                'alignment': player.get('alignment') if player.get('alignment') else 'neutral',
                'location_name': player.get('location_name'),
                'ship_name': player.get('ship_name'),
                # Default values for non-existent stats
                'total_distance': 0,
                'locations_visited': 0,
                'jobs_completed': 0,
                'pirates_defeated': 0,
                'reputation_loyalist': 0,
                'reputation_outlaw': 0
            })
        return formatted

    def _format_wiki_npcs(self, npcs):
        """Format NPC data for wiki"""
        formatted = []
        for npc in npcs:
            formatted.append({
                'id': npc.get('npc_id'),
                'name': npc.get('name'),
                'callsign': npc.get('callsign'),
                'age': npc.get('age'),
                'ship_name': npc.get('ship_name'),
                'ship_type': npc.get('ship_type'),
                'location': npc.get('current_location'),
                'credits': npc.get('credits'),
                'alignment': npc.get('alignment'),
                'combat_rating': npc.get('combat_rating'),
                'location_name': npc.get('location_name')
            })
        return formatted

    def _format_wiki_logs(self, logs):
        """Format location logs for wiki"""
        formatted = []
        for log in logs:
            formatted.append({
                'id': log.get('log_id'),
                'location_id': log.get('location_id'),
                'location_name': log.get('location_name'),
                'character_name': log.get('author_name'),
                'action': log.get('message'),
                'timestamp': log.get('posted_at'),
                'game_date': self._convert_to_game_date(log.get('posted_at'))
            })
        return formatted
    
    def get_landing_html(self):
        """Get landing page HTML"""
        try:
            landing_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'landing', 'index.html')
            with open(landing_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Quiet End - Web Interface</title>
    <link href="https://fonts.googleapis.com/css2?family=Tektur:wght@400;700;900&display=swap" rel="stylesheet">
    <style>''' + self.get_shared_css() + '''</style>
</head>
<body class="theme-blue">
    <div class="static-overlay"></div>
    <div class="scanlines"></div>
    <div class="main-container">
        <header class="game-header">
            <div class="terminal-indicator">
                <div class="power-light"></div>
                <span class="terminal-id">TERMINAL-2754-ACTIVE</span>
            </div>
            <h1 class="game-title">THE QUIET END</h1>
            <p class="game-subtitle">WEB INTERFACE</p>
        </header>
        
        <div class="action-buttons">
            <a href="/map" class="action-button">
                <div class="button-icon">🗺️</div>
                <div class="button-text">
                    <div class="button-title">GALAXY MAP</div>
                    <div class="button-subtitle">Real-time Navigation</div>
                </div>
                <div class="button-glow"></div>
            </a>
            
            <a href="/wiki" class="action-button">
                <div class="button-icon">📚</div>
                <div class="button-text">
                    <div class="button-title">GALACTIC WIKI</div>
                    <div class="button-subtitle">Knowledge Database</div>
                </div>
                <div class="button-glow"></div>
            </a>
        </div>
    </div>
</body>
</html>'''
    
    def get_map_html(self):
        """Get map page HTML with enhanced info panel"""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galaxy Map - {self.bot.user.name if self.bot.user else "Space RPG"}</title>
    <link href="https://fonts.googleapis.com/css2?family=Tektur:wght@400;700&display=swap" rel="stylesheet">
    <style>
        {self.get_shared_css()}
        {self.get_map_css()}
    </style>
</head>
<body>
    <div class="static-overlay"></div>
    <div class="scanlines"></div>
    
    <div class="map-container">
        <div class="map-header" id="map-header">
            <div class="header-section">
                <h1 class="map-title">
                    <span id="galaxy-name">Galaxy Map</span>
                </h1>
                <div class="map-status">
                    <span class="status-indicator"></span>
                    <span id="current-time">Loading...</span>
                    <span id="last-update">Loading...</span>
                </div>
            </div>
            <div class="header-controls">
                <button class="header-toggle-btn" id="header-toggle" onclick="toggleHeader()" title="Hide/Show Header">
                    <span class="toggle-icon">▲</span>
                </button>
                <div class="map-action-buttons">
                    <a href="/wiki" class="action-button">
                        <div class="button-icon">📚</div>
                        <div class="button-text">
                            <div class="button-title">WIKI</div>
                        </div>
                        <div class="button-glow"></div>
                    </a>
                    <a href="/" class="action-button">
                        <div class="button-icon">🏠</div>
                        <div class="button-text">
                            <div class="button-title">HOME</div>
                        </div>
                        <div class="button-glow"></div>
                    </a>
                </div>
            </div>
        </div>
        
        <!-- Collapsed header toggle when header is hidden -->
        <div class="header-toggle-collapsed" id="header-toggle-collapsed" style="display: none;">
            <button class="header-toggle-btn collapsed" onclick="toggleHeader()" title="Show Header">
                <span class="toggle-icon">▼</span>
            </button>
        </div>
        
        <div class="map-controls">
            <div class="control-row">
                <div class="control-group control-group-compact">
                    <label class="toggle-control">
                        <input type="checkbox" id="toggle-labels">
                        <span>Labels</span>
                    </label>
                    <label class="toggle-control">
                        <input type="checkbox" id="toggle-routes" checked>
                        <span>Routes</span>
                    </label>
                    <label class="toggle-control">
                        <input type="checkbox" id="toggle-active-routes-only">
                        <span>Active Routes Only</span>
                    </label>
                    <label class="toggle-control">
                        <input type="checkbox" id="toggle-players">
                        <span>Players</span>
                    </label>
                    <label class="toggle-control">
                        <input type="checkbox" id="toggle-npcs">
                        <span>NPCs</span>
                    </label>
                </div>
                <div class="control-group">
                    <div class="search-container">
                        <input type="text" id="search-input" placeholder="Search..." class="search-input" autocomplete="off">
                        <div id="search-dropdown" class="search-dropdown"></div>
                    </div>
                    <button class="control-button control-button-compact" onclick="galaxyMap.searchLocation()">Go</button>
                    <button class="control-button control-button-compact" onclick="galaxyMap.clearSearch()">Clear</button>
                    <button class="control-button control-button-compact" onclick="galaxyMap.resetView()">Reset</button>
                </div>
            </div>
            <div class="control-row">
                <div class="control-group">
                    <span class="control-label">🔍</span>
                    <button class="control-button control-button-compact" onclick="galaxyMap.zoom(1.25)">+</button>
                    <button class="control-button control-button-compact" onclick="galaxyMap.zoom(0.8)">-</button>
                    <button class="control-button control-button-compact" onclick="galaxyMap.zoomToFit()">Fit</button>
                    <span id="zoom-level" class="zoom-display">100%</span>
                </div>
                <div class="control-group route-planning-group">
                    <span class="control-label">📍</span>
                    <select id="route-start" class="route-select">
                        <option value="">Start</option>
                    </select>
                    <select id="route-end" class="route-select">
                        <option value="">End</option>
                    </select>
                    <select id="route-midpoint" class="route-select">
                        <option value="">Via</option>
                    </select>
                    <button class="control-button" onclick="galaxyMap.plotRouteFromControls()">Plot Route</button>
                    <button class="control-button control-button-compact" onclick="galaxyMap.clearPlottedRoute()">Clear</button>
                </div>
            </div>
        </div>
        
        <div class="map-viewport">
            <canvas id="galaxy-map"></canvas>
            <div id="tooltip" class="map-tooltip"></div>
            <div id="location-info" class="location-info-panel">
                <button class="info-panel-close" onclick="window.galaxyMap.closeInfoPanel()">×</button>
                <!-- Content will be dynamically inserted here -->
            </div>
        </div>
    </div>
    
    <script src="/landing/js/theme-manager.js"></script>
    <script>{self.get_map_script()}</script>
</body>
</html>'''
    
    def get_wiki_html(self):
        """Get wiki page HTML"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Quiet End - Galactic Wiki</title>
    <link href="https://fonts.googleapis.com/css2?family=Tektur:wght@400;700;900&display=swap" rel="stylesheet">
    <style>''' + self.get_shared_css() + self.get_wiki_css() + '''</style>
</head>
<body class="theme-blue">
    <div class="static-overlay"></div>
    <div class="scanlines"></div>
    
    <div class="wiki-container">
        <header class="wiki-header">
            <div class="header-section">
                <h1 class="wiki-title">
                    <span id="galaxy-name">GALACTIC WIKI</span>
                </h1>
                <div class="wiki-status">
                    <div class="status-indicator online"></div>
                    <span id="current-time">DATABASE ONLINE</span>
                </div>
            </div>
            <div class="header-controls">
                <div class="wiki-action-buttons">
                    <a href="/" class="action-button">
                        <div class="button-icon">🏠</div>
                        <div class="button-text">
                            <div class="button-title">HOME</div>
                        </div>
                        <div class="button-glow"></div>
                    </a>
                    <a href="/map" class="action-button">
                        <div class="button-icon">🗺️</div>
                        <div class="button-text">
                            <div class="button-title">MAP</div>
                        </div>
                        <div class="button-glow"></div>
                    </a>
                </div>
            </div>
        </header>
        
        <div class="wiki-tabs">
            <button class="wiki-tab active" data-tab="locations">Locations</button>
            <button class="wiki-tab" data-tab="routes">Routes</button>
            <button class="wiki-tab" data-tab="players">Pilots</button>
            <button class="wiki-tab" data-tab="npcs">NPCs</button>
            <button class="wiki-tab" data-tab="logs">Activity Logs</button>
            <button class="wiki-tab" data-tab="news">News Feed</button>
        </div>
        
        <div class="wiki-content">
            <div id="loading" class="loading-message">Loading database...</div>
            <div id="wiki-data" class="wiki-data"></div>
        </div>
    </div>
    
    <!-- Wiki info panel - positioned outside container for proper overlay behavior -->
    <div id="wiki-location-info" class="location-info-panel">
        <button class="info-panel-close">×</button>
        <!-- Content will be dynamically inserted here -->
    </div>
    
    <script src="/landing/js/theme-manager.js"></script>
    <script>''' + self.get_wiki_script() + '''</script>
</body>
</html>'''
    
    def get_shared_css(self):
        """Get shared CSS styles - Mobile-first responsive design"""
        return '''
        :root {
            /* Default theme variables - will be overridden by theme manager */
            --primary-color: #00ffff;
            --secondary-color: #00cccc;
            --accent-color: #0088cc;
            --warning-color: #ff8800;
            --success-color: #00ff88;
            --error-color: #ff3333;
            --primary-bg: #000408;
            --secondary-bg: #0a0f1a;
            --accent-bg: #1a2332;
            --text-primary: #e0ffff;
            --text-secondary: #88ccdd;
            --text-muted: #556677;
            --border-color: #003344;
            --shadow-dark: rgba(0, 0, 0, 0.9);
            --glow-primary: rgba(0, 255, 255, 0.6);
            --glow-secondary: rgba(0, 204, 204, 0.4);
            --gradient-panel: linear-gradient(145deg, rgba(10, 15, 26, 0.95), rgba(26, 35, 50, 0.95));
            --gradient-holo: linear-gradient(135deg, rgba(0, 255, 255, 0.1), rgba(0, 204, 204, 0.2));
            
            /* Mobile-first sizing variables - Progressive touch targets */
            --base-font-size: 14px;
            --small-font-size: 12px;
            --large-font-size: 16px;
            --touch-target-size: 36px;
            --checkbox-size: 20px;
            --button-padding: 0.75rem;
            --control-spacing: 0.5rem;
            --panel-padding: 1rem;
            --element-gap: 0.5rem;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        /* Device-responsive base styles */
        body {
            font-family: 'Tektur', monospace;
            font-size: var(--base-font-size);
            line-height: 1.6;
            background: var(--primary-bg);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            -webkit-text-size-adjust: 100%;
            -webkit-font-smoothing: antialiased;
        }
        
        .static-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 255, 255, 0.01) 2px,
                rgba(0, 255, 255, 0.01) 4px
            );
            pointer-events: none;
            z-index: 1;
            opacity: 0.2;
        }
        
        .scanlines {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                transparent 50%,
                rgba(0, 0, 0, 0.25) 50%
            );
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 2;
            animation: flicker 0.15s infinite;
        }
        
        @keyframes flicker {
            0%, 100% { opacity: 0.97; }
            50% { opacity: 1; }
        }
        
        /* Mobile-first main container */
        .main-container {
            position: relative;
            z-index: 10;
            padding: var(--mobile-padding);
            width: 100%;
            margin: 0 auto;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        
        /* Mobile-first game header */
        .game-header {
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 8px;
            padding: 1.5rem var(--mobile-padding);
            box-shadow: 0 0 30px var(--glow-primary);
            margin-bottom: 2rem;
            width: 100%;
            max-width: 500px;
        }
        
        .terminal-indicator {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: var(--mobile-gap);
            margin-bottom: 1rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        
        .power-light {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success-color);
            box-shadow: 0 0 10px var(--success-color);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        /* Mobile-first typography */
        .game-title {
            font-size: 2rem;
            font-weight: 900;
            color: var(--primary-color);
            text-shadow: 0 0 20px var(--glow-primary);
            margin-bottom: 0.5rem;
            line-height: 1.2;
        }
        
        .game-subtitle {
            font-size: 0.75rem;
            color: var(--text-secondary);
            letter-spacing: 2px;
        }
        
        /* Mobile-first action buttons */
        .action-buttons {
            display: flex;
            flex-direction: column;
            gap: var(--element-gap);
            width: 100%;
            max-width: 400px;
        }
        
        .action-button {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: var(--element-gap);
            padding: var(--button-padding);
            min-height: var(--touch-target-size);
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 8px;
            text-decoration: none;
            color: var(--text-primary);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
            width: 100%;
            cursor: pointer;
            touch-action: manipulation;
        }
        
        .action-button:hover,
        .action-button:focus {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 255, 255, 0.3);
            border-color: var(--secondary-color);
            outline: none;
        }
        
        .action-button:active {
            transform: translateY(0);
        }
        
        .button-icon {
            font-size: 1.5rem;
            filter: drop-shadow(0 0 10px var(--glow-primary));
            flex-shrink: 0;
        }
        
        .button-text {
            text-align: center;
            flex: 1;
        }
        
        .button-title {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.25rem;
            line-height: 1.2;
        }
        
        .button-subtitle {
            font-size: 0.75rem;
            color: var(--text-secondary);
            line-height: 1.3;
        }
        
        .button-glow {
            position: absolute;
            top: 50%;
            left: 50%;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle, var(--glow-primary) 0%, transparent 70%);
            transform: translate(-50%, -50%);
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        }
        
        .action-button:hover .button-glow {
            opacity: 0.2;
        }
        
        /* Tablet breakpoint - Optimize touch targets for tablet use */
        @media (min-width: 768px) {
            :root {
                --touch-target-size: 32px;
                --checkbox-size: 18px;
                --button-padding: 0.6rem;
                --control-spacing: 0.6rem;
                --panel-padding: 1.5rem;
                --element-gap: 0.75rem;
            }
            
            .main-container {
                padding: 2rem;
            }
            
            .game-header {
                padding: 2rem;
                border-radius: 12px;
                margin-bottom: 2.5rem;
                max-width: 600px;
            }
            
            .game-title {
                font-size: 2.5rem;
            }
            
            .game-subtitle {
                font-size: 0.85rem;
                letter-spacing: 2.5px;
            }
            
            .action-buttons {
                flex-direction: row;
                flex-wrap: wrap;
                justify-content: center;
                gap: 1.5rem;
                max-width: 700px;
            }
            
            .action-button {
                flex: 1;
                min-width: 300px;
                max-width: 350px;
            }
            
            .button-text {
                text-align: left;
            }
            
            .power-light {
                width: 10px;
                height: 10px;
            }
        }
        
        /* Desktop breakpoint - Compact layouts for efficiency */
        @media (min-width: 1024px) {
            :root {
                --touch-target-size: 28px;
                --checkbox-size: 16px;
                --button-padding: 0.375rem;
                --control-spacing: 0.375rem;
                --panel-padding: 0.75rem;
                --element-gap: 0.375rem;
                --base-font-size: 14px;
                --small-font-size: 12px;
                --large-font-size: 16px;
            }
            
            .main-container {
                max-width: 1200px;
                padding: 2rem;
            }
            
            /* More aggressive compact sizing for desktop */
            .control-button-compact {
                padding: 0.25rem 0.5rem;
                min-height: 24px;
                font-size: 0.7rem;
                border-radius: 4px;
            }
            
            .nav-button {
                padding: 0.25rem 0.5rem;
                min-height: 24px;
                font-size: 0.75rem;
                border-radius: 4px;
            }
            
            /* Standard control buttons for desktop */
            .control-button {
                padding: 0.25rem 0.75rem;
                min-height: 26px;
                font-size: 0.75rem;
                border-radius: 4px;
            }
            
            /* Route select optimization for desktop */
            .route-select {
                padding: 0.25rem 0.5rem;
                min-height: 26px;
                font-size: 0.75rem;
                min-width: 100px;
            }
            
            /* Search input optimization */
            .search-input {
                padding: 0.25rem 0.5rem;
                min-height: 26px;
                font-size: 0.75rem;
                max-width: 200px;
            }
            
            /* Toggle controls optimization for desktop */
            .toggle-control {
                min-height: 24px;
                padding: 0.25rem;
                font-size: 0.75rem;
                gap: 0.375rem;
            }
            
            /* Control labels for desktop */
            .control-label {
                font-size: 0.75rem;
                margin-right: 0.25rem;
            }
            
            /* Desktop horizontal layouts for efficiency */
            .control-row {
                flex-direction: row;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                margin-bottom: 0.5rem;
            }
            
            .map-controls {
                max-height: 20vh; /* Reduce height for more map space */
                padding: 0.75rem;
            }
            
            /* Control group spacing optimization for desktop */
            .control-group {
                gap: 0.375rem;
                margin: 0;
            }
            
            .control-group-compact {
                gap: 0.25rem;
            }
            
            .route-planning-group {
                gap: 0.375rem;
                flex-wrap: nowrap;
                justify-content: flex-start;
                max-width: none;
            }
            
            /* Enhanced horizontal layout for desktop */
            .map-controls .control-row:first-child {
                display: grid;
                grid-template-columns: auto 1fr auto;
                gap: 1rem;
                align-items: center;
            }
            
            .map-controls .control-row:last-child {
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                flex-wrap: nowrap;
            }
            
            /* Desktop typography optimization */
            .terminal-indicator {
                font-size: 0.7rem;
                gap: 0.5rem;
                margin-bottom: 0.75rem;
            }
            
            /* Panel and info typography for desktop */
            .info-panel {
                font-size: 0.8rem;
                line-height: 1.4;
            }
            
            .info-panel h3 {
                font-size: 1rem;
                margin-bottom: 0.5rem;
            }
            
            .wiki-content {
                font-size: 0.85rem;
                line-height: 1.5;
            }
            
            .game-header {
                padding: 2.5rem;
                margin-bottom: 3rem;
                max-width: 800px;
            }
            
            .game-title {
                font-size: 3rem;
            }
            
            .game-subtitle {
                font-size: 0.9rem;
                letter-spacing: 3px;
            }
            
            .action-buttons {
                gap: 2rem;
                max-width: 900px;
            }
            
            .action-button {
                padding: 1.5rem 2rem;
                min-width: 350px;
            }
            
            .button-icon {
                font-size: 2rem;
            }
            
            .button-title {
                font-size: 1.1rem;
            }
            
            .button-subtitle {
                font-size: 0.8rem;
            }
        }
        
        /* Large desktop breakpoint */
        @media (min-width: 1440px) {
            .static-overlay {
                opacity: 0.3;
            }
        }

        /* =================================
           LOCATION INFO PANEL STYLES
           Used by both map and wiki pages
           ================================= */

        /* Device-responsive location info panel - slide-up modal design */
        .location-info-panel {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            width: 100%;
            max-height: 40vh;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 16px 16px 0 0;
            padding: var(--panel-padding);
            box-shadow: 0 -8px 32px var(--glow-primary);
            z-index: 9999;
            display: none;
            transform: translateY(100%);
            transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            touch-action: pan-y;
            /* Fix blur on mobile devices */
            -webkit-transform: translateZ(0);
            -webkit-backface-visibility: hidden;
            -webkit-font-smoothing: antialiased;
            transform-style: preserve-3d;
        }
        
        .location-info-panel.visible {
            display: block;
            transform: translateY(0);
        }
        
        /* Add gesture indicator for mobile */
        .location-info-panel::before {
            content: '';
            position: absolute;
            top: 0.5rem;
            left: 50%;
            transform: translateX(-50%);
            width: 40px;
            height: 4px;
            background: var(--text-secondary);
            border-radius: 2px;
            opacity: 0.6;
        }
        
        /* Backdrop overlay for mobile modal */
        .info-panel-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: transparent;
            z-index: 1500;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }
        
        .info-panel-backdrop.visible {
            opacity: 1;
            visibility: visible;
        }

        .location-info-panel::-webkit-scrollbar {
            width: 8px;
        }

        .location-info-panel::-webkit-scrollbar-track {
            background: var(--secondary-bg);
            border-radius: 4px;
        }

        .location-info-panel::-webkit-scrollbar-thumb {
            background: var(--primary-color);
            border-radius: 4px;
            border: 1px solid var(--secondary-bg);
        }

        .location-info-panel::-webkit-scrollbar-thumb:hover {
            background: var(--text-primary);
        }
        
        /* Smooth scrolling behavior */
        .location-info-panel {
            scroll-behavior: smooth;
            overscroll-behavior: contain;
        }

        .location-info-panel h3 {
            color: var(--primary-color);
            margin: 0 0 1.5rem 0;
            font-size: 1.3rem;
            font-weight: 600;
            text-shadow: 0 0 8px var(--glow-primary);
            border-bottom: 2px solid var(--primary-color);
            padding-bottom: 0.75rem;
            padding-right: 3rem;
            position: relative;
        }

        /* Enhanced information hierarchy */
        .location-detail {
            margin-bottom: 1rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.6;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(64, 224, 208, 0.1);
        }

        .location-detail:last-child {
            border-bottom: none;
        }

        .location-detail strong {
            color: var(--text-primary);
            display: block;
            margin-bottom: 0.25rem;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.8;
        }
        
        .location-detail-value {
            color: var(--primary-color);
            font-size: 1rem;
            font-weight: 500;
        }
        
        /* Enhanced close button for info panel - touch-friendly */
        .info-panel-close {
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            padding: 0.5rem;
            line-height: 1;
            border-radius: 50%;
            min-height: 44px;
            min-width: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            touch-action: manipulation;
        }

        .info-panel-close:hover,
        .info-panel-close:focus {
            color: var(--primary-color);
            background: rgba(64, 224, 208, 0.2);
            border-color: var(--primary-color);
            text-shadow: 0 0 10px var(--glow-primary);
            transform: scale(1.1);
            outline: none;
        }

        .info-panel-close:active {
            transform: scale(0.95);
        }

        /* Desktop layout - right-side overlay panel */
        @media (min-width: 1024px) {
            .location-info-panel {
                position: fixed;
                top: 2rem;
                right: 0;
                bottom: 2rem;
                left: auto;
                width: 350px;
                max-width: 25vw;
                max-height: 90vh;
                border-radius: 8px 0 0 8px;
                border-left: 2px solid var(--primary-color);
                border-top: none;
                border-right: none;
                border-bottom: none;
                transform: translateX(100%);
                transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                padding: 1.5rem 1rem;
            }
            
            .location-info-panel.visible {
                display: block;
                transform: translateX(0);
            }
            
            .location-info-panel::before {
                display: none; /* Hide mobile gesture indicator */
            }
            
            .info-panel-close {
                top: 0.75rem;
                right: 0.75rem;
                font-size: 1.2rem;
                background: rgba(0, 0, 0, 0.5);
                border-radius: 50%;
                min-height: 32px;
                min-width: 32px;
                padding: 0;
            }
            
            .info-panel-backdrop {
                display: none; /* No backdrop needed on desktop */
            }
        }
        
        /* Tablet layout - adaptive sizing */
        @media (min-width: 768px) and (max-width: 1023px) {
            .location-info-panel {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                width: 100%;
                max-height: 45vh;
                border-radius: 16px 16px 0 0;
                padding: 1.5rem;
            }
            
            .info-panel-close {
                top: 1rem;
                right: 1rem;
                font-size: 1.5rem;
                padding: 0.5rem;
                min-height: 44px;
                min-width: 44px;
                background: rgba(0, 0, 0, 0.4);
                border-radius: 50%;
            }
        }
        
        /* Mobile specific adjustments */
        @media (max-width: 767px) {
            .location-info-panel {
                position: fixed;
                bottom: 0;
                right: 0;
                left: 0;
                width: 100%;
                max-height: 35vh;
                border-radius: 16px 16px 0 0;
                padding: 1.5rem 1rem 1rem 1rem;
                z-index: 9999;
            }
            
            .info-panel-close {
                top: 0.5rem;
                right: 0.5rem;
                font-size: 1.25rem;
                padding: 0.5rem;
                min-height: 32px;
                min-width: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 50%;
            }
        }
        '''
    
    def get_map_css(self):
        """Get map-specific CSS - Mobile-first responsive design"""
        return '''
        /* Mobile-first map container */
        .map-container {
            position: relative;
            z-index: 10;
            width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        /* Device-responsive map header */
        .map-header {
            background: var(--gradient-panel);
            border-bottom: 2px solid var(--primary-color);
            padding: var(--button-padding) var(--panel-padding);
            display: flex;
            flex-direction: column;
            gap: var(--control-spacing);
            flex-shrink: 0;
        }
        
        .header-section {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: var(--element-gap);
        }
        
        /* Mobile-first map title */
        .map-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--primary-color);
            text-shadow: 0 0 15px var(--glow-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .map-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
            flex-shrink: 0;
        }
        
        #current-time {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--primary-color);
            text-shadow: 0 0 8px var(--glow-primary);
            padding: 0.25rem 0.5rem;
            background: rgba(0, 255, 255, 0.05);
            border-radius: 4px;
            border: 1px solid rgba(0, 255, 255, 0.2);
        }
        
        .status-indicator {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--success-color);
            box-shadow: 0 0 8px var(--success-color);
            flex-shrink: 0;
        }
        
        /* Device-responsive header controls */
        .header-controls {
            display: flex;
            gap: var(--control-spacing);
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .nav-button {
            padding: var(--control-spacing) var(--button-padding);
            min-height: var(--touch-target-size);
            background: var(--accent-bg);
            border: 1px solid var(--primary-color);
            border-radius: 6px;
            text-decoration: none;
            color: var(--text-primary);
            font-size: 0.8rem;
            transition: all 0.3s ease;
            touch-action: manipulation;
            display: flex;
            align-items: center;
            justify-content: center;
            white-space: nowrap;
        }
        
        .nav-button:hover,
        .nav-button:focus {
            background: var(--primary-color);
            color: var(--primary-bg);
            box-shadow: 0 0 12px var(--glow-primary);
            outline: none;
        }
        
        /* Header toggle button */
        .header-toggle-btn {
            padding: var(--control-spacing);
            min-height: var(--touch-target-size);
            background: var(--accent-bg);
            border: 1px solid var(--primary-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 0.9rem;
            transition: all 0.3s ease;
            touch-action: manipulation;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            width: 40px;
            height: 40px;
        }
        
        .header-toggle-btn:hover,
        .header-toggle-btn:focus {
            background: var(--primary-color);
            color: var(--primary-bg);
            box-shadow: 0 0 15px var(--glow-primary);
        }
        
        .toggle-icon {
            font-size: 0.8rem;
            line-height: 1;
            transition: transform 0.3s ease;
        }
        
        /* Collapsed header toggle when header is hidden */
        .header-toggle-collapsed {
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: var(--gradient-panel);
            border-radius: 6px;
            padding: 5px;
            border: 1px solid var(--primary-color);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        
        .header-toggle-collapsed .header-toggle-btn {
            background: var(--primary-color);
            color: var(--primary-bg);
            box-shadow: 0 0 10px var(--glow-primary);
        }
        
        /* Hidden header state */
        .map-header.hidden {
            display: none;
        }
        
        /* Hidden controls state */
        .map-controls.hidden {
            display: none;
        }
        
        /* When header is hidden, expand map viewport to full height */
        body.header-hidden .map-viewport {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 5;
        }
        
        /* Smooth transition for header and controls visibility */
        .map-header,
        .map-controls {
            transition: transform 0.3s ease, opacity 0.3s ease;
        }
        
        /* Device-responsive map controls */
        .map-controls {
            background: var(--secondary-bg);
            border-bottom: 1px solid var(--border-color);
            padding: var(--control-spacing);
            display: flex;
            flex-direction: column;
            gap: var(--control-spacing);
            flex-shrink: 0;
            max-height: 30vh;
            overflow-y: auto;
        }
        
        .control-row {
            display: flex;
            flex-direction: column;
            gap: var(--control-spacing);
            align-items: stretch;
        }
        
        .control-group {
            display: flex;
            gap: var(--control-spacing);
            align-items: center;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .control-group-compact {
            gap: var(--control-spacing);
        }
        
        .route-planning-group {
            gap: var(--control-spacing);
            flex-wrap: wrap;
            width: 100%;
            justify-content: center;
        }
        
        /* Device-responsive toggle controls */
        .toggle-control {
            display: flex;
            align-items: center;
            gap: var(--control-spacing);
            cursor: pointer;
            font-size: 0.8rem;
            color: var(--text-secondary);
            transition: color 0.3s ease;
            min-height: var(--touch-target-size);
            padding: var(--control-spacing);
            touch-action: manipulation;
        }
        
        .toggle-control:hover,
        .toggle-control:focus {
            color: var(--text-primary);
        }
        
        .control-label {
            font-size: 0.8rem;
            color: var(--primary-color);
            margin-right: 0.25rem;
            white-space: nowrap;
        }
        
        /* Device-responsive control buttons */
        .control-button {
            padding: var(--button-padding);
            min-height: var(--touch-target-size);
            background: var(--accent-bg);
            border: 1px solid var(--primary-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.3s ease;
            white-space: nowrap;
            touch-action: manipulation;
        }
        
        .control-button:hover,
        .control-button:focus {
            background: var(--primary-color);
            color: var(--primary-bg);
            box-shadow: 0 0 12px var(--glow-primary);
            outline: none;
        }
        
        .control-button-compact {
            padding: var(--control-spacing) var(--button-padding);
            font-size: 0.75rem;
            min-height: var(--touch-target-size);
        }
        
        /* Device-responsive route select */
        .route-select {
            background: var(--accent-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            padding: var(--button-padding);
            font-size: 0.8rem;
            min-height: var(--touch-target-size);
            min-width: 120px;
            cursor: pointer;
            touch-action: manipulation;
        }
        
        .route-select:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 8px var(--glow-primary);
        }
        
        .zoom-display {
            color: var(--text-primary);
            font-family: monospace;
            font-size: 0.8rem;
            min-width: 50px;
            text-align: center;
            padding: 0.5rem;
            background: var(--secondary-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
        }
        
        /* Device-responsive checkbox styling - Progressive touch targets */
        .toggle-control input[type="checkbox"] {
            width: var(--checkbox-size);
            height: var(--checkbox-size);
            accent-color: var(--primary-color);
            cursor: pointer;
            touch-action: manipulation;
            /* Ensure checkbox is centered within its touch target */
            margin: 0;
            flex-shrink: 0;
        }
        
        .toggle-control input[type="checkbox"]:checked {
            box-shadow: 0 0 8px var(--glow-primary);
        }
        
        /* Device-responsive search input */
        .search-input {
            padding: var(--button-padding);
            background: var(--secondary-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.8rem;
            min-height: var(--touch-target-size);
            width: 100%;
            max-width: 300px;
            transition: all 0.3s ease;
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 10px rgba(64, 224, 208, 0.3);
        }
        
        .search-input::placeholder {
            color: var(--text-secondary);
        }
        
        .search-container {
            position: relative;
            width: 100%;
            max-width: 300px;
        }
        
        .search-dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--secondary-bg);
            border: 1px solid var(--border-color);
            border-top: none;
            border-radius: 0 0 6px 6px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            display: none;
        }
        
        .search-dropdown-item {
            padding: var(--button-padding);
            color: var(--text-primary);
            cursor: pointer;
            transition: background-color 0.2s ease;
            border-bottom: 1px solid var(--border-color);
            min-height: var(--touch-target-size);
            display: flex;
            align-items: center;
            touch-action: manipulation;
        }
        
        .search-dropdown-item:last-child {
            border-bottom: none;
        }
        
        .search-dropdown-item:hover,
        .search-dropdown-item.highlighted {
            background-color: var(--primary-color);
            color: var(--primary-bg);
        }
        
        .search-dropdown-item.no-results {
            color: var(--text-secondary);
            cursor: default;
        }
        
        .search-dropdown-item.no-results:hover {
            background-color: transparent;
            color: var(--text-secondary);
        }
        
        /* Map action buttons in header */
        .map-action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .map-action-buttons .action-button {
            min-width: auto;
            max-width: none;
            padding: 0.5rem 1rem;
            font-size: 0.8rem;
        }
        
        .map-action-buttons .button-icon {
            font-size: 1.2rem;
        }
        
        .map-action-buttons .button-title {
            font-size: 0.8rem;
            margin: 0;
        }
        
        /* Mobile-first map viewport */
        .map-viewport {
            flex: 1;
            position: relative;
            overflow: hidden;
            background: radial-gradient(ellipse at center, var(--secondary-bg) 0%, var(--primary-bg) 100%);
            touch-action: pan-x pan-y;
        }
        
        #galaxy-map {
            position: absolute;
            top: 0;
            left: 0;
            cursor: grab;
            touch-action: pan-x pan-y;
        }
        
        #galaxy-map:active {
            cursor: grabbing;
        }
        
        /* Device-responsive tooltip */
        .map-tooltip {
            position: absolute;
            background: var(--gradient-panel);
            border: 1px solid var(--primary-color);
            border-radius: 6px;
            padding: var(--button-padding);
            font-size: 0.8rem;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
            z-index: 100;
            max-width: 250px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(8px);
            line-height: 1.4;
        }
        
        .map-tooltip strong {
            color: var(--primary-color);
            display: block;
            margin-bottom: 0.25rem;
            font-size: 0.9rem;
        }
        
        .map-tooltip.visible {
            opacity: 1;
        }
        /* Route visualization enhancements */
        .route-highlight {
            animation: route-pulse 2s infinite;
        }

        @keyframes route-pulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }

        /* Location type specific styling */
        .location-colony {
            --location-color: #00ff88;
        }

        .location-space_station {
            --location-color: #00ffff;
        }

        .location-outpost {
            --location-color: #ffaa00;
        }

        .location-gate {
            --location-color: #ff00ff;
        }

        /* Danger level indicators */
        .danger-level-1 { color: #00ff00; }
        .danger-level-2 { color: #88ff00; }
        .danger-level-3 { color: #ffff00; }
        .danger-level-4 { color: #ff8800; }
        .danger-level-5 { color: #ff0000; }
        .corridor-active {
            stroke: var(--primary-color);
            stroke-width: 2;
            opacity: 1;
            filter: drop-shadow(0 0 5px var(--glow-primary));
        }
        
        .player-pulse {
            animation: player-pulse 2s infinite;
        }
        
        @keyframes player-pulse {
            0%, 100% { r: 4; opacity: 1; }
            50% { r: 8; opacity: 0.6; }
        }
        
        .npc-pulse {
            animation: npc-pulse 2.5s infinite;
        }
        
        @keyframes npc-pulse {
            0%, 100% { r: 3; opacity: 0.8; }
            50% { r: 6; opacity: 0.5; }
        }
        '''
    
    def get_wiki_css(self):
        """Get wiki-specific CSS"""
        return '''
        .wiki-container {
            position: relative;
            z-index: 10;
            width: 100%;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .wiki-header {
            background: var(--gradient-panel);
            border-bottom: 2px solid var(--primary-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .wiki-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
            text-shadow: 0 0 20px var(--glow-primary);
        }
        
        .wiki-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .wiki-tabs {
            background: var(--secondary-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 0 2rem;
            display: flex;
            gap: 0.5rem;
            overflow-x: auto;
        }
        
        .wiki-tab {
            padding: 1rem 1.5rem;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.3s ease;
            white-space: nowrap;
            min-height: var(--touch-target-size);
            display: flex;
            align-items: center;
            justify-content: center;
            touch-action: manipulation;
        }
        
        .wiki-tab:hover {
            color: var(--text-primary);
            background: rgba(0, 255, 255, 0.05);
        }
        
        .wiki-tab.active {
            color: var(--primary-color);
            border-bottom-color: var(--primary-color);
            text-shadow: 0 0 10px var(--glow-primary);
        }
        
        .wiki-content {
            flex: 1;
            padding: 2rem;
            overflow-y: auto;
        }
        
        .loading-message {
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
            font-size: 1.1rem;
        }
        
        .wiki-data {
            display: none;
        }
        
        .wiki-section {
            background: var(--gradient-panel);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        
        .wiki-section h3 {
            color: var(--primary-color);
            margin-bottom: 1rem;
            font-size: 1.2rem;
            text-shadow: 0 0 10px var(--glow-primary);
        }
        
        .wiki-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }
        
        .wiki-table th {
            background: var(--accent-bg);
            color: var(--primary-color);
            padding: 0.75rem;
            text-align: left;
            font-weight: 700;
            border-bottom: 2px solid var(--primary-color);
        }
        
        .wiki-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }
        
        .wiki-table tr:hover {
            background: rgba(0, 255, 255, 0.05);
        }
        
        .wiki-card {
            background: var(--accent-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .wiki-card h4 {
            color: var(--text-primary);
            margin-bottom: 0.5rem;
            font-size: 1rem;
        }
        
        .wiki-card p {
            color: var(--text-secondary);
            font-size: 0.9rem;
            line-height: 1.4;
        }
        
        .faction-loyalist { color: var(--primary-color); }
        .faction-outlaw { color: var(--error-color); }
        .faction-neutral { color: var(--text-secondary); }
        
        .wealth-rich { color: var(--success-color); }
        .wealth-moderate { color: var(--warning-color); }
        .wealth-poor { color: var(--error-color); }
        
        /* Wiki action buttons in header */
        .wiki-action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .wiki-action-buttons .action-button {
            min-width: auto;
            max-width: none;
            padding: 0.5rem 1rem;
            font-size: 0.8rem;
        }
        
        .wiki-action-buttons .button-icon {
            font-size: 1.2rem;
        }
        
        .wiki-action-buttons .button-title {
            font-size: 0.8rem;
            margin: 0;
        }
        
        /* Mobile-specific wiki improvements for touch accessibility */
        @media (max-width: 768px) {
            .wiki-header {
                padding: 0.75rem;
                flex-direction: column;
                gap: 0.75rem;
                align-items: stretch;
            }
            
            .header-section {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.5rem;
            }
            
            .wiki-title {
                font-size: 1.25rem;
                flex: 1;
                min-width: 0;
            }
            
            .wiki-status {
                font-size: 0.75rem;
                flex-shrink: 0;
            }
            
            .wiki-action-buttons {
                justify-content: center;
                gap: 0.75rem;
            }
            
            .wiki-action-buttons .action-button {
                padding: 0.5rem 0.75rem;
                min-height: 32px;
                min-width: 32px;
                flex: 1;
                max-width: 120px;
                font-size: 0.85rem;
            }
            
            .wiki-tabs {
                padding: 0 0.75rem;
                gap: 0.25rem;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
                -ms-overflow-style: none;
            }
            
            .wiki-tabs::-webkit-scrollbar {
                display: none;
            }
            
            .wiki-tab {
                padding: 0.5rem 1rem;
                font-size: 0.8rem;
                min-width: 32px;
                flex-shrink: 0;
                border-radius: 4px 4px 0 0;
            }
            
            .wiki-content {
                padding: 0.75rem;
            }
            
            .wiki-section {
                padding: 1rem;
                margin-bottom: 1rem;
            }
            
            .wiki-table {
                font-size: 0.75rem;
                display: block;
                overflow-x: auto;
                white-space: nowrap;
                -webkit-overflow-scrolling: touch;
            }
            
            .wiki-table thead,
            .wiki-table tbody,
            .wiki-table th,
            .wiki-table td,
            .wiki-table tr {
                display: block;
            }
            
            .wiki-table thead tr {
                position: absolute;
                top: -9999px;
                left: -9999px;
            }
            
            .wiki-table tr {
                border: 1px solid var(--border-color);
                margin-bottom: 0.5rem;
                padding: 0.5rem;
                background: var(--accent-bg);
                border-radius: 4px;
            }
            
            .wiki-table td {
                border: none;
                padding: 0.25rem 0;
                position: relative;
                padding-left: 35%;
                text-align: left;
            }
            
            .wiki-table td:before {
                content: attr(data-label) ": ";
                position: absolute;
                left: 0;
                width: 30%;
                padding-right: 0.5rem;
                white-space: nowrap;
                color: var(--primary-color);
                font-weight: bold;
                font-size: 0.7rem;
            }
            
            .wiki-card {
                margin-bottom: 0.75rem;
                padding: 0.75rem;
            }
            
            .wiki-card h4 {
                font-size: 0.9rem;
                margin-bottom: 0.4rem;
            }
            
            .wiki-card p {
                font-size: 0.8rem;
                line-height: 1.3;
            }
        }
        
        /* Extra small mobile devices */
        @media (max-width: 480px) {
            .wiki-header {
                padding: 0.5rem;
            }
            
            .wiki-title {
                font-size: 1.1rem;
            }
            
            .wiki-status {
                font-size: 0.7rem;
            }
            
            .wiki-action-buttons .action-button {
                padding: 0.6rem 0.8rem;
                font-size: 0.75rem;
            }
            
            .wiki-tab {
                padding: 0.6rem 1rem;
                font-size: 0.8rem;
            }
            
            .wiki-content {
                padding: 0.5rem;
            }
            
            .wiki-section {
                padding: 0.75rem;
                margin-bottom: 0.75rem;
            }
            
            .wiki-section h3 {
                font-size: 1.1rem;
            }
            
            .loading-message {
                padding: 2rem 1rem;
                font-size: 1rem;
            }
        }
        '''
    
    def get_map_script(self):
        """Get map JavaScript"""
        return '''
        class GalaxyMap {
            constructor() {
                this.canvas = document.getElementById('galaxy-map');
                this.ctx = this.canvas.getContext('2d');
                this.tooltip = document.getElementById('tooltip');
                this.locationInfo = document.getElementById('location-info');
                
                this.data = null;
                this.scale = 1;
                this.offsetX = 0;
                this.offsetY = 0;
                
                // Route planning
                this.routePlanningMode = false;
                this.routeStartLocation = null;
                this.plannedRoute = null;
                this.isDragging = false;
                this.dragStartX = 0;
                this.dragStartY = 0;
                this.mouseDownX = 0;
                this.mouseDownY = 0;
                this.hasDraggedSinceMouseDown = false;
                this.dragThreshold = 5; // pixels
                
                // Pinch-to-zoom state
                this.isPinching = false;
                this.initialPinchDistance = 0;
                this.initialScale = 1;
                this.pinchCenterX = 0;
                this.pinchCenterY = 0;
                this.touches = [];
                
                // Touch tap detection
                this.touchStartX = 0;
                this.touchStartY = 0;
                this.touchStartTime = 0;
                
                this.selectedLocation = null;
                this.selectedCorridor = null;
                
                // Search autocomplete properties
                this.searchTimeout = null;
                this.highlightedIndex = -1;
                this.currentSuggestions = [];
                this.hoveredCorridor = null;
                this.lastLocationHash = null;
                this.showLabels = false;
                this.showPlayers = false;
                this.showNPCs = false;
                this.showRoutes = true;
                this.showActiveRoutesOnly = false;
                
                // Animation timing for pulsing effects
                this.animationTime = 0;
                this.lastFrameTime = performance.now();
                this.isAnimating = false;
                
                this.init();
            }
            
            async init() {
                this.setupCanvas();
                this.setupEventListeners();
                await this.loadData();
                this.startUpdateLoop();
            }
            
            setupCanvas() {
                const resize = () => {
                    const viewport = this.canvas.parentElement;
                    this.canvas.width = viewport.clientWidth;
                    this.canvas.height = viewport.clientHeight;
                    this.render();
                };
                
                window.addEventListener('resize', resize);
                resize();
            }
            
            setupEventListeners() {
                // Mouse events
                this.canvas.addEventListener('mousedown', e => this.handleMouseDown(e));
                this.canvas.addEventListener('mousemove', e => this.handleMouseMove(e));
                this.canvas.addEventListener('mouseup', e => this.handleMouseUp(e));
                this.canvas.addEventListener('wheel', e => this.handleWheel(e));
                this.canvas.addEventListener('click', e => this.handleClick(e));
                
                // Touch events for mobile
                this.canvas.addEventListener('touchstart', e => this.handleTouchStart(e));
                this.canvas.addEventListener('touchmove', e => this.handleTouchMove(e));
                this.canvas.addEventListener('touchend', e => this.handleTouchEnd(e));
                
                // Search input - autocomplete support
                const searchInput = document.getElementById('search-input');
                const searchDropdown = document.getElementById('search-dropdown');
                
                searchInput.addEventListener('input', e => {
                    clearTimeout(this.searchTimeout);
                    const searchTerm = e.target.value.trim().toLowerCase();
                    
                    if (!searchTerm) {
                        this.hideSearchDropdown();
                        return;
                    }
                    
                    // Debounce search to avoid excessive filtering
                    this.searchTimeout = setTimeout(() => {
                        this.showSearchSuggestions(searchTerm);
                    }, 150);
                });
                
                searchInput.addEventListener('keydown', e => {
                    if (!searchDropdown.style.display || searchDropdown.style.display === 'none') {
                        if (e.key === 'Enter') {
                            this.searchLocation();
                        }
                        return;
                    }
                    
                    switch (e.key) {
                        case 'ArrowDown':
                            e.preventDefault();
                            this.highlightedIndex = Math.min(this.highlightedIndex + 1, this.currentSuggestions.length - 1);
                            this.updateHighlight();
                            break;
                        case 'ArrowUp':
                            e.preventDefault();
                            this.highlightedIndex = Math.max(this.highlightedIndex - 1, -1);
                            this.updateHighlight();
                            break;
                        case 'Enter':
                            e.preventDefault();
                            if (this.highlightedIndex >= 0 && this.currentSuggestions[this.highlightedIndex]) {
                                this.selectSuggestion(this.currentSuggestions[this.highlightedIndex]);
                            }
                            break;
                        case 'Escape':
                            this.hideSearchDropdown();
                            break;
                    }
                });
                
                searchInput.addEventListener('blur', e => {
                    // Delay hiding to allow click events on dropdown items
                    setTimeout(() => this.hideSearchDropdown(), 150);
                });
                
                searchInput.addEventListener('focus', e => {
                    if (e.target.value.trim()) {
                        this.showSearchSuggestions(e.target.value.trim().toLowerCase());
                    }
                });
                
                // Toggle controls
                document.getElementById('toggle-labels').addEventListener('change', e => {
                    this.showLabels = e.target.checked;
                    this.render();
                });
                
                document.getElementById('toggle-players').addEventListener('change', e => {
                    this.showPlayers = e.target.checked;
                    this.render();
                });
                
                document.getElementById('toggle-npcs').addEventListener('change', e => {
                    this.showNPCs = e.target.checked;
                    this.render();
                });
                
                document.getElementById('toggle-routes').addEventListener('change', e => {
                    this.showRoutes = e.target.checked;
                    this.render();
                });
                
                document.getElementById('toggle-active-routes-only').addEventListener('change', e => {
                    this.showActiveRoutesOnly = e.target.checked;
                    this.render();
                });
            }
            
            async loadData() {
                try {
                    const response = await fetch('/api/map-data');
                    this.data = await response.json();
                    this.updateLastUpdate();
                    this.populateRouteDropdowns();
                    this.updateZoomDisplay();
                    this.render();
                    
                    // Run pathfinding test after data is loaded
                    setTimeout(() => {
                        this.testPathfinding();
                    }, 1000); // Delay to ensure rendering is complete
                } catch (error) {
                    console.error('Failed to load map data:', error);
                }
            }
            
            startUpdateLoop() {
                setInterval(() => this.loadData(), 5000); // Update every 5 seconds
            }
            
            updateLastUpdate() {
                const now = new Date();
                const timeStr = now.toLocaleTimeString();
                document.getElementById('last-update').textContent = `Updated: ${timeStr}`;
                
                // Update galaxy name and current game time
                if (this.data) {
                    const galaxyNameEl = document.getElementById('galaxy-name');
                    const currentTimeEl = document.getElementById('current-time');
                    
                    if (this.data.galaxy_info && this.data.galaxy_info.name) {
                        galaxyNameEl.textContent = this.data.galaxy_info.name;
                    } else {
                        galaxyNameEl.textContent = 'Galaxy Map';
                    }
                    
                    if (this.data.current_time) {
                        currentTimeEl.textContent = this.data.current_time;
                    } else {
                        currentTimeEl.textContent = 'Time unknown';
                    }
                }
            }
            
            worldToScreen(x, y) {
                return {
                    x: (x * this.scale) + this.offsetX + this.canvas.width / 2,
                    y: (y * this.scale) + this.offsetY + this.canvas.height / 2
                };
            }
            
            screenToWorld(x, y) {
                return {
                    x: (x - this.canvas.width / 2 - this.offsetX) / this.scale,
                    y: (y - this.canvas.height / 2 - this.offsetY) / this.scale
                };
            }
            
            // Calculate distance between two touch points
            getTouchDistance(touch1, touch2) {
                const dx = touch1.clientX - touch2.clientX;
                const dy = touch1.clientY - touch2.clientY;
                return Math.sqrt(dx * dx + dy * dy);
            }
            
            shouldElementBeDimmed(elementId, elementType) {
                // If a route is plotted, dim elements not part of the route
                if (this.plannedRoute && this.plannedRoute.length > 1) {
                    if (elementType === 'location') {
                        // Don't dim locations that are part of the planned route
                        return !this.plannedRoute.includes(String(elementId));
                    }
                    
                    if (elementType === 'corridor') {
                        const corridor = this.data.corridors.find(c => c.id === elementId);
                        if (corridor) {
                            // Don't dim corridors that are part of the planned route
                            return !this.isCorridorInRoute(corridor, this.plannedRoute);
                        }
                        return true;
                    }
                }
                
                // If nothing is selected, don't dim anything
                if (!this.selectedLocation && !this.selectedCorridor) {
                    return false;
                }
                
                if (elementType === 'location') {
                    // Don't dim selected location
                    if (this.selectedLocation === elementId) {
                        return false;
                    }
                    
                    // Don't dim locations connected to selected corridor
                    if (this.selectedCorridor && 
                        (this.selectedCorridor.origin == elementId || this.selectedCorridor.destination == elementId)) {
                        return false;
                    }
                    
                    // Don't dim locations directly connected to selected location
                    if (this.selectedLocation) {
                        for (const corridor of this.data.corridors) {
                            if ((corridor.origin == this.selectedLocation && corridor.destination == elementId) ||
                                (corridor.destination == this.selectedLocation && corridor.origin == elementId)) {
                                return false;
                            }
                        }
                    }
                    
                    // Dim everything else
                    return true;
                }
                
                if (elementType === 'corridor') {
                    // Don't dim selected corridor
                    if (this.selectedCorridor && this.selectedCorridor.id === elementId) {
                        return false;
                    }
                    
                    // Don't dim corridors connected to selected location
                    if (this.selectedLocation) {
                        const corridor = this.data.corridors.find(c => c.id === elementId);
                        if (corridor && (corridor.origin == this.selectedLocation || corridor.destination == this.selectedLocation)) {
                            return false;
                        }
                    }
                    
                    // Dim everything else
                    return true;
                }
                
                return false;
            }
            
            applyDimming(color) {
                // Convert hex color to rgba with reduced opacity
                if (color.startsWith('#')) {
                    const hex = color.slice(1);
                    const r = parseInt(hex.substr(0, 2), 16);
                    const g = parseInt(hex.substr(2, 2), 16);
                    const b = parseInt(hex.substr(4, 2), 16);
                    return `rgba(${r}, ${g}, ${b}, 0.2)`;
                }
                
                // If already rgba, reduce the alpha value
                if (color.startsWith('rgba')) {
                    return color.replace(/[\\d\\.]+\\)$/g, '0.2)');
                }
                
                // If rgb, convert to rgba with low alpha
                if (color.startsWith('rgb')) {
                    return color.replace('rgb', 'rgba').replace(')', ', 0.2)');
                }
                
                // Fallback for other formats
                return color;
            }

            render() {
                if (!this.data) return;
                
                // Update animation timing
                const currentTime = performance.now();
                const deltaTime = currentTime - this.lastFrameTime;
                this.animationTime += deltaTime * 0.003; // Control animation speed
                this.lastFrameTime = currentTime;
                
                // Clear canvas
                this.ctx.fillStyle = '#000408';
                this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                
                // Draw grid
                this.drawGrid();
                
                // Draw corridors
                if (this.showRoutes) {
                    this.drawCorridors();
                }
                
                // Draw planned route
                if (this.plannedRoute) {
                    this.drawPlannedRoute();
                }
                
                // Draw locations
                this.drawLocations();
                
                // Draw players
                if (this.showPlayers) {
                    this.drawPlayers();
                }
                
                // Draw NPCs
                if (this.showNPCs) {
                    this.drawNPCs();
                }
                
                // Continue animation loop if needed (for pulsing effects or traveling animations)
                const hasTravelingEntities = this.showRoutes && (
                    Object.values(this.data.players).some(p => p.traveling) ||
                    Object.values(this.data.npcs).some(n => n.traveling)
                );
                
                if ((this.showPlayers && Object.keys(this.data.players).length > 0) || 
                    (this.showNPCs && Object.keys(this.data.npcs).length > 0) ||
                    hasTravelingEntities) {
                    if (!this.isAnimating) {
                        this.isAnimating = true;
                        this.animationLoop();
                    }
                } else {
                    this.isAnimating = false;
                }
            }
            
            animationLoop() {
                if (this.isAnimating) {
                    this.render();
                    requestAnimationFrame(() => this.animationLoop());
                }
            }
            
            drawGrid() {
                this.ctx.strokeStyle = 'rgba(0, 136, 204, 0.1)';
                this.ctx.lineWidth = 1;
                
                const gridSize = 20 * this.scale;
                const startX = (Math.floor(-this.offsetX / gridSize) - 1) * gridSize;
                const startY = (Math.floor(-this.offsetY / gridSize) - 1) * gridSize;
                const endX = startX + this.canvas.width + gridSize * 2;
                const endY = startY + this.canvas.height + gridSize * 2;
                
                for (let x = startX; x <= endX; x += gridSize) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(x + this.offsetX, 0);
                    this.ctx.lineTo(x + this.offsetX, this.canvas.height);
                    this.ctx.stroke();
                }
                
                for (let y = startY; y <= endY; y += gridSize) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(0, y + this.offsetY);
                    this.ctx.lineTo(this.canvas.width, y + this.offsetY);
                    this.ctx.stroke();
                }
            }
            
            drawCorridors() {
                for (const corridor of this.data.corridors) {
                    const origin = this.data.locations[corridor.origin];
                    const dest = this.data.locations[corridor.destination];
                    
                    if (!origin || !dest) continue;
                    
                    // Check if any players/NPCs are in this corridor
                    const travelingPlayers = Object.values(this.data.players).filter(p => 
                        p.traveling && p.corridor_id === corridor.id
                    );
                    const travelingNPCs = Object.values(this.data.npcs).filter(n => 
                        n.traveling && n.corridor_id === corridor.id
                    );
                    const hasTravelers = travelingPlayers.length > 0 || travelingNPCs.length > 0;
                    
                    // Skip this corridor if "Active Routes Only" is enabled and no travelers
                    if (this.showActiveRoutesOnly && !hasTravelers) {
                        continue;
                    }
                    
                    const start = this.worldToScreen(origin.x, origin.y);
                    const end = this.worldToScreen(dest.x, dest.y);
                    
                    // Determine if this corridor should be dimmed
                    const shouldBeDimmed = this.shouldElementBeDimmed(corridor.id, 'corridor');
                    
                    // Determine if this corridor is selected or related to selected location
                    const isSelected = this.selectedCorridor && 
                        this.selectedCorridor.id === corridor.id;
                    
                    // Check if this corridor is part of the planned route
                    const isPartOfPlannedRoute = this.plannedRoute && this.isCorridorInRoute(corridor, this.plannedRoute);
                    
                    // Only highlight location-related corridors if there's no planned route
                    const isRelatedToLocation = !this.plannedRoute && this.selectedLocation && 
                        (corridor.origin == this.selectedLocation || 
                         corridor.destination == this.selectedLocation);
                    const isHovered = this.hoveredCorridor && 
                        this.hoveredCorridor.id === corridor.id;
                    
                    // Base line width - increased for better visibility
                    let lineWidth = Math.max(3, Math.min(8, 5 / Math.sqrt(this.scale)));
                    
                    // Determine corridor type and styling
                    let strokeStyle = 'rgba(0, 51, 68, 0.3)'; // Default faded
                    let dashPattern = [];
                    
                    if (corridor.corridor_type === 'local_space' || (corridor.name && corridor.name.includes('Approach'))) {
                        // Local space - dotted line
                        strokeStyle = shouldBeDimmed ? 'rgba(136, 255, 136, 0.15)' : 'rgba(136, 255, 136, 0.5)'; // Light green
                        dashPattern = [5, 5];
                    } else if (corridor.corridor_type === 'ungated') {
                        // Ungated - dashed line
                        strokeStyle = shouldBeDimmed ? 'rgba(255, 102, 0, 0.15)' : 'rgba(255, 102, 0, 0.5)'; // Orange
                        dashPattern = [10, 5];
                    } else {
                        // Gated - solid line
                        strokeStyle = shouldBeDimmed ? 'rgba(0, 204, 204, 0.15)' : 'rgba(0, 204, 204, 0.5)'; // Cyan
                    }
                    
                    // Apply highlighting
                    // Calculate zoom-based glow intensity for corridors
                    const corridorGlowIntensity = this.scale > 2 ? 1 : 
                                                 this.scale > 1 ? 0.7 : 
                                                 this.scale > 0.5 ? 0.3 : 0;
                    
                    if (isSelected) {
                        strokeStyle = '#00ffff';
                        lineWidth = Math.max(4, Math.min(10, 8 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 20 * corridorGlowIntensity;
                        this.ctx.shadowColor = '#00ffff';
                    } else if (isPartOfPlannedRoute) {
                        // Highlight corridors that are part of the planned route
                        if (corridor.corridor_type === 'local_space' || corridor.name && corridor.name.includes('Approach')) {
                            strokeStyle = '#88ff88';
                        } else if (corridor.corridor_type === 'ungated') {
                            strokeStyle = '#ff6600';
                        } else {
                            strokeStyle = '#00cccc';
                        }
                        lineWidth = Math.max(3, Math.min(8, 6 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 10 * corridorGlowIntensity;
                        this.ctx.shadowColor = strokeStyle;
                    } else if (isRelatedToLocation) {
                        // Highlight routes from/to selected location
                        if (corridor.corridor_type === 'local_space' || corridor.name && corridor.name.includes('Approach')) {
                            strokeStyle = '#88ff88';
                        } else if (corridor.corridor_type === 'ungated') {
                            strokeStyle = '#ff6600';
                        } else {
                            strokeStyle = '#00cccc';
                        }
                        lineWidth = Math.max(3, Math.min(8, 6 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 10 * corridorGlowIntensity;
                        this.ctx.shadowColor = strokeStyle;
                    } else if (isHovered) {
                        lineWidth = Math.max(3, Math.min(8, 6 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 15 * corridorGlowIntensity;
                        this.ctx.shadowColor = strokeStyle;
                    } else if (hasTravelers) {
                        // Enhanced styling for corridors with travelers
                        strokeStyle = '#00aaff';
                        lineWidth = Math.max(4, Math.min(10, 7 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = shouldBeDimmed ? 0 : 15 * corridorGlowIntensity;
                        this.ctx.shadowColor = '#00aaff';
                    } else {
                        this.ctx.shadowBlur = 0;
                    }
                    
                    this.ctx.strokeStyle = strokeStyle;
                    this.ctx.lineWidth = lineWidth;
                    
                    // Draw the line with dash pattern if applicable
                    this.ctx.beginPath();
                    if (dashPattern.length > 0) {
                        this.ctx.setLineDash(dashPattern);
                    }
                    this.ctx.moveTo(start.x, start.y);
                    this.ctx.lineTo(end.x, end.y);
                    this.ctx.stroke();
                    this.ctx.setLineDash([]); // Reset dash
                    
                    // Draw animated flow effects for traveling entities
                    if (hasTravelers) {
                        this.drawTravelingAnimation(start, end, travelingPlayers, travelingNPCs);
                    }
                    
                    // Draw direction indicators for selected corridors
                    if (isSelected || isRelatedToLocation || isPartOfPlannedRoute) {
                        this.drawCorridorArrow(start, end, strokeStyle);
                    }
                }
                
                this.ctx.shadowBlur = 0;
            }
            
            drawTravelingAnimation(start, end, travelingPlayers, travelingNPCs) {
                this.ctx.save();
                
                // Calculate line properties
                const dx = end.x - start.x;
                const dy = end.y - start.y;
                const length = Math.sqrt(dx * dx + dy * dy);
                const unitX = dx / length;
                const unitY = dy / length;
                
                // Animation parameters
                const flowSpeed = this.animationTime * 0.5;
                const dotSpacing = Math.max(30, 40 / Math.sqrt(this.scale));
                const numDots = Math.floor(length / dotSpacing) + 2;
                
                // Draw flowing particles for players
                if (travelingPlayers.length > 0) {
                    for (let i = 0; i < numDots; i++) {
                        const progress = ((i * dotSpacing + flowSpeed * 60) % (length + dotSpacing)) / length;
                        if (progress > 1) continue;
                        
                        const x = start.x + progress * dx;
                        const y = start.y + progress * dy;
                        
                        // Fade effect based on position
                        const fadeIn = Math.min(1, progress * 4);
                        const fadeOut = Math.min(1, (1 - progress) * 4);
                        const alpha = Math.min(fadeIn, fadeOut) * 0.8;
                        
                        // Reduce travel animation glow when zoomed out
                        const travelGlowFactor = this.scale > 1 ? 1 : this.scale > 0.5 ? 0.5 : 0;
                        
                        this.ctx.globalAlpha = alpha;
                        this.ctx.fillStyle = '#00ddff';
                        this.ctx.shadowBlur = Math.min(10, 8 / Math.sqrt(this.scale)) * travelGlowFactor;
                        this.ctx.shadowColor = '#00ddff';
                        
                        const dotSize = Math.max(3, 4 / Math.sqrt(this.scale));
                        this.ctx.beginPath();
                        this.ctx.arc(x, y, dotSize, 0, Math.PI * 2);
                        this.ctx.fill();
                    }
                }
                
                // Draw flowing particles for NPCs (slightly different pattern)
                if (travelingNPCs.length > 0) {
                    for (let i = 0; i < numDots; i++) {
                        const progress = ((i * dotSpacing + flowSpeed * 45) % (length + dotSpacing)) / length;
                        if (progress > 1) continue;
                        
                        const x = start.x + progress * dx;
                        const y = start.y + progress * dy;
                        
                        // Offset NPCs slightly perpendicular to the line
                        const offsetX = -unitY * 3;
                        const offsetY = unitX * 3;
                        
                        // Fade effect
                        const fadeIn = Math.min(1, progress * 4);
                        const fadeOut = Math.min(1, (1 - progress) * 4);
                        const alpha = Math.min(fadeIn, fadeOut) * 0.6;
                        
                        this.ctx.globalAlpha = alpha;
                        this.ctx.fillStyle = '#ffaa00';
                        this.ctx.shadowBlur = Math.min(8, 6 / Math.sqrt(this.scale)) * travelGlowFactor;
                        this.ctx.shadowColor = '#ffaa00';
                        
                        const dotSize = Math.max(2, 3 / Math.sqrt(this.scale));
                        this.ctx.beginPath();
                        this.ctx.moveTo(x + offsetX, y + offsetY - dotSize);
                        this.ctx.lineTo(x + offsetX + dotSize, y + offsetY);
                        this.ctx.lineTo(x + offsetX, y + offsetY + dotSize);
                        this.ctx.lineTo(x + offsetX - dotSize, y + offsetY);
                        this.ctx.closePath();
                        this.ctx.fill();
                    }
                }
                
                this.ctx.restore();
            }
            
            drawCorridorArrow(start, end, color) {
                const angle = Math.atan2(end.y - start.y, end.x - start.x);
                const midX = (start.x + end.x) / 2;
                const midY = (start.y + end.y) / 2;
                
                const arrowLength = 15;
                const arrowAngle = Math.PI / 6;
                
                this.ctx.strokeStyle = color;
                this.ctx.fillStyle = color;
                this.ctx.lineWidth = 2;
                
                // Draw arrowhead
                this.ctx.beginPath();
                this.ctx.moveTo(midX, midY);
                this.ctx.lineTo(
                    midX - arrowLength * Math.cos(angle - arrowAngle),
                    midY - arrowLength * Math.sin(angle - arrowAngle)
                );
                this.ctx.moveTo(midX, midY);
                this.ctx.lineTo(
                    midX - arrowLength * Math.cos(angle + arrowAngle),
                    midY - arrowLength * Math.sin(angle + arrowAngle)
                );
                this.ctx.stroke();
            }
            
            drawLocations() {
                // Define importance order: gates (background) -> outposts -> space_stations -> colonies (foreground)
                const renderOrder = ['gate', 'outpost', 'space_station', 'colony'];
                
                // Render each location type in order of importance
                for (const locationType of renderOrder) {
                    for (const [id, location] of Object.entries(this.data.locations)) {
                        // Skip if this location is not the current type being rendered
                        if (location.type !== locationType) continue;
                        
                        const pos = this.worldToScreen(location.x, location.y);
                        
                        // Skip if off-screen
                        if (pos.x < -50 || pos.x > this.canvas.width + 50 ||
                            pos.y < -50 || pos.y > this.canvas.height + 50) continue;
                        
                        // Determine if this location should be dimmed
                        const shouldBeDimmed = this.shouldElementBeDimmed(id, 'location');
                        
                        // Determine color based on type
                        const colors = {
                            colony: '#00ff88',
                            space_station: '#00ffff',
                            outpost: '#ffaa00',
                            gate: '#ff00ff'
                        };
                        
                        let color = colors[location.type] || '#ffffff';
                        
                        // Apply dimming if needed
                        if (shouldBeDimmed) {
                            color = this.applyDimming(color);
                        }
                        
                        // Increased base sizes for better visibility
                        const baseSize = location.type === 'gate' ? 25 : 20;
                        const size = Math.max(baseSize / Math.sqrt(this.scale), 12);
                        
                        // Check if location is connected to selected corridor
                        const isCorridorDestination = this.selectedCorridor && 
                            (this.selectedCorridor.origin == id || 
                             this.selectedCorridor.destination == id);
                        
                        // Draw location
                        // Draw location based on type
                        this.ctx.fillStyle = color;
                        // Reduce glow effects when zoomed out for performance
                        const glowIntensity = this.scale > 1 ? Math.min(30, 25 / Math.sqrt(this.scale)) : 
                                             this.scale > 0.5 ? Math.min(15, 12 / Math.sqrt(this.scale)) : 0;
                        this.ctx.shadowBlur = shouldBeDimmed ? 0 : glowIntensity;
                        this.ctx.shadowColor = color;

                        if (location.type === 'gate') {
                            // Draw diamond for gates
                            this.ctx.beginPath();
                            this.ctx.moveTo(pos.x, pos.y - size);
                            this.ctx.lineTo(pos.x + size, pos.y);
                            this.ctx.lineTo(pos.x, pos.y + size);
                            this.ctx.lineTo(pos.x - size, pos.y);
                            this.ctx.closePath();
                            this.ctx.fill();
                        } else if (location.type === 'space_station') {
                            // Draw triangle for space stations
                            this.ctx.beginPath();
                            this.ctx.moveTo(pos.x, pos.y - size);
                            this.ctx.lineTo(pos.x + size * 0.866, pos.y + size * 0.5);
                            this.ctx.lineTo(pos.x - size * 0.866, pos.y + size * 0.5);
                            this.ctx.closePath();
                            this.ctx.fill();
                        } else if (location.type === 'outpost') {
                            // Draw square for outposts
                            this.ctx.fillRect(pos.x - size, pos.y - size, size * 2, size * 2);
                        } else {
                            // Draw circle for colonies and other types
                            this.ctx.beginPath();
                            this.ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
                            this.ctx.fill();
                        }
                        
                        // Draw selection/highlight indicators
                        if (this.selectedLocation === id || isCorridorDestination) {
                            this.ctx.strokeStyle = color;
                            this.ctx.lineWidth = 3;
                            this.ctx.beginPath();
                            this.ctx.arc(pos.x, pos.y, size + 8, 0, Math.PI * 2);
                            this.ctx.stroke();
                            
                            // Pulsing effect for corridor destinations
                            if (isCorridorDestination) {
                                const time = Date.now() / 1000;
                                const pulseSize = size + 12 + Math.sin(time * 3) * 4;
                                this.ctx.globalAlpha = 0.3;
                                this.ctx.beginPath();
                                this.ctx.arc(pos.x, pos.y, pulseSize, 0, Math.PI * 2);
                                this.ctx.stroke();
                                this.ctx.globalAlpha = 1;
                            }
                        }
                        
                        // Draw name if labels are enabled and zoomed in enough
                        if (this.showLabels && this.scale > 0.8) {
                            this.ctx.fillStyle = '#ffffff';
                            this.ctx.font = `${Math.max(12, 14 / Math.sqrt(this.scale))}px 'Tektur', monospace`;
                            this.ctx.textAlign = 'center';
                            this.ctx.textBaseline = 'top';
                            // Reduce text glow when zoomed out for performance
                            const textGlowFactor = this.scale > 2 ? 1 : this.scale > 1 ? 0.7 : 0.3;
                            this.ctx.shadowBlur = 5 * textGlowFactor;
                            this.ctx.shadowColor = '#000000';
                            this.ctx.fillText(location.name, pos.x, pos.y + size + 5);
                        }
                    }
                }
                
                this.ctx.shadowBlur = 0;
            }
            
            drawPlayers() {
                for (const [id, player] of Object.entries(this.data.players)) {
                    if (!player.location) continue;
                    
                    const location = this.data.locations[player.location];
                    if (!location) continue;
                    
                    const pos = this.worldToScreen(location.x, location.y);
                    
                    // Enhanced player colors based on alignment
                    let playerColor = '#00aaff'; // Default blue
                    let glowColor = '#0088cc';
                    
                    if (player.alignment === 'loyalist' || player.alignment === 'loyal') {
                        playerColor = '#00ff44';
                        glowColor = '#00cc33';
                    } else if (player.alignment === 'outlaw' || player.alignment === 'bandit') {
                        playerColor = '#ff4400';
                        glowColor = '#cc3300';
                    }
                    
                    // Pulsing animation calculations
                    const pulseOffset = (id.length % 10) * 0.2; // Stagger animations
                    const pulsePhase = this.animationTime + pulseOffset;
                    const pulseFactor = 0.8 + 0.4 * Math.sin(pulsePhase * 2);
                    const ringPulseFactor = 0.5 + 0.5 * Math.sin(pulsePhase * 3);
                    
                    // Base size with inverse scaling
                    const baseSize = Math.max(12 / Math.sqrt(this.scale), 8);
                    const pulseSize = baseSize * pulseFactor;
                    const ringSize = baseSize * (1.5 + ringPulseFactor * 0.8);
                    
                    this.ctx.save();
                    
                    // Calculate player glow intensity based on zoom level
                    const playerGlowFactor = this.scale > 2 ? 1 : 
                                            this.scale > 1 ? 0.7 : 
                                            this.scale > 0.5 ? 0.4 : 0;
                    
                    // Only draw complex glow effects when zoomed in enough
                    if (playerGlowFactor > 0) {
                        // Draw pulsing outer ring
                        this.ctx.globalAlpha = 0.3 * ringPulseFactor * playerGlowFactor;
                        this.ctx.fillStyle = glowColor;
                        this.ctx.shadowBlur = Math.min(30, 25 / Math.sqrt(this.scale)) * playerGlowFactor;
                        this.ctx.shadowColor = glowColor;
                        
                        this.ctx.beginPath();
                        this.ctx.arc(pos.x, pos.y, ringSize, 0, Math.PI * 2);
                        this.ctx.fill();
                        
                        // Draw middle ring
                        this.ctx.globalAlpha = 0.6 * playerGlowFactor;
                        this.ctx.fillStyle = playerColor;
                        this.ctx.shadowBlur = Math.min(20, 15 / Math.sqrt(this.scale)) * playerGlowFactor;
                        this.ctx.shadowColor = playerColor;
                        
                        this.ctx.beginPath();
                        this.ctx.arc(pos.x, pos.y, pulseSize * 1.2, 0, Math.PI * 2);
                        this.ctx.fill();
                    }
                    
                    // Draw core player indicator
                    this.ctx.globalAlpha = 1.0;
                    this.ctx.fillStyle = '#ffffff';
                    this.ctx.shadowBlur = Math.min(15, 10 / Math.sqrt(this.scale)) * Math.max(0.3, playerGlowFactor);
                    this.ctx.shadowColor = playerColor;
                    
                    this.ctx.beginPath();
                    this.ctx.arc(pos.x, pos.y, pulseSize, 0, Math.PI * 2);
                    this.ctx.fill();
                    
                    // Draw small inner core
                    this.ctx.globalAlpha = 1.0;
                    this.ctx.fillStyle = playerColor;
                    this.ctx.shadowBlur = 0;
                    
                    this.ctx.beginPath();
                    this.ctx.arc(pos.x, pos.y, pulseSize * 0.4, 0, Math.PI * 2);
                    this.ctx.fill();
                    
                    this.ctx.restore();
                }
            }
            
            drawNPCs() {
                for (const [id, npc] of Object.entries(this.data.npcs)) {
                    if (!npc.location) continue;
                    
                    const location = this.data.locations[npc.location];
                    if (!location) continue;
                    
                    const pos = this.worldToScreen(location.x, location.y);
                    
                    // Enhanced NPC colors based on alignment
                    let npcColor = '#ffaa00'; // Default orange (neutral)
                    let glowColor = '#cc8800';
                    
                    if (npc.alignment === 'hostile' || npc.alignment === 'pirate' || 
                        npc.alignment === 'bandit') {
                        npcColor = '#ff3300';  // Bright red for hostiles
                        glowColor = '#cc2200';
                    } else if (npc.alignment === 'friendly' || npc.alignment === 'loyal') {
                        npcColor = '#00cc44';  // Green for friendlies  
                        glowColor = '#009933';
                    }
                    
                    // Pulsing animation calculations
                    const pulseOffset = (id.charCodeAt(0) % 10) * 0.15; // Stagger based on ID
                    const pulsePhase = this.animationTime + pulseOffset;
                    const pulseFactor = 0.7 + 0.4 * Math.sin(pulsePhase * 1.8);
                    const glowPulseFactor = 0.4 + 0.6 * Math.sin(pulsePhase * 2.5);
                    
                    // Base size with inverse scaling
                    const baseSize = Math.max(10 / Math.sqrt(this.scale), 6);
                    const pulseSize = baseSize * pulseFactor;
                    const glowSize = baseSize * (1.8 + glowPulseFactor * 0.5);
                    
                    this.ctx.save();
                    
                    // Calculate NPC glow intensity based on zoom level
                    const npcGlowFactor = this.scale > 2 ? 1 : 
                                         this.scale > 1 ? 0.6 : 
                                         this.scale > 0.5 ? 0.3 : 0;
                    
                    // Only draw complex glow effects when zoomed in enough
                    if (npcGlowFactor > 0) {
                        // Draw pulsing glow effect
                        this.ctx.globalAlpha = 0.25 * glowPulseFactor * npcGlowFactor;
                        this.ctx.fillStyle = glowColor;
                        this.ctx.shadowBlur = Math.min(25, 20 / Math.sqrt(this.scale)) * npcGlowFactor;
                        this.ctx.shadowColor = glowColor;
                        
                        this.ctx.beginPath();
                        this.ctx.moveTo(pos.x, pos.y - glowSize);
                        this.ctx.lineTo(pos.x + glowSize * 0.8, pos.y);
                        this.ctx.lineTo(pos.x, pos.y + glowSize);
                        this.ctx.lineTo(pos.x - glowSize * 0.8, pos.y);
                        this.ctx.closePath();
                        this.ctx.fill();
                    }
                    
                    // Draw main NPC body
                    this.ctx.globalAlpha = 0.9;
                    this.ctx.fillStyle = npcColor;
                    this.ctx.shadowBlur = Math.min(15, 12 / Math.sqrt(this.scale)) * Math.max(0.2, npcGlowFactor);
                    this.ctx.shadowColor = npcColor;
                    
                    this.ctx.beginPath();
                    this.ctx.moveTo(pos.x, pos.y - pulseSize);
                    this.ctx.lineTo(pos.x + pulseSize * 0.7, pos.y);
                    this.ctx.lineTo(pos.x, pos.y + pulseSize);
                    this.ctx.lineTo(pos.x - pulseSize * 0.7, pos.y);
                    this.ctx.closePath();
                    this.ctx.fill();
                    
                    // Draw bright core
                    this.ctx.globalAlpha = 1.0;
                    this.ctx.fillStyle = '#ffffff';
                    this.ctx.shadowBlur = Math.min(8, 6 / Math.sqrt(this.scale)) * Math.max(0.2, npcGlowFactor);
                    this.ctx.shadowColor = npcColor;
                    
                    this.ctx.beginPath();
                    this.ctx.moveTo(pos.x, pos.y - pulseSize * 0.4);
                    this.ctx.lineTo(pos.x + pulseSize * 0.3, pos.y);
                    this.ctx.lineTo(pos.x, pos.y + pulseSize * 0.4);
                    this.ctx.lineTo(pos.x - pulseSize * 0.3, pos.y);
                    this.ctx.closePath();
                    this.ctx.fill();
                    
                    this.ctx.restore();
                }
            }
            
            handleMouseDown(e) {
                this.isDragging = true;
                this.dragStartX = e.clientX - this.offsetX;
                this.dragStartY = e.clientY - this.offsetY;
                this.mouseDownX = e.clientX;
                this.mouseDownY = e.clientY;
                this.hasDraggedSinceMouseDown = false;
                this.canvas.style.cursor = 'grabbing';
            }
            
            handleMouseMove(e) {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                // Check if we've moved beyond the drag threshold
                if (this.isDragging && !this.hasDraggedSinceMouseDown) {
                    const deltaX = Math.abs(e.clientX - this.mouseDownX);
                    const deltaY = Math.abs(e.clientY - this.mouseDownY);
                    if (deltaX > this.dragThreshold || deltaY > this.dragThreshold) {
                        this.hasDraggedSinceMouseDown = true;
                    }
                }
                
                if (this.isDragging) {
                    this.offsetX = e.clientX - this.dragStartX;
                    this.offsetY = e.clientY - this.dragStartY;
                    this.render();
                } else {
                    const worldPos = this.screenToWorld(x, y);
                    let hoveredLocation = null;
                    let hoveredCorridor = null;
                    
                    // Check corridor hover
                    if (this.showRoutes) {
                        for (const corridor of this.data.corridors) {
                            // Skip if active routes only mode and no travelers
                            if (this.showActiveRoutesOnly) {
                                const hasTravelers = Object.values(this.data.players).some(p => 
                                    p.traveling && p.corridor_id === corridor.id
                                ) || Object.values(this.data.npcs).some(n => 
                                    n.traveling && n.corridor_id === corridor.id
                                );
                                if (!hasTravelers) continue;
                            }
                            
                            if (this.isPointNearLine(worldPos, corridor)) {
                                hoveredCorridor = corridor;
                                break;
                            }
                        }
                    }
                    
                    // Check location hover
                    if (!hoveredCorridor) {
                        for (const [id, location] of Object.entries(this.data.locations)) {
                            const dist = Math.sqrt(
                                Math.pow(location.x - worldPos.x, 2) + 
                                Math.pow(location.y - worldPos.y, 2)
                            );
                            
                            if (dist < 15 / this.scale) {
                                hoveredLocation = location;
                                break;
                            }
                        }
                    }
                    
                    this.hoveredCorridor = hoveredCorridor;
                    
                    if (hoveredLocation) {
                        this.showTooltip(x + rect.left, y + rect.top, hoveredLocation);
                        this.canvas.style.cursor = 'pointer';
                    } else if (hoveredCorridor) {
                        this.showCorridorTooltip(x + rect.left, y + rect.top, hoveredCorridor);
                        this.canvas.style.cursor = 'pointer';
                    } else {
                        this.hideTooltip();
                        this.canvas.style.cursor = 'grab';
                    }
                }
            }
            
            handleMouseUp(e) {
                this.isDragging = false;
                this.canvas.style.cursor = 'grab';
            }
            
            handleWheel(e) {
                e.preventDefault();
                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                const delta = e.deltaY > 0 ? 0.95 : 1.05;
                this.zoomToPoint(delta, mouseX, mouseY);
            }
            
            handleClick(e) {
                // Only process clicks if no significant drag occurred
                if (this.hasDraggedSinceMouseDown) {
                    return;
                }
                
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                this.processInteraction(x, y);
            }
            
            // Unified method to handle both mouse clicks and touch taps
            processInteraction(x, y) {
                const worldPos = this.screenToWorld(x, y);
                
                // Check for corridor click first (they're drawn underneath)
                let clickedCorridor = null;
                if (this.showRoutes) {
                    for (const corridor of this.data.corridors) {
                        // Skip if active routes only mode and no travelers
                        if (this.showActiveRoutesOnly) {
                            const hasTravelers = Object.values(this.data.players).some(p => 
                                p.traveling && p.corridor_id === corridor.id
                            ) || Object.values(this.data.npcs).some(n => 
                                n.traveling && n.corridor_id === corridor.id
                            );
                            if (!hasTravelers) continue;
                        }
                        
                        if (this.isPointNearLine(worldPos, corridor)) {
                            clickedCorridor = corridor;
                            break;
                        }
                    }
                }
                
                // Check for location click
                let clickedLocation = null;
                for (const [id, location] of Object.entries(this.data.locations)) {
                    const dist = Math.sqrt(
                        Math.pow(location.x - worldPos.x, 2) + 
                        Math.pow(location.y - worldPos.y, 2)
                    );
                    
                    const hoverRadius = Math.max(25 / Math.sqrt(this.scale), 15);
                    if (dist < hoverRadius / this.scale) {
                        clickedLocation = { id, location };
                        break;
                    }
                }
                
                // Handle selection
                if (clickedLocation) {
                    // Check if we're in route planning mode
                    if (this.routePlanningMode && this.routeStartLocation) {
                        // Plot route from start to clicked location
                        if (this.plotRoute(this.routeStartLocation, clickedLocation.id)) {
                            // Route successfully plotted, exit route planning mode
                            this.routePlanningMode = false;
                            this.routeStartLocation = null;
                            
                            // Update status to show success
                            const statusEl = document.getElementById('route-planning-status');
                            if (statusEl) {
                                statusEl.textContent = 'Route plotted successfully!';
                                statusEl.style.color = '#00ff00';
                            }
                        }
                    } else if (!this.plannedRoute) {
                        // Normal location selection (only if no route is plotted)
                        this.selectLocation(clickedLocation.id, clickedLocation.location);
                    }
                    this.selectedCorridor = null;
                } else if (clickedCorridor && !this.plannedRoute) {
                    this.selectCorridor(clickedCorridor);
                    this.selectedLocation = null;
                    this.hideLocationInfo();
                } else {
                    // Clicked on empty space - deselect all
                    this.selectedLocation = null;
                    this.selectedCorridor = null;
                    this.hideLocationInfo();
                }
                
                this.render();
            }
            
            handleTouchStart(e) {
                e.preventDefault();
                
                // Store current touches
                this.touches = Array.from(e.touches);
                
                if (e.touches.length === 1) {
                    // Single touch - pan mode
                    const touch = e.touches[0];
                    this.isDragging = true;
                    this.isPinching = false;
                    this.dragStartX = touch.clientX - this.offsetX;
                    this.dragStartY = touch.clientY - this.offsetY;
                    this.mouseDownX = touch.clientX;
                    this.mouseDownY = touch.clientY;
                    this.hasDraggedSinceMouseDown = false;
                    
                    // Store touch start position for tap detection
                    this.touchStartX = touch.clientX;
                    this.touchStartY = touch.clientY;
                    this.touchStartTime = Date.now();
                } else if (e.touches.length === 2) {
                    // Two touches - pinch mode
                    this.isDragging = false;
                    this.isPinching = true;
                    
                    const touch1 = e.touches[0];
                    const touch2 = e.touches[1];
                    
                    // Calculate initial distance and center point
                    this.initialPinchDistance = this.getTouchDistance(touch1, touch2);
                    this.initialScale = this.scale;
                    
                    // Calculate center point between fingers
                    this.pinchCenterX = (touch1.clientX + touch2.clientX) / 2;
                    this.pinchCenterY = (touch1.clientY + touch2.clientY) / 2;
                    
                    this.hasDraggedSinceMouseDown = false;
                }
            }
            
            handleTouchMove(e) {
                e.preventDefault();
                
                // Update touch array
                this.touches = Array.from(e.touches);
                
                if (e.touches.length === 1 && this.isDragging && !this.isPinching) {
                    // Single touch panning
                    const touch = e.touches[0];
                    
                    // Check if we've moved beyond the drag threshold
                    if (!this.hasDraggedSinceMouseDown) {
                        const deltaX = Math.abs(touch.clientX - this.mouseDownX);
                        const deltaY = Math.abs(touch.clientY - this.mouseDownY);
                        if (deltaX > this.dragThreshold || deltaY > this.dragThreshold) {
                            this.hasDraggedSinceMouseDown = true;
                        }
                    }
                    
                    this.offsetX = touch.clientX - this.dragStartX;
                    this.offsetY = touch.clientY - this.dragStartY;
                    this.render();
                } else if (e.touches.length === 2 && this.isPinching) {
                    // Two-finger pinch-to-zoom
                    const touch1 = e.touches[0];
                    const touch2 = e.touches[1];
                    
                    // Calculate current distance between touches
                    const currentDistance = this.getTouchDistance(touch1, touch2);
                    
                    // Calculate zoom factor based on distance change
                    if (this.initialPinchDistance > 0) {
                        const distanceRatio = currentDistance / this.initialPinchDistance;
                        const newScale = this.initialScale * distanceRatio;
                        
                        // Apply zoom bounds
                        if (newScale >= 0.1 && newScale <= 100) {
                            // Calculate current center point between fingers
                            const currentCenterX = (touch1.clientX + touch2.clientX) / 2;
                            const currentCenterY = (touch1.clientY + touch2.clientY) / 2;
                            
                            // Get canvas position of pinch center
                            const rect = this.canvas.getBoundingClientRect();
                            const canvasCenterX = currentCenterX - rect.left;
                            const canvasCenterY = currentCenterY - rect.top;
                            
                            // Convert to world coordinates before zoom
                            const worldPoint = this.screenToWorld(canvasCenterX, canvasCenterY);
                            
                            // Apply new scale
                            this.scale = newScale;
                            
                            // Adjust offset to keep the pinch center point stationary
                            const newScreenPoint = this.worldToScreen(worldPoint.x, worldPoint.y);
                            this.offsetX += canvasCenterX - newScreenPoint.x;
                            this.offsetY += canvasCenterY - newScreenPoint.y;
                            
                            this.updateZoomDisplay();
                            this.render();
                            this.hasDraggedSinceMouseDown = true;
                        }
                    }
                }
            }
            
            handleTouchEnd(e) {
                // Check for tap before processing other touch end logic
                if (e.touches.length === 0 && this.isDragging && !this.isPinching) {
                    // Single touch ended - check if it was a tap
                    const touchEndTime = Date.now();
                    const touchDuration = touchEndTime - this.touchStartTime;
                    
                    // Get the touch that just ended (from changedTouches)
                    if (e.changedTouches.length > 0) {
                        const endTouch = e.changedTouches[0];
                        const deltaX = Math.abs(endTouch.clientX - this.touchStartX);
                        const deltaY = Math.abs(endTouch.clientY - this.touchStartY);
                        
                        // Check if this was a tap (short duration, small movement)
                        const maxTapDuration = 300; // milliseconds
                        const isWithinTimeLimit = touchDuration < maxTapDuration;
                        const isWithinMovementLimit = !this.hasDraggedSinceMouseDown;
                        
                        if (isWithinTimeLimit && isWithinMovementLimit) {
                            // This was a tap - process as interaction
                            const rect = this.canvas.getBoundingClientRect();
                            const x = endTouch.clientX - rect.left;
                            const y = endTouch.clientY - rect.top;
                            this.processInteraction(x, y);
                        }
                    }
                }
                
                // Update touch array
                this.touches = Array.from(e.touches);
                
                if (e.touches.length === 0) {
                    // All touches ended - reset states
                    this.isDragging = false;
                    this.isPinching = false;
                    this.initialPinchDistance = 0;
                } else if (e.touches.length === 1 && this.isPinching) {
                    // Went from pinch to single touch - switch to pan mode
                    this.isPinching = false;
                    this.initialPinchDistance = 0;
                    
                    const touch = e.touches[0];
                    this.isDragging = true;
                    this.dragStartX = touch.clientX - this.offsetX;
                    this.dragStartY = touch.clientY - this.offsetY;
                    this.mouseDownX = touch.clientX;
                    this.mouseDownY = touch.clientY;
                    
                    // Reset tap detection for new touch
                    this.touchStartX = touch.clientX;
                    this.touchStartY = touch.clientY;
                    this.touchStartTime = Date.now();
                } else if (e.touches.length >= 2 && !this.isPinching) {
                    // Went from single touch to pinch - switch to pinch mode
                    this.isDragging = false;
                    this.isPinching = true;
                    
                    const touch1 = e.touches[0];
                    const touch2 = e.touches[1];
                    
                    this.initialPinchDistance = this.getTouchDistance(touch1, touch2);
                    this.initialScale = this.scale;
                    this.pinchCenterX = (touch1.clientX + touch2.clientX) / 2;
                    this.pinchCenterY = (touch1.clientY + touch2.clientY) / 2;
                }
            }
            
            zoom(factor) {
                const newScale = this.scale * factor;
                if (newScale >= 0.1 && newScale <= 100) {
                    this.scale = newScale;
                    this.updateZoomDisplay();
                    this.render();
                }
            }
            
            zoomToPoint(factor, screenX, screenY) {
                const newScale = this.scale * factor;
                if (newScale >= 0.1 && newScale <= 100) {
                    // Convert screen coordinates to world coordinates before zoom
                    const worldPoint = this.screenToWorld(screenX, screenY);
                    
                    // Update scale
                    this.scale = newScale;
                    
                    // Convert world coordinates back to screen coordinates after zoom
                    const newScreenPoint = this.worldToScreen(worldPoint.x, worldPoint.y);
                    
                    // Adjust offset to keep the world point under the cursor
                    this.offsetX += screenX - newScreenPoint.x;
                    this.offsetY += screenY - newScreenPoint.y;
                    
                    this.updateZoomDisplay();
                    this.render();
                }
            }
            
            resetView() {
                this.scale = 1;
                this.offsetX = 0;
                this.offsetY = 0;
                this.updateZoomDisplay();
                this.render();
            }
            
            updateZoomDisplay() {
                const zoomElement = document.getElementById('zoom-level');
                if (zoomElement) {
                    zoomElement.textContent = Math.round(this.scale * 100) + '%';
                }
            }
            
            zoomToFit() {
                if (!this.data || !this.data.locations || Object.keys(this.data.locations).length === 0) return;
                
                // Find bounds of all locations
                let minX = Infinity, maxX = -Infinity;
                let minY = Infinity, maxY = -Infinity;
                
                Object.values(this.data.locations).forEach(location => {
                    minX = Math.min(minX, location.x);
                    maxX = Math.max(maxX, location.x);
                    minY = Math.min(minY, location.y);
                    maxY = Math.max(maxY, location.y);
                });
                
                // Add padding
                const padding = 50;
                const width = maxX - minX + padding * 2;
                const height = maxY - minY + padding * 2;
                
                // Calculate scale to fit
                const scaleX = this.canvas.width / width;
                const scaleY = this.canvas.height / height;
                const newScale = Math.min(scaleX, scaleY, 100); // Don't exceed max zoom
                
                // Center the view
                const centerX = (minX + maxX) / 2;
                const centerY = (minY + maxY) / 2;
                
                this.scale = Math.max(newScale, 0.1); // Don't go below min zoom
                this.offsetX = this.canvas.width / 2 - centerX * this.scale;
                this.offsetY = this.canvas.height / 2 - centerY * this.scale;
                
                this.updateZoomDisplay();
                this.render();
            }
            
            searchLocation() {
                const searchInput = document.getElementById('search-input');
                const searchTerm = searchInput.value.trim().toLowerCase();
                
                if (!searchTerm) {
                    return; // No alert needed, user can see empty input
                }
                
                if (!this.data || !this.data.locations) {
                    return; // Data will load, no need to interrupt user
                }
                
                // Search for matching locations
                const matches = Object.values(this.data.locations).filter(location => 
                    location.name.toLowerCase().includes(searchTerm) ||
                    location.system.toLowerCase().includes(searchTerm) ||
                    location.type.toLowerCase().includes(searchTerm)
                );
                
                if (matches.length === 0) {
                    return; // No matches, dropdown will show "No results"
                }
                
                // Focus on the first match
                const firstMatch = matches[0];
                this.selectSuggestion(firstMatch);
            }
            
            clearSearch() {
                const searchInput = document.getElementById('search-input');
                searchInput.value = '';
                this.hideSearchDropdown();
                searchInput.focus();
                // Clear any search timeout
                clearTimeout(this.searchTimeout);
            }
            
            showSearchSuggestions(searchTerm) {
                if (!this.data || !this.data.locations) {
                    return;
                }
                
                const searchDropdown = document.getElementById('search-dropdown');
                const matches = Object.values(this.data.locations).filter(location => 
                    location.name.toLowerCase().includes(searchTerm) ||
                    location.system.toLowerCase().includes(searchTerm) ||
                    location.type.toLowerCase().includes(searchTerm)
                );
                
                this.currentSuggestions = matches.slice(0, 8); // Limit to 8 suggestions
                this.highlightedIndex = -1;
                
                if (matches.length === 0) {
                    searchDropdown.innerHTML = '<div class="search-dropdown-item no-results">No locations found</div>';
                } else {
                    searchDropdown.innerHTML = matches.slice(0, 8).map(location => 
                        `<div class="search-dropdown-item" data-location-id="${location.id}">
                            <strong>${location.name}</strong> - ${location.system} (${location.type})
                        </div>`
                    ).join('');
                    
                    // Add click handlers to dropdown items
                    searchDropdown.querySelectorAll('.search-dropdown-item:not(.no-results)').forEach((item, index) => {
                        item.addEventListener('click', () => {
                            this.selectSuggestion(matches[index]);
                        });
                    });
                }
                
                searchDropdown.style.display = 'block';
            }
            
            hideSearchDropdown() {
                const searchDropdown = document.getElementById('search-dropdown');
                searchDropdown.style.display = 'none';
                this.highlightedIndex = -1;
            }
            
            updateHighlight() {
                const items = document.querySelectorAll('.search-dropdown-item:not(.no-results)');
                items.forEach((item, index) => {
                    if (index === this.highlightedIndex) {
                        item.classList.add('highlighted');
                    } else {
                        item.classList.remove('highlighted');
                    }
                });
            }
            
            selectSuggestion(location) {
                const searchInput = document.getElementById('search-input');
                searchInput.value = location.name;
                this.hideSearchDropdown();
                this.focusOnLocation(location);
            }
            
            focusOnLocation(location) {
                // Center the view on the location
                this.offsetX = -location.x * this.scale;
                this.offsetY = -location.y * this.scale;
                
                // Zoom in a bit to better show the location
                this.scale = Math.max(this.scale, 2.0);
                
                // Re-render the map
                this.render();
                
                // Show location info panel
                this.selectLocation(location.id, location);
            }
            
            populateRouteDropdowns() {
                if (!this.data || !this.data.locations) return;
                
                const startSelect = document.getElementById('route-start');
                const endSelect = document.getElementById('route-end');
                const midpointSelect = document.getElementById('route-midpoint');
                
                // Generate hash of current location data to detect changes
                const locationKeys = Object.keys(this.data.locations).sort();
                const locationHash = locationKeys.map(key => `${key}:${this.data.locations[key].name}`).join('|');
                
                // Only repopulate if location data has changed
                if (this.lastLocationHash === locationHash) {
                    return; // No changes, preserve dropdown state
                }
                this.lastLocationHash = locationHash;
                
                // Save current selected values
                const currentStart = startSelect.value;
                const currentEnd = endSelect.value;
                const currentMidpoint = midpointSelect.value;
                
                // Clear existing options (except first default option)
                while (startSelect.children.length > 1) {
                    startSelect.removeChild(startSelect.lastChild);
                }
                while (endSelect.children.length > 1) {
                    endSelect.removeChild(endSelect.lastChild);
                }
                while (midpointSelect.children.length > 1) {
                    midpointSelect.removeChild(midpointSelect.lastChild);
                }
                
                // Sort locations by name
                const sortedLocations = Object.values(this.data.locations).sort((a, b) => a.name.localeCompare(b.name));
                
                // Add options for each location
                sortedLocations.forEach(location => {
                    const option1 = document.createElement('option');
                    option1.value = location.id;
                    option1.textContent = location.name;
                    startSelect.appendChild(option1);
                    
                    const option2 = document.createElement('option');
                    option2.value = location.id;
                    option2.textContent = location.name;
                    endSelect.appendChild(option2);
                    
                    const option3 = document.createElement('option');
                    option3.value = location.id;
                    option3.textContent = location.name;
                    midpointSelect.appendChild(option3);
                });
                
                // Restore previously selected values
                if (currentStart && this.data.locations[currentStart]) {
                    startSelect.value = currentStart;
                }
                if (currentEnd && this.data.locations[currentEnd]) {
                    endSelect.value = currentEnd;
                }
                if (currentMidpoint && this.data.locations[currentMidpoint]) {
                    midpointSelect.value = currentMidpoint;
                }
            }
            
            plotRouteFromControls() {
                console.log('Plot route button clicked');
                
                const startId = document.getElementById('route-start').value;
                const endId = document.getElementById('route-end').value;
                const midpointId = document.getElementById('route-midpoint').value;
                
                console.log('Route values:', { startId, endId, midpointId });
                
                if (!startId || !endId) {
                    alert('Please select both start and end locations.');
                    return;
                }
                
                if (startId === endId) {
                    alert('Start and end locations cannot be the same.');
                    return;
                }
                
                console.log('Plotting route from', startId, 'to', endId);
                
                // If midpoint is specified, plot route via midpoint
                if (midpointId && midpointId !== startId && midpointId !== endId) {
                    // Plot route from start to midpoint, then midpoint to end
                    console.log('Using midpoint:', midpointId);
                    this.plotRoute(startId, midpointId);
                    setTimeout(() => {
                        this.plotRoute(midpointId, endId);
                    }, 100);
                } else {
                    // Direct route
                    this.plotRoute(startId, endId);
                }
                
                // Focus on start location
                const startLocation = this.data.locations[startId];
                if (startLocation) {
                    this.focusOnLocation(startLocation);
                }
            }
            
            clearPlottedRoute() {
                this.routePlanningMode = false;
                this.routeStartLocation = null;
                this.currentRoute = null;
                this.plannedRoute = null; // Also clear the actual plotted route
                
                // Clear the dropdowns
                document.getElementById('route-start').value = '';
                document.getElementById('route-end').value = '';
                document.getElementById('route-midpoint').value = '';
                
                this.render();
            }
            
            startRoutePlanning(fromLocationId) {
                this.routePlanningMode = true;
                this.routeStartLocation = fromLocationId;
                this.plannedRoute = null;
                
                // Update status
                const statusEl = document.getElementById('route-planning-status');
                if (statusEl) {
                    statusEl.textContent = 'Click destination to plot route...';
                    statusEl.style.color = 'var(--primary-color)';
                }
                
                // Update button text
                const routeButton = document.querySelector('button[onclick*="startRoutePlanning"]');
                if (routeButton) {
                    routeButton.textContent = '❌ Cancel Route Planning';
                    routeButton.onclick = () => this.cancelRoutePlanning();
                }
                
                this.render();
            }
            
            cancelRoutePlanning() {
                this.routePlanningMode = false;
                this.routeStartLocation = null;
                this.plannedRoute = null;
                
                // Update status
                const statusEl = document.getElementById('route-planning-status');
                if (statusEl) {
                    statusEl.textContent = '';
                }
                
                // Update button text back
                const routeButton = document.querySelector('button[onclick*="cancelRoutePlanning"]');
                if (routeButton && this.routeStartLocation) {
                    routeButton.textContent = '📍 Plot Route';
                    routeButton.onclick = () => this.startRoutePlanning(this.selectedLocation);
                }
                
                this.render();
            }
            
            plotRoute(fromId, toId) {
                console.log(`[PLOT_ROUTE] Starting route plot from ${fromId} to ${toId}`);
                
                // Validate inputs
                if (!fromId || !toId) {
                    console.error('[PLOT_ROUTE] Invalid fromId or toId');
                    return false;
                }
                
                // Check if locations exist
                if (!this.data.locations[String(fromId)]) {
                    console.error(`[PLOT_ROUTE] From location ${fromId} does not exist`);
                    return false;
                }
                if (!this.data.locations[String(toId)]) {
                    console.error(`[PLOT_ROUTE] To location ${toId} does not exist`);
                    return false;
                }
                
                // Debug connectivity for start and end locations
                this.debugCorridorConnectivity(fromId);
                this.debugCorridorConnectivity(toId);
                
                const route = this.findShortestPath(fromId, toId);
                console.log(`[PLOT_ROUTE] Pathfinding result:`, route);
                
                if (route && route.length > 1) {
                    this.plannedRoute = route;
                    this.routePlanningMode = false;
                    
                    console.log(`[PLOT_ROUTE] Route successfully planned with ${route.length} waypoints`);
                    
                    // Calculate route stats
                    const stats = this.calculateRouteStats(route);
                    
                    // Update status with route information
                    const statusEl = document.getElementById('route-planning-status');
                    if (statusEl) {
                        const routeInfo = `Route: ${route.length - 1} jumps | ${stats.totalTime}h | Danger: ${stats.avgDanger.toFixed(1)}/10`;
                        statusEl.innerHTML = `<br>${routeInfo}`;
                        statusEl.style.color = 'var(--text-primary)';
                        console.log(`[PLOT_ROUTE] Updated status: ${routeInfo}`);
                    }
                    
                    // Update button
                    const routeButton = document.querySelector('.location-plot-route-btn');
                    if (routeButton) {
                        routeButton.textContent = '🗑️ Clear Route';
                        routeButton.onclick = () => this.clearRoute();
                    }
                    
                    this.render();
                    return true;
                } else {
                    // No route found
                    console.warn(`[PLOT_ROUTE] No route found between ${fromId} and ${toId}`);
                    const statusEl = document.getElementById('route-planning-status');
                    if (statusEl) {
                        statusEl.textContent = 'No route found! Check corridor connectivity.';
                        statusEl.style.color = 'var(--danger-color, #ff4444)';
                    }
                    return false;
                }
            }
            
            clearRoute() {
                this.plannedRoute = null;
                this.routePlanningMode = false;
                this.routeStartLocation = null;
                
                const statusEl = document.getElementById('route-planning-status');
                if (statusEl) {
                    statusEl.textContent = '';
                }
                
                const routeButton = document.querySelector('.location-plot-route-btn');
                if (routeButton && this.selectedLocation) {
                    routeButton.textContent = '📍 Plot Route';
                    routeButton.onclick = () => this.startRoutePlanning(this.selectedLocation);
                }
                
                this.render();
            }
            
            // Helper function to check if a corridor is part of the planned route
            isCorridorInRoute(corridor, route) {
                if (!route || route.length < 2) {
                    return false;
                }
                
                // Check if this corridor connects any consecutive waypoints in the route
                for (let i = 0; i < route.length - 1; i++) {
                    const fromId = String(route[i]);
                    const toId = String(route[i + 1]);
                    
                    // Check if corridor connects these two waypoints (in either direction)
                    if ((corridor.origin == fromId && corridor.destination == toId) ||
                        (corridor.origin == toId && corridor.destination == fromId)) {
                        return true;
                    }
                }
                
                return false;
            }
            
            findShortestPath(fromId, toId) {
                // Enhanced Dijkstra's algorithm for pathfinding with debugging
                console.log(`[PATHFINDING] Starting pathfinding from ${fromId} to ${toId}`);
                
                // Normalize IDs to strings for consistent comparison
                fromId = String(fromId);
                toId = String(toId);
                
                if (fromId === toId) {
                    console.log(`[PATHFINDING] Same location, returning single node path`);
                    return [fromId];
                }
                
                // Check if both locations exist
                if (!this.data.locations[fromId]) {
                    console.error(`[PATHFINDING] From location ${fromId} does not exist`);
                    return null;
                }
                if (!this.data.locations[toId]) {
                    console.error(`[PATHFINDING] To location ${toId} does not exist`);
                    return null;
                }
                
                // Log corridor data for debugging
                console.log(`[PATHFINDING] Total corridors available: ${this.data.corridors.length}`);
                const relevantCorridors = this.data.corridors.filter(c => 
                    String(c.origin) === fromId || String(c.destination) === fromId ||
                    String(c.origin) === toId || String(c.destination) === toId
                );
                console.log(`[PATHFINDING] Corridors connected to start/end: ${relevantCorridors.length}`);
                
                const distances = {};
                const previous = {};
                const unvisited = new Set();
                
                // Initialize all locations (convert keys to strings)
                for (const [id] of Object.entries(this.data.locations)) {
                    const stringId = String(id);
                    distances[stringId] = Infinity;
                    previous[stringId] = null;
                    unvisited.add(stringId);
                }
                
                distances[fromId] = 0;
                console.log(`[PATHFINDING] Initialized ${unvisited.size} locations`);
                
                let iterations = 0;
                const maxIterations = Object.keys(this.data.locations).length * 2;
                
                while (unvisited.size > 0 && iterations < maxIterations) {
                    iterations++;
                    
                    // Find unvisited node with smallest distance
                    let current = null;
                    let minDistance = Infinity;
                    
                    for (const node of unvisited) {
                        if (distances[node] < minDistance) {
                            minDistance = distances[node];
                            current = node;
                        }
                    }
                    
                    if (current === null || distances[current] === Infinity) {
                        console.log(`[PATHFINDING] No more reachable nodes. Stopping at iteration ${iterations}`);
                        break; // No path exists
                    }
                    
                    console.log(`[PATHFINDING] Iteration ${iterations}: Processing node ${current} (distance: ${distances[current]})`);
                    
                    if (current === toId) {
                        // Found destination, reconstruct path
                        console.log(`[PATHFINDING] Destination reached! Reconstructing path...`);
                        const path = [];
                        let node = toId;
                        while (node !== null) {
                            path.unshift(node);
                            node = previous[node];
                        }
                        console.log(`[PATHFINDING] Path found: ${path.join(' -> ')} (${path.length} nodes, ${path.length - 1} jumps)`);
                        return path;
                    }
                    
                    unvisited.delete(current);
                    
                    // Check all corridors from current location
                    let neighborsFound = 0;
                    for (const corridor of this.data.corridors) {
                        let neighbor = null;
                        
                        // Normalize corridor IDs for comparison
                        const corridorOrigin = String(corridor.origin);
                        const corridorDest = String(corridor.destination);
                        
                        if (corridorOrigin === current) {
                            neighbor = corridorDest;
                        } else if (corridorDest === current) {
                            neighbor = corridorOrigin;
                        }
                        
                        if (neighbor && unvisited.has(neighbor)) {
                            neighborsFound++;
                            // Use travel time as weight (with danger level as penalty)
                            const weight = (corridor.travel_time || 1) + (corridor.danger_level || 0) * 0.5;
                            const alt = distances[current] + weight;
                            
                            if (alt < distances[neighbor]) {
                                const oldDistance = distances[neighbor];
                                distances[neighbor] = alt;
                                previous[neighbor] = current;
                                console.log(`[PATHFINDING] Updated ${neighbor}: ${oldDistance} -> ${alt} via ${current}`);
                            }
                        }
                    }
                    
                    if (neighborsFound === 0) {
                        console.log(`[PATHFINDING] No neighbors found for ${current}`);
                    } else {
                        console.log(`[PATHFINDING] Found ${neighborsFound} neighbors for ${current}`);
                    }
                }
                
                console.log(`[PATHFINDING] Pathfinding completed after ${iterations} iterations. No path found.`);
                console.log(`[PATHFINDING] Final distances to target: ${distances[toId]}`);
                return null; // No path found
            }
            
            debugCorridorConnectivity(locationId) {
                // Debug method to check what corridors are connected to a location
                const normalizedId = String(locationId);
                const location = this.data.locations[normalizedId];
                
                if (!location) {
                    console.error(`[DEBUG] Location ${locationId} not found`);
                    return;
                }
                
                console.log(`[DEBUG] Checking connectivity for ${location.name} (ID: ${normalizedId})`);
                
                const connectedCorridors = this.data.corridors.filter(c => 
                    String(c.origin) === normalizedId || String(c.destination) === normalizedId
                );
                
                console.log(`[DEBUG] Found ${connectedCorridors.length} connected corridors:`);
                
                connectedCorridors.forEach((corridor, index) => {
                    const otherLocationId = String(corridor.origin) === normalizedId ? 
                        String(corridor.destination) : String(corridor.origin);
                    const otherLocation = this.data.locations[otherLocationId];
                    
                    console.log(`[DEBUG] ${index + 1}. ${corridor.name || 'Unnamed'} -> ` +
                        `${otherLocation ? otherLocation.name : 'Unknown'} (ID: ${otherLocationId}), ` +
                        `Time: ${corridor.travel_time}, Danger: ${corridor.danger_level}`);
                });
                
                if (connectedCorridors.length === 0) {
                    console.warn(`[DEBUG] Location ${location.name} has no corridor connections!`);
                }
            }
            
            calculateRouteStats(route) {
                let totalTime = 0;
                let totalDanger = 0;
                let corridorCount = 0;
                
                console.log(`[ROUTE_STATS] Calculating stats for route: ${route.join(' -> ')}`);
                
                for (let i = 0; i < route.length - 1; i++) {
                    const fromId = String(route[i]);
                    const toId = String(route[i + 1]);
                    
                    // Find the corridor between these locations with proper type comparison
                    const corridor = this.data.corridors.find(c => 
                        (String(c.origin) === fromId && String(c.destination) === toId) ||
                        (String(c.origin) === toId && String(c.destination) === fromId)
                    );
                    
                    if (corridor) {
                        const segmentTime = corridor.travel_time || 1;
                        const segmentDanger = corridor.danger_level || 0;
                        totalTime += segmentTime;
                        totalDanger += segmentDanger;
                        corridorCount++;
                        console.log(`[ROUTE_STATS] Segment ${i+1}: ${fromId} -> ${toId}, Time: ${segmentTime}, Danger: ${segmentDanger}`);
                    } else {
                        console.error(`[ROUTE_STATS] No corridor found for segment ${fromId} -> ${toId}`);
                    }
                }
                
                const stats = {
                    totalTime,
                    avgDanger: corridorCount > 0 ? totalDanger / corridorCount : 0,
                    corridorCount
                };
                
                console.log(`[ROUTE_STATS] Final stats:`, stats);
                return stats;
            }
            
            testPathfinding() {
                // Test method to validate pathfinding with sample data
                console.log('[TEST] Starting pathfinding test...');
                
                if (!this.data || !this.data.locations || !this.data.corridors) {
                    console.error('[TEST] No data available for testing');
                    return;
                }
                
                const locationIds = Object.keys(this.data.locations);
                console.log(`[TEST] Available locations: ${locationIds.length}`);
                console.log(`[TEST] Available corridors: ${this.data.corridors.length}`);
                
                if (locationIds.length < 2) {
                    console.error('[TEST] Need at least 2 locations for testing');
                    return;
                }
                
                // Test with first two locations
                const fromId = locationIds[0];
                const toId = locationIds[1];
                
                console.log(`[TEST] Testing route from ${fromId} to ${toId}`);
                this.debugCorridorConnectivity(fromId);
                this.debugCorridorConnectivity(toId);
                
                const route = this.findShortestPath(fromId, toId);
                
                if (route) {
                    console.log(`[TEST] Test successful! Route found: ${route.join(' -> ')}`);
                    const stats = this.calculateRouteStats(route);
                    console.log(`[TEST] Route stats:`, stats);
                } else {
                    console.log(`[TEST] No route found between ${fromId} and ${toId}`);
                    
                    // Try to find any connected locations
                    console.log('[TEST] Looking for any connected locations...');
                    const connectedPairs = [];
                    
                    for (const corridor of this.data.corridors) {
                        const origin = String(corridor.origin);
                        const dest = String(corridor.destination);
                        
                        if (this.data.locations[origin] && this.data.locations[dest]) {
                            connectedPairs.push([origin, dest]);
                        }
                    }
                    
                    console.log(`[TEST] Found ${connectedPairs.length} directly connected location pairs`);
                    
                    if (connectedPairs.length > 0) {
                        const [testFrom, testTo] = connectedPairs[0];
                        console.log(`[TEST] Testing with directly connected pair: ${testFrom} -> ${testTo}`);
                        const testRoute = this.findShortestPath(testFrom, testTo);
                        
                        if (testRoute) {
                            console.log(`[TEST] Direct connection test successful: ${testRoute.join(' -> ')}`);
                        } else {
                            console.error('[TEST] Even direct connection failed - there may be a bug in the pathfinding');
                        }
                    }
                }
            }

            drawPlannedRoute() {
                if (!this.plannedRoute || this.plannedRoute.length < 2) {
                    console.log('[DRAW_ROUTE] No route to draw or route too short');
                    return;
                }
                
                console.log(`[DRAW_ROUTE] Drawing route with ${this.plannedRoute.length} waypoints: ${this.plannedRoute.join(' -> ')}`);
                
                this.ctx.save();
                
                // Set route style
                this.ctx.strokeStyle = '#00ffff'; // Cyan color for planned route
                this.ctx.lineWidth = Math.max(4, Math.min(10, 6 / Math.sqrt(this.scale)));
                this.ctx.lineCap = 'round';
                this.ctx.lineJoin = 'round';
                
                // Add glow effect based on zoom level
                const routeGlowFactor = this.scale > 1 ? 1 : this.scale > 0.5 ? 0.6 : 0.2;
                this.ctx.shadowColor = '#00ffff';
                this.ctx.shadowBlur = 15 * routeGlowFactor;
                
                // Draw animated dashed line
                const dashLength = 20 / this.scale;
                const animationOffset = (Date.now() * 0.01) % (dashLength * 2);
                this.ctx.setLineDash([dashLength, dashLength]);
                this.ctx.lineDashOffset = animationOffset;
                
                // Draw each segment of the planned route
                let segmentsDrawn = 0;
                for (let i = 0; i < this.plannedRoute.length - 1; i++) {
                    const fromId = String(this.plannedRoute[i]);
                    const toId = String(this.plannedRoute[i + 1]);
                    
                    const fromLocation = this.data.locations[fromId];
                    const toLocation = this.data.locations[toId];
                    
                    if (fromLocation && toLocation) {
                        const start = this.worldToScreen(fromLocation.x, fromLocation.y);
                        const end = this.worldToScreen(toLocation.x, toLocation.y);
                        
                        this.ctx.beginPath();
                        this.ctx.moveTo(start.x, start.y);
                        this.ctx.lineTo(end.x, end.y);
                        this.ctx.stroke();
                        segmentsDrawn++;
                        
                        console.log(`[DRAW_ROUTE] Drew segment ${i+1}: ${fromLocation.name} -> ${toLocation.name}`);
                    } else {
                        console.error(`[DRAW_ROUTE] Missing location data for segment ${fromId} -> ${toId}`);
                    }
                }
                console.log(`[DRAW_ROUTE] Drew ${segmentsDrawn} route segments`);
                
                // Draw route waypoint markers
                this.ctx.setLineDash([]); // Reset dash
                this.ctx.shadowBlur = 0;
                
                // Draw intermediate waypoints (not start/end)
                let waypointsDrawn = 0;
                for (let i = 1; i < this.plannedRoute.length - 1; i++) {
                    const locationId = String(this.plannedRoute[i]);
                    const location = this.data.locations[locationId];
                    
                    if (location) {
                        const pos = this.worldToScreen(location.x, location.y);
                        
                        // Draw waypoint circle (larger for better visibility)
                        this.ctx.fillStyle = '#00ffff';
                        this.ctx.beginPath();
                        this.ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
                        this.ctx.fill();
                        
                        // Draw inner circle
                        this.ctx.fillStyle = '#004444';
                        this.ctx.beginPath();
                        this.ctx.arc(pos.x, pos.y, 4, 0, 2 * Math.PI);
                        this.ctx.fill();
                        
                        // Draw waypoint number
                        this.ctx.fillStyle = '#ffffff';
                        this.ctx.font = `bold ${Math.max(12, 14 / Math.sqrt(this.scale))}px Arial`;
                        this.ctx.textAlign = 'center';
                        this.ctx.textBaseline = 'middle';
                        this.ctx.fillText(i.toString(), pos.x, pos.y);
                        waypointsDrawn++;
                        
                        console.log(`[DRAW_ROUTE] Drew waypoint ${i}: ${location.name}`);
                    } else {
                        console.error(`[DRAW_ROUTE] Missing location data for waypoint ${locationId}`);
                    }
                }
                console.log(`[DRAW_ROUTE] Drew ${waypointsDrawn} waypoint markers`);
                
                // Highlight start and end points
                if (this.plannedRoute.length >= 2) {
                    // Start point (green)
                    const startLocation = this.data.locations[String(this.plannedRoute[0])];
                    if (startLocation) {
                        const startPos = this.worldToScreen(startLocation.x, startLocation.y);
                        this.ctx.strokeStyle = '#00ff00';
                        this.ctx.lineWidth = 4;
                        this.ctx.beginPath();
                        this.ctx.arc(startPos.x, startPos.y, 15, 0, 2 * Math.PI);
                        this.ctx.stroke();
                        
                        // Add start label
                        this.ctx.fillStyle = '#00ff00';
                        this.ctx.font = `bold ${Math.max(10, 12 / Math.sqrt(this.scale))}px Arial`;
                        this.ctx.textAlign = 'center';
                        this.ctx.textBaseline = 'top';
                        this.ctx.fillText('START', startPos.x, startPos.y + 20);
                        
                        console.log(`[DRAW_ROUTE] Drew start point: ${startLocation.name}`);
                    }
                    
                    // End point (red)
                    const endLocation = this.data.locations[String(this.plannedRoute[this.plannedRoute.length - 1])];
                    if (endLocation) {
                        const endPos = this.worldToScreen(endLocation.x, endLocation.y);
                        this.ctx.strokeStyle = '#ff0000';
                        this.ctx.lineWidth = 4;
                        this.ctx.beginPath();
                        this.ctx.arc(endPos.x, endPos.y, 15, 0, 2 * Math.PI);
                        this.ctx.stroke();
                        
                        // Add end label
                        this.ctx.fillStyle = '#ff0000';
                        this.ctx.font = `bold ${Math.max(10, 12 / Math.sqrt(this.scale))}px Arial`;
                        this.ctx.textAlign = 'center';
                        this.ctx.textBaseline = 'top';
                        this.ctx.fillText('END', endPos.x, endPos.y + 20);
                        
                        console.log(`[DRAW_ROUTE] Drew end point: ${endLocation.name}`);
                    }
                }
                
                this.ctx.restore();
                console.log('[DRAW_ROUTE] Route drawing completed');
            }

            isPointNearLine(point, corridor) {
                const origin = this.data.locations[corridor.origin];
                const dest = this.data.locations[corridor.destination];
                
                if (!origin || !dest) return false;
                
                // Calculate distance from point to line segment
                const A = point.x - origin.x;
                const B = point.y - origin.y;
                const C = dest.x - origin.x;
                const D = dest.y - origin.y;
                
                const dot = A * C + B * D;
                const lenSq = C * C + D * D;
                let param = -1;
                
                if (lenSq !== 0) param = dot / lenSq;
                
                let xx, yy;
                
                if (param < 0) {
                    xx = origin.x;
                    yy = origin.y;
                } else if (param > 1) {
                    xx = dest.x;
                    yy = dest.y;
                } else {
                    xx = origin.x + param * C;
                    yy = origin.y + param * D;
                }
                
                const dx = point.x - xx;
                const dy = point.y - yy;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                return distance < 10 / this.scale;
            }
            
            showTooltip(x, y, location) {
                this.tooltip.innerHTML = `
                    <strong>${location.name}</strong><br>
                    Type: ${location.type}<br>
                    System: ${location.system}<br>
                    Wealth: ${location.wealth}
                `;
                this.tooltip.style.left = x + 10 + 'px';
                this.tooltip.style.top = y + 10 + 'px';
                this.tooltip.classList.add('visible');
            }
            
            showCorridorTooltip(x, y, corridor) {
                const origin = this.data.locations[corridor.origin];
                const dest = this.data.locations[corridor.destination];
                
                if (!origin || !dest) return;
                
                // Determine corridor type
                let corridorType = 'Gated Route';
                if (corridor.corridor_type === 'local_space' || corridor.name && corridor.name.includes('Approach')) {
                    corridorType = 'Local Space';
                } else if (corridor.corridor_type === 'ungated') {
                    corridorType = 'Ungated Route';
                }
                
                // Format travel time
                const mins = Math.floor((corridor.travel_time || 0) / 60);
                const secs = (corridor.travel_time || 0) % 60;
                const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
                
                this.tooltip.innerHTML = `
                    <strong>${corridor.name || 'Unknown Route'}</strong><br>
                    Type: ${corridorType}<br>
                    ${origin.name} → ${dest.name}<br>
                    Travel Time: ${timeStr}<br>
                    Danger Level: ${'⚠️'.repeat(corridor.danger_level || 0)}
                `;
                this.tooltip.style.left = x + 10 + 'px';
                this.tooltip.style.top = y + 10 + 'px';
                this.tooltip.classList.add('visible');
            }
            
            hideTooltip() {
                this.tooltip.classList.remove('visible');
            }
            
            selectLocation(id, location) {
                this.selectedLocation = id;
                this.render();
                
                // Count entities at location
                const playerCount = Object.values(this.data.players).filter(p => 
                    !p.traveling && p.location == id
                ).length;
                const npcCount = Object.values(this.data.npcs).filter(n => 
                    n.location == id
                ).length;
                
                // Get available routes
                const routes = this.data.corridors.filter(c => 
                    c.origin == id || c.destination == id
                );
                
                // Build route information
                let routeInfo = '';
                if (routes.length > 0) {
                    const outgoingRoutes = routes.filter(r => r.origin == id);
                    const incomingRoutes = routes.filter(r => r.destination == id);
                    
                    if (outgoingRoutes.length > 0) {
                        routeInfo += '<strong>Outgoing Routes:</strong><br>';
                        outgoingRoutes.forEach(r => {
                            const dest = this.data.locations[r.destination];
                            if (dest) {
                                const type = r.corridor_type === 'local_space' || (r.name && r.name.includes('Approach')) ? '🌌' : 
                                           r.corridor_type === 'ungated' ? '⭕' : '🔵';
                                routeInfo += `${type} → ${dest.name}<br>`;
                            }
                        });
                    }
                    
                    if (incomingRoutes.length > 0) {
                        routeInfo += '<br><strong>Incoming Routes:</strong><br>';
                        incomingRoutes.forEach(r => {
                            const origin = this.data.locations[r.origin];
                            if (origin) {
                                const type = r.corridor_type === 'local_space' || (r.name && r.name.includes('Approach')) ? '🌌' : 
                                           r.corridor_type === 'ungated' ? '⭕' : '🔵';
                                routeInfo += `${type} ← ${origin.name}<br>`;
                            }
                        });
                    }
                }
                
                // Update info panel
                this.locationInfo.innerHTML = `
                    <button class="info-panel-close">×</button>
                    <h3>${location.name}</h3>
                    <div class="location-detail">
                        <strong>Type:</strong> ${location.type.replace('_', ' ')}
                    </div>
                    <div class="location-detail">
                        <strong>System:</strong> ${location.system}
                    </div>
                    <div class="location-detail">
                        <strong>Wealth:</strong> ${location.wealth}/10
                    </div>
                    <div class="location-detail">
                        <strong>Population:</strong> ${location.population || 'Unknown'}
                    </div>
                    <div class="location-detail">
                        <strong>Players Here:</strong> ${playerCount}
                    </div>
                    <div class="location-detail">
                        <strong>NPCs Here:</strong> ${npcCount}
                    </div>
                    ${location.description ? `
                    <div class="location-detail" style="margin-top: 10px;">
                        <strong>Description:</strong><br>
                        ${location.description}
                    </div>` : ''}
                    ${routeInfo ? `
                    <div class="location-detail" style="margin-top: 10px;">
                        ${routeInfo}
                    </div>` : ''}
                    <div class="location-detail" style="margin-top: 10px; font-size: 0.8rem; color: var(--text-secondary);">
                        🌌 = Local Space | 🔵 = Gated | ⭕ = Ungated
                    </div>
                    <div class="location-actions" style="margin-top: 15px; text-align: center;">
                        <button class="control-button location-plot-route-btn" onclick="galaxyMap.startRoutePlanning('${id}')">📍 Plot Route</button>
                    </div>
                `;
                
                // No backdrop needed on mobile
                
                this.locationInfo.style.display = 'block';
                this.locationInfo.classList.add('visible');
                
                // Add event listener for close button with touch support
                const closeBtn = this.locationInfo.querySelector('.info-panel-close');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => this.closeInfoPanel());
                    closeBtn.addEventListener('touchend', (e) => {
                        e.stopPropagation();
                        this.closeInfoPanel();
                    });
                }
            }
            
            selectCorridor(corridor) {
                this.selectedCorridor = corridor;
                
                const origin = this.data.locations[corridor.origin];
                const dest = this.data.locations[corridor.destination];
                
                if (!origin || !dest) return;
                
                // Determine corridor type
                let corridorType = 'Gated Route';
                let typeIcon = '🔵';
                if (corridor.corridor_type === 'local_space' || corridor.name && corridor.name.includes('Approach')) {
                    corridorType = 'Local Space Route';
                    typeIcon = '🌌';
                } else if (corridor.corridor_type === 'ungated') {
                    corridorType = 'Ungated Route';
                    typeIcon = '⭕';
                }
                
                // Format travel time
                const mins = Math.floor((corridor.travel_time || 0) / 60);
                const secs = (corridor.travel_time || 0) % 60;
                const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
                
                // Check for travelers
                const travelers = Object.values(this.data.players).filter(p => 
                    p.traveling && p.corridor_id === corridor.id
                );
                
                // Update info panel with corridor information
                this.locationInfo.innerHTML = `
                    <button class="info-panel-close">×</button>
                    <h3>${typeIcon} ${corridor.name || 'Unknown Route'}</h3>
                    <div class="location-detail">
                        <strong>Type:</strong> ${corridorType}
                    </div>
                    <div class="location-detail">
                        <strong>Route:</strong> ${origin.name} → ${dest.name}
                    </div>
                    <div class="location-detail">
                        <strong>Travel Time:</strong> ${timeStr}
                    </div>
                    <div class="location-detail">
                        <strong>Danger Level:</strong> ${'⚠️'.repeat(corridor.danger_level || 0)}
                    </div>
                    <div class="location-detail">
                        <strong>Travelers:</strong> ${travelers.length}
                    </div>
                    ${travelers.length > 0 ? `
                    <div class="location-detail" style="margin-top: 10px;">
                        <strong>Currently Traveling:</strong><br>
                        ${travelers.map(t => `• ${t.name}`).join('<br>')}
                    </div>` : ''}
                    <div class="location-detail" style="margin-top: 15px; padding: 10px; background: var(--accent-bg); border-radius: 4px;">
                        <strong>Route Information:</strong><br>
                        ${corridorType === 'Local Space Route' ? 
                            'Safe, short-distance travel within a system. No gate required.' :
                          corridorType === 'Ungated Route' ? 
                            'Direct but dangerous travel through unprotected space. Higher risk, shorter time.' :
                            'Protected travel through established gate network. Safe but requires gate access.'}
                    </div>
                `;
                
                // No backdrop needed on mobile
                
                this.locationInfo.style.display = 'block';
                this.locationInfo.classList.add('visible');
                
                // Add event listener for close button with touch support
                const closeBtn = this.locationInfo.querySelector('.info-panel-close');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => this.closeInfoPanel());
                    closeBtn.addEventListener('touchend', (e) => {
                        e.stopPropagation();
                        this.closeInfoPanel();
                    });
                }
            }
            
            hideLocationInfo() {
                this.locationInfo.style.display = 'none';
                this.locationInfo.classList.remove('visible');
            }
            
            createBackdrop() {
                // Remove existing backdrop if present
                const existingBackdrop = document.querySelector('.info-panel-backdrop');
                if (existingBackdrop) {
                    existingBackdrop.parentNode.removeChild(existingBackdrop);
                }
                
                // Create backdrop element for mobile
                const backdrop = document.createElement('div');
                backdrop.className = 'info-panel-backdrop';
                backdrop.onclick = () => this.closeInfoPanel();
                document.body.appendChild(backdrop);
                
                // Show backdrop with transition
                setTimeout(() => {
                    backdrop.classList.add('visible');
                }, 10);
            }
            
            closeInfoPanel() {
                // Hide the info panel without clearing the selection/highlighting
                this.locationInfo.style.display = 'none';
                this.locationInfo.classList.remove('visible');
                
                // Remove backdrop if it exists
                const backdrop = document.querySelector('.info-panel-backdrop');
                if (backdrop) {
                    backdrop.classList.remove('visible');
                    // Remove backdrop element after transition
                    setTimeout(() => {
                        if (backdrop.parentNode) {
                            backdrop.parentNode.removeChild(backdrop);
                        }
                    }, 300);
                }
                
                // Keep selectedLocation and selectedCorridor intact so highlighting persists
            }
        }

        // Header toggle functionality
        function toggleHeader() {
            const header = document.getElementById('map-header');
            const controls = document.querySelector('.map-controls');
            const collapsedToggle = document.getElementById('header-toggle-collapsed');
            const toggleIcon = document.querySelector('#header-toggle .toggle-icon');
            
            if (header.classList.contains('hidden')) {
                // Show header and controls
                header.classList.remove('hidden');
                if (controls) controls.classList.remove('hidden');
                document.body.classList.remove('header-hidden');
                collapsedToggle.style.display = 'none';
                if (toggleIcon) toggleIcon.textContent = '▲';
                localStorage.setItem('headerVisible', 'true');
            } else {
                // Hide header and controls
                header.classList.add('hidden');
                if (controls) controls.classList.add('hidden');
                document.body.classList.add('header-hidden');
                collapsedToggle.style.display = 'block';
                localStorage.setItem('headerVisible', 'false');
            }
            
            // Trigger canvas resize after a brief delay to allow CSS changes
            setTimeout(() => {
                if (window.galaxyMap) {
                    window.galaxyMap.setupCanvas();
                }
            }, 100);
        }
        
        // Make toggleHeader globally accessible
        window.toggleHeader = toggleHeader;
        
        // Initialize map when page loads
        document.addEventListener('DOMContentLoaded', () => {
            // Initialize theme from URL parameter or storage
            if (window.themeManager) {
                window.themeManager.initializeTheme('blue');
            }
            
            window.galaxyMap = new GalaxyMap();
            
            // Restore header state on page load
            const headerVisible = localStorage.getItem('headerVisible');
            if (headerVisible === 'false') {
                const header = document.getElementById('map-header');
                const controls = document.querySelector('.map-controls');
                const collapsedToggle = document.getElementById('header-toggle-collapsed');
                if (header && collapsedToggle) {
                    header.classList.add('hidden');
                    if (controls) controls.classList.add('hidden');
                    document.body.classList.add('header-hidden');
                    collapsedToggle.style.display = 'block';
                }
            }
        });
        '''
    
    def get_wiki_script(self):
        """Get wiki JavaScript"""
        return '''
        class GalacticWiki {
            constructor() {
                console.log('Wiki: GalacticWiki constructor called');
                this.currentTab = 'locations';
                this.data = null;
                this.init();
            }
            
            async init() {
                console.log('Wiki: init() called');
                this.setupEventListeners();
                console.log('Wiki: Event listeners set up');
                await this.loadData();
                console.log('Wiki: Data loaded');
            }
            
            setupEventListeners() {
                document.querySelectorAll('.wiki-tab').forEach(tab => {
                    tab.addEventListener('click', () => {
                        const tabName = tab.dataset.tab;
                        this.switchTab(tabName);
                    });
                });
                
                // Event delegation for location and route rows
                document.addEventListener('click', (e) => {
                    console.log('Wiki: Click detected on:', e.target);
                    console.log('Wiki: Click target classes:', e.target.className);
                    console.log('Wiki: Click target parent:', e.target.parentElement);
                    
                    const locationRow = e.target.closest('.location-row');
                    const routeRow = e.target.closest('.route-row');
                    
                    console.log('Wiki: Location row found:', locationRow);
                    console.log('Wiki: Route row found:', routeRow);
                    
                    if (locationRow) {
                        const locationId = locationRow.dataset.locationId;
                        console.log('Wiki: Calling showLocationInfoFromWiki with ID:', locationId);
                        this.showLocationInfoFromWiki(locationId);
                    } else if (routeRow) {
                        const routeId = routeRow.dataset.routeId;
                        console.log('Wiki: Calling showRouteInfoFromWiki with ID:', routeId);
                        this.showRouteInfoFromWiki(routeId);
                    }
                });
            }
            
            async loadData() {
                try {
                    document.getElementById('loading').style.display = 'block';
                    document.getElementById('wiki-data').style.display = 'none';
                    
                    const response = await fetch('/api/wiki-data');
                    this.data = await response.json();
                    
                    // Update galaxy name and current time in header
                    this.updateHeader();
                    
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('wiki-data').style.display = 'block';
                    
                    this.renderCurrentTab();
                } catch (error) {
                    console.error('Failed to load wiki data:', error);
                    document.getElementById('loading').innerHTML = 'Failed to load data. Please refresh.';
                }
            }
            
            updateHeader() {
                if (this.data) {
                    const galaxyNameEl = document.getElementById('galaxy-name');
                    const currentTimeEl = document.getElementById('current-time');
                    
                    if (this.data.galaxy_info && this.data.galaxy_info.name) {
                        galaxyNameEl.textContent = this.data.galaxy_info.name.toUpperCase() + ' WIKI';
                    } else {
                        galaxyNameEl.textContent = 'GALACTIC WIKI';
                    }
                    
                    if (this.data.current_time) {
                        currentTimeEl.textContent = this.data.current_time;
                    } else {
                        currentTimeEl.textContent = 'DATABASE ONLINE';
                    }
                }
            }
            
            switchTab(tabName) {
                this.currentTab = tabName;
                
                // Update tab styles
                document.querySelectorAll('.wiki-tab').forEach(tab => {
                    if (tab.dataset.tab === tabName) {
                        tab.classList.add('active');
                    } else {
                        tab.classList.remove('active');
                    }
                });
                
                this.renderCurrentTab();
            }
            
            renderCurrentTab() {
                const container = document.getElementById('wiki-data');
                
                switch (this.currentTab) {
                    case 'locations':
                        container.innerHTML = this.renderLocations();
                        break;
                    case 'routes':
                        container.innerHTML = this.renderRoutes();
                        break;
                    case 'players':
                        container.innerHTML = this.renderPlayers();
                        break;
                    case 'npcs':
                        container.innerHTML = this.renderNPCs();
                        break;
                    case 'logs':
                        container.innerHTML = this.renderLogs();
                        break;
                    case 'news':
                        container.innerHTML = this.renderNews();
                        break;
                }
            }
            
            renderLocations() {
                let html = '<div class="wiki-section"><h3>Galaxy Locations</h3>';
                
                if (!this.data.locations || this.data.locations.length === 0) {
                    return html + '<p>No locations found.</p></div>';
                }
                
                // Group by system
                const systems = {};
                this.data.locations.forEach(loc => {
                    if (!systems[loc.system]) systems[loc.system] = [];
                    systems[loc.system].push(loc);
                });
                
                for (const [system, locations] of Object.entries(systems)) {
                    html += `<div class="wiki-section"><h4>System: ${system}</h4>`;
                    html += '<table class="wiki-table"><thead><tr>';
                    html += '<th>Name</th><th>Type</th><th>Wealth</th><th>Population</th>';
                    html += '<th>Faction</th><th>Pilots</th><th>NPCs</th>';
                    html += '</tr></thead><tbody>';
                    
                    locations.sort((a, b) => a.name.localeCompare(b.name));
                    
                    for (const loc of locations) {
                        html += `<tr class="location-row" data-location-id="${loc.id}" style="cursor: pointer;">`;
                        html += `<td><strong>${loc.name}</strong></td>`;
                        html += `<td>${loc.type}</td>`;
                        html += `<td class="wealth-${loc.wealth}">${loc.wealth}</td>`;
                        html += `<td>${loc.population.toLocaleString()}</td>`;
                        html += `<td class="faction-${loc.faction}">${loc.faction}</td>`;
                        html += `<td>${loc.player_count || 0}</td>`;
                        html += `<td>${(loc.static_npc_count || 0) + (loc.dynamic_npc_count || 0)}</td>`;
                        html += '</tr>';
                    }
                    
                    html += '</tbody></table></div>';
                }
                
                return html + '</div>';
            }
            
            renderRoutes() {
                let html = '<div class="wiki-section"><h3>Space Routes</h3>';
                
                if (!this.data.routes || this.data.routes.length === 0) {
                    return html + '<p>No active routes found.</p></div>';
                }
                
                html += '<table class="wiki-table"><thead><tr>';
                html += '<th>Route Name</th><th>Origin</th><th>Destination</th>';
                html += '<th>Travel Time</th><th>Danger Level</th><th>Stability</th>';
                html += '</tr></thead><tbody>';
                
                for (const route of this.data.routes) {
                    const minutes = Math.floor(route.travel_time / 60);
                    const seconds = route.travel_time % 60;
                    const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
                    
                    // Determine route emoji based on type
                    let routeEmoji = '🔵'; // Default gated
                    if (route.corridor_type === 'local_space' || (route.name && route.name.includes('Approach'))) {
                        routeEmoji = '🌌'; // Local space
                    } else if (route.corridor_type === 'ungated') {
                        routeEmoji = '⭕'; // Ungated
                    }
                    
                    html += `<tr class="route-row" data-route-id="${route.id}" style="cursor: pointer;">`;
                    html += `<td><strong>${routeEmoji} ${route.name}</strong></td>`;
                    html += `<td>${route.origin_name} (${route.origin_system})</td>`;
                    html += `<td>${route.dest_name} (${route.dest_system})</td>`;
                    html += `<td>${timeStr}</td>`;
                    html += `<td>${route.danger_level}/10</td>`;
                    html += `<td>${route.stability}%</td>`;
                    html += '</tr>';
                }
                
                html += '</tbody></table></div>';
                return html;
            }
            
            renderPlayers() {
                let html = '<div class="wiki-section"><h3>Active Pilots</h3>';
                
                if (!this.data.players || this.data.players.length === 0) {
                    return html + '<p>No active pilots found.</p></div>';
                }
                
                html += '<table class="wiki-table"><thead><tr>';
                html += '<th>Pilot Name</th><th>Location</th><th>Ship</th>';
                html += '<th>Credits</th><th>Alignment</th><th>Level</th>';
                html += '</tr></thead><tbody>';
                
                for (const player of this.data.players) {
                    const alignmentClass = player.alignment === 'loyal' || player.alignment === 'loyalist' ? 
                        'faction-loyalist' : 
                        (player.alignment === 'outlaw' || player.alignment === 'bandit' ? 
                            'faction-outlaw' : 'faction-neutral');
                    
                    html += '<tr>';
                    html += `<td><strong>${player.name}</strong></td>`;
                    html += `<td>${player.location_name || 'In Transit'}</td>`;
                    html += `<td>${player.ship_name || 'Unknown'}</td>`;
                    html += `<td>${player.credits.toLocaleString()}</td>`;
                    html += `<td class="${alignmentClass}">${player.alignment}</td>`;
                    html += `<td>Level ${player.level}</td>`;
                    html += '</tr>';
                }
                
                html += '</tbody></table></div>';
                return html;
            }
            renderNPCs() {
                let html = '<div class="wiki-section"><h3>Dynamic NPCs</h3>';
                
                if (!this.data.npcs || this.data.npcs.length === 0) {
                    return html + '<p>No dynamic NPCs found.</p></div>';
                }
                
                html += '<table class="wiki-table"><thead><tr>';
                html += '<th>Name</th><th>Callsign</th><th>Ship</th>';
                html += '<th>Location</th><th>Credits</th><th>Alignment</th>';
                html += '<th>Combat Rating</th>';
                html += '</tr></thead><tbody>';
                
                for (const npc of this.data.npcs) {
                    const alignmentClass = npc.alignment === 'loyal' || npc.alignment === 'friendly' ? 
                        'faction-loyalist' : 
                        (npc.alignment === 'bandit' || npc.alignment === 'hostile' || npc.alignment === 'pirate' ? 
                            'faction-outlaw' : 'faction-neutral');
                    
                    html += '<tr>';
                    html += `<td><strong>${npc.name}</strong></td>`;
                    html += `<td>${npc.callsign}</td>`;
                    html += `<td>${npc.ship_name} (${npc.ship_type})</td>`;
                    html += `<td>${npc.location_name || 'Unknown'}</td>`;
                    html += `<td>${npc.credits.toLocaleString()}</td>`;
                    html += `<td class="${alignmentClass}">${npc.alignment}</td>`;
                    html += `<td>${npc.combat_rating}/10</td>`;
                    html += '</tr>';
                }
                
                html += '</tbody></table></div>';
                return html;
            }
            renderLogs() {
                let html = '<div class="wiki-section"><h3>Recent Activity Logs</h3>';
                
                if (!this.data.logs || this.data.logs.length === 0) {
                    return html + '<p>No recent activity.</p></div>';
                }
                
                for (const log of this.data.logs) {
                    html += '<div class="wiki-card">';
                    html += `<h4>${log.game_date} - ${log.location_name}</h4>`;
                    html += `<p><strong>${log.character_name}</strong> ${log.action}</p>`;
                    html += '</div>';
                }
                
                return html + '</div>';
            }
            
            renderNews() {
                let html = '<div class="wiki-section"><h3>Galactic News Feed</h3>';
                
                if (!this.data.news || this.data.news.length === 0) {
                    return html + '<p>No recent news.</p></div>';
                }
                
                for (const article of this.data.news) {
                    html += '<div class="wiki-card">';
                    html += `<h4>${article.title}</h4>`;
                    html += `<p class="news-date">${article.game_date}</p>`;
                    html += `<p>${article.content}</p>`;
                    html += '</div>';
                }
                
                return html + '</div>';
            }
            
            showLocationInfoFromWiki(locationId) {
                console.log('Wiki: Attempting to show location info for:', locationId);
                console.log('Wiki: Data available:', !!this.data);
                console.log('Wiki: Locations available:', !!this.data?.locations);
                console.log('Wiki: All locations:', this.data?.locations);
                
                if (!this.data || !this.data.locations) {
                    console.error('Wiki: No data or locations available');
                    return;
                }
                
                // Find the location data - locations is an array in wiki data
                console.log('Wiki: Looking for location ID (type):', typeof locationId, locationId);
                const location = this.data.locations.find(loc => {
                    console.log('Wiki: Comparing with location ID (type):', typeof loc.id, loc.id);
                    return loc.id == locationId || String(loc.id) === String(locationId);
                });
                console.log('Wiki: Found location:', location);
                if (!location) {
                    console.error('Wiki: Location not found:', locationId);
                    console.log('Wiki: Available location IDs:', this.data.locations.map(l => l.id));
                    return;
                }
                
                // Count players and NPCs at this location
                const players = this.data.players || Object.values(this.data.players || {});
                const npcs = this.data.npcs || Object.values(this.data.npcs || {});
                const playerCount = (Array.isArray(players) ? players : Object.values(players)).filter(p => p.location === locationId).length;
                const npcCount = (Array.isArray(npcs) ? npcs : Object.values(npcs)).filter(n => n.location === locationId).length;
                
                // Get info panel element
                const locationInfo = document.getElementById('wiki-location-info');
                console.log('Wiki: Location info panel element:', locationInfo);
                if (!locationInfo) {
                    console.error('Wiki: Location info panel element not found');
                    return;
                }
                
                // Populate info panel with location details
                locationInfo.innerHTML = `
                    <button class="info-panel-close">×</button>
                    <h3>${location.name}</h3>
                    <div class="location-detail">
                        <strong>Type:</strong> ${location.type.replace('_', ' ')}
                    </div>
                    <div class="location-detail">
                        <strong>System:</strong> ${location.system}
                    </div>
                    <div class="location-detail">
                        <strong>Wealth:</strong> ${location.wealth}/10
                    </div>
                    <div class="location-detail">
                        <strong>Population:</strong> ${location.population || 'Unknown'}
                    </div>
                    <div class="location-detail">
                        <strong>Faction Control:</strong> ${location.faction}
                    </div>
                    ${location.owner_name ? `
                    <div class="location-detail">
                        <strong>Owner:</strong> ${location.owner_name}
                    </div>
                    <div class="location-detail">
                        <strong>Docking Fee:</strong> ${location.docking_fee || 0} credits
                    </div>` : ''}
                    <div class="location-detail">
                        <strong>Players Here:</strong> ${playerCount}
                    </div>
                    <div class="location-detail">
                        <strong>NPCs Here:</strong> ${npcCount}
                    </div>
                    ${location.description ? `
                    <div class="location-detail">
                        <strong>Description:</strong> ${location.description}
                    </div>` : ''}
                    ${this.getConnectedRoutesInfo(locationId)}
                `;
                
                // Show the info panel
                console.log('Wiki: Showing location info panel');
                // No backdrop needed
                locationInfo.style.display = 'block';
                locationInfo.classList.add('visible');
                
                // Add event listener for close button with touch support
                const closeBtn = locationInfo.querySelector('.info-panel-close');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => this.closeInfoPanel());
                    closeBtn.addEventListener('touchend', (e) => {
                        e.stopPropagation();
                        this.closeInfoPanel();
                    });
                }
                
                // Ensure proper overlay behavior for wiki panel
                setTimeout(() => {
                    const isVisible = locationInfo.classList.contains('visible');
                    const hasDisplay = locationInfo.style.display === 'block';
                    const computedStyle = window.getComputedStyle(locationInfo);
                    console.log('Wiki: Panel visible class:', isVisible, 'Display style:', hasDisplay);
                    console.log('Wiki: Computed position:', computedStyle.position, 'z-index:', computedStyle.zIndex);
                    
                    // Ensure the panel displays as a proper overlay
                    if (!isVisible || hasDisplay !== 'block' || computedStyle.position !== 'fixed') {
                        console.warn('Wiki: Panel not displaying properly, applying enhanced styles');
                        locationInfo.style.position = 'fixed';
                        locationInfo.style.display = 'block';
                        locationInfo.style.zIndex = '9999';
                        locationInfo.style.bottom = '0';
                        locationInfo.style.left = '0';
                        locationInfo.style.right = '0';
                        locationInfo.style.transform = 'translateY(0)';
                        locationInfo.classList.add('visible');
                    }
                }, 100);
                
                console.log('Wiki: Location info panel visibility class added');
            }
            
            getConnectedRoutesInfo(locationId) {
                if (!this.data || !this.data.routes) return '';
                
                const connectedRoutes = this.data.routes.filter(r => 
                    r.origin == locationId || r.destination == locationId
                );
                
                if (connectedRoutes.length === 0) return '';
                
                let routeInfo = '<div class="location-detail"><strong>Connected Routes:</strong><br>';
                
                connectedRoutes.forEach(route => {
                    let emoji = '🔵'; // Default gated
                    if (route.corridor_type === 'local_space' || (route.name && route.name.includes('Approach'))) {
                        emoji = '🌌'; // Local space
                    } else if (route.corridor_type === 'ungated') {
                        emoji = '⭕'; // Ungated
                    }
                    
                    // Determine destination name
                    const isOrigin = route.origin == locationId;
                    const destinationName = isOrigin ? route.dest_name : route.origin_name;
                    const direction = isOrigin ? '→' : '←';
                    
                    routeInfo += `${emoji} ${direction} ${destinationName}<br>`;
                });
                
                routeInfo += '<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 5px;">';
                routeInfo += '🌌 = Local Space | 🔵 = Gated | ⭕ = Ungated</div>';
                routeInfo += '</div>';
                
                return routeInfo;
            }

            showRouteInfoFromWiki(routeId) {
                console.log('Wiki: Attempting to show route info for:', routeId);
                console.log('Wiki: Data available:', !!this.data);
                console.log('Wiki: Routes available:', !!this.data?.routes);
                
                if (!this.data || !this.data.routes) {
                    console.error('Wiki: No data or routes available');
                    return;
                }
                
                // Find the route data - routes is an array in wiki data
                console.log('Wiki: Looking for route ID (type):', typeof routeId, routeId);
                const route = this.data.routes.find(r => {
                    console.log('Wiki: Comparing with route ID (type):', typeof r.id, r.id);
                    return r.id == routeId || String(r.id) === String(routeId);
                });
                console.log('Wiki: Found route:', route);
                if (!route) {
                    console.error('Wiki: Route not found:', routeId);
                    console.log('Wiki: Available route IDs:', this.data.routes.map(r => r.id));
                    return;
                }
                
                // Calculate travel time string
                const minutes = Math.floor(route.travel_time / 60);
                const seconds = route.travel_time % 60;
                const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
                
                // Count travelers on this route
                const players = this.data.players || Object.values(this.data.players || {});
                const travelers = (Array.isArray(players) ? players : Object.values(players)).filter(p => p.traveling && p.corridor_id === routeId);
                
                // Get info panel element  
                const locationInfo = document.getElementById('wiki-location-info');
                console.log('Wiki: Route info panel element:', locationInfo);
                if (!locationInfo) {
                    console.error('Wiki: Route info panel element not found');
                    return;
                }
                
                // Determine route emoji based on type
                let routeEmoji = '🔵'; // Default gated
                if (route.corridor_type === 'local_space' || (route.name && route.name.includes('Approach'))) {
                    routeEmoji = '🌌'; // Local space
                } else if (route.corridor_type === 'ungated') {
                    routeEmoji = '⭕'; // Ungated
                }
                
                // Populate info panel with route details
                locationInfo.innerHTML = `
                    <button class="info-panel-close">×</button>
                    <h3>${routeEmoji} ${route.name || 'Unknown Route'}</h3>
                    <div class="location-detail">
                        <strong>Route:</strong> ${route.origin_name} → ${route.dest_name}
                    </div>
                    <div class="location-detail">
                        <strong>Travel Time:</strong> ${timeStr}
                    </div>
                    <div class="location-detail">
                        <strong>Danger Level:</strong> ${route.danger_level}/10 ${'⚠️'.repeat(Math.min(route.danger_level || 0, 3))}
                    </div>
                    <div class="location-detail">
                        <strong>Stability:</strong> ${route.stability}%
                    </div>
                    <div class="location-detail">
                        <strong>Travelers:</strong> ${travelers.length}
                    </div>
                    ${travelers.length > 0 ? `
                    <div class="location-detail" style="margin-top: 10px;">
                        <strong>Currently Traveling:</strong><br>
                        ${travelers.map(t => `• ${t.name}`).join('<br>')}
                    </div>` : ''}
                    ${route.description ? `
                    <div class="location-detail">
                        <strong>Description:</strong> ${route.description}
                    </div>` : ''}
                `;
                
                // Show the info panel
                console.log('Wiki: Showing route info panel');
                // No backdrop needed
                locationInfo.style.display = 'block';
                locationInfo.classList.add('visible');
                
                // Add event listener for close button with touch support
                const closeBtn = locationInfo.querySelector('.info-panel-close');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => this.closeInfoPanel());
                    closeBtn.addEventListener('touchend', (e) => {
                        e.stopPropagation();
                        this.closeInfoPanel();
                    });
                }
                
                // Ensure proper overlay behavior for wiki panel
                setTimeout(() => {
                    const isVisible = locationInfo.classList.contains('visible');
                    const hasDisplay = locationInfo.style.display === 'block';
                    const computedStyle = window.getComputedStyle(locationInfo);
                    console.log('Wiki: Route panel visible class:', isVisible, 'Display style:', hasDisplay);
                    console.log('Wiki: Computed position:', computedStyle.position, 'z-index:', computedStyle.zIndex);
                    
                    // Ensure the panel displays as a proper overlay
                    if (!isVisible || hasDisplay !== 'block' || computedStyle.position !== 'fixed') {
                        console.warn('Wiki: Route panel not displaying properly, applying enhanced styles');
                        locationInfo.style.position = 'fixed';
                        locationInfo.style.display = 'block';
                        locationInfo.style.zIndex = '9999';
                        locationInfo.style.bottom = '0';
                        locationInfo.style.left = '0';
                        locationInfo.style.right = '0';
                        locationInfo.style.transform = 'translateY(0)';
                        locationInfo.classList.add('visible');
                    }
                }, 100);
                
                console.log('Wiki: Route info panel visibility class added');
            }
            
            createBackdrop() {
                // Remove existing backdrop if present
                const existingBackdrop = document.querySelector('.info-panel-backdrop');
                if (existingBackdrop) {
                    existingBackdrop.parentNode.removeChild(existingBackdrop);
                }
                
                // Create backdrop element for mobile
                const backdrop = document.createElement('div');
                backdrop.className = 'info-panel-backdrop';
                backdrop.onclick = () => this.closeInfoPanel();
                document.body.appendChild(backdrop);
                
                // Show backdrop with transition
                setTimeout(() => {
                    backdrop.classList.add('visible');
                }, 10);
            }
            
            closeInfoPanel() {
                // Hide the wiki info panel without clearing any selection state
                const locationInfo = document.getElementById('wiki-location-info');
                if (locationInfo) {
                    locationInfo.style.display = 'none';
                    locationInfo.classList.remove('visible');
                }
                
                // Remove backdrop if it exists
                const backdrop = document.querySelector('.info-panel-backdrop');
                if (backdrop) {
                    backdrop.classList.remove('visible');
                    // Remove backdrop element after transition
                    setTimeout(() => {
                        if (backdrop.parentNode) {
                            backdrop.parentNode.removeChild(backdrop);
                        }
                    }, 300);
                }
            }
        }
        
        // Initialize wiki when page loads
        document.addEventListener('DOMContentLoaded', () => {
            console.log('Wiki: DOMContentLoaded event fired');
            
            // Initialize theme from URL parameter or storage
            if (window.themeManager) {
                window.themeManager.initializeTheme('blue');
            }
            
            window.galacticWiki = new GalacticWiki();
            console.log('Wiki: GalacticWiki instance created and assigned to window');
        });
        '''


async def setup(bot):
    await bot.add_cog(WebMapCog(bot))