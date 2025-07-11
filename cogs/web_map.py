# cogs/web_map.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import threading

# FastAPI imports
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

class WebMapCog(commands.Cog, name="WebMap"):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.app = None
        self.server = None
        self.server_thread = None
        self.websocket_clients = set()
        self.is_running = False
        self.host = "0.0.0.0"
        self.port = 8090
        self.external_ip_override = None
        # Create web directories if they don't exist
        self._ensure_web_directories()
        
        # Create HTML and static files
        self._create_web_files()
    
    def _ensure_web_directories(self):
        """Create necessary directories for web files"""
        os.makedirs("web/templates", exist_ok=True)
        os.makedirs("web/static/css", exist_ok=True)
        os.makedirs("web/static/js", exist_ok=True)
    async def _get_external_ip(self) -> str:
        """Get the server's external IP address"""
        import aiohttp
        import asyncio
        
        # List of IP detection services as fallbacks
        services = [
            "https://api.ipify.org",
            "https://ipv4.icanhazip.com",
            "https://api.my-ip.io/ip",
            "https://checkip.amazonaws.com"
        ]
        
        for service in services:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(service) as response:
                        if response.status == 200:
                            ip = (await response.text()).strip()
                            # Basic IP validation
                            parts = ip.split('.')
                            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                                return ip
            except Exception as e:
                print(f"Failed to get IP from {service}: {e}")
                continue
        
        return None
    
    def _get_display_url(self) -> tuple[str, str]:
        """Get the display URL and note for users"""
        # If there's an override, use it
        if self.external_ip_override:
            display_url = f"http://{self.external_ip_override}:{self.port}"
            url_note = f"Connect to: {display_url}"
            return display_url, url_note
        
        # If bound to specific host, use that
        if self.host != "0.0.0.0":
            display_url = f"http://{self.host}:{self.port}"
            url_note = f"Connect to: {display_url}"
            return display_url, url_note
        # Default fallback
        display_url = f"http://[SERVER_IP]:{self.port}"
        url_note = f"Connect to: {display_url}\n*Use `/webmap_set_ip <your_external_ip_or_domain>` to set the correct address*"
        return display_url, url_note
        
    def _create_web_files(self):
        """Create the HTML template and static files"""
        # Create the main HTML template
        html_content = '''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Galaxy Map - The Quiet End</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="/static/css/map.css" />
    </head>
    <body>
        <div id="header">
            <h1>🌌 Galaxy Map - The Quiet End</h1>
            <div id="controls-section">
                <div id="search-container">
                    <input type="text" id="location-search" placeholder="Search locations..." />
                    <button id="search-btn">🔍</button>
                </div>
                <div id="route-container">
                    <select id="route-from" disabled>
                        <option value="">From...</option>
                    </select>
                    <select id="route-to" disabled>
                        <option value="">To...</option>
                    </select>
                    <button id="plot-route-btn" disabled>Plot Route</button>
                    <button id="clear-route-btn" disabled>Clear</button>
                </div>
                <div id="label-container">
                    <label class="label-control">
                        <input type="checkbox" id="show-labels" checked> Show Labels
                    </label>
                    <label class="label-control">
                        <input type="checkbox" id="show-colonies" checked> Colonies
                    </label>
                    <label class="label-control">
                        <input type="checkbox" id="show-stations" checked> Stations
                    </label>
                    <label class="label-control">
                        <input type="checkbox" id="show-outposts" checked> Outposts
                    </label>
                    <label class="label-control">
                        <input type="checkbox" id="show-gates"> Gates
                    </label>
                </div>
            </div>
            <div id="info-panel">
                <div id="galaxy-info">
                    <span id="galaxy-name">Loading...</span> | 
                    <span id="galaxy-time">--:--</span> | 
                    <span id="location-count">0 locations</span> | 
                    <span id="player-count">0 players online</span>
                </div>
                <div id="connection-status">🔴 Connecting...</div>
            </div>
        </div>
        
        <div id="map"></div>
        
        <div id="location-panel" class="panel hidden">
            <div class="panel-header">
                <h3 id="location-title">Location Details</h3>
                <button id="close-panel" class="close-btn">&times;</button>
            </div>
            <div class="panel-content">
                <div id="location-details"></div>
            </div>
        </div>
        
        <div id="legend" class="panel">
            <div class="panel-header">
                <h3>🗺️ Legend</h3>
                <button id="toggle-legend" class="toggle-btn">−</button>
            </div>
            <div class="panel-content" id="legend-content">
                <div class="legend-item"><span class="marker colony"></span> Colonies</div>
                <div class="legend-item"><span class="marker station"></span> Space Stations</div>
                <div class="legend-item"><span class="marker outpost"></span> Outposts</div>
                <div class="legend-item"><span class="marker gate"></span> Transit Gates</div>
                <div class="legend-item"><span class="corridor gated"></span> Gated Corridors</div>
                <div class="legend-item"><span class="corridor ungated"></span> Ungated Corridors</div>
                <div class="legend-item"><span class="player-indicator"></span> Players Present</div>
            </div>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="/static/js/map.js"></script>
    </body>
    </html>'''
        
        with open("web/templates/index.html", "w", encoding='utf-8') as f:
            f.write(html_content)
        
        # Create CSS file
        css_content = '''body {
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #000;
            color: #fff;
            overflow: hidden;
        }

        #header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 80px;
            background: rgba(0, 0, 0, 0.9);
            border-bottom: 2px solid #333;
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 20px;
            box-sizing: border-box;
        }

        #header h1 {
            margin: 0;
            font-size: 24px;
            color: #4a9eff;
            flex-shrink: 0;
        }

        #controls-section {
            display: flex;
            flex-direction: column;
            gap: 8px;
            flex-grow: 1;
            margin: 0 20px;
            max-width: 600px;
        }

        #search-container, #route-container, #label-container {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        #location-search {
            padding: 6px 10px;
            border: 1px solid #555;
            border-radius: 4px;
            background: #222;
            color: #fff;
            font-size: 14px;
            flex-grow: 1;
            min-width: 200px;
        }

        #search-btn, #plot-route-btn, #clear-route-btn {
            padding: 6px 12px;
            border: 1px solid #555;
            border-radius: 4px;
            background: #333;
            color: #fff;
            cursor: pointer;
            font-size: 14px;
        }

        #search-btn:hover, #plot-route-btn:hover, #clear-route-btn:hover {
            background: #444;
        }

        #route-from, #route-to {
            padding: 6px 10px;
            border: 1px solid #555;
            border-radius: 4px;
            background: #222;
            color: #fff;
            font-size: 14px;
            min-width: 120px;
        }

        #plot-route-btn:disabled, #clear-route-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        #label-container {
            display: flex;
            gap: 12px;
            align-items: center;
            flex-wrap: wrap;
        }

        .label-control {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 12px;
            color: #ccc;
            cursor: pointer;
            user-select: none;
        }

        .label-control input[type="checkbox"] {
            accent-color: #4a9eff;
        }

        .label-control:hover {
            color: #fff;
        }

        #info-panel {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 5px;
            flex-shrink: 0;
        }

        #galaxy-info {
            font-size: 14px;
            color: #ccc;
        }

        #connection-status {
            font-size: 12px;
            font-weight: bold;
        }

        #map {
            position: absolute;
            top: 80px;
            left: 0;
            right: 0;
            bottom: 0;
            background: #000011;
        }

        .leaflet-container {
            background: #000011;
        }

        .leaflet-tile {
            filter: invert(1) hue-rotate(180deg);
        }

        /* Remove default leaflet zoom controls */
        .leaflet-control-zoom {
            display: none;
        }

        .panel {
            position: fixed;
            background: rgba(0, 0, 0, 0.95);
            border: 2px solid #333;
            border-radius: 8px;
            z-index: 1000;
            max-width: 400px;
        }

        #location-panel {
            top: 100px;
            right: 20px;
            width: 350px;
        }

        #legend {
            bottom: 20px;
            left: 20px;
            width: 200px;
            transition: height 0.3s ease;
        }

        #legend.collapsed {
            height: auto;
        }

        #legend.collapsed #legend-content {
            display: none;
        }

        .panel-header {
            background: #1a1a1a;
            padding: 10px 15px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-header h3 {
            margin: 0;
            color: #4a9eff;
        }

        .panel-content {
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
        }

        .close-btn, .toggle-btn {
            background: none;
            border: none;
            color: #999;
            font-size: 18px;
            cursor: pointer;
            padding: 0;
            width: 25px;
            height: 25px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .close-btn:hover, .toggle-btn:hover {
            color: #fff;
        }

        .hidden {
            display: none !important;
        }

        .legend-item {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            font-size: 14px;
        }

        .marker {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid #fff;
        }

        .marker.colony { background: #ff6600; }
        .marker.station { background: #00aaff; }
        .marker.outpost { background: #888888; }
        .marker.gate { background: #ffdd00; }

        .corridor {
            width: 20px;
            height: 3px;
            margin-right: 10px;
        }

        .corridor.gated { background: #00ff88; }
        .corridor.ungated { background: #ff6600; }

        .player-indicator {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
            border: 3px solid #00ff00;
            background: transparent;
        }

        .location-detail {
            margin-bottom: 10px;
        }

        .location-detail strong {
            color: #4a9eff;
        }

        .players-list {
            background: rgba(255, 255, 255, 0.1);
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
        }

        .player-item {
            padding: 5px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .player-item:last-child {
            border-bottom: none;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }

        .status-online { background: #00ff00; }
        .status-transit { background: #ffaa00; }

        .sub-locations {
            margin-top: 10px;
        }

        .sub-location-item {
            padding: 5px 0;
            color: #ccc;
            font-size: 13px;
        }

        /* Route mode styles */
        .location-dimmed {
            opacity: 0.3 !important;
            filter: grayscale(0.7) !important;
        }

        .location-route-highlight {
            opacity: 1 !important;
            filter: none !important;
            stroke: #ffff00 !important;
            stroke-width: 3 !important;
            stroke-opacity: 1 !important;
        }

        .route-highlight {
            stroke: #ffff00 !important;
            stroke-width: 4 !important;
            stroke-opacity: 0.8 !important;
            z-index: 1000;
        }

        .location-highlight {
            stroke: #ffff00 !important;
            stroke-width: 4 !important;
            stroke-opacity: 1 !important;
            fill-opacity: 1 !important;
        }

        /* Label styles */
        .location-label {
            background: rgba(0, 0, 0, 0.8) !important;
            border: 1px solid #333 !important;
            border-radius: 4px !important;
            padding: 2px 6px !important;
            font-size: 11px !important;
            color: #fff !important;
            white-space: nowrap !important;
            pointer-events: none !important;
            z-index: 1000 !important;
        }

        .location-label.wealth-high {
            border-color: #ffd700 !important;
            color: #ffd700 !important;
        }

        .location-label.wealth-medium {
            border-color: #90ee90 !important;
            color: #90ee90 !important;
        }

        .location-label.wealth-low {
            border-color: #ff6b6b !important;
            color: #ff6b6b !important;
        }

        /* Custom leaflet popup styling */
        .leaflet-popup-content-wrapper {
            background: rgba(0, 0, 0, 0.9);
            color: #fff;
            border: 1px solid #333;
        }

        .leaflet-popup-tip {
            background: rgba(0, 0, 0, 0.9);
        }

        /* Mobile responsiveness */
        @media (max-width: 768px) {
            #header {
                height: 100px;
                flex-direction: column;
                justify-content: center;
                padding: 10px;
            }
            
            #header h1 {
                font-size: 18px;
                margin-bottom: 5px;
            }
            
            #controls-section {
                margin: 0;
                max-width: 100%;
            }
            
            #search-container, #route-container, #label-container {
                flex-wrap: wrap;
            }
            
            #label-container {
                gap: 8px;
            }
            
            .label-control {
                font-size: 11px;
            }
            
            #location-search {
                min-width: 150px;
            }
            
            #route-from, #route-to {
                min-width: 100px;
            }
            
            #map {
                top: 100px;
            }
            
            #location-panel {
                width: 90%;
                right: 5%;
                top: 110px;
            }
            
            #legend {
                width: 160px;
            }
        }'''
        
        with open("web/static/css/map.css", "w", encoding='utf-8') as f:
            f.write(css_content)
        
        # Create JavaScript file
        js_content = '''class GalaxyMap {
            constructor() {
                this.map = null;
                this.websocket = null;
                this.locations = new Map();
                this.corridors = new Map();
                this.players = new Map();
                this.selectedLocation = null;
                this.routePolylines = [];
                this.highlightedLocations = [];
                this.currentRoute = null;
                this.labels = new Map();
                this.routeMode = false;
                this.labelSettings = {
                    showLabels: true,
                    showColonies: true,
                    showStations: true,
                    showOutposts: true,
                    showGates: false
                };
                
                this.init();
            }
            
            init() {
                this.setupMap();
                this.connectWebSocket();
                this.setupEventListeners();
            }
            
            setupMap() {
                // Initialize map with space-like view - remove default zoom controls
                this.map = L.map('map', {
                    crs: L.CRS.Simple,
                    minZoom: -3,
                    maxZoom: 5,
                    zoomControl: false,  // Disable default zoom controls
                    attributionControl: false
                });
                
                // Add custom zoom controls only in bottom right
                L.control.zoom({
                    position: 'bottomright'
                }).addTo(this.map);
                
                // Set initial view at a more zoomed in level
                this.map.setView([0, 0], 1);
            }
            
            connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;
                
                this.websocket = new WebSocket(wsUrl);
                
                this.websocket.onopen = () => {
                    this.updateConnectionStatus('🟢 Connected', '#00ff00');
                    console.log('WebSocket connected');
                };
                
                this.websocket.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                };
                
                this.websocket.onclose = () => {
                    this.updateConnectionStatus('🔴 Disconnected', '#ff0000');
                    console.log('WebSocket disconnected');
                    // Attempt to reconnect after 5 seconds
                    setTimeout(() => this.connectWebSocket(), 5000);
                };
                
                this.websocket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.updateConnectionStatus('🟡 Error', '#ffaa00');
                };
            }
            
            handleWebSocketMessage(data) {
                switch(data.type) {
                    case 'galaxy_data':
                        this.updateGalaxyData(data.data);
                        break;
                    case 'player_update':
                        this.updatePlayers(data.data);
                        break;
                    case 'location_update':
                        this.updateLocation(data.data);
                        break;
                }
            }
            
            updateGalaxyData(data) {
                // Update galaxy info
                document.getElementById('galaxy-name').textContent = data.galaxy_name;
                document.getElementById('galaxy-time').textContent = data.current_time;
                document.getElementById('location-count').textContent = `${data.locations.length} locations`;
                
                // Clear existing markers
                this.map.eachLayer((layer) => {
                    if (layer !== this.map._layers[Object.keys(this.map._layers)[0]]) {
                        this.map.removeLayer(layer);
                    }
                });
                
                this.locations.clear();
                this.corridors.clear();
                this.labels.clear();
                
                // Populate route dropdowns
                this.populateRouteSelectors(data.locations);
                
                // Add corridors first (so they appear under locations)
                data.corridors.forEach(corridor => this.addCorridor(corridor));
                
                // Add locations
                data.locations.forEach(location => this.addLocation(location));
                
                // Update map bounds
                if (data.locations.length > 0) {
                    const bounds = L.latLngBounds(
                        data.locations.map(loc => [loc.y_coord, loc.x_coord])
                    );
                    this.map.fitBounds(bounds, { 
                        padding: [50, 50],
                        maxZoom: 3
                    });
                }
            }
            
            populateRouteSelectors(locations) {
                const fromSelect = document.getElementById('route-from');
                const toSelect = document.getElementById('route-to');
                
                // Clear existing options except first
                fromSelect.innerHTML = '<option value="">From...</option>';
                toSelect.innerHTML = '<option value="">To...</option>';
                
                // Sort locations by name
                const sortedLocations = locations.sort((a, b) => a.name.localeCompare(b.name));
                
                sortedLocations.forEach(location => {
                    const fromOption = new Option(location.name, location.location_id);
                    const toOption = new Option(location.name, location.location_id);
                    fromSelect.add(fromOption);
                    toSelect.add(toOption);
                });
                
                // Enable route controls
                fromSelect.disabled = false;
                toSelect.disabled = false;
                document.getElementById('plot-route-btn').disabled = false;
                document.getElementById('clear-route-btn').disabled = false;
            }
            
            addLocation(location) {
                const marker = this.createLocationMarker(location);
                marker.addTo(this.map);
                
                // Create label
                const label = this.createLocationLabel(location);
                this.labels.set(location.location_id, label);
                
                this.locations.set(location.location_id, { ...location, marker });
                
                // Update label visibility
                this.updateLabelVisibility();
            }
            
            createLocationMarker(location) {
                const color = this.getLocationColor(location.location_type);
                const size = this.getLocationSize(location.location_type, location.wealth_level);
                
                const marker = L.circleMarker([location.y_coord, location.x_coord], {
                    radius: size,
                    fillColor: color,
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                });
                
                // Add popup
                const popupContent = this.createLocationPopup(location);
                marker.bindPopup(popupContent);
                
                // Add click handler
                marker.on('click', () => {
                    this.selectLocation(location.location_id);
                });
                
                return marker;
            }
            
            getLocationColor(type) {
                const colors = {
                    'colony': '#ff6600',
                    'space_station': '#00aaff',
                    'outpost': '#888888',
                    'gate': '#ffdd00'
                };
                return colors[type] || '#ffffff';
            }
            
            getLocationSize(type, wealth) {
                const baseSizes = {
                    'colony': 8,
                    'space_station': 10,
                    'outpost': 6,
                    'gate': 4
                };
                const baseSize = baseSizes[type] || 6;
                return baseSize + (wealth * 0.5);
            }
            
            createLocationLabel(location) {
                const label = L.marker([location.y_coord, location.x_coord], {
                    icon: L.divIcon({
                        className: 'location-label',
                        html: `<div class="location-label ${this.getLabelClass(location)}">${location.name}</div>`,
                        iconSize: [100, 20],
                        iconAnchor: [50, 10]
                    }),
                    interactive: false,
                    zIndexOffset: 1000
                });
                
                return label;
            }

            getLabelClass(location) {
                if (location.wealth_level >= 8) return 'wealth-high';
                if (location.wealth_level >= 5) return 'wealth-medium';
                return 'wealth-low';
            }
            
            updateLabelVisibility() {
                const currentZoom = this.map.getZoom();
                const showLabels = this.labelSettings.showLabels;
                
                this.labels.forEach((label, locationId) => {
                    const location = this.locations.get(locationId);
                    if (!location) return;
                    
                    let shouldShow = showLabels;
                    
                    // Check type-specific toggles
                    if (shouldShow) {
                        switch (location.location_type) {
                            case 'colony':
                                shouldShow = this.labelSettings.showColonies;
                                break;
                            case 'space_station':
                                shouldShow = this.labelSettings.showStations;
                                break;
                            case 'outpost':
                                shouldShow = this.labelSettings.showOutposts;
                                break;
                            case 'gate':
                                shouldShow = this.labelSettings.showGates;
                                break;
                        }
                    }
                    
                    // Zoom-based visibility
                    if (shouldShow) {
                        if (currentZoom < -1) {
                            // Very zoomed out - only show major locations
                            shouldShow = (location.location_type === 'space_station' || 
                                        (location.location_type === 'colony' && location.wealth_level >= 7));
                        } else if (currentZoom < 1) {
                            // Medium zoom - show stations and wealthy colonies
                            shouldShow = (location.location_type === 'space_station' || 
                                        (location.location_type === 'colony' && location.wealth_level >= 5));
                        } else if (currentZoom < 3) {
                            // Close zoom - show most locations except gates
                            shouldShow = shouldShow && location.location_type !== 'gate';
                        }
                        // At highest zoom, show all that are enabled
                    }
                    
                    // In route mode, only show route-relevant labels
                    if (shouldShow && this.routeMode && this.currentRoute) {
                        shouldShow = this.currentRoute.path.includes(locationId);
                    }
                    
                    if (shouldShow) {
                        label.addTo(this.map);
                    } else {
                        this.map.removeLayer(label);
                    }
                });
            }
            
            createLocationPopup(location) {
                return `
                    <div style="color: white;">
                        <h4 style="margin: 0 0 10px 0; color: #4a9eff;">${location.name}</h4>
                        <div><strong>Type:</strong> ${location.location_type.replace('_', ' ')}</div>
                        <div><strong>Population:</strong> ${location.population.toLocaleString()}</div>
                        <div><strong>Wealth:</strong> ${'⭐'.repeat(Math.min(location.wealth_level, 5))}</div>
                    </div>
                `;
            }
            
            addCorridor(corridor) {
                const style = this.getCorridorStyle(corridor);
                const line = L.polyline([
                    [corridor.origin_y, corridor.origin_x],
                    [corridor.dest_y, corridor.dest_x]
                ], style);
                
                line.addTo(this.map);
                this.corridors.set(corridor.corridor_id, { ...corridor, line });
            }
            
            getCorridorStyle(corridor) {
                const isUngated = corridor.name.includes('Ungated');
                return {
                    color: isUngated ? '#ff6600' : '#00ff88',
                    weight: isUngated ? 2 : 1,
                    opacity: 0.6,
                    dashArray: isUngated ? '5, 5' : null
                };
            }
            
            updatePlayers(players) {
                document.getElementById('player-count').textContent = `${players.length} players online`;
                
                // Store player data for location panel use
                this.players.clear();
                players.forEach(player => {
                    if (!this.players.has(player.location_id)) {
                        this.players.set(player.location_id, []);
                    }
                    this.players.get(player.location_id).push(player);
                });
                
                // Clear existing player indicators
                this.locations.forEach((location) => {
                    this.removePlayerIndicator(location);
                });
                
                // Update location markers with player counts
                this.locations.forEach((location, locationId) => {
                    const playersHere = players.filter(p => p.location_id === locationId);
                    this.updateLocationWithPlayers(location, playersHere);
                });
                
                // Update selected location panel if open
                if (this.selectedLocation) {
                    this.updateLocationPanel(this.selectedLocation);
                }
            }
            
            removePlayerIndicator(location) {
                // Remove green ring if exists
                if (location.playerIndicator) {
                    this.map.removeLayer(location.playerIndicator);
                    delete location.playerIndicator;
                }
            }
            
            updateLocationWithPlayers(location, players) {
                this.removePlayerIndicator(location);
                
                if (players.length > 0) {
                    // Add green ring indicator for locations with players
                    const ringMarker = L.circleMarker([location.y_coord, location.x_coord], {
                        radius: location.marker.options.radius + 4,
                        fillColor: 'transparent',
                        color: '#00ff00',
                        weight: 3,
                        opacity: 0.8,
                        fillOpacity: 0,
                        interactive: false  // Add this line to make the ring non-interactive
                    });
                    
                    ringMarker.addTo(this.map);
                    location.playerIndicator = ringMarker;
                }
            }
            
            selectLocation(locationId) {
                this.selectedLocation = locationId;
                this.updateLocationPanel(locationId);
                this.showLocationPanel();
            }
            
            async updateLocationPanel(locationId) {
                const location = this.locations.get(locationId);
                if (!location) return;
                
                document.getElementById('location-title').textContent = location.name;
                
                // Get players at this location
                const playersHere = await this.getPlayersAtLocation(locationId);
                
                // Get sub-locations from API
                const subLocations = await this.getSubLocations(locationId);
                
                const detailsHtml = `
                    <div class="location-detail">
                        <strong>Type:</strong> ${location.location_type.replace('_', ' ')}
                    </div>
                    <div class="location-detail">
                        <strong>Population:</strong> ${location.population.toLocaleString()}
                    </div>
                    <div class="location-detail">
                        <strong>Wealth Level:</strong> ${location.wealth_level}/10 ${'⭐'.repeat(Math.min(location.wealth_level, 5))}
                    </div>
                    <div class="location-detail">
                        <strong>Coordinates:</strong> (${location.x_coord.toFixed(1)}, ${location.y_coord.toFixed(1)})
                    </div>
                    <div class="location-detail">
                        <strong>Description:</strong><br>
                        <em>${location.description || 'No description available.'}</em>
                    </div>
                    ${subLocations.length > 0 ? `
                        <div class="sub-locations">
                            <strong>Available Areas:</strong>
                            ${subLocations.map(sub => `
                                <div class="sub-location-item">
                                    ${sub.icon} ${sub.name} - ${sub.description}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    ${playersHere.length > 0 ? `
                        <div class="players-list">
                            <strong>Players Present (${playersHere.length}):</strong>
                            ${playersHere.map(player => `
                                <div class="player-item">
                                    <span class="status-indicator status-online"></span>
                                    ${player.name}
                                </div>
                            `).join('')}
                        </div>
                    ` : '<div class="location-detail"><em>No players currently present</em></div>'}
                `;
                
                document.getElementById('location-details').innerHTML = detailsHtml;
            }
            
            async getSubLocations(locationId) {
                try {
                    const response = await fetch(`/api/location/${locationId}/sub-locations`);
                    if (response.ok) {
                        return await response.json();
                    }
                } catch (error) {
                    console.error('Failed to fetch sub-locations:', error);
                }
                return [];
            }
            
            async getPlayersAtLocation(locationId) {
                // Get from stored player data
                return this.players.get(locationId) || [];
            }
            
            showLocationPanel() {
                document.getElementById('location-panel').classList.remove('hidden');
            }
            
            hideLocationPanel() {
                document.getElementById('location-panel').classList.add('hidden');
                this.selectedLocation = null;
            }
            
            searchLocations(query) {
                this.clearHighlights();
                
                if (!query.trim()) return;
                
                const results = [];
                this.locations.forEach((location, id) => {
                    if (location.name.toLowerCase().includes(query.toLowerCase())) {
                        results.push(location);
                    }
                });
                
                if (results.length > 0) {
                    // Highlight matching locations
                    results.forEach(location => {
                        this.highlightLocation(location);
                    });
                    
                    // Zoom to first result if only one match
                    if (results.length === 1) {
                        this.map.setView([results[0].y_coord, results[0].x_coord], 4);
                    } else {
                        // Fit bounds to all results
                        const bounds = L.latLngBounds(
                            results.map(loc => [loc.y_coord, loc.x_coord])
                        );
                        this.map.fitBounds(bounds, { padding: [20, 20] });
                    }
                }
            }
            
            highlightLocation(location) {
                const highlightMarker = L.circleMarker([location.y_coord, location.x_coord], {
                    radius: location.marker.options.radius + 6,
                    fillColor: 'transparent',
                    color: '#ffff00',
                    weight: 4,
                    opacity: 1,
                    fillOpacity: 0,
                    className: 'location-highlight'
                });
                
                highlightMarker.addTo(this.map);
                this.highlightedLocations.push(highlightMarker);
            }
            
            clearHighlights() {
                this.highlightedLocations.forEach(marker => {
                    this.map.removeLayer(marker);
                });
                this.highlightedLocations = [];
            }
            
            async plotRoute(fromId, toId) {
                this.clearRoute();
                
                if (!fromId || !toId || fromId === toId) return;
                
                try {
                    const response = await fetch(`/api/route/${fromId}/${toId}`);
                    if (response.ok) {
                        const routeData = await response.json();
                        this.displayRoute(routeData);
                    } else {
                        alert('No route found between these locations.');
                    }
                } catch (error) {
                    console.error('Failed to plot route:', error);
                    alert('Error calculating route.');
                }
            }
            
            displayRoute(routeData) {
                if (!routeData.path || routeData.path.length < 2) return;
                
                this.routeMode = true;
                
                // Dim all locations first
                this.locations.forEach((location) => {
                    location.marker.getElement()?.classList.add('location-dimmed');
                });
                
                // Dim all corridors
                this.corridors.forEach((corridor) => {
                    if (corridor.line.getElement) {
                        corridor.line.getElement()?.classList.add('location-dimmed');
                    }
                });
                
                // Highlight route corridors and un-dim them
                for (let i = 0; i < routeData.path.length - 1; i++) {
                    const fromId = routeData.path[i];
                    const toId = routeData.path[i + 1];
                    
                    this.corridors.forEach((corridor) => {
                        if ((corridor.origin_location === fromId && corridor.destination_location === toId) ||
                            (corridor.origin_location === toId && corridor.destination_location === fromId)) {
                            
                            // Remove dim and add highlight
                            if (corridor.line.getElement) {
                                corridor.line.getElement()?.classList.remove('location-dimmed');
                                corridor.line.getElement()?.classList.add('route-highlight');
                            }
                            
                            // Create additional highlight line for better visibility
                            const routeLine = L.polyline([
                                [corridor.origin_y, corridor.origin_x],
                                [corridor.dest_y, corridor.dest_x]
                            ], {
                                color: '#ffff00',
                                weight: 5,
                                opacity: 0.9,
                                className: 'route-highlight-overlay',
                                interactive: false
                            });
                            
                            routeLine.addTo(this.map);
                            this.routePolylines.push(routeLine);
                        }
                    });
                }
                
                // Highlight and un-dim waypoint locations
                routeData.path.forEach(locationId => {
                    const location = this.locations.get(locationId);
                    if (location) {
                        location.marker.getElement()?.classList.remove('location-dimmed');
                        location.marker.getElement()?.classList.add('location-route-highlight');
                        this.highlightLocation(location);
                    }
                });
                
                // Update label visibility for route mode
                this.updateLabelVisibility();
                
                // Fit map to route with padding
                const routeLocations = routeData.path.map(id => {
                    const loc = this.locations.get(id);
                    return loc ? [loc.y_coord, loc.x_coord] : null;
                }).filter(coord => coord !== null);
                
                if (routeLocations.length > 0) {
                    const bounds = L.latLngBounds(routeLocations);
                    this.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 3 });
                }
                
                this.currentRoute = routeData;
            }
            
            clearRoute() {
                this.routeMode = false;
                
                // Remove route highlight lines
                this.routePolylines.forEach(line => {
                    this.map.removeLayer(line);
                });
                this.routePolylines = [];
                
                // Remove location highlights
                this.clearHighlights();
                
                // Remove all dimming and highlighting classes
                this.locations.forEach((location) => {
                    const element = location.marker.getElement();
                    if (element) {
                        element.classList.remove('location-dimmed', 'location-route-highlight');
                    }
                });
                
                this.corridors.forEach((corridor) => {
                    const element = corridor.line.getElement ? corridor.line.getElement() : null;
                    if (element) {
                        element.classList.remove('location-dimmed', 'route-highlight');
                    }
                });
                
                // Update label visibility
                this.updateLabelVisibility();
                
                this.currentRoute = null;
            }
            
            updateConnectionStatus(text, color) {
                const statusEl = document.getElementById('connection-status');
                statusEl.textContent = text;
                statusEl.style.color = color;
            }
            
            setupLabelControls() {
                // Main label toggle
                document.getElementById('show-labels').addEventListener('change', (e) => {
                    this.labelSettings.showLabels = e.target.checked;
                    this.updateLabelVisibility();
                });
                
                // Type-specific toggles
                document.getElementById('show-colonies').addEventListener('change', (e) => {
                    this.labelSettings.showColonies = e.target.checked;
                    this.updateLabelVisibility();
                });
                
                document.getElementById('show-stations').addEventListener('change', (e) => {
                    this.labelSettings.showStations = e.target.checked;
                    this.updateLabelVisibility();
                });
                
                document.getElementById('show-outposts').addEventListener('change', (e) => {
                    this.labelSettings.showOutposts = e.target.checked;
                    this.updateLabelVisibility();
                });
                
                document.getElementById('show-gates').addEventListener('change', (e) => {
                    this.labelSettings.showGates = e.target.checked;
                    this.updateLabelVisibility();
                });
                
                // Update labels on zoom
                this.map.on('zoomend', () => {
                    this.updateLabelVisibility();
                });
            }
            
            setupEventListeners() {
                // Legend toggle
                document.getElementById('toggle-legend').addEventListener('click', () => {
                    const legend = document.getElementById('legend');
                    const toggleBtn = document.getElementById('toggle-legend');
                    
                    legend.classList.toggle('collapsed');
                    toggleBtn.textContent = legend.classList.contains('collapsed') ? '+' : '−';
                });
                
                // Location panel close
                document.getElementById('close-panel').addEventListener('click', () => {
                    this.hideLocationPanel();
                });
                
                // Search functionality
                const searchInput = document.getElementById('location-search');
                const searchBtn = document.getElementById('search-btn');
                
                const performSearch = () => {
                    this.searchLocations(searchInput.value);
                };
                
                searchBtn.addEventListener('click', performSearch);
                searchInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        performSearch();
                    }
                });
                
                // Route plotting
                document.getElementById('plot-route-btn').addEventListener('click', () => {
                    const fromId = document.getElementById('route-from').value;
                    const toId = document.getElementById('route-to').value;
                    if (fromId && toId) {
                        this.plotRoute(parseInt(fromId), parseInt(toId));
                    }
                });
                
                document.getElementById('clear-route-btn').addEventListener('click', () => {
                    this.clearRoute();
                    document.getElementById('route-from').value = '';
                    document.getElementById('route-to').value = '';
                });
                
                // Close panel when clicking outside
                document.addEventListener('click', (e) => {
                    const panel = document.getElementById('location-panel');
                    if (!panel.contains(e.target) && !this.map.getContainer().contains(e.target)) {
                        this.hideLocationPanel();
                    }
                });
                
                // Add label controls
                this.setupLabelControls();
            }
        }

        // Initialize map when page loads
        document.addEventListener('DOMContentLoaded', () => {
            new GalaxyMap();
        });'''
        
        with open("web/static/js/map.js", "w", encoding='utf-8') as f:
            f.write(js_content)      
        
    def _setup_fastapi(self):
        """Setup FastAPI application"""
        if not FASTAPI_AVAILABLE:
            return None
            
        app = FastAPI(title="Galaxy Map", description="Interactive galaxy map for The Quiet End")
        
        # Mount static files
        app.mount("/static", StaticFiles(directory="web/static"), name="static")
        
        @app.get("/", response_class=HTMLResponse)
        async def read_root():
            with open("web/templates/index.html", "r", encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        
        @app.get("/api/galaxy")
        async def get_galaxy_data():
            """Get galaxy data for the map"""
            return await self._get_galaxy_data()
        
        @app.get("/api/location/{location_id}/sub-locations")
        async def get_location_sub_locations(location_id: int):
            """Get sub-locations for a specific location"""
            try:
                from utils.sub_locations import SubLocationManager
                sub_manager = SubLocationManager(self.bot)
                sub_locations = await sub_manager.get_available_sub_locations(location_id)
                return sub_locations
            except Exception as e:
                print(f"Error getting sub-locations: {e}")
                return []

        @app.get("/api/route/{from_id}/{to_id}")
        async def get_route(from_id: int, to_id: int):
            """Calculate route between two locations"""
            try:
                route_data = await self._calculate_route(from_id, to_id)
                return route_data
            except Exception as e:
                print(f"Error calculating route: {e}")
                return {"error": "Route calculation failed"}
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websocket_clients.add(websocket)
            
            try:
                # Send initial data
                galaxy_data = await self._get_galaxy_data()
                await websocket.send_text(json.dumps({
                    "type": "galaxy_data",
                    "data": galaxy_data
                }))
                
                # Keep connection alive and handle messages
                while True:
                    data = await websocket.receive_text()
                    # Handle any client messages if needed
                    
            except WebSocketDisconnect:
                self.websocket_clients.discard(websocket)
        
        return app
    
    async def _get_galaxy_data(self):
        """Get current galaxy data"""
        # Get galaxy info
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = galaxy_info[0] if galaxy_info else "Unknown Galaxy"
        
        current_time = time_system.calculate_current_ingame_time()
        formatted_time = time_system.format_ingame_datetime(current_time) if current_time else "Unknown"
        
        # Get locations
        locations = self.db.execute_query(
            """SELECT location_id, name, location_type, x_coord, y_coord, 
                      wealth_level, population, description
               FROM locations ORDER BY name""",
            fetch='all'
        )
        
        # Get active corridors
        # Replace the existing corridors query in _get_galaxy_data() method
        corridors = self.db.execute_query(
            '''SELECT c.corridor_id, c.name, c.danger_level, c.origin_location, c.destination_location,
                      ol.x_coord as origin_x, ol.y_coord as origin_y,
                      dl.x_coord as dest_x, dl.y_coord as dest_y, ol.location_type as origin_type
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.is_active = 1''',
            fetch='all'
        )
        
        # Get online players
        players = self.db.execute_query(
            """SELECT c.name, c.current_location, c.is_logged_in
               FROM characters c
               WHERE c.is_logged_in = 1""",
            fetch='all'
        )
        
        return {
            "galaxy_name": galaxy_name,
            "current_time": formatted_time,
            "locations": [
                {
                    "location_id": loc[0],
                    "name": loc[1],
                    "location_type": loc[2],
                    "x_coord": loc[3],
                    "y_coord": loc[4],
                    "wealth_level": loc[5],
                    "population": loc[6],
                    "description": loc[7]
                }
                for loc in locations
            ],
            "corridors": [
                {
                    "corridor_id": cor[0],
                    "name": cor[1],
                    "danger_level": cor[2],
                    "origin_location": cor[3],
                    "destination_location": cor[4],
                    "origin_x": cor[5],
                    "origin_y": cor[6],
                    "dest_x": cor[7],
                    "dest_y": cor[8]
                }
                for cor in corridors
            ],
            "players": [
                {
                    "name": player[0],
                    "location_id": player[1],
                    "is_logged_in": player[2]
                }
                for player in players
            ]
        }
    
    async def _broadcast_update(self, update_type: str, data: dict):
        """Broadcast update to all connected WebSocket clients"""
        if not self.websocket_clients:
            return
            
        message = json.dumps({
            "type": update_type,
            "data": data
        })
        
        # Remove disconnected clients
        disconnected = set()
        for client in self.websocket_clients.copy():
            try:
                await client.send_text(message)
            except:
                disconnected.add(client)
        
        self.websocket_clients -= disconnected
    
    async def _start_update_loop(self):
        """Start the periodic update loop"""
        while self.is_running:
            try:
                # Broadcast player updates every minute
                players = self.db.execute_query(
                    """SELECT c.name, c.current_location, c.is_logged_in
                       FROM characters c
                       WHERE c.is_logged_in = 1""",
                    fetch='all'
                )
                
                player_data = [
                    {
                        "name": player[0],
                        "location_id": player[1],
                        "is_logged_in": player[2]
                    }
                    for player in players
                ]
                
                await self._broadcast_update("player_update", player_data)
                
                # Wait 60 seconds
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"❌ Error in web map update loop: {e}")
                await asyncio.sleep(60)
    
    def _run_server(self):
        """Run the FastAPI server in a separate thread"""
        if not self.app:
            return
            
        try:
            import uvicorn
            uvicorn.run(
                self.app, 
                host=self.host, 
                port=self.port, 
                log_level="warning",
                access_log=False  # Reduce console spam
            )
        except Exception as e:
            print(f"❌ Error running web server: {e}")
            self.is_running = False
    
    @app_commands.command(name="webmap_start", description="Start the interactive web map server")
    @app_commands.describe(
        port="Port to run the web server on (default: 8090)",
        host="Host to bind to (default: 0.0.0.0)"
    )
    async def start_webmap(self, interaction: discord.Interaction, port: int = 8090, host: str = "0.0.0.0"):
        """Start the web map server"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not FASTAPI_AVAILABLE:
            await interaction.response.send_message(
                "❌ FastAPI is not installed. Please install with: `pip install fastapi uvicorn[standard]`",
                ephemeral=True
            )
            return
        
        if self.is_running:
            display_url, url_note = self._get_display_url()
            await interaction.response.send_message(
                f"❌ Web map is already running!\n{url_note}",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Check if port is available
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            check_host = 'localhost' if host == '0.0.0.0' else host
            result = sock.connect_ex((check_host, port))
            sock.close()
            
            if result == 0:
                await interaction.followup.send(
                    f"❌ Port {port} is already in use!\n"
                    f"Common conflicts:\n"
                    f"• Port 8080: Steam CEF Remote Debugging\n"
                    f"• Try a different port like 8090, 8091, or 9000",
                    ephemeral=True
                )
                return
            
            self.host = host
            self.port = port
            self.app = self._setup_fastapi()
            
            if not self.app:
                await interaction.followup.send("❌ Failed to setup FastAPI application.")
                return
            
            # Start server in separate thread
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            # Give the server a moment to start
            await asyncio.sleep(3)
            
            # Verify server is actually running
            try:
                import aiohttp
                verify_url = f"http://localhost:{port}/"
                async with aiohttp.ClientSession() as session:
                    async with session.get(verify_url, timeout=10) as resp:
                        if resp.status != 200:
                            raise Exception(f"Server returned status {resp.status}")
                        content = await resp.text()
                        if "Galaxy Map" not in content:
                            raise Exception("Server response doesn't contain expected content")
            except asyncio.TimeoutError:
                await interaction.followup.send("❌ Server start timed out. Try a different port or check for conflicts.")
                self.is_running = False
                return
            except Exception as e:
                await interaction.followup.send(f"❌ Server failed to start properly: {str(e)}")
                self.is_running = False
                return
            
            # Start update loop
            self.is_running = True
            asyncio.create_task(self._start_update_loop())
            
            # Try to detect external IP
            external_ip = None
            try:
                external_ip = await self._get_external_ip()
            except Exception as e:
                print(f"Failed to detect external IP: {e}")
            
            embed = discord.Embed(
                title="🌐 Web Map Server Started",
                description="Interactive galaxy map is now available!",
                color=0x00ff00
            )
            
            # Determine URLs to display
            local_url = f"http://localhost:{port}"
            
            if self.external_ip_override:
                # Use override
                external_url = f"http://{self.external_ip_override}:{port}"
                embed.add_field(
                    name="🌐 Public Access URL (Custom)",
                    value=f"{external_url}",
                    inline=False
                )
            elif external_ip:
                # Use detected external IP
                external_url = f"http://{external_ip}:{port}"
                embed.add_field(
                    name="🌐 External Access URL (Auto-detected)",
                    value=f"{external_url}",
                    inline=False
                )
                embed.add_field(
                    name="💡 Custom Domain/IP",
                    value="Use `/webmap_set_ip <domain_or_ip>` if you have a custom domain or different external IP",
                    inline=False
                )
            else:
                # Couldn't detect external IP
                embed.add_field(
                    name="⚠️ External IP Detection Failed",
                    value="Use `/webmap_set_ip <your_external_ip_or_domain>` to set the external address for remote users",
                    inline=False
                )
            
            embed.add_field(
                name="🏠 Local Access URL",
                value=f"{local_url}",
                inline=False
            )
            
            embed.add_field(
                name="🔄 Features",
                value="• Real-time player positions\n• Interactive location details\n• Zoomable/scrollable map\n• Live updates every minute\n• Route planning\n• Location search",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start web map server: {str(e)}")
            self.is_running = False
    @app_commands.command(name="webmap_set_ip", description="Set custom external IP or domain for the web map")
    @app_commands.describe(
        address="External IP address or domain name (e.g., '123.45.67.89' or 'myserver.com')"
    )
    async def set_external_ip(self, interaction: discord.Interaction, address: str):
        """Set custom external IP or domain for the web map"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        # Basic validation
        address = address.strip()
        if not address:
            await interaction.response.send_message("❌ Address cannot be empty.", ephemeral=True)
            return
        
        # Remove protocol if provided
        if address.startswith(('http://', 'https://')):
            address = address.split('://', 1)[1]
        
        # Remove trailing slash
        address = address.rstrip('/')
        
        # Store the override
        self.external_ip_override = address
        
        embed = discord.Embed(
            title="🌐 External IP/Domain Set",
            description=f"Web map external address updated to: `{address}`",
            color=0x00ff00
        )
        
        if self.is_running:
            full_url = f"http://{address}:{self.port}"
            embed.add_field(
                name="🔗 Updated Access URL",
                value=f"[{full_url}]({full_url})",
                inline=False
            )
            embed.add_field(
                name="📌 Note",
                value="This setting will persist until the bot restarts or is changed again.",
                inline=False
            )
        else:
            embed.add_field(
                name="📌 Note",
                value="Web map is not currently running. This setting will be used when you start the server.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="webmap_clear_ip", description="Clear custom external IP and use auto-detection")
    async def clear_external_ip(self, interaction: discord.Interaction):
        """Clear custom external IP setting"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        self.external_ip_override = None
        
        embed = discord.Embed(
            title="🌐 External IP Setting Cleared",
            description="Web map will now use automatic IP detection.",
            color=0x00ff00
        )
        
        if self.is_running:
            # Try to detect external IP again
            try:
                external_ip = await self._get_external_ip()
                if external_ip:
                    new_url = f"http://{external_ip}:{self.port}"
                    embed.add_field(
                        name="🔗 Auto-detected URL",
                        value=f"[{new_url}]({new_url})",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⚠️ Auto-detection Failed",
                        value="Could not automatically detect external IP. Use `/webmap_set_ip` to set manually.",
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name="⚠️ Auto-detection Error",
                    value=f"Error detecting external IP: {str(e)}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @app_commands.command(name="webmap_stop", description="Stop the interactive web map server")
    async def stop_webmap(self, interaction: discord.Interaction):
        """Stop the web map server"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if not self.is_running:
            await interaction.response.send_message("❌ Web map is not currently running.", ephemeral=True)
            return
        
        try:
            self.is_running = False
            
            # Close WebSocket connections
            for client in self.websocket_clients.copy():
                try:
                    await client.close()
                except:
                    pass
            self.websocket_clients.clear()
            
            # The server thread will stop when the main process stops
            # FastAPI/Uvicorn doesn't have a clean shutdown method when run in thread
            
            embed = discord.Embed(
                title="🛑 Web Map Server Stopped",
                description="Interactive galaxy map has been shut down.",
                color=0xff0000
            )
            
            await interaction.response.send_message(embed=embed)
            print("🛑 Web map server stopped")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error stopping web map: {str(e)}")
    
    @app_commands.command(name="webmap_status", description="Check web map server status")
    async def webmap_status(self, interaction: discord.Interaction):
        """Check the status of the web map server"""
        
        embed = discord.Embed(
            title="🗺️ Web Map Status",
            color=0x00ff00 if self.is_running else 0xff0000
        )
        
        if self.is_running:
            embed.add_field(
                name="Status",
                value="🟢 Running",
                inline=True
            )
            
            # Show correct URL
            display_url, url_note = self._get_display_url()
            
            if self.external_ip_override:
                embed.add_field(
                    name="External URL (Custom)",
                    value=f"{display_url}",
                    inline=False
                )
            else:
                # Try to get auto-detected IP
                try:
                    external_ip = await self._get_external_ip()
                    if external_ip:
                        auto_url = f"http://{external_ip}:{self.port}"
                        embed.add_field(
                            name="External URL (Auto-detected)",
                            value=f"{auto_url}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="External URL",
                            value="❌ Could not detect external IP\nUse `/webmap_set_ip` to set manually",
                            inline=False
                        )
                except:
                    embed.add_field(
                        name="External URL",
                        value="❌ Error detecting external IP\nUse `/webmap_set_ip` to set manually",
                        inline=False
                    )
            
            local_url = f"http://localhost:{self.port}"
            embed.add_field(
                name="Local URL",
                value=f"{local_url}",
                inline=False
            )
            
            embed.add_field(
                name="Connected Clients",
                value=str(len(self.websocket_clients)),
                inline=True
            )
            
            # Port conflict check
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            check_host = 'localhost' if self.host == '0.0.0.0' else self.host
            result = sock.connect_ex((check_host, self.port))
            sock.close()
            
            if result != 0:
                embed.add_field(
                    name="⚠️ Warning",
                    value="Port appears to be unreachable - server may have stopped",
                    inline=False
                )
        else:
            embed.add_field(
                name="Status",
                value="🔴 Stopped",
                inline=True
            )
            
            if self.external_ip_override:
                embed.add_field(
                    name="Saved External IP",
                    value=f"`{self.external_ip_override}` (will be used when server starts)",
                    inline=False
                )
            
            embed.add_field(
                name="Info",
                value="Use `/webmap_start` to start the server",
                inline=True
            )
            
            # Check if default port is occupied
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 8090))
            sock.close()
            
            if result == 0:
                embed.add_field(
                    name="⚠️ Port 8090 Conflict",
                    value="Port 8090 is in use. Use a different port when starting.",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _calculate_route(self, from_id: int, to_id: int) -> dict:
        """Calculate the shortest route between two locations using Dijkstra's algorithm"""
        
        # Get all active corridors
        corridors = self.db.execute_query(
            """SELECT origin_location, destination_location, travel_time, fuel_cost
               FROM corridors WHERE is_active = 1""",
            fetch='all'
        )
        
        # Build graph
        graph = {}
        for origin, dest, time, fuel in corridors:
            if origin not in graph:
                graph[origin] = []
            if dest not in graph:
                graph[dest] = []
            
            # Use travel time as weight for shortest route calculation
            weight = time + (fuel * 10)  # Factor in fuel cost
            graph[origin].append((dest, weight))
            graph[dest].append((origin, weight))  # Bidirectional
        
        # Dijkstra's algorithm
        import heapq
        
        distances = {node: float('infinity') for node in graph}
        distances[from_id] = 0
        previous = {}
        pq = [(0, from_id)]
        visited = set()
        
        while pq:
            current_distance, current = heapq.heappop(pq)
            
            if current in visited:
                continue
                
            visited.add(current)
            
            if current == to_id:
                break
            
            for neighbor, weight in graph.get(current, []):
                distance = current_distance + weight
                
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    heapq.heappush(pq, (distance, neighbor))
        
        # Reconstruct path
        if to_id not in previous and from_id != to_id:
            return {"error": "No route found"}
        
        path = []
        current = to_id
        while current is not None:
            path.append(current)
            current = previous.get(current)
        
        path.reverse()
        
        # Calculate total time and fuel
        total_time = 0
        total_fuel = 0
        
        for i in range(len(path) - 1):
            origin = path[i]
            dest = path[i + 1]
            
            corridor = self.db.execute_query(
                """SELECT travel_time, fuel_cost FROM corridors 
                   WHERE origin_location = ? AND destination_location = ? AND is_active = 1""",
                (origin, dest),
                fetch='one'
            )
            
            if corridor:
                total_time += corridor[0]
                total_fuel += corridor[1]
        
        return {
            "path": path,
            "total_time": total_time,
            "total_fuel": total_fuel,
            "distance": len(path) - 1
        }
async def setup(bot):
    await bot.add_cog(WebMapCog(bot))