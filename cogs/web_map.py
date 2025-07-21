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


class WebMapCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.app = None
        self.runner = None
        self.site = None
        self.is_running = False
        self.host = '0.0.0.0'
        self.port = 8090
        self.external_ip = None
        self.domain = None
        
        # Cache for performance
        self.cache = {
            'locations': {},
            'corridors': [],
            'players': {},
            'npcs': {},
            'news': [],
            'last_update': None
        }
        
        # Update interval
        self.update_cache.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_cache.cancel()
        if self.is_running:
            asyncio.create_task(self.stop_webmap())
    
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
        # Get locations with explicit column names
        locations_data = self.db.execute_query(
            """SELECT l.location_id, l.name, l.location_type, l.x_coord, l.y_coord,
                      l.system_name, l.wealth_level, l.population, l.description, l.faction,
                      lo.owner_id, lo.docking_fee, c.name as owner_name
               FROM locations l
               LEFT JOIN location_ownership lo ON l.location_id = lo.location_id
               LEFT JOIN characters c ON lo.owner_id = c.user_id
               ORDER BY l.location_id""",
            fetch='all'
        )
        
        locations = {}
        for loc in locations_data:
            try:
                loc_id = loc[0]
                locations[loc_id] = {
                    'id': loc_id,
                    'name': loc[1],
                    'type': loc[2],
                    'x': float(loc[3]) if loc[3] is not None else 0.0,
                    'y': float(loc[4]) if loc[4] is not None else 0.0,
                    'system': loc[5],
                    'wealth': loc[6],
                    'population': loc[7],
                    'description': loc[8],
                    'faction': loc[9] if loc[9] else 'Independent',
                    'owner_id': loc[10],
                    'owner_name': loc[12],
                    'docking_fee': loc[11] if loc[11] else 0,
                    # Default values for non-existent columns
                    'tech_level': 5,
                    'stability': 75
                }
            except Exception as e:
                print(f"Error processing location {loc_id if 'loc_id' in locals() else 'unknown'}: {e}")
                continue
        
        # Get corridors
        corridors_data = self.db.execute_query(
            """SELECT corridor_id, origin_location, destination_location, 
                      name, travel_time, danger_level
               FROM corridors
               WHERE is_active = 1""",
            fetch='all'
        )
        
        corridors = []
        for corr in corridors_data:
            corridors.append({
                'id': corr[0],
                'origin': corr[1],
                'destination': corr[2],
                'name': corr[3],
                'travel_time': corr[4],
                'danger_level': corr[5]
            })
        
        # Get active players - FIXED: use end_time not arrival_time, remove non-existent columns
        players_data = self.db.execute_query(
            """SELECT c.user_id, c.name, c.current_location, c.money,
                      t.corridor_id, t.start_time, t.end_time,
                      l.name as location_name, l.x_coord, l.y_coord,
                      c.level, c.experience
               FROM characters c
               LEFT JOIN travel_sessions t ON c.user_id = t.user_id AND t.status = 'traveling'
               LEFT JOIN locations l ON c.current_location = l.location_id""",
            fetch='all'
        )
        
        players = {}
        for player in players_data:
            try:
                players[player[0]] = {
                    'id': player[0],
                    'name': player[1],
                    'location': player[2],
                    'location_name': player[7],
                    'x': float(player[8]) if player[8] is not None else 0.0,
                    'y': float(player[9]) if player[9] is not None else 0.0,
                    'credits': player[3],
                    'traveling': player[4] is not None,
                    'corridor_id': player[4],
                    'travel_progress': self._calculate_travel_progress(player[5], player[6]) if player[4] else 0,
                    'level': player[10] if player[10] else 1,
                    'experience': player[11] if player[11] else 0
                }
            except Exception as e:
                print(f"Error parsing player {player[0] if player else 'unknown'}: {e}")
                continue
        
        # Get dynamic NPCs
        npcs_data = self.db.execute_query(
            """SELECT n.npc_id, n.name, n.callsign, n.current_location,
                      n.destination_location, n.travel_start_time, n.travel_duration,
                      n.alignment, n.is_alive, l.name as location_name,
                      l.x_coord, l.y_coord
               FROM dynamic_npcs n
               LEFT JOIN locations l ON n.current_location = l.location_id
               WHERE n.is_alive = 1""",
            fetch='all'
        )
        
        npcs = {}
        for npc in npcs_data:
            try:
                npcs[npc[0]] = {
                    'id': npc[0],
                    'name': npc[1],
                    'callsign': npc[2],
                    'location': npc[3],
                    'location_name': npc[9],
                    'x': float(npc[10]) if npc[10] is not None else 0.0,
                    'y': float(npc[11]) if npc[11] is not None else 0.0,
                    'destination': npc[4],
                    'traveling': npc[4] is not None,
                    'travel_progress': self._calculate_npc_travel_progress(npc[5], npc[6]) if npc[4] else 0,
                    'alignment': npc[7]
                }
            except Exception as e:
                print(f"Error parsing NPC {npc[0] if npc else 'unknown'}: {e}")
                continue
        
        # Get recent news - FIXED: use correct galactic_history columns
        news_data = self.db.execute_query(
            """SELECT event_title, event_description, location_id, event_date
               FROM galactic_history
               ORDER BY created_at DESC
               LIMIT 20""",
            fetch='all'
        )
        
        news = []
        for item in news_data:
            news.append({
                'title': item[0],
                'content': item[1],
                'location_id': item[2],
                'timestamp': item[3],
                'game_date': self._convert_to_game_date(item[3])
            })
        
        # Update cache with timestamp
        self.cache = {
            'locations': locations,
            'corridors': corridors,
            'players': players,
            'npcs': npcs,
            'news': news,
            'last_update': datetime.now().isoformat()
        }
    
    def _calculate_travel_progress(self, start_time, end_time):
        """Calculate travel progress as percentage"""
        if not start_time or not end_time:
            return 0
        
        try:
            # Handle both string and datetime objects
            if isinstance(start_time, str):
                start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start = start_time
                
            if isinstance(end_time, str):
                end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
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
            start = datetime.fromisoformat(start_time)
            now = datetime.now()
            elapsed = (now - start).total_seconds()
            
            progress = (elapsed / duration) * 100
            return min(max(progress, 0), 100)
        except:
            return 0
    
    def _convert_to_game_date(self, timestamp):
        """Convert real date to in-game date (2700s)"""
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            
            # Game year calculation
            game_year = 2700 + (dt.year - 2024)
            return dt.strftime(f"{game_year}-%m-%d %H:%M GST")
        except:
            return "Unknown Date"
    
    webmap_group = app_commands.Group(name="webmap", description="Web map management commands")
    
    @webmap_group.command(name="start", description="Start the web map server")
    @app_commands.describe(
        port="Port to run the server on (default: 8090)",
        host="Host to bind to (default: 0.0.0.0)",
        domain="Domain name for the server (optional)"
    )
    async def start_webmap(self, interaction: discord.Interaction, port: int = 8090, host: str = '0.0.0.0', domain: str = None):
        """Start the web map server"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if self.is_running:
            await interaction.response.send_message("Web map is already running!", ephemeral=True)
            return
        
        
        await interaction.response.defer()
        
        try:
            self.port = port
            self.host = host
            self.domain = domain
            
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
            protocol = "https" if self.port == 443 else "http"
            port_str = "" if self.port in [80, 443] else f":{self.port}"
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
        self.app.router.add_static('/', path=os.path.dirname(__file__))
    
    async def handle_index(self, request):
        """Serve the landing page"""
        html_content = self.get_landing_html()
        return web.Response(text=html_content, content_type='text/html')
    
    async def handle_map(self, request):
        """Serve the map page"""
        html_content = self.get_map_html()
        return web.Response(text=html_content, content_type='text/html')
    
    async def handle_wiki(self, request):
        """Serve the wiki page"""
        html_content = self.get_wiki_html()
        return web.Response(text=html_content, content_type='text/html')
    
    async def handle_api_map_data(self, request):
        """API endpoint for map data"""
        return web.json_response(self.cache)
    
    async def handle_api_wiki_data(self, request):
        """API endpoint for wiki data"""
        wiki_data = await self._compile_wiki_data()
        return web.json_response(wiki_data)
    
    async def _compile_wiki_data(self):
        """Compile comprehensive wiki data"""
        # Get detailed location information - removed tech_level and stability
        locations = self.db.execute_query(
            """SELECT l.location_id, l.name, l.location_type, l.x_coord, l.y_coord,
                      l.system_name, l.wealth_level, l.population, l.description, l.faction,
                      COUNT(DISTINCT c.user_id) as player_count,
                      COUNT(DISTINCT sn.npc_id) as static_npc_count,
                      COUNT(DISTINCT dn.npc_id) as dynamic_npc_count
               FROM locations l
               LEFT JOIN characters c ON l.location_id = c.current_location
               LEFT JOIN static_npcs sn ON l.location_id = sn.location_id
               LEFT JOIN dynamic_npcs dn ON l.location_id = dn.current_location AND dn.is_alive = 1
               GROUP BY l.location_id""",
            fetch='all'
        )
        
        # Get route information - removed stability
        routes = self.db.execute_query(
            """SELECT c.corridor_id, c.origin_location, c.destination_location, c.name,
                      c.travel_time, c.danger_level,
                      ol.name as origin_name, dl.name as dest_name,
                      ol.system_name as origin_system, dl.system_name as dest_system
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.is_active = 1
               ORDER BY ol.name, dl.name""",
            fetch='all'
        )
        
        # Get player information - only existing columns
        players = self.db.execute_query(
            """SELECT c.user_id, c.name, c.current_location, c.money,
                      c.level, c.experience, c.alignment,
                      l.name as location_name, s.name as ship_name
               FROM characters c
               LEFT JOIN locations l ON c.current_location = l.location_id
               LEFT JOIN ships s ON c.ship_id = s.ship_id
               ORDER BY c.name""",
            fetch='all'
        )
        
        # Get dynamic NPC information
        dynamic_npcs = self.db.execute_query(
            """SELECT n.npc_id, n.name, n.callsign, n.age, n.ship_name, n.ship_type,
                      n.current_location, n.credits, n.alignment, n.combat_rating,
                      l.name as location_name
               FROM dynamic_npcs n
               LEFT JOIN locations l ON n.current_location = l.location_id
               WHERE n.is_alive = 1
               ORDER BY n.name""",
            fetch='all'
        )
        
        # Get location logs
        location_logs = self.db.execute_query(
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
            'news': self.cache['news']
        }
    
    def _format_wiki_locations(self, locations):
        """Format location data for wiki"""
        formatted = []
        for loc in locations:
            formatted.append({
                'id': loc[0],
                'name': loc[1],
                'type': loc[2],
                'system': loc[5],
                'wealth': loc[6],
                'population': loc[7],
                'tech_level': 5,  # Default since column doesn't exist
                'description': loc[8],
                'faction': loc[9],
                'stability': 75,  # Default since column doesn't exist
                'player_count': loc[10],
                'static_npc_count': loc[11],
                'dynamic_npc_count': loc[12]
            })
        return formatted

    def _format_wiki_routes(self, routes):
        """Format route data for wiki"""
        formatted = []
        for route in routes:
            formatted.append({
                'id': route[0],
                'origin': route[1],
                'destination': route[2],
                'name': route[3],
                'travel_time': route[4],
                'danger_level': route[5],
                'stability': 90,  # Default since column doesn't exist
                'origin_name': route[6],
                'dest_name': route[7],
                'origin_system': route[8],
                'dest_system': route[9]
            })
        return formatted

    def _format_wiki_players(self, players):
        """Format player data for wiki"""
        formatted = []
        for player in players:
            formatted.append({
                'id': player[0],
                'name': player[1],
                'location': player[2],
                'credits': player[3],
                'level': player[4] if player[4] else 1,
                'experience': player[5] if player[5] else 0,
                'alignment': player[6] if player[6] else 'neutral',
                'location_name': player[7],
                'ship_name': player[8],
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
                'id': npc[0],
                'name': npc[1],
                'callsign': npc[2],
                'age': npc[3],
                'ship_name': npc[4],
                'ship_type': npc[5],
                'location': npc[6],
                'credits': npc[7],
                'alignment': npc[8],
                'combat_rating': npc[9],
                'location_name': npc[10]
            })
        return formatted

    def _format_wiki_logs(self, logs):
        """Format location logs for wiki"""
        formatted = []
        for log in logs:
            formatted.append({
                'id': log[0],
                'location_id': log[1],
                'location_name': log[6],
                'character_name': log[3],
                'action': log[4],
                'timestamp': log[5],
                'game_date': self._convert_to_game_date(log[5])
            })
        return formatted
    
    def get_landing_html(self):
        """Get landing page HTML"""
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
        <div class="map-header">
            <div class="header-section">
                <h1 class="map-title">Galaxy Map</h1>
                <div class="map-status">
                    <span class="status-indicator"></span>
                    <span id="last-update">Loading...</span>
                </div>
            </div>
            <div class="header-controls">
                <a href="/wiki" class="nav-button">Wiki</a>
                <a href="/" class="nav-button">Home</a>
            </div>
        </div>
        
        <div class="map-controls">
            <div class="control-group">
                <label class="toggle-control">
                    <input type="checkbox" id="toggle-labels">
                    <span>Show Labels</span>
                </label>
                <label class="toggle-control">
                    <input type="checkbox" id="toggle-routes" checked>
                    <span>Show Routes</span>
                </label>
                <label class="toggle-control">
                    <input type="checkbox" id="toggle-players">
                    <span>Show Players</span>
                </label>
                <label class="toggle-control">
                    <input type="checkbox" id="toggle-npcs">
                    <span>Show NPCs</span>
                </label>
            </div>
            <div class="control-group">
                <button class="control-button" onclick="galaxyMap.resetView()">Reset View</button>
            </div>
        </div>
        
        <div class="map-viewport">
            <canvas id="galaxy-map"></canvas>
            <div id="tooltip" class="map-tooltip"></div>
            <div id="location-info" class="location-info-panel">
                <button class="info-panel-close" onclick="document.getElementById('location-info').style.display='none'">×</button>
                <!-- Content will be dynamically inserted here -->
            </div>
        </div>
    </div>
    
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
                <h1 class="wiki-title">GALACTIC WIKI</h1>
                <div class="wiki-status">
                    <div class="status-indicator online"></div>
                    <span>DATABASE ONLINE</span>
                </div>
            </div>
            <div class="header-controls">
                <a href="/" class="nav-button">HOME</a>
                <a href="/map" class="nav-button">MAP</a>
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
    
    <script>''' + self.get_wiki_script() + '''</script>
</body>
</html>'''
    
    def get_shared_css(self):
        """Get shared CSS styles"""
        return '''
        :root {
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
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Tektur', monospace;
            background: var(--primary-bg);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
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
            opacity: 0.3;
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
        
        .main-container {
            position: relative;
            z-index: 10;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        
        .game-header {
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 0 40px var(--glow-primary);
            margin-bottom: 3rem;
        }
        
        .terminal-indicator {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        
        .power-light {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--success-color);
            box-shadow: 0 0 15px var(--success-color);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .game-title {
            font-size: 3rem;
            font-weight: 900;
            color: var(--primary-color);
            text-shadow: 0 0 30px var(--glow-primary);
            margin-bottom: 0.5rem;
        }
        
        .game-subtitle {
            font-size: 0.9rem;
            color: var(--text-secondary);
            letter-spacing: 3px;
        }
        
        .action-buttons {
            display: flex;
            gap: 2rem;
            justify-content: center;
            flex-wrap: wrap;
        }
        
        .action-button {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1.5rem 2rem;
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 8px;
            text-decoration: none;
            color: var(--text-primary);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }
        
        .action-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 30px rgba(0, 255, 255, 0.3);
            border-color: var(--secondary-color);
        }
        
        .button-icon {
            font-size: 2rem;
            filter: drop-shadow(0 0 10px var(--glow-primary));
        }
        
        .button-text {
            text-align: left;
        }
        
        .button-title {
            font-weight: 700;
            font-size: 1.1rem;
            margin-bottom: 0.25rem;
        }
        
        .button-subtitle {
            font-size: 0.8rem;
            color: var(--text-secondary);
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
        '''
    
    def get_map_css(self):
        """Get map-specific CSS"""
        return '''
        .map-container {
            position: relative;
            z-index: 10;
            width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .map-header {
            background: var(--gradient-panel);
            border-bottom: 2px solid var(--primary-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-section {
            display: flex;
            align-items: center;
            gap: 2rem;
        }
        
        .map-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
            text-shadow: 0 0 20px var(--glow-primary);
        }
        
        .map-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success-color);
            box-shadow: 0 0 10px var(--success-color);
        }
        
        .header-controls {
            display: flex;
            gap: 1rem;
        }
        
        .nav-button {
            padding: 0.5rem 1rem;
            background: var(--accent-bg);
            border: 1px solid var(--primary-color);
            border-radius: 4px;
            text-decoration: none;
            color: var(--text-primary);
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }
        
        .nav-button:hover {
            background: var(--primary-color);
            color: var(--primary-bg);
            box-shadow: 0 0 15px var(--glow-primary);
        }
        
        .map-controls {
            background: var(--secondary-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .control-group {
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        
        .toggle-control {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            font-size: 0.9rem;
            color: var(--text-secondary);
            transition: color 0.3s ease;
        }
        
        .toggle-control:hover {
            color: var(--text-primary);
        }
        
        .toggle-control input[type="checkbox"] {
            width: 18px;
            height: 18px;
            accent-color: var(--primary-color);
            cursor: pointer;
        }
        
        .toggle-control input[type="checkbox"]:checked {
            box-shadow: 0 0 5px var(--glow-primary);
        }
        .control-button {
            padding: 0.5rem 1rem;
            background: var(--accent-bg);
            border: 1px solid var(--primary-color);
            border-radius: 4px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .control-button:hover {
            background: var(--primary-color);
            color: var(--primary-bg);
            box-shadow: 0 0 15px var(--glow-primary);
        }
        
        .map-viewport {
            flex: 1;
            position: relative;
            overflow: hidden;
            background: radial-gradient(ellipse at center, var(--secondary-bg) 0%, var(--primary-bg) 100%);
        }
        
        #galaxy-map {
            position: absolute;
            top: 0;
            left: 0;
            cursor: grab;
        }
        
        #galaxy-map:active {
            cursor: grabbing;
        }
        
        .map-tooltip {
            position: absolute;
            background: var(--gradient-panel);
            border: 1px solid var(--primary-color);
            border-radius: 4px;
            padding: 0.75rem 1rem;
            font-size: 0.85rem;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
            z-index: 100;
            max-width: 300px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(10px);
        }
        .map-tooltip strong {
            color: var(--primary-color);
            display: block;
            margin-bottom: 0.25rem;
            font-size: 0.95rem;
        }
        .map-tooltip.visible {
            opacity: 1;
        }
        
        .location-info-panel {
            position: absolute;
            right: 2rem;
            bottom: 2rem;
            width: 350px;
            max-height: 70vh;
            overflow-y: auto;
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 0 30px var(--glow-primary);
            z-index: 50;
            display: none;
            backdrop-filter: blur(10px);
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
        }

        .location-info-panel h3 {
            color: var(--primary-color);
            margin-bottom: 1rem;
            font-size: 1.3rem;
            text-shadow: 0 0 10px var(--glow-primary);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
        }

        .location-detail {
            margin-bottom: 0.75rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        .location-detail strong {
            color: var(--text-primary);
            display: inline-block;
            margin-right: 0.5rem;
        }
        .route-type-local {
            color: #88ff88;
        }

        .route-type-gated {
            color: #00cccc;
        }

        .route-type-ungated {
            color: #ff6600;
        }
        /* Map object styles */
        .location-colony { fill: #00ff88; }
        .location-space_station { fill: #00ffff; }
        .location-outpost { fill: #ffaa00; }
        .location-gate { fill: #ff00ff; }
        
        .corridor-line {
            stroke: var(--border-color);
            stroke-width: 1;
            fill: none;
            opacity: 0.5;
        }
        /* Map controls responsive adjustments */
        @media (max-width: 768px) {
            .map-controls {
                flex-direction: column;
                gap: 1rem;
                padding: 0.75rem 1rem;
            }
            
            .control-group {
                width: 100%;
                justify-content: space-between;
                flex-wrap: wrap;
            }
            
            .location-info-panel {
                position: fixed;
                bottom: 0;
                right: 0;
                left: 0;
                width: 100%;
                max-height: 50vh;
                border-radius: 8px 8px 0 0;
            }
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

        /* Close button for info panel */
        .info-panel-close {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            transition: color 0.3s ease;
            padding: 0.25rem;
            line-height: 1;
        }

        .info-panel-close:hover {
            color: var(--primary-color);
            text-shadow: 0 0 10px var(--glow-primary);
        }
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
                this.isDragging = false;
                this.dragStartX = 0;
                this.dragStartY = 0;
                this.selectedLocation = null;
                this.selectedCorridor = null;
                this.hoveredCorridor = null;
                this.showLabels = false;
                this.showPlayers = false;
                this.showNPCs = false;
                this.showRoutes = true; // Default to true to match HTML
                
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
            }
            
            async loadData() {
                try {
                    const response = await fetch('/api/map-data');
                    this.data = await response.json();
                    this.updateLastUpdate();
                    this.render();
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
            
            render() {
                if (!this.data) return;
                
                // Clear canvas
                this.ctx.fillStyle = '#000408';
                this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                
                // Draw grid
                this.drawGrid();
                
                // Draw corridors
                if (this.showRoutes) {
                    this.drawCorridors();
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
                    
                    const start = this.worldToScreen(origin.x, origin.y);
                    const end = this.worldToScreen(dest.x, dest.y);
                    
                    // Determine if this corridor is selected or related to selected location
                    const isSelected = this.selectedCorridor && 
                        this.selectedCorridor.id === corridor.id;
                    const isRelatedToLocation = this.selectedLocation && 
                        (corridor.origin == this.selectedLocation || 
                         corridor.destination == this.selectedLocation);
                    const isHovered = this.hoveredCorridor && 
                        this.hoveredCorridor.id === corridor.id;
                    
                    // Base line width - increased for better visibility
                    let lineWidth = Math.max(3, Math.min(8, 5 / Math.sqrt(this.scale)));
                    
                    // Determine corridor type and styling
                    let strokeStyle = 'rgba(0, 51, 68, 0.3)'; // Default faded
                    let dashPattern = [];
                    
                    if (corridor.name && corridor.name.includes('Approach')) {
                        // Local space - dotted line
                        strokeStyle = 'rgba(136, 255, 136, 0.5)'; // Light green
                        dashPattern = [5, 5];
                    } else if (corridor.name && corridor.name.includes('Ungated')) {
                        // Ungated - dashed line
                        strokeStyle = 'rgba(255, 102, 0, 0.5)'; // Orange
                        dashPattern = [10, 5];
                    } else {
                        // Gated - solid line
                        strokeStyle = 'rgba(0, 204, 204, 0.5)'; // Cyan
                    }
                    
                    // Check if any players are in this corridor
                    const hasPlayers = Object.values(this.data.players).some(p => 
                        p.traveling && p.corridor_id === corridor.id
                    );
                    
                    // Apply highlighting
                    if (isSelected) {
                        strokeStyle = '#00ffff';
                        lineWidth = Math.max(4, Math.min(10, 8 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 20;
                        this.ctx.shadowColor = '#00ffff';
                    } else if (isRelatedToLocation) {
                        // Highlight routes from/to selected location
                        if (corridor.name && corridor.name.includes('Approach')) {
                            strokeStyle = '#88ff88';
                        } else if (corridor.name && corridor.name.includes('Ungated')) {
                            strokeStyle = '#ff6600';
                        } else {
                            strokeStyle = '#00cccc';
                        }
                        lineWidth = Math.max(3, Math.min(8, 6 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 10;
                        this.ctx.shadowColor = strokeStyle;
                    } else if (isHovered) {
                        lineWidth = Math.max(3, Math.min(8, 6 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 15;
                        this.ctx.shadowColor = strokeStyle;
                    } else if (hasPlayers) {
                        strokeStyle = '#00ffff';
                        lineWidth = Math.max(3, Math.min(8, 6 / Math.sqrt(this.scale)));
                        this.ctx.shadowBlur = 10;
                        this.ctx.shadowColor = '#00ffff';
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
                    
                    // Draw direction indicators for selected corridors
                    if (isSelected || isRelatedToLocation) {
                        this.drawCorridorArrow(start, end, strokeStyle);
                    }
                }
                
                this.ctx.shadowBlur = 0;
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
                for (const [id, location] of Object.entries(this.data.locations)) {
                    const pos = this.worldToScreen(location.x, location.y);
                    
                    // Skip if off-screen
                    if (pos.x < -50 || pos.x > this.canvas.width + 50 ||
                        pos.y < -50 || pos.y > this.canvas.height + 50) continue;
                    
                    // Determine color based on type
                    const colors = {
                        colony: '#00ff88',
                        space_station: '#00ffff',
                        outpost: '#ffaa00',
                        gate: '#ff00ff'
                    };
                    
                    const color = colors[location.type] || '#ffffff';
                    
                    // Increased base sizes for better visibility
                    const baseSize = location.type === 'gate' ? 25 : 20;
                    const size = Math.max(baseSize / Math.sqrt(this.scale), 12);
                    
                    // Check if location is connected to selected corridor
                    const isCorridorDestination = this.selectedCorridor && 
                        (this.selectedCorridor.origin == id || 
                         this.selectedCorridor.destination == id);
                    
                    // Draw location
                    this.ctx.fillStyle = color;
                    this.ctx.shadowBlur = Math.min(30, 25 / Math.sqrt(this.scale));
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
                    } else {
                        // Draw circle for other locations
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
                    
                    // Draw name if labels are enabled
                    if (this.showLabels && this.scale > 0.8) {
                        this.ctx.fillStyle = '#ffffff';
                        this.ctx.font = `${Math.max(12, 14 / Math.sqrt(this.scale))}px 'Tektur', monospace`;
                        this.ctx.textAlign = 'center';
                        this.ctx.textBaseline = 'top';
                        this.ctx.shadowBlur = 5;
                        this.ctx.shadowColor = '#000000';
                        this.ctx.fillText(location.name, pos.x, pos.y + size + 5);
                    }
                }
                
                this.ctx.shadowBlur = 0;
            }
            
            drawPlayers() {
                this.ctx.fillStyle = '#00ff00';
                
                for (const [id, player] of Object.entries(this.data.players)) {
                    if (!player.location || player.traveling) continue;
                    
                    const location = this.data.locations[player.location];
                    if (!location) continue;
                    
                    const pos = this.worldToScreen(location.x, location.y);
                    
                    // Draw player indicator with inverse scaling
                    const triangleSize = Math.max(12 / Math.sqrt(this.scale), 6);

                    this.ctx.shadowBlur = Math.min(25, 20 / Math.sqrt(this.scale));
                    this.ctx.shadowColor = '#00ff00';
                    
                    this.ctx.beginPath();
                    this.ctx.moveTo(pos.x, pos.y - triangleSize * 2);
                    this.ctx.lineTo(pos.x - triangleSize, pos.y - triangleSize);
                    this.ctx.lineTo(pos.x + triangleSize, pos.y - triangleSize);
                    this.ctx.closePath();
                    this.ctx.fill();
                }
                
                this.ctx.shadowBlur = 0;
            }
            
            drawNPCs() {
                for (const [id, npc] of Object.entries(this.data.npcs)) {
                    if (!npc.location) continue;
                    
                    const location = this.data.locations[npc.location];
                    if (!location) continue;
                    
                    const pos = this.worldToScreen(location.x, location.y);
                    
                    // Determine NPC color based on alignment
                    if (npc.alignment === 'hostile' || npc.alignment === 'pirate') {
                        this.ctx.fillStyle = '#ff0000';
                    } else if (npc.alignment === 'friendly') {
                        this.ctx.fillStyle = '#00ff88';
                    } else {
                        this.ctx.fillStyle = '#ff6600';
                    }
                    
                    // Draw NPC indicator with inverse scaling
                    const squareSize = Math.max(10 / Math.sqrt(this.scale), 5);

                    this.ctx.shadowBlur = Math.min(20, 15 / Math.sqrt(this.scale));
                    this.ctx.shadowColor = this.ctx.fillStyle;
                    
                    this.ctx.fillRect(
                        pos.x - squareSize, 
                        pos.y - squareSize, 
                        squareSize * 2, 
                        squareSize * 2
                    );
                }
                
                this.ctx.shadowBlur = 0;
            }
            
            handleMouseDown(e) {
                this.isDragging = true;
                this.dragStartX = e.clientX - this.offsetX;
                this.dragStartY = e.clientY - this.offsetY;
                this.canvas.style.cursor = 'grabbing';
            }
            
            handleMouseMove(e) {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
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
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                this.zoom(delta);
            }
            
            handleClick(e) {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const worldPos = this.screenToWorld(x, y);
                
                // Check for corridor click first (they're drawn underneath)
                let clickedCorridor = null;
                if (this.showRoutes) {
                    for (const corridor of this.data.corridors) {
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
                    this.selectLocation(clickedLocation.id, clickedLocation.location);
                    this.selectedCorridor = null;
                } else if (clickedCorridor) {
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
                if (e.touches.length === 1) {
                    const touch = e.touches[0];
                    this.isDragging = true;
                    this.dragStartX = touch.clientX - this.offsetX;
                    this.dragStartY = touch.clientY - this.offsetY;
                }
            }
            
            handleTouchMove(e) {
                e.preventDefault();
                if (e.touches.length === 1 && this.isDragging) {
                    const touch = e.touches[0];
                    this.offsetX = touch.clientX - this.dragStartX;
                    this.offsetY = touch.clientY - this.dragStartY;
                    this.render();
                }
            }
            
            handleTouchEnd(e) {
                this.isDragging = false;
            }
            
            zoom(factor) {
                const newScale = this.scale * factor;
                if (newScale >= 0.5 && newScale <= 20) {
                    this.scale = newScale;
                    this.render();
                }
            }
            
            resetView() {
                this.scale = 1;
                this.offsetX = 0;
                this.offsetY = 0;
                this.render();
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
                if (corridor.name && corridor.name.includes('Approach')) {
                    corridorType = 'Local Space';
                } else if (corridor.name && corridor.name.includes('Ungated')) {
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
                                const type = r.name && r.name.includes('Approach') ? '🌌' : 
                                           r.name && r.name.includes('Ungated') ? '⭕' : '🔵';
                                routeInfo += `${type} → ${dest.name}<br>`;
                            }
                        });
                    }
                    
                    if (incomingRoutes.length > 0) {
                        routeInfo += '<br><strong>Incoming Routes:</strong><br>';
                        incomingRoutes.forEach(r => {
                            const origin = this.data.locations[r.origin];
                            if (origin) {
                                const type = r.name && r.name.includes('Approach') ? '🌌' : 
                                           r.name && r.name.includes('Ungated') ? '⭕' : '🔵';
                                routeInfo += `${type} ← ${origin.name}<br>`;
                            }
                        });
                    }
                }
                
                // Update info panel
                this.locationInfo.innerHTML = `
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
                `;
                
                this.locationInfo.style.display = 'block';
            }
            
            selectCorridor(corridor) {
                this.selectedCorridor = corridor;
                
                const origin = this.data.locations[corridor.origin];
                const dest = this.data.locations[corridor.destination];
                
                if (!origin || !dest) return;
                
                // Determine corridor type
                let corridorType = 'Gated Route';
                let typeIcon = '🔵';
                if (corridor.name && corridor.name.includes('Approach')) {
                    corridorType = 'Local Space Route';
                    typeIcon = '🌌';
                } else if (corridor.name && corridor.name.includes('Ungated')) {
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
                
                this.locationInfo.style.display = 'block';
            }
            
            hideLocationInfo() {
                this.locationInfo.style.display = 'none';
            }
        }

        // Initialize map when page loads
        document.addEventListener('DOMContentLoaded', () => {
            const map = new GalaxyMap();
        });
        '''
    
    def get_wiki_script(self):
        """Get wiki JavaScript"""
        return '''
        class GalacticWiki {
            constructor() {
                this.currentTab = 'locations';
                this.data = null;
                this.init();
            }
            
            async init() {
                this.setupEventListeners();
                await this.loadData();
            }
            
            setupEventListeners() {
                document.querySelectorAll('.wiki-tab').forEach(tab => {
                    tab.addEventListener('click', () => {
                        const tabName = tab.dataset.tab;
                        this.switchTab(tabName);
                    });
                });
            }
            
            async loadData() {
                try {
                    document.getElementById('loading').style.display = 'block';
                    document.getElementById('wiki-data').style.display = 'none';
                    
                    const response = await fetch('/api/wiki-data');
                    this.data = await response.json();
                    
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('wiki-data').style.display = 'block';
                    
                    this.renderCurrentTab();
                } catch (error) {
                    console.error('Failed to load wiki data:', error);
                    document.getElementById('loading').innerHTML = 'Failed to load data. Please refresh.';
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
                    html += '<th>Tech</th><th>Faction</th><th>Pilots</th><th>NPCs</th>';
                    html += '</tr></thead><tbody>';
                    
                    locations.sort((a, b) => a.name.localeCompare(b.name));
                    
                    for (const loc of locations) {
                        html += '<tr>';
                        html += `<td><strong>${loc.name}</strong></td>`;
                        html += `<td>${loc.type}</td>`;
                        html += `<td class="wealth-${loc.wealth}">${loc.wealth}</td>`;
                        html += `<td>${loc.population.toLocaleString()}</td>`;
                        html += `<td>${loc.tech_level}</td>`;
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
                    
                    html += '<tr>';
                    html += `<td><strong>${route.name}</strong></td>`;
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
                    const alignmentClass = player.alignment === 'loyal' ? 'faction-loyal' : 
                                          player.alignment === 'bandit' ? 'faction-bandit' : 'faction-neutral';
                    
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
        }
        
        // Initialize wiki when page loads
        document.addEventListener('DOMContentLoaded', () => {
            const wiki = new GalacticWiki();
        });
        '''


async def setup(bot):
    await bot.add_cog(WebMapCog(bot))