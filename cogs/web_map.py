import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
from typing import Optional, Dict, List, Set, Any
from datetime import datetime, timedelta
import threading
from dataclasses import dataclass, asdict
import hashlib
import time

# FastAPI imports
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

@dataclass
class CachedData:
    """Container for cached data with metadata"""
    data: Any
    timestamp: float
    hash: str
    
    def is_expired(self, ttl_seconds: float) -> bool:
        return (time.time() - self.timestamp) > ttl_seconds

class OptimizedWebMapCog(commands.Cog, name="WebMap"):
    """Optimized web-based interactive galaxy map with high performance for large-scale games"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Check if database is available
        try:
            test_query = self.db.execute_query("SELECT 1", fetch='one')
            print("✅ Database connection verified")
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            
        self.is_running = False
        self.host = "0.0.0.0"
        self.port = 8090
        self.external_ip_override = None
        self.server_task = None
        self.websocket_clients: Set[WebSocket] = set()
        
        # Performance optimization settings
        self.cache = {}
        self.cache_ttl = {
            'locations': 300,      # 5 minutes for static data
            'corridors': 300,      # 5 minutes for static data
            'galaxy_info': 300,    # 5 minutes for galaxy metadata
            'npcs_static': 60,     # 1 minute for static NPCs
            'npcs_dynamic': 10,    # 10 seconds for dynamic NPCs
            'players': 5,          # 5 seconds for player positions
            'news': 30,           # 30 seconds for news
            'logs': 30,           # 30 seconds for logs
            'history': 300        # 5 minutes for history
        }
        
        # Delta tracking for efficient updates
        self.last_data_hashes = {}
        self.viewport_cache = {}  # Cache data by viewport bounds
        
        # Performance metrics
        self.update_metrics = {
            'total_updates': 0,
            'delta_updates': 0,
            'full_updates': 0,
            'cache_hits': 0,
            'db_queries': 0
        }
        
        # Create necessary directories
        for directory in ["web", "web/static", "web/static/css", "web/static/js", "web/templates"]:
            os.makedirs(directory, exist_ok=True)
            
        print("✅ Web directories created")
        
        # Auto-start configuration - Try to import config safely
        try:
            from config import WEBMAP_CONFIG
            webmap_config = WEBMAP_CONFIG
        except ImportError:
            webmap_config = {}
        except Exception as e:
            print(f"Error loading WEBMAP_CONFIG: {e}")
            webmap_config = {}
            
        self.auto_start = webmap_config.get('auto_start', False)
        self.auto_start_port = webmap_config.get('auto_start_port', 8090)
        self.auto_start_host = webmap_config.get('auto_start_host', '0.0.0.0')
        self.auto_start_delay = webmap_config.get('auto_start_time', 30)
        
        # Start background tasks when cog is loaded
        if self.auto_start:
            asyncio.create_task(self._delayed_auto_start())
    
    async def _delayed_auto_start(self):
        """Auto-start web map after delay"""
        await asyncio.sleep(self.auto_start_delay)
        if not self.is_running:
            print(f"🚀 Auto-starting web map on {self.auto_start_host}:{self.auto_start_port}")
            try:
                await self._start_server(self.auto_start_host, self.auto_start_port)
            except Exception as e:
                print(f"❌ Failed to auto-start web map: {e}")
    
    def _compute_hash(self, data: Any) -> str:
        """Compute hash of data for change detection"""
        return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    
    async def _get_cached_data(self, key: str, fetch_func, *args, **kwargs) -> Any:
        """Get data from cache or fetch if expired"""
        ttl = self.cache_ttl.get(key, 60)
        
        if key in self.cache:
            cached = self.cache[key]
            if not cached.is_expired(ttl):
                self.update_metrics['cache_hits'] += 1
                return cached.data
        
        # Fetch fresh data
        self.update_metrics['db_queries'] += 1
        data = await fetch_func(*args, **kwargs)
        data_hash = self._compute_hash(data)
        
        self.cache[key] = CachedData(
            data=data,
            timestamp=time.time(),
            hash=data_hash
        )
        
        return data
    
    async def _get_delta_update(self, data_type: str, new_data: Any) -> Optional[Dict]:
        """Generate delta update if data has changed"""
        new_hash = self._compute_hash(new_data)
        old_hash = self.last_data_hashes.get(data_type)
        
        if old_hash == new_hash:
            return None  # No changes
        
        self.last_data_hashes[data_type] = new_hash
        
        # For certain data types, compute actual deltas
        if data_type in ['players', 'npcs_dynamic']:
            # These change frequently, send full update
            return {
                'type': 'delta',
                'data_type': data_type,
                'full_data': new_data,
                'timestamp': datetime.now().isoformat()
            }
        else:
            # For static data, only send if actually changed
            return {
                'type': 'update',
                'data_type': data_type,
                'data': new_data,
                'timestamp': datetime.now().isoformat()
            }
    
    # Optimized data fetching methods
    async def _fetch_locations_optimized(self, viewport_bounds=None):
        """Fetch locations with optional viewport filtering"""
        try:
            query = """
                SELECT location_id, name, location_type, x_coord, y_coord, 
                       wealth_level, population, description, has_black_market, 
                       has_federal_supplies, faction, has_jobs, has_shops, 
                       has_medical, has_repairs, has_fuel, has_upgrades,
                       is_derelict, gate_status
                FROM locations
            """
            
            params = []
            if viewport_bounds:
                query += " WHERE x_coord BETWEEN ? AND ? AND y_coord BETWEEN ? AND ?"
                params = [viewport_bounds['min_x'], viewport_bounds['max_x'], 
                         viewport_bounds['min_y'], viewport_bounds['max_y']]
            
            query += " ORDER BY name"
            
            locations_data = self.db.execute_query(query, params, fetch='all')
            
            if not locations_data:
                print("⚠️ No locations found in database! Has the galaxy been generated?")
                return []
            
            print(f"✅ Fetched {len(locations_data)} locations")
            
            return [
                {
                    "id": loc[0],
                    "name": loc[1],
                    "type": loc[2],
                    "coordinates": {"x": float(loc[3]) if loc[3] is not None else 0.0, 
                                  "y": float(loc[4]) if loc[4] is not None else 0.0},
                    "wealth_level": loc[5] or 3,
                    "population": loc[6] or 0,
                    "description": loc[7] or "No description available",
                    "has_black_market": bool(loc[8]),
                    "has_federal_supplies": bool(loc[9]),
                    "faction": loc[10] or "Independent",
                    "services": {
                        "jobs": bool(loc[11]),
                        "shops": bool(loc[12]),
                        "medical": bool(loc[13]),
                        "repairs": bool(loc[14]),
                        "fuel": bool(loc[15]),
                        "upgrades": bool(loc[16])
                    },
                    "is_derelict": bool(loc[17]),
                    "gate_status": loc[18] or "active"
                }
                for loc in locations_data
            ]
        except Exception as e:
            print(f"❌ Error fetching locations: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _fetch_corridors_optimized(self, location_ids=None):
        """Fetch corridors with optional location filtering"""
        try:
            query = """
                SELECT c.corridor_id, c.name, c.origin_location, c.destination_location,
                       c.travel_time, c.fuel_cost, c.danger_level, c.is_active,
                       l1.name as origin_name, l2.name as destination_name
                FROM corridors c
                JOIN locations l1 ON c.origin_location = l1.location_id
                JOIN locations l2 ON c.destination_location = l2.location_id
            """
            
            params = []
            if location_ids:
                placeholders = ','.join(['?' for _ in location_ids])
                query += f" WHERE c.origin_location IN ({placeholders}) OR c.destination_location IN ({placeholders})"
                params = location_ids + location_ids
            
            query += " ORDER BY c.name"
            
            corridors_data = self.db.execute_query(query, params, fetch='all')
            
            if not corridors_data:
                print("⚠️ No corridors found in database!")
                return []
            
            print(f"✅ Fetched {len(corridors_data)} corridors")
            
            return [
                {
                    "id": c[0],
                    "name": c[1],
                    "origin": {"id": c[2], "name": c[8]},
                    "destination": {"id": c[3], "name": c[9]},
                    "travel_time": c[4],
                    "fuel_cost": c[5],
                    "danger_level": c[6],
                    "is_active": bool(c[7])
                }
                for c in corridors_data
            ]
        except Exception as e:
            print(f"❌ Error fetching corridors: {e}")
            return []
    
    async def _fetch_dynamic_data(self):
        """Fetch only dynamic data (players, NPCs in transit)"""
        # Get online players
        players_data = self.db.execute_query("""
            SELECT c.name, c.current_location, c.is_logged_in, c.user_id
            FROM characters c
            WHERE c.is_logged_in = 1 OR c.last_activity > datetime('now', '-30 minutes')
        """, fetch='all')
        
        players = [
            {
                "name": p[0],
                "location_id": p[1],
                "is_logged_in": bool(p[2]),
                "user_id": p[3]
            }
            for p in players_data
        ] if players_data else []
        
        # Get NPCs in transit
        transit_npcs = self.db.execute_query("""
            SELECT d.npc_id, d.name, d.current_location, d.destination_location, 
                   d.travel_start_time, 
                   datetime(d.travel_start_time, '+' || d.travel_duration || ' seconds') as arrival_time
            FROM dynamic_npcs d
            WHERE d.travel_start_time IS NOT NULL 
            AND datetime('now') < datetime(d.travel_start_time, '+' || d.travel_duration || ' seconds')
        """, fetch='all')
        
        npcs_in_transit = [
            {
                "id": n[0],
                "name": n[1],
                "origin_id": n[2],
                "destination_id": n[3],
                "departure_time": n[4],
                "arrival_time": n[5]
            }
            for n in transit_npcs
        ] if transit_npcs else []
        
        return {
            "players": players,
            "npcs_in_transit": npcs_in_transit,
            "timestamp": datetime.now().isoformat()
        }
    
    # WebSocket message handling
    async def _broadcast_update(self, update_type: str, data: Any, client_filter=None):
        """Broadcast updates to WebSocket clients with optional filtering"""
        if not self.websocket_clients:
            return
        
        self.update_metrics['total_updates'] += 1
        
        # Check if this is a delta update
        delta = await self._get_delta_update(update_type, data)
        if delta is None and update_type in ['players', 'npcs_dynamic']:
            return  # No changes to broadcast
        
        message_data = delta if delta else {
            "type": update_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if delta:
            self.update_metrics['delta_updates'] += 1
        else:
            self.update_metrics['full_updates'] += 1
        
        message = json.dumps(message_data, default=str)
        
        # Send to clients
        disconnected = set()
        for client in self.websocket_clients.copy():
            if client_filter and not client_filter(client):
                continue
                
            try:
                await client.send_text(message)
            except Exception:
                disconnected.add(client)
        
        # Clean up disconnected clients
        self.websocket_clients -= disconnected
    
    @tasks.loop(seconds=5)
    async def update_dynamic_data_task(self):
        """Update only dynamic data frequently"""
        if not self.is_running or not self.websocket_clients:
            return
        
        try:
            dynamic_data = await self._fetch_dynamic_data()
            await self._broadcast_update("dynamic_update", dynamic_data)
        except Exception as e:
            print(f"Error updating dynamic data: {e}")
    
    @tasks.loop(minutes=5)
    async def cleanup_cache_task(self):
        """Clean up expired cache entries"""
        now = time.time()
        expired_keys = []
        
        for key, cached in self.cache.items():
            ttl = self.cache_ttl.get(key, 60)
            if cached.is_expired(ttl * 2):  # Clean up if expired for 2x TTL
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            print(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
    
    # FastAPI setup
    async def _create_fastapi_app(self):
        """Create optimized FastAPI application"""
        app = FastAPI()
        templates = Jinja2Templates(directory="web/templates")
        
        # Mount static files
        app.mount("/static", StaticFiles(directory="web/static"), name="static")
        
        # Debug endpoint
        @app.get("/debug/locations")
        async def debug_locations():
            """Debug endpoint to check locations data"""
            locations = await self._fetch_locations_optimized()
            return {
                "count": len(locations),
                "sample": locations[:5] if locations else [],
                "cache_status": {
                    key: {
                        "age": time.time() - cached.timestamp,
                        "expired": cached.is_expired(self.cache_ttl.get(key, 60))
                    }
                    for key, cached in self.cache.items()
                }
            }
        
        # Main map endpoint
        @app.get("/map", response_class=HTMLResponse)
        async def map_view(request: Request):
            # Get initial data with caching
            locations = await self._get_cached_data('locations', self._fetch_locations_optimized)
            galaxy_info = await self._get_cached_data('galaxy_info', self._fetch_galaxy_info)
            
            return templates.TemplateResponse("map.html", {
                "request": request,
                "galaxy_name": galaxy_info.get('name', 'Unknown Galaxy'),
                "initial_locations": len(locations)
            })
        
        # API endpoints for data
        @app.get("/api/map/initial")
        async def get_initial_data(viewport: Optional[str] = None):
            """Get initial map data with optional viewport filtering"""
            print("📍 API: Fetching initial map data...")
            
            viewport_bounds = None
            if viewport:
                # Parse viewport bounds
                try:
                    bounds = json.loads(viewport)
                    viewport_bounds = bounds
                except:
                    pass
            
            # Get cached data
            locations = await self._get_cached_data(
                f'locations_{viewport}' if viewport else 'locations',
                self._fetch_locations_optimized,
                viewport_bounds
            )
            
            print(f"📍 API: Found {len(locations)} locations")
            
            location_ids = [loc['id'] for loc in locations] if viewport_bounds else None
            
            corridors = await self._get_cached_data(
                f'corridors_{viewport}' if viewport else 'corridors',
                self._fetch_corridors_optimized,
                location_ids
            )
            
            print(f"📍 API: Found {len(corridors)} corridors")
            
            galaxy_info = await self._get_cached_data('galaxy_info', self._fetch_galaxy_info)
            
            response_data = {
                "locations": locations,
                "corridors": corridors,
                "galaxy": galaxy_info,
                "metrics": self.update_metrics
            }
            
            print(f"📍 API: Sending response with {len(locations)} locations, {len(corridors)} corridors")
            
            return response_data
        
        @app.get("/api/map/dynamic")
        async def get_dynamic_data():
            """Get only dynamic data"""
            return await self._fetch_dynamic_data()
        
        # WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websocket_clients.add(websocket)
            
            try:
                # Send initial data
                initial_data = await self._fetch_dynamic_data()
                await websocket.send_json({
                    "type": "initial",
                    "data": initial_data
                })
                
                # Keep connection alive
                while True:
                    # Wait for client messages (ping/pong)
                    data = await websocket.receive_text()
                    
                    # Handle viewport updates
                    try:
                        message = json.loads(data)
                        if message.get('type') == 'viewport_update':
                            # Client moved viewport, might need different data
                            viewport = message.get('viewport')
                            # Could implement viewport-based data loading here
                    except:
                        pass
                        
            except WebSocketDisconnect:
                self.websocket_clients.discard(websocket)
            except Exception as e:
                print(f"WebSocket error: {e}")
                self.websocket_clients.discard(websocket)
        
        # Wiki endpoint
        @app.get("/wiki", response_class=HTMLResponse)
        async def wiki_view(request: Request):
            return templates.TemplateResponse("wiki.html", {
                "request": request
            })
        
        # Wiki data API endpoint
        @app.get("/api/wiki/data")
        async def get_wiki_data():
            """Get wiki data"""
            wiki_data = await self._get_wiki_data_optimized()
            return wiki_data
        
        return app
    
    async def _fetch_galaxy_info(self):
        """Fetch basic galaxy information"""
        try:
            from utils.time_system import TimeSystem
            time_system = TimeSystem(self.bot)
            
            galaxy_data = self.db.execute_query(
                "SELECT name, start_date, time_scale_factor, is_time_paused FROM galaxy_info WHERE galaxy_id = 1",
                fetch='one'
            )
            
            if not galaxy_data:
                return {
                    "name": "Unknown Galaxy",
                    "start_date": "2751-01-01",
                    "time_scale": 4.0,
                    "is_paused": False,
                    "current_time": "Unknown"
                }
            
            return {
                "name": galaxy_data[0],
                "start_date": galaxy_data[1],
                "time_scale": galaxy_data[2],
                "is_paused": bool(galaxy_data[3]),
                "current_time": time_system.format_ingame_datetime(time_system.calculate_current_ingame_time())
            }
        except Exception as e:
            print(f"❌ Error fetching galaxy info: {e}")
            return {
                "name": "Error Loading Galaxy",
                "start_date": "2751-01-01",
                "time_scale": 4.0,
                "is_paused": False,
                "current_time": "Error"
            }
    
    async def _get_wiki_data_optimized(self):
        """Get wiki data with intelligent caching"""
        # Use longer TTL for wiki data
        locations = await self._get_cached_data('locations', self._fetch_locations_optimized)
        corridors = await self._get_cached_data('corridors', self._fetch_corridors_optimized)
        galaxy_info = await self._get_cached_data('galaxy_info', self._fetch_galaxy_info)
        
        # Get other data as needed
        npcs = await self._get_cached_data('npcs_static', self._fetch_static_npcs)
        news = await self._get_cached_data('news', self._fetch_recent_news)
        logs = await self._get_cached_data('logs', self._fetch_logs)
        history = await self._get_cached_data('history', self._fetch_history)
        
        return {
            "galaxy": galaxy_info,
            "locations": locations,
            "corridors": corridors,
            "npcs": npcs,
            "news": news,
            "logs": logs,
            "history": history,
            "statistics": self._calculate_statistics(locations, corridors, npcs)
        }
    
    def _calculate_statistics(self, locations, corridors, npcs):
        """Calculate galaxy statistics"""
        location_types = {}
        total_population = 0
        
        for loc in locations:
            loc_type = loc["type"]
            location_types[loc_type] = location_types.get(loc_type, 0) + 1
            if loc.get("population"):
                total_population += loc["population"]
        
        active_corridors = sum(1 for c in corridors if c["is_active"])
        
        return {
            "locations": {
                "total": len(locations),
                "by_type": location_types,
                "total_population": total_population
            },
            "corridors": {
                "total": len(corridors),
                "active": active_corridors
            },
            "npcs": {
                "total": len(npcs.get('static', [])) + len(npcs.get('dynamic', []))
            }
        }
    
    # Helper methods for specific data types
    async def _fetch_static_npcs(self):
        """Fetch static NPC data"""
        static_npcs = self.db.execute_query("""
            SELECT npc_id, name, occupation, location_id, alignment
            FROM static_npcs
            WHERE is_alive = 1
        """, fetch='all')
        
        dynamic_npcs = self.db.execute_query("""
            SELECT npc_id, name, ship_name, current_location, alignment
            FROM dynamic_npcs
            WHERE is_alive = 1
        """, fetch='all')
        
        return {
            "static": [
                {
                    "id": n[0],
                    "name": n[1],
                    "occupation": n[2],
                    "location_id": n[3],
                    "alignment": n[4]
                }
                for n in static_npcs
            ] if static_npcs else [],
            "dynamic": [
                {
                    "id": n[0],
                    "name": n[1],
                    "ship_name": n[2],
                    "location_id": n[3],
                    "alignment": n[4]
                }
                for n in dynamic_npcs
            ] if dynamic_npcs else []
        }
    
    async def _fetch_recent_news(self):
        """Fetch recent news"""
        news_data = self.db.execute_query("""
            SELECT news_id, news_type, title, description, location_id,
                   scheduled_delivery
            FROM news_queue
            WHERE is_delivered = 1
            ORDER BY scheduled_delivery DESC
            LIMIT 50
        """, fetch='all')
        
        return [
            {
                "id": n[0],
                "type": n[1],
                "title": n[2],
                "description": n[3],
                "location_id": n[4],
                "delivered_at": n[5]
            }
            for n in news_data
        ]
    
    async def _fetch_logs(self):
        """Fetch recent logs"""
        logs_data = self.db.execute_query("""
            SELECT ll.author_name, ll.message, ll.posted_at, l.name as location_name
            FROM location_logs ll
            JOIN locations l ON ll.location_id = l.location_id
            ORDER BY ll.posted_at DESC
            LIMIT 100
        """, fetch='all')
        
        return [
            {
                "author": log[0],
                "message": log[1],
                "timestamp": log[2],
                "location": log[3]
            }
            for log in logs_data
        ] if logs_data else []
    
    async def _fetch_history(self):
        """Fetch galaxy history"""
        history_data = self.db.execute_query("""
            SELECT event_title, event_description, historical_figure, 
                   event_date, event_type, location_id
            FROM galactic_history
            ORDER BY history_id DESC
            LIMIT 100
        """, fetch='all')
        
        return [
            {
                "title": h[0],
                "description": h[1],
                "figure": h[2],
                "date": h[3],
                "type": h[4],
                "location_id": h[5]
            }
            for h in history_data
        ] if history_data else []
    
    async def _start_server(self, host: str, port: int):
        """Start the optimized web server"""
        self.host = host
        self.port = port
        
        # Ensure directories exist
        os.makedirs("web", exist_ok=True)
        os.makedirs("web/static", exist_ok=True)
        os.makedirs("web/static/css", exist_ok=True)
        os.makedirs("web/static/js", exist_ok=True)
        os.makedirs("web/templates", exist_ok=True)
        
        # Create web files
        self._create_web_files()
        
        print("🌐 Creating FastAPI application...")
        
        # Create FastAPI app
        app = await self._create_fastapi_app()
        
        print(f"🚀 Starting web server on {host}:{port}...")
        
        # Run server in background thread
        config = uvicorn.Config(app, host=host, port=port, log_level="error")
        server = uvicorn.Server(config)
        
        self.server_task = asyncio.create_task(server.serve())
        self.is_running = True
        
        print("✅ Web server started successfully")
        
        # Update game panels
        await self._update_game_panels_for_map_status()
    
    def _create_web_files(self):
        """Create optimized HTML and static files"""
        # Create optimized HTML
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>Galaxy Map - High Performance</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="/static/css/map.css" />
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Tektur:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <div id="loading" class="loading-overlay">
        <div class="loading-content">
            <div class="loading-spinner"></div>
            <p>Initializing Navigation Systems...</p>
        </div>
    </div>
    
    <div id="header" class="header-expanded">
        <div class="header-brand">
            <span class="brand-icon">🛸</span>
            <span class="brand-text">GALAXY NAVIGATION</span>
        </div>
        <div class="header-stats">
            <div class="stat-item">
                <span class="stat-label">LOCATIONS</span>
                <span class="stat-value" id="location-count">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">ONLINE</span>
                <span class="stat-value" id="player-count">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">FPS</span>
                <span class="stat-value" id="fps-counter">60</span>
            </div>
        </div>
        <div class="header-controls">
            <button id="toggle-labels" class="control-btn">LABELS</button>
            <button id="toggle-routes" class="control-btn">ROUTES</button>
            <button id="performance-mode" class="control-btn">PERF MODE</button>
        </div>
    </div>
    
    <div id="map"></div>
    
    <div id="location-panel" class="location-panel hidden"></div>
    
    <button id="header-toggle" class="header-toggle">
        <span class="toggle-icon">▼</span>
    </button>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="/static/js/map.js"></script>
</body>
</html>'''
        
        with open("web/templates/map.html", "w", encoding='utf-8') as f:
            f.write(html_content)
        
        # Create optimized CSS
        css_content = '''/* Optimized Galaxy Map Styles */
:root {
    --primary-color: #00ffff;
    --secondary-color: #00cccc;
    --primary-bg: #000408;
    --secondary-bg: #0a0f1a;
    --text-primary: #e0ffff;
    --border-color: #003344;
    --success-color: #00ff88;
    --warning-color: #ff8800;
    --error-color: #ff3333;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Share Tech Mono', monospace;
    background: var(--primary-bg);
    color: var(--text-primary);
    overflow: hidden;
    position: relative;
}

/* Loading overlay */
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--primary-bg);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    transition: opacity 0.5s ease;
}

.loading-spinner {
    width: 60px;
    height: 60px;
    border: 3px solid var(--border-color);
    border-top-color: var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

.loading-content button {
    background: var(--secondary-bg);
    border: 2px solid var(--primary-color);
    color: var(--primary-color);
    padding: 10px 20px;
    font-family: inherit;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s ease;
    text-transform: uppercase;
}

.loading-content button:hover {
    background: var(--primary-color);
    color: var(--primary-bg);
    box-shadow: 0 0 20px var(--primary-color);
}

.loading-content code {
    background: rgba(0, 255, 255, 0.1);
    padding: 2px 6px;
    border-radius: 3px;
    font-family: 'Share Tech Mono', monospace;
}

/* Header styles */
#header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: linear-gradient(180deg, var(--secondary-bg) 0%, rgba(10, 15, 26, 0.95) 100%);
    border-bottom: 2px solid var(--primary-color);
    padding: 1rem;
    z-index: 1000;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: transform 0.3s ease;
}

.header-collapsed {
    transform: translateY(-100%);
}

.header-brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.brand-icon {
    font-size: 1.5rem;
    filter: drop-shadow(0 0 10px var(--primary-color));
}

.brand-text {
    font-family: 'Tektur', sans-serif;
    font-weight: 700;
    font-size: 1.2rem;
    text-shadow: 0 0 10px var(--primary-color);
}

.header-stats {
    display: flex;
    gap: 2rem;
}

.stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.stat-label {
    font-size: 0.7rem;
    color: var(--text-secondary);
}

.stat-value {
    font-size: 1.2rem;
    font-weight: bold;
    color: var(--primary-color);
}

.header-controls {
    display: flex;
    gap: 0.5rem;
}

.control-btn {
    background: linear-gradient(145deg, var(--secondary-bg), var(--primary-bg));
    border: 1px solid var(--primary-color);
    color: var(--primary-color);
    padding: 0.5rem 1rem;
    font-family: inherit;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.3s ease;
    text-transform: uppercase;
}

.control-btn:hover {
    background: var(--primary-color);
    color: var(--primary-bg);
    box-shadow: 0 0 20px var(--primary-color);
}

.control-btn.active {
    background: var(--primary-color);
    color: var(--primary-bg);
}

/* Map container with visible background */
#map {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(ellipse at center, #0a1020 0%, #000408 100%);
    z-index: 1;
}

/* Header toggle */
#header-toggle {
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--secondary-bg);
    border: 1px solid var(--primary-color);
    border-radius: 0 0 10px 10px;
    padding: 5px 20px;
    cursor: pointer;
    z-index: 1001;
    transition: all 0.3s ease;
}

#header-toggle:hover {
    background: var(--primary-color);
    color: var(--primary-bg);
}

/* Location markers */
.location-marker {
    background: transparent;
    border: none;
}

.marker-icon {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.3s ease;
    background: rgba(10, 15, 26, 0.9);
    border: 2px solid var(--primary-color);
    box-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
}

.marker-icon:hover {
    transform: scale(1.2);
    box-shadow: 0 0 30px var(--primary-color);
}

.marker-colony {
    border-color: #4169E1;
    box-shadow: 0 0 20px rgba(65, 105, 225, 0.5);
}

.marker-space_station {
    border-color: #FFD700;
    box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
}

.marker-outpost {
    border-color: #FF6347;
    box-shadow: 0 0 20px rgba(255, 99, 71, 0.5);
}

.marker-gate {
    border-color: #9370DB;
    box-shadow: 0 0 20px rgba(147, 112, 219, 0.5);
    animation: gate-pulse 2s infinite;
}

@keyframes gate-pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.8; }
}

.location-label {
    background: rgba(10, 15, 26, 0.95) !important;
    border: 1px solid var(--primary-color) !important;
    border-radius: 3px !important;
    color: var(--text-primary) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    padding: 2px 6px !important;
    white-space: nowrap !important;
}

.marker-symbol {
    filter: drop-shadow(0 0 3px rgba(255, 255, 255, 0.8));
    user-select: none;
}
.player-marker {
    z-index: 1000 !important;
}
.location-panel {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 400px;
    max-width: calc(100vw - 40px);
    background: linear-gradient(145deg, var(--secondary-bg), var(--primary-bg));
    border: 2px solid var(--primary-color);
    border-radius: 10px;
    padding: 1.5rem;
    box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
    transition: all 0.3s ease;
    max-height: calc(100vh - 120px);
    overflow-y: auto;
}

.location-panel.hidden {
    transform: translateX(120%);
    opacity: 0;
}

/* Performance mode styles */
.performance-mode .leaflet-marker-icon {
    transition: none !important;
}

.performance-mode .location-marker {
    filter: none !important;
}

.performance-mode * {
    animation: none !important;
}

/* Mobile optimizations */
@media (max-width: 768px) {
    #header {
        flex-direction: column;
        gap: 1rem;
        padding: 0.75rem;
    }
    
    .header-stats {
        gap: 1rem;
    }
    
    .location-panel {
        bottom: 0;
        left: 0;
        right: 0;
        width: 100%;
        max-width: 100%;
        border-radius: 20px 20px 0 0;
        max-height: 60vh;
    }
}

/* DEBUG: Ensure leaflet divs are visible */
.leaflet-pane {
    z-index: 400 !important;
}

.leaflet-marker-pane {
    z-index: 600 !important;
}
.leaflet-container {
    background: transparent;
    font-family: inherit;
}

.leaflet-control-zoom {
    border: none !important;
    box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
}

.leaflet-control-zoom a {
    background: var(--secondary-bg) !important;
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
}

.leaflet-control-zoom a:hover {
    background: var(--primary-color) !important;
    color: var(--primary-bg) !important;
}'''
        
        with open("web/static/css/map.css", "w", encoding='utf-8') as f:
            f.write(css_content)
        
        # Create optimized JavaScript
        js_content = '''// Optimized Galaxy Map JavaScript
class GalaxyMap {
    constructor() {
        this.map = null;
        this.locations = new Map();
        this.corridors = new Map();
        this.markers = new Map();
        this.routes = new Map();
        this.playerMarkers = new Map();
        
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        
        // Performance settings
        this.performanceMode = false;
        this.updateThrottle = new Map();
        this.frameTime = 16; // Target 60 FPS
        this.lastFrameTime = 0;
        
        // UI state
        this.showLabels = true;
        this.showRoutes = true;
        this.selectedLocation = null;
        
        // Initialize
        this.init();
    }
    
    async init() {
        try {
            console.log('🚀 Initializing Galaxy Map...');
            
            // Load initial data first
            await this.loadInitialData();
            
            // Setup map
            this.setupMap();
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Connect WebSocket
            this.connectWebSocket();
            
            // Start performance monitoring
            this.startPerformanceMonitoring();
            
            // Hide loading overlay
            const loading = document.getElementById('loading');
            if (loading) {
                loading.style.opacity = '0';
                setTimeout(() => loading.style.display = 'none', 500);
            }
            
            console.log('✅ Galaxy Map initialization complete');
        } catch (error) {
            console.error('❌ Failed to initialize Galaxy Map:', error);
            alert('Failed to initialize map. Please check the console for errors.');
        }
    }
    
    async loadInitialData() {
        try {
            console.log('Loading initial data...');
            const response = await fetch('/api/map/initial');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            console.log('Initial data received:', data);
            
            // Check if we have locations
            if (!data.locations || data.locations.length === 0) {
                throw new Error('No locations found. Has the galaxy been generated? Use /galaxy generate in Discord.');
            }
            
            // Process locations
            data.locations.forEach(loc => {
                this.locations.set(loc.id, loc);
            });
            console.log(`Loaded ${data.locations.length} locations`);
            
            // Process corridors
            if (data.corridors) {
                data.corridors.forEach(corridor => {
                    this.corridors.set(corridor.id, corridor);
                });
                console.log(`Loaded ${data.corridors.length} corridors`);
            }
            
            // Update UI
            document.getElementById('location-count').textContent = data.locations.length;
            
            console.log('Performance metrics:', data.metrics);
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
            
            // Show error in loading screen
            const loading = document.getElementById('loading');
            loading.innerHTML = `
                <div class="loading-content" style="text-align: center;">
                    <h2 style="color: #ff3333;">⚠️ Map Data Not Available</h2>
                    <p>${error.message}</p>
                    <p style="margin-top: 20px;">If you're an admin, run <code>/galaxy generate</code> in Discord first.</p>
                    <button onclick="location.reload()" style="margin-top: 20px; padding: 10px 20px;">
                        🔄 Retry
                    </button>
                </div>
            `;
            
            throw error; // Re-throw to stop initialization
        }
    }
    
    setupMap() {
        this.map = L.map('map', {
            crs: L.CRS.Simple,
            minZoom: -3,
            maxZoom: 6,
            zoomControl: false,
            attributionControl: false,
            preferCanvas: true // Use canvas for better performance
        });
        
        // Add zoom control
        L.control.zoom({ position: 'bottomright' }).addTo(this.map);
        
        // Set initial view
        this.map.setView([0, 0], 1);
        
        // Render initial locations
        this.renderLocations();
        this.renderCorridors();
        
        // Setup viewport change detection
        this.map.on('moveend', () => this.onViewportChange());
    }
    
    renderLocations() {
        const bounds = this.map.getBounds();
        
        console.log(`Rendering ${this.locations.size} locations...`);
        
        this.locations.forEach(location => {
            const coords = [location.coordinates.y, location.coordinates.x];
            
            // Skip if outside viewport in performance mode
            if (this.performanceMode && !bounds.contains(coords)) {
                return;
            }
            
            // Create marker if not exists
            if (!this.markers.has(location.id)) {
                const marker = this.createLocationMarker(location);
                this.markers.set(location.id, marker);
            }
        });
        
        console.log(`Created ${this.markers.size} markers`);
    }
    
    createLocationMarker(location) {
        const iconClass = this.getLocationIconClass(location.type);
        const icon = L.divIcon({
            className: 'location-marker',
            html: `<div class="marker-icon ${iconClass}" data-location-id="${location.id}">
                     <span class="marker-symbol">${this.getLocationSymbol(location.type)}</span>
                   </div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
        
        const marker = L.marker([location.coordinates.y, location.coordinates.x], { icon })
            .addTo(this.map)
            .on('click', () => this.selectLocation(location.id));
        
        // Add label if enabled  
        if (this.showLabels) {
            const tooltipMethod = 'bind' + 'Tooltip'; // Leaflet tooltip method
            marker[tooltipMethod](location.name, {
                permanent: true,
                className: 'location-label',
                offset: [0, 20]
            });
        }
        
        return marker;
    }
    
    getLocationSymbol(type) {
        const symbols = {
            'colony': '🏙️',
            'space_station': '🛸',
            'outpost': '📡',
            'gate': '🌀'
        };
        return symbols[type] || '📍';
    }
    
    getLocationIconClass(type) {
        return `marker-${type}`;
    }
    
    renderCorridors() {
        if (!this.showRoutes) return;
        
        this.corridors.forEach(corridor => {
            if (!corridor.is_active) return;
            
            const origin = this.locations.get(corridor.origin.id);
            const dest = this.locations.get(corridor.destination.id);
            
            if (!origin || !dest) return;
            
            const route = L.polyline([
                [origin.coordinates.y, origin.coordinates.x],
                [dest.coordinates.y, dest.coordinates.x]
            ], {
                color: this.getCorridorColor(corridor.danger_level),
                weight: 2,
                opacity: 0.6,
                className: 'corridor-line'
            }).addTo(this.map);
            
            this.routes.set(corridor.id, route);
        });
    }
    
    getCorridorColor(dangerLevel) {
        if (dangerLevel <= 2) return '#00ff88';
        if (dangerLevel <= 4) return '#ffff00';
        if (dangerLevel <= 6) return '#ff8800';
        return '#ff3333';
    }
    
    selectLocation(locationId) {
        const location = this.locations.get(locationId);
        if (!location) return;
        
        this.selectedLocation = locationId;
        this.showLocationPanel(location);
    }
    
    showLocationPanel(location) {
        const panel = document.getElementById('location-panel');
        
        // Build panel content
        panel.innerHTML = `
            <button class="panel-close" onclick="galaxyMap.hideLocationPanel()">×</button>
            <h2>${location.name}</h2>
            <p class="location-type">${location.type.toUpperCase()}</p>
            <p>${location.description}</p>
            
            <div class="location-stats">
                <div class="stat">
                    <span>Population:</span>
                    <span>${location.population?.toLocaleString() || 'None'}</span>
                </div>
                <div class="stat">
                    <span>Wealth:</span>
                    <span>${'⭐'.repeat(location.wealth_level)}</span>
                </div>
                <div class="stat">
                    <span>Faction:</span>
                    <span>${location.faction || 'Independent'}</span>
                </div>
            </div>
            
            <div class="location-services">
                <h3>Services</h3>
                <div class="services-grid">
                    ${this.renderServices(location.services)}
                </div>
            </div>
        `;
        
        panel.classList.remove('hidden');
    }
    
    hideLocationPanel() {
        document.getElementById('location-panel').classList.add('hidden');
        this.selectedLocation = null;
    }
    
    renderServices(services) {
        return Object.entries(services)
            .filter(([_, available]) => available)
            .map(([service, _]) => `<span class="service">${service}</span>`)
            .join('');
    }
    
    setupEventListeners() {
        // Header toggle
        document.getElementById('header-toggle').addEventListener('click', () => {
            const header = document.getElementById('header');
            header.classList.toggle('header-collapsed');
        });
        
        // Control buttons
        document.getElementById('toggle-labels').addEventListener('click', () => {
            this.showLabels = !this.showLabels;
            this.updateLabels();
            event.target.classList.toggle('active');
        });
        
        document.getElementById('toggle-routes').addEventListener('click', () => {
            this.showRoutes = !this.showRoutes;
            this.updateRoutes();
            event.target.classList.toggle('active');
        });
        
        document.getElementById('performance-mode').addEventListener('click', () => {
            this.performanceMode = !this.performanceMode;
            document.body.classList.toggle('performance-mode');
            event.target.classList.toggle('active');
        });
        
        // Close panel on map click
        this.map.on('click', (e) => {
            if (!e.originalEvent.target.closest('.location-marker')) {
                this.hideLocationPanel();
            }
        });
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.scheduleReconnect();
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleWebSocketMessage(message) {
        // Throttle updates for performance
        const now = Date.now();
        const lastUpdate = this.updateThrottle.get(message.type) || 0;
        
        if (now - lastUpdate < 100) return; // 100ms throttle
        
        this.updateThrottle.set(message.type, now);
        
        switch (message.type) {
            case 'dynamic_update':
                this.updateDynamicData(message.data);
                break;
            case 'delta':
                this.applyDelta(message);
                break;
            case 'update':
                this.applyUpdate(message);
                break;
        }
    }
    
    updateDynamicData(data) {
        // Update player count
        document.getElementById('player-count').textContent = data.players.length;
        
        // Update player positions
        this.updatePlayerMarkers(data.players);
        
        // Update NPCs in transit
        // Could implement transit animations here
    }
    
    updatePlayerMarkers(players) {
        const activePlayerIds = new Set();
        
        players.forEach(player => {
            activePlayerIds.add(player.user_id);
            
            if (!this.playerMarkers.has(player.user_id)) {
                // Create new player marker
                const location = this.locations.get(player.location_id);
                if (!location) return;
                
                const marker = L.circleMarker([location.coordinates.y, location.coordinates.x], {
                    radius: 8,
                    fillColor: '#00ff88',
                    color: '#00ff88',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.5,
                    className: 'player-marker'
                }).addTo(this.map);
                
                this.playerMarkers.set(player.user_id, marker);
            } else {
                // Update existing marker position
                const marker = this.playerMarkers.get(player.user_id);
                const location = this.locations.get(player.location_id);
                if (location && !this.performanceMode) {
                    marker.setLatLng([location.coordinates.y, location.coordinates.x]);
                }
            }
        });
        
        // Remove markers for offline players
        this.playerMarkers.forEach((marker, userId) => {
            if (!activePlayerIds.has(userId)) {
                this.map.removeLayer(marker);
                this.playerMarkers.delete(userId);
            }
        });
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000);
        
        setTimeout(() => this.connectWebSocket(), delay);
    }
    
    onViewportChange() {
        if (!this.performanceMode) return;
        
        // In performance mode, load data for visible viewport
        const bounds = this.map.getBounds();
        
        // Hide markers outside viewport
        this.markers.forEach((marker, locationId) => {
            const location = this.locations.get(locationId);
            const coords = [location.coordinates.y, location.coordinates.x];
            
            if (bounds.contains(coords)) {
                this.map.addLayer(marker);
            } else {
                this.map.removeLayer(marker);
            }
        });
    }
    
    updateLabels() {
        this.markers.forEach(marker => {
            if (this.showLabels) {
                marker['open' + 'Tooltip']();
            } else {
                marker['close' + 'Tooltip']();
            }
        });
    }
    
    updateRoutes() {
        this.routes.forEach(route => {
            if (this.showRoutes) {
                this.map.addLayer(route);
            } else {
                this.map.removeLayer(route);
            }
        });
    }
    
    startPerformanceMonitoring() {
        let frameCount = 0;
        let lastTime = performance.now();
        
        const updateFPS = () => {
            frameCount++;
            const currentTime = performance.now();
            
            if (currentTime >= lastTime + 1000) {
                const fps = Math.round(frameCount * 1000 / (currentTime - lastTime));
                document.getElementById('fps-counter').textContent = fps;
                frameCount = 0;
                lastTime = currentTime;
            }
            
            requestAnimationFrame(updateFPS);
        };
        
        requestAnimationFrame(updateFPS);
    }
}

// Add debug helper to window
window.debugMap = () => {
    if (!window.galaxyMap) {
        console.error('Galaxy map not initialized');
        return;
    }
    
    const map = window.galaxyMap;
    console.log('=== Galaxy Map Debug Info ===');
    console.log('Locations:', map.locations.size);
    console.log('Corridors:', map.corridors.size);
    console.log('Markers:', map.markers.size);
    console.log('Routes:', map.routes.size);
    console.log('Player Markers:', map.playerMarkers.size);
    console.log('WebSocket:', map.websocket?.readyState === 1 ? 'Connected' : 'Disconnected');
    console.log('Performance Mode:', map.performanceMode);
    console.log('Show Labels:', map.showLabels);
    console.log('Show Routes:', map.showRoutes);
    
    // Sample location data
    if (map.locations.size > 0) {
        const firstLocation = map.locations.values().next().value;
        console.log('Sample location:', firstLocation);
    }
    
    // Check map bounds
    if (map.map) {
        const bounds = map.map.getBounds();
        console.log('Map bounds:', bounds);
        console.log('Map zoom:', map.map.getZoom());
        console.log('Map center:', map.map.getCenter());
    }
    
    console.log('===========================');
    console.log('Run window.debugMap() again to refresh');
};'''
        
        with open("web/static/js/map.js", "w", encoding='utf-8') as f:
            f.write(js_content)
        
        # Create wiki template
        self._create_wiki_template()
    
    def _create_wiki_template(self):
        """Create wiki template"""
        wiki_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galaxy Encyclopedia</title>
    <link rel="stylesheet" href="/static/css/wiki.css" />
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
</head>
<body>
    <div id="wiki-container">
        <h1>Galaxy Encyclopedia</h1>
        <div id="wiki-content">
            <p>Loading galaxy data...</p>
        </div>
    </div>
    <script>
        // Load wiki data on page load
        async function loadWikiData() {
            try {
                const response = await fetch('/api/wiki/data');
                const data = await response.json();
                
                const container = document.getElementById('wiki-content');
                container.innerHTML = generateWikiHTML(data);
            } catch (error) {
                console.error('Failed to load wiki data:', error);
                document.getElementById('wiki-content').innerHTML = '<p>Error loading wiki data</p>';
            }
        }
        
        function generateWikiHTML(data) {
            let html = '<div class="wiki-sections">';
            
            // Galaxy Overview
            html += '<section><h2>Galaxy Overview</h2>';
            html += `<p>Name: ${data.galaxy?.name || 'Unknown'}</p>`;
            html += `<p>Current Time: ${data.galaxy?.current_time || 'Unknown'}</p>`;
            html += '</section>';
            
            // Locations
            html += '<section><h2>Locations</h2>';
            if (data.locations && data.locations.length > 0) {
                html += '<ul>';
                data.locations.forEach(loc => {
                    html += `<li><strong>${loc.name}</strong> - ${loc.type}</li>`;
                });
                html += '</ul>';
            } else {
                html += '<p>No locations found</p>';
            }
            html += '</section>';
            
            html += '</div>';
            return html;
        }
        
        loadWikiData();
    </script>
</body>
</html>'''
        
        with open("web/templates/wiki.html", "w", encoding='utf-8') as f:
            f.write(wiki_html)
        
        # Also create basic wiki CSS
        wiki_css = '''
body {
    font-family: 'Share Tech Mono', monospace;
    background: #000408;
    color: #e0ffff;
    margin: 0;
    padding: 20px;
}

#wiki-container {
    max-width: 1200px;
    margin: 0 auto;
}

h1, h2 {
    color: #00ffff;
}

section {
    margin-bottom: 30px;
    padding: 20px;
    background: rgba(10, 15, 26, 0.8);
    border: 1px solid #003344;
    border-radius: 5px;
}
'''
        with open("web/static/css/wiki.css", "w", encoding='utf-8') as f:
            f.write(wiki_css)
    
    async def _update_game_panels_for_map_status(self):
        """Update game panels to reflect web map status"""
        try:
            panel_cog = self.bot.get_cog('GamePanelCog')
            if not panel_cog:
                print("⚠️ GamePanelCog not found, skipping panel updates")
                return
                
            # Get all active panels
            panels = self.bot.db.execute_query(
                "SELECT guild_id, channel_id, message_id FROM game_panels",
                fetch='all'
            )
            
            if not panels:
                return
                
            print(f"🔄 Updating {len(panels)} game panels with webmap status: {self.is_running}")
            
            for guild_id, channel_id, message_id in panels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    # Create fresh embed and view for each panel
                    embed = await panel_cog.create_panel_embed(guild)
                    new_view = await panel_cog.create_panel_view()
                    
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.edit(embed=embed, view=new_view)
                        print(f"✅ Updated game panel in {guild.name} with webmap status: {self.is_running}")
                    except discord.NotFound:
                        # Message was deleted, remove from database
                        self.bot.db.execute_query(
                            "DELETE FROM game_panels WHERE message_id = ?",
                            (message_id,)
                        )
                        print(f"🗑️ Removed orphaned panel record for message {message_id}")
                    except discord.Forbidden:
                        print(f"❌ No permission to update panel in {guild.name}")
                    except Exception as e:
                        print(f"❌ Error updating panel message {message_id}: {e}")
                
                except Exception as e:
                    print(f"❌ Error processing panel update for guild {guild_id}: {e}")
            
            # Force refresh persistent views after updating messages
            await panel_cog.refresh_all_panel_views()
        
        except Exception as e:
            print(f"❌ Error in _update_game_panels_for_map_status: {e}")
            import traceback
            traceback.print_exc()
    
    # Discord commands
    @app_commands.command(name="webmap", description="Start the interactive web map server")
    @app_commands.describe(
        port="Port number (default: 8090)",
        host="Host address (default: 0.0.0.0)"
    )
    async def start_webmap(self, interaction: discord.Interaction, 
                          port: Optional[int] = None, 
                          host: Optional[str] = None):
        """Start the web map server"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if self.is_running:
            await interaction.response.send_message("Web map is already running!", ephemeral=True)
            return
        
        port = port or self.port
        host = host or self.host
        
        await interaction.response.defer()
        
        try:
            await self._start_server(host, port)
            
            display_url, url_note = self._get_display_url()
            
            embed = discord.Embed(
                title="🗺️ Web Map Server Started",
                description=f"Interactive galaxy map is now accessible!\n\n{url_note}",
                color=0x00ff00
            )
            
            embed.add_field(
                name="Performance Metrics",
                value="Use `/webmap_stats` to view performance metrics",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start web map: {str(e)}")
    
    @app_commands.command(name="webmap_stop", description="Stop the web map server")
    async def stop_webmap(self, interaction: discord.Interaction):
        """Stop the web map server"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not self.is_running:
            await interaction.response.send_message("Web map is not running.", ephemeral=True)
            return
        
        self.is_running = False
        
        # Close WebSocket connections
        for client in self.websocket_clients.copy():
            try:
                await client.close()
            except:
                pass
        
        self.websocket_clients.clear()
        
        # Cancel server task
        if self.server_task:
            self.server_task.cancel()
        
        # Update panels
        await self._update_game_panels_for_map_status()
        
        embed = discord.Embed(
            title="🛑 Web Map Server Stopped",
            description="The interactive galaxy map has been shut down.",
            color=0xff0000
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="webmap_stats", description="View web map performance statistics")
    async def webmap_stats(self, interaction: discord.Interaction):
        """View performance statistics"""
        
        if not self.is_running:
            await interaction.response.send_message("Web map is not running.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 Web Map Performance Statistics",
            color=0x00ffff
        )
        
        # Cache statistics
        cache_info = []
        for key, cached in self.cache.items():
            ttl = self.cache_ttl.get(key, 60)
            age = time.time() - cached.timestamp
            status = "✅ Fresh" if age < ttl else "⚠️ Stale"
            cache_info.append(f"{key}: {status} ({age:.1f}s old)")
        
        embed.add_field(
            name="Cache Status",
            value="\n".join(cache_info[:5]) or "No cached data",
            inline=False
        )
        
        # Update metrics
        total = self.update_metrics['total_updates']
        if total > 0:
            delta_pct = (self.update_metrics['delta_updates'] / total) * 100
            cache_hit_rate = (self.update_metrics['cache_hits'] / 
                            (self.update_metrics['cache_hits'] + self.update_metrics['db_queries'])) * 100
        else:
            delta_pct = 0
            cache_hit_rate = 0
        
        embed.add_field(
            name="Update Statistics",
            value=f"Total Updates: {total}\n"
                  f"Delta Updates: {self.update_metrics['delta_updates']} ({delta_pct:.1f}%)\n"
                  f"Full Updates: {self.update_metrics['full_updates']}\n"
                  f"Cache Hit Rate: {cache_hit_rate:.1f}%\n"
                  f"DB Queries: {self.update_metrics['db_queries']}",
            inline=False
        )
        
        embed.add_field(
            name="Connected Clients",
            value=f"{len(self.websocket_clients)} active WebSocket connections",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="webmap_set_ip", description="Set the external IP for web map access")
    async def set_external_ip(self, interaction: discord.Interaction, ip_or_domain: str):
        """Set external IP or domain for web map access"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        self.external_ip_override = ip_or_domain
        
        embed = discord.Embed(
            title="✅ External IP Set",
            description=f"Web map will now be accessible at:\n`http://{ip_or_domain}:{self.port}/map`",
            color=0x00ff00
        )
        
        if self.is_running:
            await self._update_game_panels_for_map_status()
            embed.add_field(
                name="Note",
                value="Game panels have been updated with the new URL.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def _get_display_url(self) -> tuple[str, str]:
        """Get the display URL and note for users"""
        if self.external_ip_override:
            display_url = f"http://{self.external_ip_override}:{self.port}/map"
            url_note = f"Connect to: {display_url}"
            return display_url, url_note
        
        if self.host != "0.0.0.0":
            display_url = f"http://{self.host}:{self.port}/map"
            url_note = f"Connect to: {display_url}"
            return display_url, url_note
        
        display_url = f"http://[SERVER_IP]:{self.port}/map"
        url_note = f"Connect to: {display_url}\n*Use `/webmap_set_ip <your_external_ip_or_domain>` to set the correct address*"
        return display_url, url_note
    
    async def get_final_map_url(self) -> tuple[str, str]:
        """Public method to get the final map URL (for GamePanelCog)"""
        return self._get_display_url()
    
    async def cog_unload(self):
        """Clean up when cog is unloaded"""
        # Cancel background tasks
        if hasattr(self, 'update_dynamic_data_task'):
            self.update_dynamic_data_task.cancel()
        if hasattr(self, 'cleanup_cache_task'):
            self.cleanup_cache_task.cancel()
        
        # Stop server if running
        if self.is_running:
            self.is_running = False
            
            # Close WebSocket connections
            for client in self.websocket_clients:
                try:
                    await client.close()
                except:
                    pass
            
            # Cancel server task
            if self.server_task:
                self.server_task.cancel()
        
        print("✅ WebMap cog unloaded successfully")

async def setup(bot):
    if not FASTAPI_AVAILABLE:
        print("❌ FastAPI not installed. Run: pip install fastapi uvicorn websockets")
        return
    
    await bot.add_cog(OptimizedWebMapCog(bot))