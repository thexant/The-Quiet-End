# cogs/web_map.py
import discord
from discord.ext import commands, tasks
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
        self.update_player_data_task.start()
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
    async def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_player_data_task.cancel()
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
        """Create the HTML template and static files with enhanced holo-table design"""
        # Create the main HTML template
        html_content = html_content = '''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <title>Galaxy Map - Navigation Terminal</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="/static/css/map.css" />
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono:wght@400&family=Tektur:wght@400;500;700;900&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="scanlines"></div>
        <div class="static-overlay"></div>
        
        <!-- Header Toggle Button - Always Visible -->
        <button id="header-toggle" class="header-toggle" title="Toggle Navigation Panel">
            <span class="toggle-icon">▼</span>
        </button>
        
        <div id="header" class="header-expanded">
            <div class="header-brand">
                <div class="terminal-indicator">
                    <div class="power-light"></div>
                    <span class="terminal-id">NAV-7742</span>
                </div>
                <h1>NAVIGATION TERMINAL</h1>
                <div class="subtitle">◦ TRANSIT NETWORK OVERVIEW: ACTIVE ROUTES AND KNOWN LOCATIONS ◦</div>
            </div>
            
            <button id="mobile-toggle" class="mobile-toggle">☰</button>
            
            <div id="controls-section" class="controls-section">
                <div class="controls-row">
                    <div id="search-container" class="control-group">
                        <input type="text" id="location-search" placeholder="SEARCH LOCATIONS..." />
                        <button id="search-btn" class="btn-primary">SCAN</button>
                        <button id="clear-search-btn" class="btn-secondary">CLR</button>
                    </div>
                    
                    <div id="status-container" class="status-container">
                        <div id="connection-status" class="connection-status">
                            <span id="connection-indicator">●</span>
                            <span id="connection-text">CONNECTING...</span>
                        </div>
                        <div id="player-info" class="player-info">
                            <span id="player-count">0 CONTACTS</span>
                        </div>
                    </div>
                </div>
                
                <div class="controls-row">
                    <div id="route-container" class="control-group">
                        <select id="route-from" disabled>
                            <option value="">ORIGIN...</option>
                        </select>
                        <select id="route-to" disabled>
                            <option value="">DESTINATION...</option>
                        </select>
                        <button id="plot-route-btn" class="btn-primary" disabled>PLOT</button>
                        <button id="clear-route-btn" class="btn-secondary" disabled>CLEAR</button>
                    </div>
                    
                    <div id="view-controls" class="control-group">
                        <button id="fit-bounds-btn" class="btn-secondary">CENTER</button>
                        <button id="toggle-labels-btn" class="btn-secondary">LABELS</button>
                        <button id="toggle-routes-btn" class="btn-secondary toggle-active">ROUTES</button>
                        <button id="toggle-npcs-btn" class="btn-secondary toggle-active">NPCS</button>
                    </div>
                </div>
            </div>
        </div>

        <div id="map"></div>

        <div id="location-panel" class="location-panel hidden">
            <div class="panel-header">
                <div class="panel-status">
                    <div class="status-light"></div>
                    <span>LOCATION DATA</span>
                </div>
                <h3 id="location-title">UNKNOWN</h3>
                <button id="close-panel" class="close-btn">×</button>
            </div>
            <div class="panel-content">
                <div id="location-details"></div>
            </div>
        </div>

        <div id="legend" class="legend">
            <div class="legend-header">
                <div class="legend-status">
                    <div class="status-light"></div>
                    <span>LEGEND</span>
                </div>
            </div>
                <div class="legend-items">
                    <div class="legend-item"><span class="marker colony"></span> COLONIES (●)</div>
                    <div class="legend-item"><span class="marker station"></span> STATIONS (▲)</div>
                    <div class="legend-item"><span class="marker outpost"></span> OUTPOSTS (■)</div>
                    <div class="legend-item"><span class="marker gate"></span> GATES (◆)</div>
                    <div class="legend-item"><span class="alignment-marker loyalist"></span> LOYALIST</div>
                    <div class="legend-item"><span class="alignment-marker outlaw"></span> OUTLAW</div>
                    <div class="legend-item"><span class="corridor gated"></span> GATED</div>
                    <div class="legend-item"><span class="corridor ungated"></span> UNGATED</div>
                    <div class="legend-item"><span class="corridor approach"></span> LOCAL SPACE</div>
                    <div class="legend-item"><span class="player-indicator"></span> CONTACTS</div>
                    <div class="legend-item"><span class="npc-indicator"></span> NPCS</div>
                </div>
        </div>

        <div id="loading-overlay" class="loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">INITIALIZING NAVIGATION SYSTEMS...</div>
            <div class="loading-subtext">SCANNING GALACTIC INFRASTRUCTURE...</div>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="/static/js/map.js"></script>
    </body>
    </html>'''
        
        with open("web/templates/index.html", "w", encoding='utf-8') as f:
            f.write(html_content)
        
        # Create enhanced CSS file with holo-table aesthetic
        # Create enhanced CSS file with randomized CRT color schemes
        css_content = css_content = '''/* CRT Navigation Terminal with Random Color Schemes */
        :root {
            /* Default blue scheme - will be overridden by JS */
            --primary-color: #00ffff;
            --secondary-color: #00cccc;
            --accent-color: #0088cc;
            --warning-color: #ff8800;
            --success-color: #00ff88;
            --error-color: #ff3333;
            
            /* Base colors */
            --primary-bg: #000408;
            --secondary-bg: #0a0f1a;
            --accent-bg: #1a2332;
            --text-primary: #e0ffff;
            --text-secondary: #88ccdd;
            --text-muted: #556677;
            --border-color: #003344;
            --shadow-dark: rgba(0, 0, 0, 0.9);
            
            /* Dynamic colors based on scheme */
            --glow-primary: rgba(0, 255, 255, 0.6);
            --glow-secondary: rgba(0, 204, 204, 0.4);
            --gradient-holo: linear-gradient(135deg, rgba(0, 255, 255, 0.1), rgba(0, 204, 204, 0.2));
            --gradient-panel: linear-gradient(145deg, rgba(10, 15, 26, 0.95), rgba(26, 35, 50, 0.95));
        }

        /* Color Schemes */
        .theme-blue {
            --primary-color: #00ffff;
            --secondary-color: #00cccc;
            --accent-color: #0088cc;
            --glow-primary: rgba(0, 255, 255, 0.6);
            --glow-secondary: rgba(0, 204, 204, 0.4);
            --gradient-holo: linear-gradient(135deg, rgba(0, 255, 255, 0.1), rgba(0, 204, 204, 0.2));
        }

        .theme-amber {
            --primary-color: #ffaa00;
            --secondary-color: #cc8800;
            --accent-color: #ff6600;
            --glow-primary: rgba(255, 170, 0, 0.6);
            --glow-secondary: rgba(204, 136, 0, 0.4);
            --gradient-holo: linear-gradient(135deg, rgba(255, 170, 0, 0.1), rgba(204, 136, 0, 0.2));
            --text-primary: #fff0e0;
            --text-secondary: #ddcc88;
            --border-color: #443300;
        }

        .theme-green {
            --primary-color: #00ff88;
            --secondary-color: #00cc66;
            --accent-color: #00aa44;
            --glow-primary: rgba(0, 255, 136, 0.6);
            --glow-secondary: rgba(0, 204, 102, 0.4);
            --gradient-holo: linear-gradient(135deg, rgba(0, 255, 136, 0.1), rgba(0, 204, 102, 0.2));
            --text-primary: #e0ffe8;
            --text-secondary: #88dd99;
            --border-color: #003322;
        }

        .theme-red {
            --primary-color: #ff4444;
            --secondary-color: #cc2222;
            --accent-color: #aa0000;
            --glow-primary: rgba(255, 68, 68, 0.6);
            --glow-secondary: rgba(204, 34, 34, 0.4);
            --gradient-holo: linear-gradient(135deg, rgba(255, 68, 68, 0.1), rgba(204, 34, 34, 0.2));
            --text-primary: #ffe0e0;
            --text-secondary: #dd8888;
            --border-color: #330000;
        }

        .theme-purple {
            --primary-color: #aa44ff;
            --secondary-color: #8822cc;
            --accent-color: #6600aa;
            --glow-primary: rgba(170, 68, 255, 0.6);
            --glow-secondary: rgba(136, 34, 204, 0.4);
            --gradient-holo: linear-gradient(135deg, rgba(170, 68, 255, 0.1), rgba(136, 34, 204, 0.2));
            --text-primary: #f0e0ff;
            --text-secondary: #cc88dd;
            --border-color: #220033;
        }
        /* Alignment-specific location colors */
        .location-loyalist {
            filter: drop-shadow(0 0 8px #4169E1) !important;
        }

        .location-outlaw {
            filter: drop-shadow(0 0 8px #DC143C) !important;
        }

        .location-neutral {
            filter: drop-shadow(0 0 6px #ffffff) !important;
        }

        /* Alignment panel styling */
        .alignment-panel {
            background: linear-gradient(145deg, rgba(var(--glow-primary), 0.3), rgba(var(--glow-secondary), 0.2));
            border: 2px solid var(--primary-color);
            border-radius: 6px;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            text-align: center;
            font-weight: bold;
            font-family: 'Tektur', monospace;
            text-shadow: 0 0 8px var(--glow-primary);
            box-shadow: 
                0 0 20px var(--glow-primary),
                inset 0 1px 0 rgba(var(--glow-primary), 0.3);
        }

        .alignment-loyalist {
            --primary-color: #4169E1;
            --glow-primary: rgba(65, 105, 225, 0.6);
            --glow-secondary: rgba(65, 105, 225, 0.4);
            color: #4169E1;
            border-color: #4169E1;
        }

        .alignment-outlaw {
            --primary-color: #DC143C;
            --glow-primary: rgba(220, 20, 60, 0.6);
            --glow-secondary: rgba(220, 20, 60, 0.4);
            color: #DC143C;
            border-color: #DC143C;
        }
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            background: var(--primary-bg);
            color: var(--text-primary);
            overflow: hidden;
            position: relative;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Enhanced CRT Effects */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                /* Screen curvature simulation */
                radial-gradient(ellipse 100% 100% at 50% 50%, transparent 98%, rgba(0,0,0,0.1) 100%),
                /* Phosphor glow */
                radial-gradient(ellipse 200% 100% at 50% 0%, rgba(var(--glow-primary), 0.02) 0%, transparent 50%),
                radial-gradient(ellipse 200% 100% at 50% 100%, rgba(var(--glow-primary), 0.02) 0%, transparent 50%);
            pointer-events: none;
            z-index: 1;
        }

        .scanlines {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 1px,
                rgba(var(--glow-primary), 0.03) 1px,
                rgba(var(--glow-primary), 0.03) 3px
            );
            pointer-events: none;
            z-index: 5;
            animation: flicker 4s infinite linear;
        }

        .static-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                /* Static noise */
                url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><defs><filter id="noise"><feTurbulence baseFrequency="0.9" numOctaves="1" stitchTiles="stitch"/></filter></defs><rect width="100%" height="100%" filter="url(%23noise)" opacity="0.02"/></svg>'),
                /* Chromatic aberration */
                radial-gradient(circle at 25% 25%, rgba(255, 0, 0, 0.01) 0%, transparent 50%),
                radial-gradient(circle at 75% 75%, rgba(0, 255, 0, 0.01) 0%, transparent 50%);
            pointer-events: none;
            z-index: 3;
            animation: static-drift 12s infinite linear;
        }

        @keyframes flicker {
            0%, 97%, 100% { opacity: 1; }
            98% { opacity: 0.92; }
            99% { opacity: 1; }
            99.5% { opacity: 0.95; }
        }

        @keyframes static-drift {
            0% { transform: translateX(0) translateY(0); }
            25% { transform: translateX(-0.5px) translateY(0.5px); }
            50% { transform: translateX(0.5px) translateY(-0.5px); }
            75% { transform: translateX(-0.3px) translateY(-0.3px); }
            100% { transform: translateX(0) translateY(0); }
        }

        /* Header Toggle Button */
        .header-toggle {
            position: fixed;
            top: 0.5rem;
            right: 0.5rem;
            z-index: 2000;
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 6px;
            color: var(--primary-color);
            padding: 0.5rem;
            cursor: pointer;
            font-family: 'Share Tech Mono', monospace;
            font-size: 0.8rem;
            transition: all 0.3s ease;
            box-shadow: 0 0 15px var(--glow-primary);
            backdrop-filter: blur(5px);
            min-width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .header-toggle:hover {
            box-shadow: 0 0 25px var(--glow-primary);
            transform: scale(1.05);
        }

        .toggle-icon {
            transition: transform 0.3s ease;
            font-weight: bold;
        }

        .header-toggle.collapsed .toggle-icon {
            transform: rotate(180deg);
        }

        /* Header Styles */
        #header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: var(--gradient-panel);
            border-bottom: 2px solid var(--primary-color);
            box-shadow: 
                0 0 30px var(--glow-primary),
                inset 0 1px 0 rgba(var(--glow-primary), 0.2),
                0 4px 20px var(--shadow-dark);
            z-index: 1000;
            padding: 1rem;
            backdrop-filter: blur(5px);
            border-top: 1px solid rgba(var(--glow-primary), 0.1);
            transition: all 0.3s ease;
        }

        #header.header-expanded {
            transform: translateY(0);
        }

        #header.header-collapsed {
            transform: translateY(-100%);
        }

        .header-brand {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }

        .terminal-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.25rem;
            font-size: 0.7rem;
            color: var(--text-muted);
        }

        .power-light {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success-color);
            box-shadow: 0 0 12px var(--success-color);
            animation: power-pulse 2s infinite;
        }

        @keyframes power-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        .terminal-id {
            font-family: 'Tektur', monospace;
            font-weight: 700;
        }

        .header-brand h1 {
            margin: 0;
            font-family: 'Tektur', monospace;
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--primary-color);
            text-shadow: 
                0 0 10px var(--glow-primary),
                0 0 20px var(--glow-primary),
                0 0 30px var(--glow-primary);
            filter: drop-shadow(0 0 8px var(--glow-primary));
        }

        .subtitle {
            font-size: 0.7rem;
            color: var(--text-secondary);
            font-weight: 400;
            margin-top: 0.25rem;
            opacity: 0.8;
            letter-spacing: 2px;
        }

        .mobile-toggle {
            display: none;
            background: linear-gradient(145deg, var(--accent-bg), var(--secondary-bg));
            border: 1px solid var(--primary-color);
            color: var(--primary-color);
            font-size: 1.2rem;
            padding: 0.5rem;
            border-radius: 4px;
            cursor: pointer;
            text-shadow: 0 0 5px var(--glow-primary);
            box-shadow: 0 0 15px var(--glow-primary);
            transition: all 0.3s ease;
        }

        .mobile-toggle:hover {
            box-shadow: 0 0 25px var(--glow-primary);
            text-shadow: 0 0 15px var(--glow-primary);
        }

        .controls-section {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-top: 1rem;
            transition: all 0.3s ease;
        }

        .controls-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
        }

        .control-group {
            display: flex;
            gap: 0.5rem;
            align-items: center;
            flex-wrap: wrap;
        }

        /* Input Styles - Fixed dropdown visibility */
        input[type="text"] {
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.8), rgba(var(--glow-secondary), 0.1));
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-primary);
            padding: 0.5rem 0.75rem;
            font-size: 0.8rem;
            font-family: 'Share Tech Mono', monospace;
            min-width: 120px;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        select {
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.9), rgba(var(--glow-secondary), 0.2)) !important;
            border: 2px solid var(--border-color) !important;
            border-radius: 4px !important;
            color: var(--text-primary) !important;
            padding: 0.5rem 0.75rem !important;
            font-size: 0.8rem !important;
            font-family: 'Share Tech Mono', monospace !important;
            min-width: 120px !important;
            transition: all 0.3s ease !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            appearance: none !important;
            -webkit-appearance: none !important;
            -moz-appearance: none !important;
            background-image: linear-gradient(145deg, rgba(0, 0, 0, 0.9), rgba(var(--glow-secondary), 0.2)),
                              linear-gradient(to bottom, transparent 50%, var(--primary-color) 50%) !important;
            background-size: 100% 100%, 12px 12px !important;
            background-position: 0 0, calc(100% - 8px) center !important;
            background-repeat: no-repeat !important;
        }

        select option {
            background: var(--secondary-bg) !important;
            color: var(--text-primary) !important;
            border: none !important;
            padding: 0.5rem !important;
            font-family: 'Share Tech Mono', monospace !important;
            text-transform: uppercase !important;
        }

        input[type="text"]:focus, select:focus {
            outline: none !important;
            border-color: var(--primary-color) !important;
            box-shadow: 
                0 0 0 1px var(--primary-color),
                0 0 15px var(--glow-primary),
                inset 0 0 10px rgba(var(--glow-primary), 0.1) !important;
            background: linear-gradient(145deg, rgba(var(--glow-secondary), 0.2), rgba(var(--glow-primary), 0.1)) !important;
        }

        input[type="text"]::placeholder {
            color: var(--text-muted);
            opacity: 0.7;
        }

        #location-search {
            min-width: 180px;
        }

        /* Button Styles */
        .btn-primary, .btn-secondary, button {
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 0.5rem 1rem;
            font-size: 0.75rem;
            font-family: 'Share Tech Mono', monospace;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }

        .btn-primary {
            background: linear-gradient(145deg, var(--primary-color), var(--secondary-color));
            color: var(--primary-bg);
            border-color: var(--primary-color);
            box-shadow: 0 0 15px var(--glow-primary);
            text-shadow: none;
        }

        .btn-primary:hover:not(:disabled) {
            box-shadow: 0 0 25px var(--glow-primary);
            text-shadow: 0 0 5px rgba(0, 0, 0, 0.8);
        }

        .btn-secondary {
            background: linear-gradient(145deg, rgba(var(--glow-secondary), 0.3), rgba(var(--accent-bg), 0.8));
            color: var(--text-secondary);
            border-color: var(--border-color);
            text-shadow: 0 0 3px var(--glow-primary);
        }

        .btn-secondary:hover:not(:disabled) {
            background: linear-gradient(145deg, rgba(var(--glow-secondary), 0.5), rgba(var(--accent-bg), 0.9));
            color: var(--primary-color);
            border-color: var(--primary-color);
            box-shadow: 0 0 15px var(--glow-primary);
            text-shadow: 0 0 8px var(--glow-primary);
        }

        .btn-secondary.toggle-active {
            background: linear-gradient(145deg, var(--warning-color), #cc6600);
            color: var(--primary-bg);
            border-color: var(--warning-color);
            box-shadow: 0 0 15px rgba(255, 136, 0, 0.6);
            text-shadow: none;
        }

        .btn-secondary.toggle-active:hover:not(:disabled) {
            box-shadow: 0 0 25px rgba(255, 136, 0, 0.8);
        }

        button:disabled {
            opacity: 0.3;
            cursor: not-allowed;
            box-shadow: none !important;
            text-shadow: none !important;
        }

        /* Status Container */
        .status-container {
            display: flex;
            gap: 1rem;
            align-items: center;
        }

        .connection-status, .player-info {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.6), rgba(var(--glow-secondary), 0.2));
            border: 1px solid var(--border-color);
            font-family: 'Share Tech Mono', monospace;
        }

        .connection-status {
            text-shadow: 0 0 5px var(--glow-primary);
        }

        .player-info {
            color: var(--text-secondary);
        }

        /* Map Styles - Adjust for collapsible header */
        #map {
            position: fixed;
            top: 110px;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 2;
            background: radial-gradient(ellipse at center, #0a0f1a 0%, #000408 100%);
            border-top: 1px solid rgba(var(--glow-primary), 0.2);
            transition: top 0.3s ease;
        }

        #map.header-collapsed {
            top: 50px; /* Adjust when header is collapsed */
        }

        /* Location Panel */
        .location-panel {
            position: fixed;
            top: 120px;
            right: 1rem;
            width: 320px;
            max-height: calc(100vh - 140px);
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 6px;
            box-shadow: 
                0 0 40px var(--glow-primary),
                inset 0 1px 0 rgba(var(--glow-primary), 0.2),
                0 8px 32px var(--shadow-dark);
            z-index: 1500;
            transition: all 0.3s ease;
            overflow: hidden;
            backdrop-filter: blur(10px);
        }

        .location-panel.header-collapsed {
            top: 60px;
            max-height: calc(100vh - 80px);
        }

        .location-panel.hidden {
            transform: translateX(100%);
            opacity: 0;
            pointer-events: none;
        }

        .panel-header {
            padding: 1rem;
            background: linear-gradient(145deg, var(--primary-color), var(--secondary-color));
            color: var(--primary-bg);
            border-bottom: 1px solid rgba(var(--glow-primary), 0.3);
            position: relative;
        }

        .panel-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.7rem;
            margin-bottom: 0.5rem;
            font-weight: 400;
        }

        .status-light {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--success-color);
            box-shadow: 0 0 10px var(--success-color);
            animation: status-pulse 1.5s infinite;
        }

        @keyframes status-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .panel-header h3 {
            margin: 0;
            font-family: 'Tektur', monospace;
            font-size: 1rem;
            font-weight: 700;
            text-shadow: 0 0 5px rgba(0, 0, 0, 0.8);
        }

        .close-btn {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            font-weight: bold;
            transition: all 0.3s ease;
        }

        .close-btn:hover {
            background: rgba(255, 51, 51, 0.8);
            border-color: #ff3333;
            box-shadow: 0 0 15px rgba(255, 51, 51, 0.5);
        }

        .panel-content {
            padding: 1rem;
            max-height: calc(100vh - 200px);
            overflow-y: auto;
            font-size: 0.85rem;
        }

        /* Legend */
        .legend {
            position: fixed;
            bottom: 1rem;
            left: 1rem;
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 6px;
            padding: 1rem;
            box-shadow: 
                0 0 30px var(--glow-primary),
                inset 0 1px 0 rgba(var(--glow-primary), 0.2),
                0 4px 20px var(--shadow-dark);
            z-index: 1500;
            min-width: 180px;
            backdrop-filter: blur(10px);
        }

        .legend-header {
            margin-bottom: 0.75rem;
        }

        .legend-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--primary-color);
            font-family: 'Tektur', monospace;
            font-weight: 500;
            text-shadow: 0 0 8px var(--glow-primary);
        }

        .legend-items {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .legend-item {
            display: flex;
            align-items: center;
            font-size: 0.7rem;
            color: var(--text-secondary);
        }

        /* Marker styles in legend
        .marker {
            width: 12px;
            height: 12px;
            margin-right: 0.5rem;
            border: 2px solid white;
            box-shadow: 0 0 8px rgba(0, 0, 0, 0.5);
            background: white;
        }

        .marker.colony { 
            border-radius: 50%; /* Circle - correct */
        }

        .marker.station { 
            border-radius: 0; /* Square */
            clip-path: polygon(50% 0%, 0% 100%, 100% 100%); /* Triangle - fixed */
        }

        .marker.outpost { 
            border-radius: 0; /* Square - fixed */
            /* No clip-path needed for square */
        }

        .marker.gate { 
            border-radius: 0; /* Square */
            transform: rotate(45deg); /* Diamond - correct */
            margin-right: 0.75rem; /* Extra margin due to rotation */
        }
        .alignment-marker {
            width: 12px;
            height: 12px;
            margin-right: 0.5rem;
            border: 2px solid;
            border-radius: 50%;
            display: inline-block;
            position: relative;
        }

        .alignment-marker.loyalist {
            border-color: #4169E1;
            background: #4169E1;
            box-shadow: 0 0 8px rgba(65, 105, 225, 0.6);
        }

        .alignment-marker.outlaw {
            border-color: #DC143C;
            background: #DC143C;
            box-shadow: 0 0 8px rgba(220, 20, 60, 0.6);
        }

        .alignment-marker.loyalist::before {
            content: "🛡️";
            position: absolute;
            top: -6px;
            left: -6px;
            font-size: 8px;
            z-index: 1;
        }

        .alignment-marker.outlaw::before {
            content: "⚔️";
            position: absolute;
            top: -6px;
            left: -6px;
            font-size: 8px;
            z-index: 1;
        }
        .corridor {
            width: 20px;
            height: 3px;
            margin-right: 0.5rem;
            border-radius: 2px;
        }

        .corridor.gated { background: var(--success-color); }
        .corridor.ungated { background: var(--warning-color); }
        .corridor.approach { 
            background: #8c75ff; 
            opacity: 0.6;
        }
        .player-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
            border: 2px solid var(--success-color);
            background: transparent;
            position: relative;
            animation: contact-pulse 2s infinite;
        }

        @keyframes contact-pulse {
            0% { box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
            70% { box-shadow: 0 0 0 8px rgba(0, 255, 136, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }

        /* Loading Overlay */
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--primary-bg);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 2000;
            transition: opacity 0.5s ease;
        }

        .loading-overlay.hidden {
            opacity: 0;
            pointer-events: none;
        }

        .loading-spinner {
            width: 60px;
            height: 60px;
            border: 3px solid rgba(var(--glow-primary), 0.3);
            border-top: 3px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 1.5rem;
            box-shadow: 0 0 30px var(--glow-primary);
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .loading-text {
            font-family: 'Tektur', monospace;
            color: var(--primary-color);
            font-size: 1.1rem;
            font-weight: 500;
            text-shadow: 0 0 15px var(--glow-primary);
            margin-bottom: 0.5rem;
        }

        .loading-subtext {
            font-family: 'Share Tech Mono', monospace;
            color: var(--text-secondary);
            font-size: 0.8rem;
            opacity: 0.8;
        }

        /* Enhanced Location Labels with proper text containment */
        .location-label {
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.95), rgba(var(--glow-secondary), 0.3)) !important;
            border: 2px solid var(--primary-color) !important;
            border-radius: 8px !important;
            padding: 6px 10px !important;
            font-size: 11px !important;
            font-weight: bold !important;
            color: var(--text-primary) !important;
            font-family: 'Share Tech Mono', monospace !important;
            white-space: nowrap !important;
            pointer-events: none !important;
            z-index: 1000 !important;
            text-shadow: 0 0 8px var(--glow-primary) !important;
            box-shadow: 
                0 0 20px var(--glow-primary),
                inset 0 1px 0 rgba(var(--glow-primary), 0.3) !important;
            backdrop-filter: blur(5px) !important;
            text-align: center !important;
            letter-spacing: 0.5px !important;
            transition: all 0.3s ease !important;
            overflow: hidden !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        .label-text {
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            line-height: 1.2;
        }

        /* Enhanced marker shapes */
        .triangle-marker {
            filter: drop-shadow(0 0 8px var(--primary-color)) !important;
        }

        .square-marker {
            filter: drop-shadow(0 0 6px var(--warning-color)) !important;
        }

        .diamond-marker {
            filter: drop-shadow(0 0 10px #ffdd00) !important;
        }

        /* Pulsing animation for active corridors */
        /* Player transit corridors - blue pulse */
        .corridor-player-transit {
            stroke: #00aaff !important;
            stroke-width: 4 !important;
            stroke-opacity: 1 !important;
            animation: corridor-player-pulse 2s ease-in-out infinite !important;
            filter: drop-shadow(0 0 8px #00aaff) !important;
            z-index: 1000 !important;
        }

        @keyframes corridor-player-pulse {
            0%, 100% { 
                stroke-opacity: 0.8; 
                stroke-width: 4px;
                filter: drop-shadow(0 0 8px #00aaff);
            }
            50% { 
                stroke-opacity: 1; 
                stroke-width: 6px;
                filter: drop-shadow(0 0 20px #00aaff);
            }
        }

        /* NPC transit corridors - faint yellow pulse */
        .corridor-npc-transit {
            stroke: #ffcc44 !important;
            stroke-width: 3 !important;
            stroke-opacity: 0.6 !important;
            animation: corridor-npc-pulse 3s ease-in-out infinite !important;
            filter: drop-shadow(0 0 6px #ffcc44) !important;
            z-index: 999 !important;
        }

        @keyframes corridor-npc-pulse {
            0%, 100% { 
                stroke-opacity: 0.4; 
                stroke-width: 3px;
                filter: drop-shadow(0 0 6px #ffcc44);
            }
            50% { 
                stroke-opacity: 0.8; 
                stroke-width: 4px;
                filter: drop-shadow(0 0 15px #ffcc44);
            }
        }

        /* Corridor selection styling */
        .corridor-selected {
            stroke: #ffff00 !important;
            stroke-width: 5 !important;
            stroke-opacity: 1 !important;
            filter: drop-shadow(0 0 12px #ffff00) !important;
            z-index: 999 !important;
        }

        .location-label.wealth-high {
            border-color: #ffd700 !important;
            color: #ffd700 !important;
            text-shadow: 0 0 8px #ffd700 !important;
            box-shadow: 
                0 0 20px rgba(255, 215, 0, 0.6),
                inset 0 1px 0 rgba(255, 215, 0, 0.3) !important;
        }

        .location-label.wealth-medium {
            border-color: var(--success-color) !important;
            color: var(--success-color) !important;
            text-shadow: 0 0 8px var(--success-color) !important;
            box-shadow: 
                0 0 20px rgba(0, 255, 136, 0.6),
                inset 0 1px 0 rgba(0, 255, 136, 0.3) !important;
        }

        .location-label.wealth-low {
            border-color: var(--error-color) !important;
            color: var(--error-color) !important;
            text-shadow: 0 0 8px var(--error-color) !important;
            box-shadow: 
                0 0 20px rgba(255, 51, 51, 0.6),
                inset 0 1px 0 rgba(255, 51, 51, 0.3) !important;
        }

        /* Zoom-based label sizing */
        .location-label.zoom-small {
            font-size: 10px !important;
            padding: 2px 4px !important;
        }

        .location-label.zoom-medium {
            font-size: 12px !important;
            padding: 4px 8px !important;
        }

        .location-label.zoom-large {
            font-size: 14px !important;
            padding: 6px 10px !important;
        }

        /* Location Details Styles */
        .location-detail {
            margin-bottom: 0.75rem;
            line-height: 1.4;
        }

        .location-detail strong {
            color: var(--primary-color);
            font-weight: 600;
            text-shadow: 0 0 5px var(--glow-primary);
        }

        .players-list {
            background: linear-gradient(145deg, rgba(var(--glow-secondary), 0.2), rgba(0, 0, 0, 0.6));
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 0.75rem;
            margin-top: 0.75rem;
        }

        .player-item {
            display: flex;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(var(--glow-primary), 0.1);
            font-size: 0.8rem;
        }

        .player-item:last-child {
            border-bottom: none;
        }

        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 0.5rem;
            flex-shrink: 0;
        }

        .status-online { 
            background: var(--success-color); 
            box-shadow: 0 0 8px var(--success-color);
        }
        .status-transit { 
            background: var(--warning-color);
            box-shadow: 0 0 8px var(--warning-color);
        }

        .sub-locations {
            margin-top: 0.75rem;
            background: linear-gradient(145deg, rgba(var(--glow-secondary), 0.2), rgba(0, 0, 0, 0.6));
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 0.75rem;
        }

        .sub-location-item {
            padding: 0.5rem 0;
            color: var(--text-secondary);
            font-size: 0.8rem;
            line-height: 1.3;
        }

        /* Leaflet customizations */
        .leaflet-popup-content-wrapper {
            background: var(--gradient-panel);
            color: var(--text-primary);
            border: 2px solid var(--primary-color);
            border-radius: 6px;
            box-shadow: 
                0 0 40px var(--glow-primary),
                0 4px 20px var(--shadow-dark);
            font-family: 'Share Tech Mono', monospace;
            text-transform: uppercase;
        }

        .leaflet-popup-tip {
            background: var(--secondary-bg);
            border: 1px solid var(--primary-color);
        }

        .leaflet-popup-close-button {
            color: var(--text-primary) !important;
            font-size: 18px !important;
            font-weight: bold !important;
            text-shadow: 0 0 8px var(--glow-primary) !important;
        }

        .leaflet-control-zoom {
            border: none !important;
            border-radius: 4px !important;
            overflow: hidden;
            box-shadow: 
                0 0 30px var(--glow-primary),
                0 4px 15px var(--shadow-dark) !important;
        }

        .leaflet-control-zoom a {
            background: var(--gradient-panel) !important;
            border: 1px solid var(--border-color) !important;
            color: var(--text-primary) !important;
            transition: all 0.3s ease !important;
            font-family: 'Share Tech Mono', monospace !important;
            text-shadow: 0 0 5px var(--glow-primary) !important;
        }

        .leaflet-control-zoom a:hover {
            background: linear-gradient(145deg, var(--primary-color), var(--secondary-color)) !important;
            border-color: var(--primary-color) !important;
            color: var(--primary-bg) !important;
            box-shadow: 0 0 20px var(--glow-primary) !important;
            text-shadow: none !important;
        }

        /* Route and highlight styles */
        .location-dimmed {
            opacity: 0.2 !important;
            filter: grayscale(0.9) !important;
            transition: all 0.5s ease !important;
        }

        .location-route-highlight {
            opacity: 1 !important;
            filter: none !important;
            stroke: #ffff00 !important;
            stroke-width: 4 !important;
            stroke-opacity: 1 !important;
            animation: route-glow 2s ease-in-out infinite alternate !important;
        }

        @keyframes route-glow {
            from { 
                stroke-width: 4px; 
                filter: drop-shadow(0 0 10px #ffff00);
            }
            to { 
                stroke-width: 6px; 
                filter: drop-shadow(0 0 25px #ffff00);
            }
        }

        .route-highlight {
            stroke: #ffff00 !important;
            stroke-width: 5 !important;
            stroke-opacity: 0.9 !important;
            z-index: 1000 !important;
            filter: drop-shadow(0 0 8px #ffff00) !important;
            animation: route-pulse 3s ease-in-out infinite !important;
        }

        @keyframes route-pulse {
            0%, 100% { 
                stroke-opacity: 0.6; 
                stroke-width: 4px;
                filter: drop-shadow(0 0 8px #ffff00);
            }
            50% { 
                stroke-opacity: 1; 
                stroke-width: 6px;
                filter: drop-shadow(0 0 20px #ffff00);
            }
        }

        .location-highlight {
            stroke: var(--primary-color) !important;
            stroke-width: 4 !important;
            stroke-opacity: 1 !important;
            fill-opacity: 1 !important;
            filter: drop-shadow(0 0 15px var(--primary-color)) !important;
            animation: search-highlight 2s ease-in-out infinite alternate !important;
        }

        @keyframes search-highlight {
            from { 
                stroke-width: 4px; 
                filter: drop-shadow(0 0 15px var(--primary-color));
            }
            to { 
                stroke-width: 6px; 
                filter: drop-shadow(0 0 30px var(--primary-color));
            }
        }

        /* Routes hidden state */
        .routes-hidden {
            opacity: 0 !important;
            pointer-events: none !important;
            transition: opacity 0.3s ease !important;
            z-index: -1 !important; /* Ensure hidden routes go behind everything */
        }

        /* Mobile Responsiveness */
        @media (max-width: 768px) {
            .header-toggle {
                top: 0.25rem;
                right: 0.25rem;
                padding: 0.4rem;
                min-width: 36px;
                height: 36px;
                font-size: 0.7rem;
            }
            
            .mobile-toggle {
                display: block;
                position: absolute;
                top: 1rem;
                right: 3rem;
            }
            
            #header {
                padding: 1rem;
                height: auto;
                min-height: 80px;
            }
            
            .header-brand {
                margin-right: 4rem;
            }
            
            .header-brand h1 {
                font-size: 1.3rem;
            }
            
            .controls-section {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: var(--gradient-panel);
                border-top: 1px solid var(--border-color);
                padding: 1rem;
                box-shadow: 0 4px 20px var(--shadow-dark);
            }
            
            .controls-section.active {
                display: flex;
            }
            
            .controls-row {
                flex-direction: column;
                align-items: stretch;
                gap: 0.75rem;
            }
            
            .control-group {
                justify-content: center;
                flex-wrap: wrap;
                gap: 0.5rem;
            }
            
            .status-container {
                flex-direction: column;
                gap: 0.5rem;
                align-items: center;
            }
            
            #location-search {
                min-width: 160px;
                flex-grow: 1;
            }
            
            select {
                min-width: 100px !important;
                flex-grow: 1 !important;
            }
            
            #map {
                top: 80px;
            }
            
            #map.header-collapsed {
                top: 40px;
            }
            
            .location-panel {
                width: calc(100% - 2rem);
                right: 1rem;
                left: 1rem;
                top: 100px;
                max-height: calc(100vh - 120px);
            }
            
            .location-panel.header-collapsed {
                top: 50px;
                max-height: calc(100vh - 70px);
            }
            
            .legend {
                bottom: 0.5rem;
                left: 0.5rem;
                right: 0.5rem;
                width: auto;
                min-width: auto;
            }
            
            .legend-items {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
                gap: 0.375rem;
            }
            
            .legend-item {
                font-size: 0.65rem;
            }
            
            .location-label {
                font-size: 10px !important;
                padding: 3px 6px !important;
            }
            
            .location-label.zoom-small {
                font-size: 8px !important;
                padding: 2px 4px !important;
            }
            
            .location-label.zoom-medium {
                font-size: 10px !important;
                padding: 3px 6px !important;
            }
            
            .location-label.zoom-large {
                font-size: 12px !important;
                padding: 4px 8px !important;
            }
        }

        @media (max-width: 480px) {
            .header-brand h1 {
                font-size: 1.1rem;
            }
            
            .subtitle {
                font-size: 0.65rem;
            }
            
            .btn-primary, .btn-secondary, button {
                padding: 0.4rem 0.6rem;
                font-size: 0.7rem;
            }
            
            input[type="text"], select {
                padding: 0.4rem 0.6rem !important;
                font-size: 0.75rem !important;
            }
            
            .legend {
                padding: 0.75rem;
            }
            
            .panel-content {
                padding: 0.75rem;
            }
            
            .location-label {
                font-size: 9px !important;
                padding: 2px 4px !important;
            }
        }

        /* High contrast mode support */
        @media (prefers-contrast: high) {
            :root {
                --border-color: var(--primary-color);
                --text-secondary: var(--text-primary);
            }
            
            .btn-secondary {
                border-width: 2px;
            }
        }

        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
            
            .scanlines, .static-overlay {
                animation: none;
                opacity: 0.5;
            }
        }
        
        .player-presence-indicator {
            pointer-events: none !important;
            animation: player-pulse 2.5s infinite ease-in-out;
            filter: drop-shadow(0 0 4px var(--success-color));
            z-index: 1 !important;
        }

        @keyframes player-pulse {
            0% {
                stroke-opacity: 0.6;
                filter: drop-shadow(0 0 4px var(--success-color));
            }
            50% {
                stroke-opacity: 1;
                filter: drop-shadow(0 0 10px var(--success-color));
            }
            100% {
                stroke-opacity: 0.6;
                filter: drop-shadow(0 0 4px var(--success-color));
            }
        }
        /* Improve click targets for location markers */
        .leaflet-interactive {
            cursor: pointer !important;
        }
        
        .leaflet-marker-icon {
            cursor: pointer !important;
        }
        
        /* Ensure player indicators don't block clicks */
        .player-presence-indicator {
            pointer-events: none !important;
            z-index: 1 !important;
        }
        
        /* Make sure location markers are above indicators */
        .location-marker {
            z-index: 10 !important;
        }
        .npc-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
            border: 2px solid var(--warning-color);
            background: transparent;
            position: relative;
            animation: npc-pulse 2.5s infinite;
        }

        @keyframes npc-pulse {
            0% { box-shadow: 0 0 0 0 rgba(255, 136, 0, 0.7); }
            70% { box-shadow: 0 0 0 8px rgba(255, 136, 0, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 136, 0, 0); }
        }
        
        .npc-presence-indicator {
            pointer-events: none !important;
            animation: npc-pulse-live 2.5s infinite ease-in-out;
            filter: drop-shadow(0 0 4px var(--warning-color));
            z-index: 1 !important;
        }

        @keyframes npc-pulse-live {
            0% {
                stroke-opacity: 0.6;
                filter: drop-shadow(0 0 4px var(--warning-color));
            }
            50% {
                stroke-opacity: 1;
                filter: drop-shadow(0 0 10px var(--warning-color));
            }
            100% {
                stroke-opacity: 0.6;
                filter: drop-shadow(0 0 4px var(--warning-color));
            }
        }
        /* Corridor information panel */
        .corridor-info-overlay {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--gradient-panel);
            border: 2px solid var(--primary-color);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 
                0 0 40px var(--glow-primary),
                0 8px 32px var(--shadow-dark);
            z-index: 2000;
            min-width: 300px;
            max-width: 500px;
            backdrop-filter: blur(10px);
            display: none;
        }

        .corridor-info-panel h3 {
            margin: 0 0 15px 0;
            color: var(--primary-color);
            text-shadow: 0 0 10px var(--glow-primary);
            font-family: 'Tektur', monospace;
        }

        .corridor-details p {
            margin: 8px 0;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        .transit-players {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid var(--border-color);
        }

        .transit-players h4 {
            margin: 0 0 10px 0;
            color: var(--success-color);
            font-size: 0.9rem;
        }

        .transit-player {
            background: rgba(var(--glow-secondary), 0.2);
            padding: 5px 10px;
            margin: 5px 0;
            border-radius: 4px;
            font-size: 0.8rem;
            color: var(--text-primary);
        }

        .corridor-info-panel button {
            margin-top: 15px;
            background: var(--primary-color);
            color: var(--primary-bg);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-family: 'Share Tech Mono', monospace;
            text-transform: uppercase;
            font-weight: bold;
        }

        .corridor-info-panel button:hover {
            background: var(--secondary-color);
            box-shadow: 0 0 15px var(--glow-primary);
        }'''
        with open("web/static/css/map.css", "w", encoding='utf-8') as f:
            f.write(css_content)

        # Create enhanced JavaScript file with color randomization and improved labels
        js_content = '''class GalaxyMap {
                    constructor() {
                        this.map = null;
                        this.websocket = null;
                        this.locations = new Map();
                        this.corridors = new Map();
                        this.players = new Map();
                        this.npcs = new Map();  // ADD THIS LINE
                        this.npcsInTransit = new Map();
                        this.selectedLocation = null;
                        this.routePolylines = [];
                        this.highlightedLocations = [];
                        this.currentRoute = null;
                        this.labels = new Map();
                        this.routeMode = false;
                        this.showLabels = false;
                        this.showRoutes = false;
                        this.showNPCs = true;  // ADD THIS LINE
                        this.headerExpanded = true;
                        this.reconnectAttempts = 0;
                        this.maxReconnectAttempts = 10;
                        this.reconnectDelay = 1000;
                        this.labelGrid = new Map();
                        this.selectedCorridor = null;
                        this.corridorPolylines = new Map(); // Track corridor polylines
                        this.showRoutes = false; // Change default to false (hidden)
                        this.playersInTransit = new Map(); // Track players in transit
                        this.pendingLabelTimeouts = [];
                        this.initializeColorScheme();
                        console.log('🎨 Color scheme initialized');
                        this.init();
                    }
                    
                    initializeColorScheme() {
                        const themes = ['blue', 'amber', 'green', 'red', 'purple'];
                        const selectedTheme = themes[Math.floor(Math.random() * themes.length)];
                        
                        document.body.className = `theme-${selectedTheme}`;
                        
                        console.log(`🎨 CRT Terminal initialized with ${selectedTheme.toUpperCase()} color scheme`);
                    }
                    
                    init() {
                        console.log('🗺️ Setting up map...');
                        this.setupMap();
                        console.log('🎛️ Setting up event listeners...');
                        this.setupEventListeners();
                        console.log('🔌 Connecting WebSocket...');
                        this.connectWebSocket();
                        console.log('👁️ Hiding loading overlay...');
                        this.hideLoadingOverlay();
                        console.log('✅ Map initialization complete');
                    }
                    
                    setupMap() {
                        this.map = L.map('map', {
                            crs: L.CRS.Simple,
                            minZoom: -3,
                            maxZoom: 6,
                            zoomControl: false,
                            attributionControl: false,
                            maxBounds: [[-5000, -5000], [5000, 5000]],
                            maxBoundsViscosity: 1.0
                        });
                        
                        L.control.zoom({
                            position: 'bottomright'
                        }).addTo(this.map);
                        
                        this.map.setView([0, 0], 1);
                        
                        this.map.on('click', () => {
                            this.hideLocationPanel();
                        });
                        
                        // Update labels when zoom changes
                        this.map.on('zoomend', () => {
                            if (this.showLabels) {
                                this.updateLabelsForZoom();
                            }
                        });
                        
                        this.map.on('moveend', () => {
                            if (this.showLabels) {
                                this.updateLabelsForZoom();
                            }
                        });
                    }

                    setupEventListeners() {
                        // Header toggle
                        const headerToggle = document.getElementById('header-toggle');
                        const header = document.getElementById('header');
                        const map = document.getElementById('map');
                        const locationPanel = document.getElementById('location-panel');
                        
                        headerToggle?.addEventListener('click', () => {
                            this.headerExpanded = !this.headerExpanded;
                            
                            if (this.headerExpanded) {
                                header.classList.remove('header-collapsed');
                                header.classList.add('header-expanded');
                                map.classList.remove('header-collapsed');
                                locationPanel?.classList.remove('header-collapsed');
                                headerToggle.classList.remove('collapsed');
                            } else {
                                header.classList.remove('header-expanded');
                                header.classList.add('header-collapsed');
                                map.classList.add('header-collapsed');
                                locationPanel?.classList.add('header-collapsed');
                                headerToggle.classList.add('collapsed');
                            }
                        });
                        
                        // Mobile toggle
                        const mobileToggle = document.getElementById('mobile-toggle');
                        const controlsSection = document.getElementById('controls-section');
                        
                        mobileToggle?.addEventListener('click', () => {
                            controlsSection.classList.toggle('active');
                        });
                        
                        // Search functionality
                        const searchInput = document.getElementById('location-search');
                        const searchBtn = document.getElementById('search-btn');
                        const clearSearchBtn = document.getElementById('clear-search-btn');
                        
                        const performSearch = () => {
                            const query = searchInput.value.trim();
                            if (query) {
                                this.searchLocations(query);
                            }
                        };
                        
                        const clearSearch = () => {
                            searchInput.value = '';
                            this.clearHighlights();
                            this.clearSearch();
                        };
                        
                        searchBtn?.addEventListener('click', performSearch);
                        clearSearchBtn?.addEventListener('click', clearSearch);
                        
                        searchInput?.addEventListener('keypress', (e) => {
                            if (e.key === 'Enter') {
                                performSearch();
                            }
                        });
                        
                        searchInput?.addEventListener('input', (e) => {
                            if (!e.target.value.trim()) {
                                this.clearHighlights();
                            }
                        });
                        
                        // Route plotting
                        const plotRouteBtn = document.getElementById('plot-route-btn');
                        const clearRouteBtn = document.getElementById('clear-route-btn');
                        
                        plotRouteBtn?.addEventListener('click', () => {
                            const fromId = document.getElementById('route-from').value;
                            const toId = document.getElementById('route-to').value;
                            if (fromId && toId && fromId !== toId) {
                                this.plotRoute(parseInt(fromId), parseInt(toId));
                            }
                        });
                        
                        clearRouteBtn?.addEventListener('click', () => {
                            this.clearRoute();
                            document.getElementById('route-from').value = '';
                            document.getElementById('route-to').value = '';
                        });
                        
                        // View controls
                        // View controls
                        const fitBoundsBtn = document.getElementById('fit-bounds-btn');
                        const toggleLabelsBtn = document.getElementById('toggle-labels-btn');
                        const toggleRoutesBtn = document.getElementById('toggle-routes-btn');
                        const toggleNPCsBtn = document.getElementById('toggle-npcs-btn');

                        fitBoundsBtn?.addEventListener('click', () => {
                            this.fitMapToBounds();
                        });

                        toggleLabelsBtn?.addEventListener('click', () => {
                            this.toggleLabels();
                        });

                        // Route toggle - single event listener only
                        toggleRoutesBtn?.addEventListener('click', () => {
                            this.toggleRoutes();
                        });

                        // Set initial button state
                        if (toggleRoutesBtn) {
                            toggleRoutesBtn.textContent = 'SHOW ROUTES';
                            toggleRoutesBtn.classList.remove('toggle-active');
                        }

                        if (toggleNPCsBtn) {
                            toggleNPCsBtn.addEventListener('click', () => {
                                this.toggleNPCs();
                            });
                        }

                        // Panel close
                        const closePanel = document.getElementById('close-panel');
                        closePanel?.addEventListener('click', () => {
                            this.hideLocationPanel();
                        });
                        
                        // Close panel when clicking outside
                        document.addEventListener('click', (e) => {
                            const panel = document.getElementById('location-panel');
                            const mapContainer = this.map?.getContainer();
                            
                            if (panel && !panel.contains(e.target) && 
                                mapContainer && !mapContainer.contains(e.target)) {
                                this.hideLocationPanel();
                            }
                        });
                        // Keyboard shortcuts
                        document.addEventListener('keydown', (e) => {
                            if (e.target.tagName.toLowerCase() === 'input' || e.target.tagName.toLowerCase() === 'select') return;
                            
                            switch(e.key) {
                                case 'Escape':
                                    this.hideLocationPanel();
                                    this.clearHighlights();
                                    this.clearRoute();
                                    break;
                                case 'f':
                                case 'F':
                                    this.fitMapToBounds();
                                    break;
                                case 'l':
                                case 'L':
                                    this.toggleLabels();
                                    break;
                                case 'r':
                                case 'R':
                                    this.toggleRoutes();
                                    break;
                                case 'h':
                                case 'H':
                                    headerToggle?.click();
                                    break;
                            }
                        });
                    }
                    
                    connectWebSocket() {
                        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                        const wsUrl = `${protocol}//${window.location.host}/ws`;
                        
                        if (this.websocket) {
                            this.websocket.close();
                        }
                        
                        this.websocket = new WebSocket(wsUrl);
                        
                        this.websocket.onopen = () => {
                            this.updateConnectionStatus('CONNECTED', 'var(--success-color)');
                            this.reconnectAttempts = 0;
                            console.log('🔗 WebSocket connected to navigation systems');
                        };
                        
                        this.websocket.onmessage = (event) => {
                            try {
                                const data = JSON.parse(event.data);
                                this.handleWebSocketMessage(data);
                            } catch (error) {
                                console.error('Failed to parse WebSocket message:', error);
                            }
                        };
                        
                        this.websocket.onclose = () => {
                            this.updateConnectionStatus('DISCONNECTED', 'var(--error-color)');
                            console.log('🔌 WebSocket disconnected');
                            this.scheduleReconnect();
                        };

                        this.websocket.onerror = (error) => {
                            console.error('❌ WebSocket error:', error);
                            this.updateConnectionStatus('ERROR', 'var(--warning-color)');
                        };
                    }
                    
                    scheduleReconnect() {
                        if (this.reconnectAttempts < this.maxReconnectAttempts) {
                            this.reconnectAttempts++;
                            const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);
                            
                            this.updateConnectionStatus(`RECONNECTING... (${this.reconnectAttempts})`, 'var(--warning-color)');
                            
                            setTimeout(() => {
                                this.connectWebSocket();
                            }, delay);
                        } else {
                            this.updateConnectionStatus('CONNECTION FAILED', 'var(--error-color)');
                        }
                    }
                    
                    handleWebSocketMessage(data) {
                        switch(data.type) {
                            case 'galaxy_data':
                                this.updateGalaxyData(data.data);
                                break;
                            case 'player_update':
                                this.updatePlayers(data.data);
                                break;
                            case 'npc_update':
                                this.updateNPCs(data.data);
                                break;
                            case 'transit_update':  // Add this new case
                                this.updatePlayersInTransit(data.data);
                                break;
                            case 'location_update':
                                this.updateLocation(data.data);
                                break;
                            case 'npc_transit_update':
                                this.updateNPCsInTransit(data.data);
                                break;    
                            default:
                                console.warn('Unknown WebSocket message type:', data.type);
                        }
                    }
                    
                    updateGalaxyData(data) {
                        try {
                            this.locations.clear();
                            this.corridors.clear();
                            this.labelGrid.clear();
                            this.map.eachLayer((layer) => {
                                if (layer !== this.map._layers[Object.keys(this.map._layers)[0]]) {
                                    this.map.removeLayer(layer);
                                }
                            });
                            this.updatePlayersInTransit(data.players_in_transit || []);
                            this.updateNPCsInTransit(data.npcs_in_transit || []);
                            
                            data.locations.forEach(location => {
                                this.addLocation(location);
                            });
                            
                            data.corridors.forEach(corridor => {
                                this.addCorridor(corridor);
                            });
                            
                            this.applyRouteVisibility();
                            this.updatePlayers(data.players || []);
                            this.updateNPCs(data.dynamic_npcs || []);  // ADD THIS LINE
                            this.populateRouteSelects();
                            this.fitMapToBounds();
                            
                        } catch (error) {
                            console.error('Error updating galaxy data:', error);
                        }
                    }
                    
                    addLocation(location) {
                        const marker = this.createLocationMarker(location);
                        marker.addTo(this.map);
                        
                        this.locations.set(location.location_id, {
                            ...location,
                            marker: marker
                        });
                        
                        marker.on('click', (e) => {
                            L.DomEvent.stopPropagation(e);
                            this.selectLocation(location);
                        });
                    }
                    
                    createLocationMarker(location) {
                        const colors = {
                            'Colony': 'var(--success-color)',
                            'Space Station': 'var(--primary-color)',
                            'Outpost': 'var(--warning-color)',
                            'Transit Gate': '#ffdd00'
                        };
                        
                        // Override color based on alignment
                        let color = colors[location.location_type] || '#ffffff';
                        
                        if (location.alignment === 'loyalist') {
                            color = '#4169E1'; // Royal Blue for Loyalists
                        } else if (location.alignment === 'outlaw') {
                            color = '#DC143C'; // Crimson for Outlaws
                        }
                        
                        const zoom = this.map.getZoom();
                        
                        // Apply consistent zoom scaling to ALL locations
                        let finalSize;
                        if (zoom < -1) {
                            finalSize = 12; // All tiny when zoomed way out
                        } else if (zoom < 0) {
                            finalSize = 13; // All small when zoomed out
                        } else if (zoom < 1) {
                            finalSize = 14; // All medium when mid-zoom
                        } else {
                            finalSize = 15; // All normal when zoomed in
                        }
                        
                        const marker = this.createShapedMarker(location, color, finalSize);
                        
                        // Add alignment class to marker element for additional styling
                        if (location.alignment !== 'neutral') {
                            marker.on('add', () => {
                                const element = marker.getElement();
                                if (element) {
                                    element.classList.add(`location-${location.alignment}`);
                                }
                            });
                        }
                        
                        return marker;
                    }    
                    getZoomAdjustedBaseSize(locationType) {
                        const zoom = this.map.getZoom();
                        
                        // Force complete uniformity at low zoom levels
                        if (zoom < -0.5) {
                            return 14; // Everyone gets exactly the same size when zoomed way out
                        }
                        
                        const baseSizes = {
                            'colony': 15,
                            'space_station': 15, 
                            'outpost': 15,
                            'gate': 15
                        };
                        
                        const baseSize = baseSizes[locationType.toLowerCase()] || 14;
                        
                        if (zoom < 1.5) {
                            // Still zoomed out: very minimal differences (max 1px variance)
                            const uniformSize = 15;
                            const variance = (baseSize - uniformSize) * 0.2; // Only 20% of type difference
                            return uniformSize + variance;
                        } else {
                            // Zoomed in enough: allow full differences
                            return baseSize;
                        }
                    }
                    addCorridor(corridor) {
                        // Improved corridor type detection
                        let corridorType = 'ungated'; // default
                        let color = 'var(--warning-color)'; // orange for ungated
                        
                        // Detect corridor type based on name patterns
                        if (corridor.name.toLowerCase().includes('approach')) {
                            corridorType = 'approach';
                            color = '#8c75ff'; // light green for local space
                        } else if (corridor.name.toLowerCase().includes('ungated')) {
                            corridorType = 'ungated';
                            color = 'var(--warning-color)'; // orange for ungated
                        } else {
                            // Check if route connects to gates by looking at endpoint types
                            const originIsGate = this.locations.get(corridor.origin_location)?.location_type === 'gate';
                            const destIsGate = this.locations.get(corridor.destination_location)?.location_type === 'gate';
                            
                            if (originIsGate || destIsGate) {
                                corridorType = 'gated';
                                color = 'var(--success-color)'; // green for gated
                            }
                        }
                        
                        // Create invisible thick line for better click targets
                        const clickTarget = L.polyline([
                            [corridor.origin_y, corridor.origin_x],
                            [corridor.dest_y, corridor.dest_x]
                        ], {
                            color: 'transparent',
                            weight: 12,
                            opacity: 0,
                            interactive: true
                        });

                        // Create visible line with proper styling
                        const polyline = L.polyline([
                            [corridor.origin_y, corridor.origin_x],
                            [corridor.dest_y, corridor.dest_x]
                        ], {
                            color: color,
                            weight: corridorType === 'gated' ? 2 : corridorType === 'approach' ? 1.5 : 3,
                            opacity: 0.7,
                            dashArray: corridorType === 'ungated' ? '8, 5' : corridorType === 'approach' ? '4, 2' : null,
                            className: `corridor ${corridorType}`,
                            corridorId: corridor.corridor_id,
                            interactive: false
                        });

                        // Add both to map
                        clickTarget.addTo(this.map);
                        polyline.addTo(this.map);

                        // Make click target interactive
                        clickTarget.on('click', (e) => {
                            L.DomEvent.stopPropagation(e);
                            this.selectCorridor(corridor, polyline);
                        });
                        
                        // Add mouseover effects to click target
                        clickTarget.on('mouseover', () => {
                            if (!polyline.getElement()?.classList.contains('corridor-selected')) {
                                polyline.setStyle({opacity: 1, weight: polyline.options.weight + 1});
                            }
                        });

                        clickTarget.on('mouseout', () => {
                            if (!polyline.getElement()?.classList.contains('corridor-selected')) {
                                polyline.setStyle({opacity: 0.7, weight: polyline.options.weight - 1});
                            }
                        });
                        
                        // Store both polylines for later reference
                        this.corridorPolylines.set(corridor.corridor_id, polyline);

                        this.corridors.set(corridor.corridor_id, {
                            ...corridor,
                            polyline: polyline,
                            clickTarget: clickTarget,
                            isGated: corridorType === 'gated',
                            corridorType: corridorType
                        });
                    }

                    // Add corridor selection functionality
                    selectCorridor(corridor, polyline) {
                        // Clear previous selection
                        if (this.selectedCorridor) {
                            this.selectedCorridor.polyline.getElement()?.classList.remove('corridor-selected');
                        }
                        
                        // Select new corridor
                        this.selectedCorridor = {corridor, polyline};
                        polyline.getElement()?.classList.add('corridor-selected');
                        
                        // Show corridor information panel
                        this.showCorridorInfo(corridor);
                    }

                    // Add corridor information panel
                    showCorridorInfo(corridor) {
                        // Get players and NPCs in this corridor
                        const playersInCorridor = this.playersInTransit.get(corridor.corridor_id) || [];
                        const npcsInCorridor = this.npcsInTransit.get(corridor.corridor_id) || [];
                        
                        const panelContent = `
                            <div class="corridor-info-panel">
                                <h3>${corridor.name}</h3>
                                <div class="corridor-details">
                                    <p><strong>Type:</strong> ${corridor.name.includes('Ungated') ? 'Ungated (Dangerous)' : 'Gated (Safe)'}</p>
                                    <p><strong>Travel Time:</strong> ${Math.floor(corridor.travel_time / 60)} minutes ${corridor.travel_time % 60} seconds</p>
                                    <p><strong>Fuel Cost:</strong> ${corridor.fuel_cost} units</p>
                                    <p><strong>Danger Level:</strong> ${corridor.danger_level}/5</p>
                                </div>
                                ${playersInCorridor.length > 0 ? `
                                    <div class="transit-players">
                                        <h4>Players in Transit:</h4>
                                        ${playersInCorridor.map(player => `
                                            <div class="transit-player">
                                                ${player.name} (${player.origin} → ${player.destination})
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                                ${npcsInCorridor.length > 0 ? `
                                    <div class="transit-players">
                                        <h4>NPCs in Transit:</h4>
                                        ${npcsInCorridor.map(npc => `
                                            <div class="transit-player" style="color: var(--warning-color);">
                                                ${npc.name} (${npc.callsign}) - ${npc.ship_name}<br>
                                                ${npc.origin} → ${npc.destination}
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                                ${playersInCorridor.length === 0 && npcsInCorridor.length === 0 ? '<p>No players or NPCs currently in transit</p>' : ''}
                                <button onclick="galaxyMap.clearCorridorSelection()">Close</button>
                            </div>
                        `;
                        
                        // Create or update info panel
                        let infoPanel = document.getElementById('corridor-info-panel');
                        if (!infoPanel) {
                            infoPanel = document.createElement('div');
                            infoPanel.id = 'corridor-info-panel';
                            infoPanel.className = 'corridor-info-overlay';
                            document.body.appendChild(infoPanel);
                        }
                        
                        infoPanel.innerHTML = panelContent;
                        infoPanel.style.display = 'block';
                    }
                    // Clear corridor selection
                    clearCorridorSelection() {
                        if (this.selectedCorridor) {
                            this.selectedCorridor.polyline.getElement()?.classList.remove('corridor-selected');
                            this.selectedCorridor = null;
                        }
                        
                        const infoPanel = document.getElementById('corridor-info-panel');
                        if (infoPanel) {
                            infoPanel.style.display = 'none';
                        }
                    }
                    updatePlayersInTransit(transitData) {
                        this.playersInTransit.clear();
                        
                        transitData.forEach(player => {
                            if (!this.playersInTransit.has(player.corridor_id)) {
                                this.playersInTransit.set(player.corridor_id, []);
                            }
                            this.playersInTransit.get(player.corridor_id).push(player);
                        });
                        
                        // Update corridor highlighting
                        this.updateCorridorHighlighting();
                    }

                    // Highlight corridors with players in transit
                    updateCorridorHighlighting() {
                        this.corridorPolylines.forEach((polyline, corridorId) => {
                            const hasPlayers = this.playersInTransit.has(corridorId);
                            const hasNPCs = this.npcsInTransit.has(corridorId);
                            const element = polyline.getElement();
                            
                            if (element) {
                                // Remove all transit classes
                                element.classList.remove('corridor-active', 'corridor-player-transit', 'corridor-npc-transit');
                                
                                if (hasPlayers && hasNPCs) {
                                    // Both players and NPCs - use player color (blue) as priority
                                    element.classList.add('corridor-player-transit');
                                } else if (hasPlayers) {
                                    // Only players - blue pulse
                                    element.classList.add('corridor-player-transit');
                                } else if (hasNPCs) {
                                    // Only NPCs - yellow pulse
                                    element.classList.add('corridor-npc-transit');
                                }
                            }
                        });
                    }
                    toggleRoutes() {
                        this.showRoutes = !this.showRoutes;
                        const btn = document.getElementById('toggle-routes-btn');
                        
                        this.applyRouteVisibility();
                        
                        if (btn) {
                            if (this.showRoutes) {
                                btn.textContent = 'HIDE ROUTES';
                                btn.classList.add('toggle-active');
                            } else {
                                btn.textContent = 'SHOW ROUTES';
                                btn.classList.remove('toggle-active');
                                // Clear corridor selection when hiding routes
                                this.clearCorridorSelection();
                            }
                        }
                    }
                    toggleNPCs() {
                        this.showNPCs = !this.showNPCs;
                        const btn = document.getElementById('toggle-npcs-btn');
                        
                        this.applyNPCVisibility();
                        
                        if (btn) {
                            if (this.showNPCs) {
                                btn.textContent = 'NPCS';
                                btn.classList.add('toggle-active');
                            } else {
                                btn.textContent = 'NPCS';
                                btn.classList.remove('toggle-active');
                            }
                        }
                    }
                    
                    applyNPCVisibility() {
                        this.locations.forEach(location => {
                            if (location.npcIndicator) {
                                if (this.showNPCs) {
                                    location.npcIndicator.getElement()?.classList.remove('routes-hidden');
                                } else {
                                    location.npcIndicator.getElement()?.classList.add('routes-hidden');
                                }
                            }
                        });
                    }
                    applyRouteVisibility() {
                        this.corridors.forEach(corridor => {
                            // Apply visibility to the visible polyline
                            if (corridor.polyline) {
                                if (this.showRoutes) {
                                    corridor.polyline.getElement()?.classList.remove('routes-hidden');
                                } else {
                                    corridor.polyline.getElement()?.classList.add('routes-hidden');
                                }
                            }
                            
                            // Apply interactivity to the click target
                            if (corridor.clickTarget) {
                                if (this.showRoutes) {
                                    corridor.clickTarget.setStyle({interactive: true});
                                    corridor.clickTarget.getElement()?.classList.remove('routes-hidden');
                                } else {
                                    corridor.clickTarget.setStyle({interactive: false});
                                    corridor.clickTarget.getElement()?.classList.add('routes-hidden');
                                }
                            }
                        });
                        
                        this.routePolylines.forEach(routeLine => {
                            if (this.showRoutes) {
                                routeLine.getElement()?.classList.remove('routes-hidden');
                            } else {
                                routeLine.getElement()?.classList.add('routes-hidden');
                            }
                        });
                    }
                    updateNPCs(npcs) {
                        this.npcs.clear();
                        
                        npcs.forEach(npc => {
                            if (!this.npcs.has(npc.location_id)) {
                                this.npcs.set(npc.location_id, []);
                            }
                            this.npcs.get(npc.location_id).push(npc);
                        });
                        
                        this.locations.forEach((location, locationId) => {
                            this.updateLocationWithNPCs(location, this.npcs.get(locationId) || []);
                        });
                        
                        if (this.selectedLocation) {
                            this.updateLocationPanel(this.selectedLocation);
                        }
                    }
                    
                    updateLocationWithNPCs(location, npcsHere) {
                        const marker = location.marker;
                        if (!marker) return;

                        if (location.npcIndicator) {
                            this.map.removeLayer(location.npcIndicator);
                            delete location.npcIndicator;
                        }

                        if (npcsHere.length > 0) {
                            const indicator = L.circleMarker([location.y_coord, location.x_coord], {
                                radius: 16,
                                fillColor: 'transparent',
                                color: 'var(--warning-color)',
                                weight: 3,
                                opacity: 1,
                                fillOpacity: 0,
                                className: 'npc-presence-indicator',
                                interactive: false,
                                pane: 'shadowPane'
                            });

                            indicator.addTo(this.map);
                            location.npcIndicator = indicator;
                            
                            marker.bringToFront();
                        }
                    }
                    updatePlayers(players) {
                        const playerCount = document.getElementById('player-count');
                        if (playerCount) {
                            // Use total count from server data, or calculate if not provided
                            const totalCount = this.galaxyData?.total_player_count || 
                                              (players.length + (this.playersInTransit.size > 0 ? 
                                               Array.from(this.playersInTransit.values()).flat().length : 0));
                            playerCount.textContent = `${totalCount} CONTACTS`;
                        }
                        
                        this.players.clear();
                        
                        players.forEach(player => {
                            if (!this.players.has(player.location_id)) {
                                this.players.set(player.location_id, []);
                            }
                            this.players.get(player.location_id).push(player);
                        });
                        
                        this.locations.forEach((location, locationId) => {
                            this.updateLocationWithPlayers(location, this.players.get(locationId) || []);
                        });
                        
                        if (this.selectedLocation) {
                            this.updateLocationPanel(this.selectedLocation);
                        }
                    }
                    
                    updateLocationWithPlayers(location, playersHere) {
                        const marker = location.marker;
                        if (!marker) return;

                        if (location.playerIndicator) {
                            this.map.removeLayer(location.playerIndicator);
                            delete location.playerIndicator;
                        }

                        if (playersHere.length > 0) {
                            const indicator = L.circleMarker([location.y_coord, location.x_coord], {
                                radius: 18,
                                fillColor: 'transparent',
                                color: 'var(--success-color)',
                                weight: 3,
                                opacity: 1,
                                fillOpacity: 0,
                                className: 'player-presence-indicator',
                                interactive: false,
                                pane: 'shadowPane' // Put it in a lower layer
                            });

                            indicator.addTo(this.map);
                            location.playerIndicator = indicator;
                            
                            // Ensure the main marker stays clickable by bringing it to front
                            marker.bringToFront();
                        }
                    }
                    updateNPCsInTransit(transitData) {
                        this.npcsInTransit.clear();
                        
                        transitData.forEach(npc => {
                            if (!this.npcsInTransit.has(npc.corridor_id)) {
                                this.npcsInTransit.set(npc.corridor_id, []);
                            }
                            this.npcsInTransit.get(npc.corridor_id).push(npc);
                        });
                        
                        // Update corridor highlighting
                        this.updateCorridorHighlighting();
                    }
                    selectLocation(location) {
                        this.selectedLocation = location;
                        this.updateLocationPanel(location);
                        this.showLocationPanel();
                        
                        this.clearHighlights();
                        this.highlightLocation(location, 'var(--primary-color)');
                    }
                    
                    async updateLocationPanel(location) {
                        const titleElement = document.getElementById('location-title');
                        const detailsElement = document.getElementById('location-details');
                        
                        if (!titleElement || !detailsElement) return;
                        
                        titleElement.textContent = location.name.toUpperCase();
                        
                        const playersHere = this.players.get(location.location_id) || [];
                        const npcsHere = this.npcs.get(location.location_id) || [];
                        const staticNPCs = location.static_npcs || [];
                        const subLocations = await this.getSubLocations(location.location_id);
                        
                        const wealthDisplay = this.getWealthDisplay(location.wealth_level);
                        const typeIcon = this.getLocationTypeIcon(location.location_type);
                        
                        // Create alignment panel if not neutral
                        let alignmentPanel = '';
                        if (location.alignment === 'loyalist') {
                            alignmentPanel = `
                                <div class="alignment-panel alignment-loyalist">
                                    🛡️ LOYALISTS
                                </div>
                            `;
                        } else if (location.alignment === 'outlaw') {
                            alignmentPanel = `
                                <div class="alignment-panel alignment-outlaw">
                                    ⚔️ OUTLAWS
                                </div>
                            `;
                        }
                        
                        const detailsHtml = `
                            ${alignmentPanel}
                            <div class="location-detail">
                                <strong>${typeIcon} TYPE:</strong> ${location.location_type.toUpperCase()}
                            </div>
                            <div class="location-detail">
                                <strong>💰 WEALTH:</strong> ${wealthDisplay}
                            </div>
                            <div class="location-detail">
                                <strong>👥 POPULATION:</strong> ${location.population?.toLocaleString() || 'UNKNOWN'}
                            </div>
                            <div class="location-detail">
                                <strong>📍 COORDINATES:</strong> (${location.x_coord}, ${location.y_coord})
                            </div>
                            <div class="location-detail">
                                <strong>📄 DESCRIPTION:</strong>
                                <div style="margin-top: 0.5rem; font-style: italic; color: var(--text-secondary); text-transform: none;">
                                    ${location.description || 'No description available.'}
                                </div>
                            </div>
                            ${subLocations.length > 0 ? `
                                <div class="sub-locations">
                                    <strong>🏢 AVAILABLE AREAS:</strong>
                                    ${subLocations.map(sub => `
                                        <div class="sub-location-item">
                                            ${sub.icon || '📍'} ${sub.name.toUpperCase()} - ${sub.description}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${playersHere.length > 0 ? `
                                <div class="players-list">
                                    <strong>👥 CONTACTS PRESENT (${playersHere.length}):</strong>
                                    ${playersHere.map(player => `
                                        <div class="player-item">
                                            <span class="status-indicator status-online"></span>
                                            ${player.name.toUpperCase()}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${npcsHere.length > 0 ? `
                                <div class="players-list">
                                    <strong>🤖 NPCS PRESENT (${npcsHere.length}):</strong>
                                    ${npcsHere.map(npc => `
                                        <div class="player-item">
                                            <span class="status-indicator" style="background: var(--warning-color); box-shadow: 0 0 8px var(--warning-color);"></span>
                                            ${npc.name.toUpperCase()} (${npc.callsign}) - ${npc.ship_name}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${staticNPCs.length > 0 ? `
                                <div class="players-list">
                                    <strong>👤 NOTABLE INHABITANTS (${staticNPCs.length}):</strong>
                                    ${staticNPCs.map(npc => `
                                        <div class="player-item">
                                            <span class="status-indicator" style="background: var(--accent-color); box-shadow: 0 0 8px var(--accent-color);"></span>
                                            ${npc.name.toUpperCase()} (${npc.age}) - ${npc.occupation.toUpperCase()}
                                            <div style="font-size: 0.7rem; color: var(--text-muted); margin-left: 1rem; font-style: italic;">
                                                ${npc.personality}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${playersHere.length === 0 && npcsHere.length === 0 && staticNPCs.length === 0 ? '<div class="location-detail"><em>No contacts, NPCs, or notable inhabitants currently present</em></div>' : ''}
                        `;
                        
                        detailsElement.innerHTML = detailsHtml;
                    }
                    
                    
                    getWealthDisplay(wealthLevel) {
                        if (wealthLevel >= 9) return '👑 OPULENT';
                        if (wealthLevel >= 7) return '💎 WEALTHY';
                        if (wealthLevel >= 5) return '💰 PROSPEROUS';
                        if (wealthLevel >= 3) return '⚖️ AVERAGE';
                        if (wealthLevel >= 2) return '📉 POOR';
                        if (wealthLevel >= 1) return '🗑️ IMPOVERISHED';
                        return '❓ UNKNOWN';
                    }
                    
                    getLocationTypeIcon(locationType) {
                        const icons = {
                            'Colony': '🏘️',
                            'Space Station': '🛰️',
                            'Outpost': '🏭',
                            'Transit Gate': '🌌'
                        };
                        return icons[locationType] || '📍';
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
                    
                    showLocationPanel() {
                        const panel = document.getElementById('location-panel');
                        if (panel) {
                            panel.classList.remove('hidden');
                        }
                    }
                    
                    hideLocationPanel() {
                        const panel = document.getElementById('location-panel');
                        if (panel) {
                            panel.classList.add('hidden');
                        }
                        this.selectedLocation = null;
                        this.clearHighlights();
                    }
                    
                    searchLocations(query) {
                        this.clearHighlights();
                        
                        if (!query.trim()) return;
                        
                        const results = [];
                        const queryLower = query.toLowerCase();
                        
                        this.locations.forEach((location) => {
                            if (location.name.toLowerCase().includes(queryLower) ||
                                location.location_type.toLowerCase().includes(queryLower)) {
                                results.push(location);
                            }
                        });
                        
                        if (results.length > 0) {
                            results.forEach(location => {
                                this.highlightLocation(location, 'var(--primary-color)');
                            });
                            
                            if (results.length === 1) {
                                this.map.setView([results[0].y_coord, results[0].x_coord], 4);
                                this.selectLocation(results[0]);
                            } else {
                                this.fitBoundsToLocations(results);
                            }
                        }
                    }
                    
                    clearSearch() {
                        const searchInput = document.getElementById('location-search');
                        if (searchInput) {
                            searchInput.value = '';
                        }
                        this.clearHighlights();
                    }
                    
                    highlightLocation(location, color = '#ffff00') {
                        if (!location.marker) return;
                        
                        const originalOptions = location.marker.options;
                        location.marker.setStyle({
                            ...originalOptions,
                            color: color,
                            weight: 4,
                            opacity: 1,
                            className: `${originalOptions.className} location-highlight`
                        });
                        
                        this.highlightedLocations.push(location);
                    }
                    
                    clearHighlights() {
                        this.highlightedLocations.forEach(location => {
                            if (location.marker) {
                                const originalOptions = location.marker.options;
                                location.marker.setStyle({
                                    ...originalOptions,
                                    color: '#ffffff',
                                    weight: 2,
                                    opacity: 1,
                                    className: originalOptions.className.replace(' location-highlight', '')
                                });
                            }
                        });
                        this.highlightedLocations = [];
                    }
                    
                    async plotRoute(fromId, toId) {
                        try {
                            const response = await fetch(`/api/route/${fromId}/${toId}`);
                            if (!response.ok) throw new Error('Route calculation failed');
                            
                            const routeData = await response.json();
                            
                            if (routeData.error) {
                                alert('NO ROUTE FOUND BETWEEN SELECTED LOCATIONS');
                                return;
                            }
                            
                            this.displayRoute(routeData);
                            
                        } catch (error) {
                            console.error('Error plotting route:', error);
                            alert('FAILED TO CALCULATE ROUTE');
                        }
                    }
                    
                    displayRoute(routeData) {
                        this.clearRoute();
                        
                        if (!routeData.path || routeData.path.length < 2) return;
                        
                        const routeCoords = routeData.path.map(location => [location.y_coord, location.x_coord]);
                        const routeLine = L.polyline(routeCoords, {
                            color: '#ffff00',
                            weight: 5,
                            opacity: 0.9,
                            className: 'route-highlight'
                        });
                        
                        routeLine.addTo(this.map);
                        this.routePolylines.push(routeLine);
                        
                        if (!this.showRoutes) {
                            routeLine.getElement()?.classList.add('routes-hidden');
                        }
                        
                        routeData.path.forEach(location => {
                            const loc = this.locations.get(location.location_id);
                            if (loc) {
                                this.highlightLocation(loc, '#ffff00');
                            }
                        });
                        
                        this.map.fitBounds(routeLine.getBounds(), { padding: [20, 20] });
                        this.currentRoute = routeData;
                        
                        const clearBtn = document.getElementById('clear-route-btn');
                        if (clearBtn) clearBtn.disabled = false;
                    }
                    
                    clearRoute() {
                        this.routePolylines.forEach(polyline => {
                            this.map.removeLayer(polyline);
                        });
                        this.routePolylines = [];
                        
                        this.clearHighlights();
                        this.currentRoute = null;
                        
                        const clearBtn = document.getElementById('clear-route-btn');
                        if (clearBtn) clearBtn.disabled = true;
                    }
                    
                    populateRouteSelects() {
                        const fromSelect = document.getElementById('route-from');
                        const toSelect = document.getElementById('route-to');
                        
                        if (!fromSelect || !toSelect) return;
                        
                        [fromSelect, toSelect].forEach(select => {
                            while (select.children.length > 1) {
                                select.removeChild(select.lastChild);
                            }
                        });
                        
                        const sortedLocations = Array.from(this.locations.values())
                            .sort((a, b) => a.name.localeCompare(b.name));
                        
                        sortedLocations.forEach(location => {
                            [fromSelect, toSelect].forEach(select => {
                                const option = document.createElement('option');
                                option.value = location.location_id;
                                option.textContent = `${location.name.toUpperCase()} (${location.location_type.toUpperCase()})`;
                                select.appendChild(option);
                            });
                        });
                        
                        fromSelect.disabled = false;
                        toSelect.disabled = false;
                        
                        [fromSelect, toSelect].forEach(select => {
                            select.addEventListener('change', () => {
                                const plotBtn = document.getElementById('plot-route-btn');
                                if (plotBtn) {
                                    plotBtn.disabled = !(fromSelect.value && toSelect.value && fromSelect.value !== toSelect.value);
                                }
                            });
                        });
                    }
                    
                    fitMapToBounds() {
                        if (this.locations.size === 0) return;
                        
                        const bounds = L.latLngBounds();
                        this.locations.forEach(location => {
                            bounds.extend([location.y_coord, location.x_coord]);
                        });
                        
                        this.map.fitBounds(bounds, { padding: [20, 20] });
                    }
                    
                    fitBoundsToLocations(locations) {
                        if (locations.length === 0) return;
                        
                        const bounds = L.latLngBounds();
                        locations.forEach(location => {
                            bounds.extend([location.y_coord, location.x_coord]);
                        });
                        
                        this.map.fitBounds(bounds, { padding: [40, 40] });
                    }
                    
                toggleLabels() {
                    this.showLabels = !this.showLabels;
                    const btn = document.getElementById('toggle-labels-btn');
                    
                    if (this.showLabels) {
                        this.addLocationLabels();
                        if (btn) {
                            btn.textContent = 'HIDE LABELS';
                            btn.classList.add('toggle-active');
                        }
                    } else {
                        this.removeLocationLabels();
                        if (btn) {
                            btn.textContent = 'SHOW LABELS';
                            btn.classList.remove('toggle-active');
                        }
                    }
                }
                
                addLocationLabels() {
                    this.removeLocationLabels();
                    
                    const zoom = this.map.getZoom();
                    const bounds = this.map.getBounds();
                    
                    // Get all visible locations
                    let visibleLocations = [];
                    this.locations.forEach(location => {
                        const point = L.latLng(location.y_coord, location.x_coord);
                        if (bounds.contains(point)) {
                            visibleLocations.push(location);
                        }
                    });

                    // Simple, predictable logic: if few locations visible, show all labels
                    // If many locations visible, show only the most important ones
                    let locationsToLabel;
                    
                    if (visibleLocations.length <= 8) {
                        // When zoomed in close or few locations visible, show ALL labels
                        locationsToLabel = visibleLocations;
                    } else if (zoom >= 2) {
                        // High zoom with many locations - show top 75%
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.floor(visibleLocations.length * 0.75));
                    } else if (zoom >= 0) {
                        // Medium zoom - show top 50%
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.floor(visibleLocations.length * 0.5));
                    } else if (zoom >= -2) {
                        // Low zoom - show top 25%
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.max(1, Math.floor(visibleLocations.length * 0.25)));
                    } else {
                        // Very low zoom - show only top 10 most important
                        visibleLocations.sort((a, b) => this.getLocationImportance(b) - this.getLocationImportance(a));
                        locationsToLabel = visibleLocations.slice(0, Math.min(10, visibleLocations.length));
                    }

                    // Initialize timeout tracking
                    if (!this.pendingLabelTimeouts) {
                        this.pendingLabelTimeouts = [];
                    }

                    // Add labels immediately instead of with delays to prevent conflicts
                    locationsToLabel.forEach((location) => {
                        this.addSimpleLabel(location);
                    });
                }

                
                // Replace the existing addSimpleLabel function
                addSimpleLabel(location) {
                    const zoom = this.map.getZoom();
                    const labelSize = this.getSimpleLabelSize(zoom);
                    
                    // Simple offset pattern - cycle through positions to avoid overlap
                    const offsetPatterns = [
                        [0, -35],      // Above
                        [30, -20],     // Top-right
                        [30, 20],      // Bottom-right
                        [0, 35],       // Below
                        [-30, 20],     // Bottom-left
                        [-30, -20],    // Top-left
                        [40, 0],       // Right
                        [-40, 0]       // Left
                    ];
                    
                    // Use location ID to get consistent positioning
                    const patternIndex = location.location_id % offsetPatterns.length;
                    const [offsetX, offsetY] = offsetPatterns[patternIndex];
                    
                    // Scale offset with zoom
                    const zoomScale = Math.max(0.7, Math.min(1.5, 1.0 + (zoom * 0.1)));
                    const finalOffsetX = offsetX * zoomScale;
                    const finalOffsetY = offsetY * zoomScale;
                    
                    // Calculate label position
                    const basePoint = this.map.latLngToContainerPoint([location.y_coord, location.x_coord]);
                    const labelPoint = L.point(basePoint.x + finalOffsetX, basePoint.y + finalOffsetY);
                    const labelPosition = this.map.containerPointToLatLng(labelPoint);
                    
                    // Check if position is within map bounds
                    if (!this.map.getBounds().contains(labelPosition)) {
                        // Try opposite offset if out of bounds
                        const fallbackPoint = L.point(basePoint.x - finalOffsetX, basePoint.y - finalOffsetY);
                        const fallbackPosition = this.map.containerPointToLatLng(fallbackPoint);
                        if (this.map.getBounds().contains(fallbackPosition)) {
                            this.createLabelMarker(location, fallbackPosition, labelSize, zoom);
                        }
                        return;
                    }
                    
                    this.createLabelMarker(location, labelPosition, labelSize, zoom);
                }

                // Add this new function to create properly sized label markers
                createLabelMarker(location, position, labelSize, zoom) {
                    const wealthClass = this.getWealthClass(location.wealth_level);
                    const zoomClass = this.getZoomClass(zoom);
                    const labelText = this.formatLabelText(location.name, zoom);
                    
                    // Calculate proper text dimensions
                    const textLength = labelText.length;
                    const charWidth = zoom >= 2 ? 8 : zoom >= 0 ? 7 : 6;
                    const calculatedWidth = Math.max(labelSize.width, textLength * charWidth + 20);
                    
                    const label = L.marker(position, {
                        icon: L.divIcon({
                            className: `location-label ${wealthClass} ${zoomClass}`,
                            html: `<div class="label-text">${labelText}</div>`,
                            iconSize: [calculatedWidth, labelSize.height],
                            iconAnchor: [calculatedWidth / 2, labelSize.height / 2]
                        }),
                        interactive: false
                    });

                    label.addTo(this.map);
                    location.label = label;
                }
                formatLabelText(name, zoom) {
                    // Truncate long names at low zoom levels
                    if (zoom < -1 && name.length > 12) {
                        return name.substring(0, 10).toUpperCase() + '...';
                    } else if (zoom < 1 && name.length > 15) {
                        return name.substring(0, 12).toUpperCase() + '...';
                    }
                    return name.toUpperCase();
                }

                getSimpleLabelSize(zoom) {
                    if (zoom >= 3) {
                        return { width: 120, height: 28 };
                    } else if (zoom >= 1) {
                        return { width: 100, height: 24 };
                    } else if (zoom >= -1) {
                        return { width: 80, height: 20 };
                    } else {
                        return { width: 70, height: 18 };
                    }
                }

                getLocationImportance(location) {
                    const typeWeights = {
                        'Space Station': 100,
                        'Colony': 80,
                        'Transit Gate': 60,
                        'Outpost': 40
                    };
                    
                    const baseScore = typeWeights[location.location_type] || 20;
                    const wealthBonus = (location.wealth_level || 1) * 10;
                    const populationBonus = Math.log10((location.population || 1) + 1) * 5;
                    
                    return baseScore + wealthBonus + populationBonus;
                }

                getWealthClass(wealthLevel) {
                    if (wealthLevel >= 7) return 'wealth-high';
                    if (wealthLevel >= 4) return 'wealth-medium';
                    return 'wealth-low';
                }

                getZoomClass(zoom) {
                    if (zoom >= 3) return 'zoom-large';
                    if (zoom >= 0) return 'zoom-medium';
                    return 'zoom-small';
                }

                updateLabelsForZoom() {
                    if (this.showLabels) {
                        clearTimeout(this.labelUpdateTimeout);
                        this.labelUpdateTimeout = setTimeout(() => {
                            this.addLocationLabels();
                        }, 200);
                    }
                }
                // Fix the removeLocationLabels function
                removeLocationLabels() {
                    this.locations.forEach(location => {
                        if (location.label) {
                            this.map.removeLayer(location.label);
                            location.label = null;
                        }
                    });
                }

                // Update the createLocationMarker function to use different shapes and sizes
                createLocationMarker(location) {
                    const colors = {
                        'Colony': 'var(--success-color)',
                        'Space Station': 'var(--primary-color)',
                        'Outpost': 'var(--warning-color)',
                        'Transit Gate': '#ffdd00'
                    };
                    
                    const color = colors[location.location_type] || '#ffffff';
                    const zoom = this.map.getZoom();
                    
                    // Apply consistent zoom scaling to ALL locations
                    let finalSize;
                    if (zoom < -1) {
                        finalSize = 12; // All tiny when zoomed way out
                    } else if (zoom < 0) {
                        finalSize = 13; // All small when zoomed out
                    } else if (zoom < 1) {
                        finalSize = 14; // All medium when mid-zoom
                    } else {
                        finalSize = 15; // All normal when zoomed in
                    }
                    
                    return this.createShapedMarker(location, color, finalSize);
                }
                calculatePopulationSize(population) {
                    // Disabled to ensure uniform scaling
                    return 0;
                }
                getBaseMarkerSize(locationType) {
                    // Uniform base size - differentiation comes from shape, not size
                    return 15;
                }
                createShapedMarker(location, color, size) {
                    const markerOptions = {
                        radius: size,
                        fillColor: '#ffffff',
                        color: '#ffffff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9,
                        className: `location-marker ${location.location_type.toLowerCase().replace(' ', '-')}`
                    };

                    let marker;
                    
                    // Use different shapes based on location type
                    switch(location.location_type.toLowerCase()) {
                        case 'colony':
                            marker = L.circleMarker([location.y_coord, location.x_coord], markerOptions);
                            break;
                            
                        case 'space_station':
                            const trianglePoints = this.getTrianglePoints(location.x_coord, location.y_coord, size);
                            marker = L.polygon(trianglePoints, {
                                ...markerOptions,
                                className: `${markerOptions.className} triangle-marker`
                            });
                            break;
                            
                        case 'outpost':
                            const squarePoints = this.getSquarePoints(location.x_coord, location.y_coord, size);
                            marker = L.polygon(squarePoints, {
                                ...markerOptions,
                                className: `${markerOptions.className} square-marker`
                            });
                            break;
                            
                        case 'gate':
                            const diamondPoints = this.getDiamondPoints(location.x_coord, location.y_coord, size);
                            marker = L.polygon(diamondPoints, {
                                ...markerOptions,
                                className: `${markerOptions.className} diamond-marker`
                            });
                            break;
                            
                        default:
                            marker = L.circleMarker([location.y_coord, location.x_coord], markerOptions);
                            break;
                    }
                    
                    marker.on('click', (e) => {
                        L.DomEvent.stopPropagation(e);
                        this.selectLocation(location);  // ✅ CORRECT - passing location object
                    });
                    
                    return marker;
                }
                            

                getTrianglePoints(x, y, size) {
                    const offset = size * 0.018; // Slightly larger for better visibility
                    return [
                        [y + offset, x],           // Top
                        [y - offset, x - offset],  // Bottom left
                        [y - offset, x + offset]   // Bottom right
                    ];
                }

                getSquarePoints(x, y, size) {
                    const offset = size * 0.015; // Slightly larger for better visibility
                    return [
                        [y + offset, x - offset],  // Top left
                        [y + offset, x + offset],  // Top right
                        [y - offset, x + offset],  // Bottom right
                        [y - offset, x - offset]   // Bottom left
                    ];
                }

                getDiamondPoints(x, y, size) {
                    const offset = size * 0.018; // Slightly larger for better visibility
                    return [
                        [y + offset, x],           // Top
                        [y, x + offset],           // Right
                        [y - offset, x],           // Bottom
                        [y, x - offset]            // Left
                    ];
                }
                    
                    updateConnectionStatus(text, color) {
                        const indicator = document.getElementById('connection-indicator');
                        const statusText = document.getElementById('connection-text');
                        
                        if (indicator && statusText) {
                            indicator.style.color = color;
                            statusText.textContent = text;
                        }
                    }
                    
                    hideLoadingOverlay() {
                        const overlay = document.getElementById('loading-overlay');
                        if (overlay) {
                            setTimeout(() => {
                                overlay.classList.add('hidden');
                            }, 1500);
                        }
                    }
                }

                let galaxyMap;

                // Initialize map when page loads
                document.addEventListener('DOMContentLoaded', () => {
                    galaxyMap = new GalaxyMap();
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
        @app.get("/api/npc/{npc_id}")
        async def get_npc_details(npc_id: int):
            """Get details for a specific NPC"""
            try:
                npc_data = self.db.execute_query(
                    """SELECT name, callsign, age, ship_name, ship_type, current_location, credits
                       FROM dynamic_npcs WHERE npc_id = ? AND is_alive = 1""",
                    (npc_id,),
                    fetch='one'
                )
                
                if npc_data:
                    return {
                        "name": npc_data[0],
                        "callsign": npc_data[1],
                        "age": npc_data[2],
                        "ship_name": npc_data[3],
                        "ship_type": npc_data[4],
                        "current_location": npc_data[5],
                        "credits": npc_data[6]
                    }
                else:
                    return {"error": "NPC not found"}
            except Exception as e:
                return {"error": str(e)}
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websocket_clients.add(websocket)
            
            try:
                # Send initial data
                try:
                    galaxy_data = await self._get_galaxy_data()
                    await websocket.send_text(json.dumps({
                        "type": "galaxy_data",
                        "data": galaxy_data
                    }))
                    
                    # Send transit data
                    await websocket.send_text(json.dumps({
                        "type": "transit_update",
                        "data": galaxy_data.get("players_in_transit", [])
                    }))
                    print(f"✅ WebSocket client connected and sent initial data")
                except Exception as e:
                    print(f"❌ Error sending initial galaxy data: {e}")
                    # Send minimal data to prevent frontend from hanging
                    await websocket.send_text(json.dumps({
                        "type": "galaxy_data",
                        "data": {
                            "galaxy_name": "Unknown Galaxy",
                            "current_time": "Unknown",
                            "locations": [],
                            "corridors": [],
                            "players": [],
                            "dynamic_npcs": [],
                            "players_in_transit": []
                        }
                    }))
                
                # Keep connection alive and handle messages
                while True:
                    data = await websocket.receive_text()
                    # Handle any client messages if needed
                    
            except WebSocketDisconnect:
                self.websocket_clients.discard(websocket)
                print(f"📱 WebSocket client disconnected")
            except Exception as e:
                print(f"❌ WebSocket error: {e}")
                self.websocket_clients.discard(websocket)

        return app
    
    async def _get_galaxy_data(self):
        """Get current galaxy data with transit information"""
        # Get galaxy info
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = galaxy_info[0] if galaxy_info else "Unknown Galaxy"
        
        current_time = time_system.calculate_current_ingame_time()
        formatted_time = time_system.format_ingame_datetime(current_time) if current_time else "Unknown"
        
        # Define alignment function properly
        def determine_location_alignment(has_black_market, has_federal_supplies, wealth_level):
            """Determine location alignment based on properties"""
            if has_black_market:
                return "outlaw"
            elif has_federal_supplies or wealth_level >= 8:
                return "loyalist"
            else:
                return "neutral"
        
        # Get locations
        try:
            locations = self.db.execute_query(
                """SELECT location_id, name, location_type, x_coord, y_coord, 
                          wealth_level, population, description, has_black_market, has_federal_supplies
                   FROM locations ORDER BY name""",
                fetch='all'
            )
            if locations is None:
                locations = []
        except Exception as e:
            print(f"Error fetching locations: {e}")
            locations = []
        
        # Ensure locations is not None
        if locations is None:
            locations = []
        # Get static NPCs for each location FIRST
        static_npcs_by_location = {}
        try:
            static_npcs = self.db.execute_query(
                """SELECT location_id, name, age, occupation, personality 
                   FROM static_npcs ORDER BY location_id, name""",
                fetch='all'
            )
            if static_npcs:
                for location_id, name, age, occupation, personality in static_npcs:
                    if location_id not in static_npcs_by_location:
                        static_npcs_by_location[location_id] = []
                    static_npcs_by_location[location_id].append({
                        "name": name,
                        "age": age,
                        "occupation": occupation,
                        "personality": personality
                    })
        except Exception as e:
            print(f"Warning: Could not fetch static NPCs: {e}")
            static_npcs_by_location = {}

        # Process locations with alignment
        processed_locations = []
        for loc in (locations or []):
            alignment = determine_location_alignment(loc[8], loc[9], loc[5])
            processed_locations.append({
                "location_id": loc[0],
                "name": loc[1],
                "location_type": loc[2],
                "x_coord": loc[3],
                "y_coord": loc[4],
                "wealth_level": loc[5],
                "population": loc[6],
                "description": loc[7],
                "alignment": alignment,
                "static_npcs": static_npcs_by_location.get(loc[0], [])
            })
        # Get active corridors
        try:
            corridors = self.db.execute_query(
                '''SELECT c.corridor_id, c.name, c.danger_level, c.travel_time, c.fuel_cost,
                          c.origin_location, c.destination_location,
                          ol.x_coord as origin_x, ol.y_coord as origin_y,
                          dl.x_coord as dest_x, dl.y_coord as dest_y, ol.location_type as origin_type
                   FROM corridors c
                   JOIN locations ol ON c.origin_location = ol.location_id
                   JOIN locations dl ON c.destination_location = dl.location_id
                   WHERE c.is_active = 1''',
                fetch='all'
            )
            if corridors is None:
                corridors = []
        except Exception as e:
            print(f"Error fetching corridors: {e}")
            corridors = []
        
        # Get online players
        # Get online players with better error handling
        try:
            players = self.db.execute_query(
                """SELECT c.name, c.current_location, c.is_logged_in
                   FROM characters c
                   WHERE c.is_logged_in = 1""",
                fetch='all'
            )
            if players is None:
                players = []
        except Exception as e:
            print(f"Error fetching players: {e}")
            players = []
        
        try:
            players_in_transit = self.db.execute_query(
                """SELECT ts.corridor_id, c.name as character_name, ts.origin_location, ts.destination_location,
                          ol.name as origin_name, dl.name as dest_name, c.user_id
                   FROM travel_sessions ts
                   JOIN characters c ON ts.user_id = c.user_id
                   JOIN locations ol ON ts.origin_location = ol.location_id
                   JOIN locations dl ON ts.destination_location = dl.location_id
                   WHERE ts.status = 'traveling'""",
                fetch='all'
            )
            if players_in_transit is None:
                players_in_transit = []
        except Exception as e:
            print(f"Error fetching players in transit: {e}")
            players_in_transit = []
        # Get NPCs in transit using their own travel system
        npcs_in_transit = []
        try:
            npcs_in_transit = self.db.execute_query(
                """SELECT n.npc_id, n.name, n.callsign, n.ship_name, 
                          n.current_location as origin_location, n.destination_location,
                          ol.name as origin_name, dl.name as dest_name, c.corridor_id
                   FROM dynamic_npcs n
                   JOIN locations ol ON n.current_location = ol.location_id
                   JOIN locations dl ON n.destination_location = dl.location_id
                   JOIN corridors c ON (c.origin_location = n.current_location AND c.destination_location = n.destination_location)
                   WHERE n.travel_start_time IS NOT NULL AND n.destination_location IS NOT NULL AND n.is_alive = 1""",
                fetch='all'
            )
            if npcs_in_transit is None:
                npcs_in_transit = []
        except Exception as e:
            print(f"Warning: Could not fetch NPCs in transit: {e}")
            npcs_in_transit = []
        except Exception as e:
            # If that fails, try a simpler approach or just return empty list
            print(f"Warning: Could not fetch NPCs in transit (travel_sessions approach): {e}")
            try:
                # Alternative: just return NPCs that have travel_start_time set (but no destination info)
                npcs_with_travel_time = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.callsign, n.ship_name, n.current_location
                       FROM dynamic_npcs n
                       WHERE n.travel_start_time IS NOT NULL AND n.is_alive = 1""",
                    fetch='all'
                )
                # For now, we can't determine their destination, so return empty list
                npcs_in_transit = []
                if npcs_with_travel_time:
                    print(f"Found {len(npcs_with_travel_time)} NPCs with travel_start_time set, but no destination info available")
            except Exception as e2:
                print(f"Warning: Could not fetch NPCs in transit (fallback approach): {e2}")
                npcs_in_transit = []
        # Get dynamic NPCs - with error handling
        dynamic_npcs = []
        try:
            dynamic_npcs = self.db.execute_query(
                """SELECT n.name, n.callsign, n.current_location, n.ship_name, n.ship_type,
                          n.is_alive, n.travel_start_time
                   FROM dynamic_npcs n
                   WHERE n.is_alive = 1 AND n.current_location IS NOT NULL 
                   AND n.travel_start_time IS NULL""",
                fetch='all'
            )
            if dynamic_npcs is None:
                dynamic_npcs = []
        except Exception as e:
            print(f"Warning: Could not fetch dynamic NPCs: {e}")
            dynamic_npcs = []
        
        return {
            "galaxy_name": galaxy_name,
            "current_time": formatted_time,
            "locations": processed_locations,
            "corridors": [
                {
                    "corridor_id": cor[0],
                    "name": cor[1],
                    "danger_level": cor[2],
                    "travel_time": cor[3],
                    "fuel_cost": cor[4],
                    "origin_location": cor[5],
                    "destination_location": cor[6],
                    "origin_x": cor[7],
                    "origin_y": cor[8],
                    "dest_x": cor[9],
                    "dest_y": cor[10]
                }
                for cor in (corridors or [])
            ],
            "players": [
                {
                    "name": player[0],
                    "location_id": player[1],
                    "is_logged_in": player[2]
                }
                for player in (players or [])
            ],
            "players_in_transit": [
                {
                    "corridor_id": transit[0],
                    "name": transit[1],
                    "origin": transit[4],
                    "destination": transit[5],
                    "user_id": transit[6]
                }
                for transit in (players_in_transit or [])
            ],
            # Add NPC transit data
            "npcs_in_transit": [
                {
                    "npc_id": npc[0],
                    "name": npc[1],
                    "callsign": npc[2], 
                    "ship_name": npc[3],
                    "origin": npc[6],
                    "destination": npc[7],
                    "corridor_id": npc[8]
                }
                for npc in npcs_in_transit
            ] if npcs_in_transit else [],
            "dynamic_npcs": [
                {
                    "name": npc[0],
                    "callsign": npc[1],
                    "location_id": npc[2],
                    "ship_name": npc[3],
                    "ship_type": npc[4],
                    "is_alive": npc[5]
                }
                for npc in dynamic_npcs
            ],
            # Add total player count including transit
            "total_player_count": len(players or []) + len(players_in_transit or [])
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
    @tasks.loop(seconds=10)  # Update every 10 seconds instead of waiting for events
    async def update_player_data_task(self):
        """Regularly update player data for real-time map"""
        if self.is_running and self.websocket_clients:
            await self._broadcast_player_updates()
    async def _broadcast_player_updates(self):
        """Optimized player and NPC updates with caching"""
        try:
            # Get current player data
            players_data = []
            try:
                players_data = self.db.execute_query(
                    """SELECT c.name, c.current_location, c.is_logged_in, c.user_id
                       FROM characters c
                       WHERE c.is_logged_in = 1 AND c.current_location IS NOT NULL""",
                    fetch='all'
                )
                if players_data is None:
                    players_data = []
            except Exception as e:
                print(f"Warning: Could not fetch player data: {e}")
                players_data = []
            
            current_players = [
                {
                    "name": player[0],
                    "location_id": player[1],
                    "is_logged_in": player[2] == 1,
                    "user_id": player[3]
                }
                for player in players_data
            ]
            # Get NPCs in transit using their own travel system
            npcs_in_transit = []
            try:
                npcs_in_transit_data = self.db.execute_query(
                    """SELECT n.npc_id, n.name, n.callsign, n.ship_name, 
                              n.current_location as origin_location, n.destination_location,
                              ol.name as origin_name, dl.name as dest_name, c.corridor_id
                       FROM dynamic_npcs n
                       JOIN locations ol ON n.current_location = ol.location_id
                       JOIN locations dl ON n.destination_location = dl.location_id
                       JOIN corridors c ON (c.origin_location = n.current_location AND c.destination_location = n.destination_location)
                       WHERE n.travel_start_time IS NOT NULL AND n.destination_location IS NOT NULL AND n.is_alive = 1""",
                    fetch='all'
                )
                if npcs_in_transit_data:
                    npcs_in_transit = [
                        {
                            "npc_id": npc[0],
                            "name": npc[1],
                            "callsign": npc[2],
                            "ship_name": npc[3],
                            "origin": npc[6],
                            "destination": npc[7],
                            "corridor_id": npc[8]
                        }
                        for npc in npcs_in_transit_data
                    ]
            except Exception as e:
                print(f"Warning: Could not fetch NPCs in transit: {e}")
                npcs_in_transit = []
            # Get current dynamic NPC data
            npcs_data = []
            try:
                npcs_data = self.db.execute_query(
                    """SELECT n.name, n.callsign, n.current_location, n.ship_name, n.ship_type
                       FROM dynamic_npcs n
                       WHERE n.is_alive = 1 AND n.current_location IS NOT NULL 
                       AND n.travel_start_time IS NULL""",
                    fetch='all'
                )
                if npcs_data is None:
                    npcs_data = []
            except Exception as e:
                print(f"Warning: Could not fetch NPC data: {e}")
                npcs_data = []
            
            current_npcs = [
                {
                    "name": npc[0],
                    "callsign": npc[1],
                    "location_id": npc[2],
                    "ship_name": npc[3],
                    "ship_type": npc[4]
                }
                for npc in npcs_data
            ]
            
            # Broadcast both updates
            await self._broadcast_update("player_update", current_players)
            await self._broadcast_update("npc_update", current_npcs)
            await self._broadcast_update("npc_transit_update", npcs_in_transit)
            
        except Exception as e:
            print(f"Error broadcasting updates: {e}")
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
            
            # Set state and start updates
            self.is_running = True

            # Update game panels with proper sequencing
            await self._update_game_panels_for_map_status()
            
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
                name="🔄 Features",
                value="• Real-time player positions\n• Interactive location details\n• Zoomable/scrollable map\n• Live updates every minute\n• Route planning\n• Location search",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
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

            # Update panels with the correct sequence
            await self._update_game_panels_for_map_status()
            
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
    async def _update_game_panels_for_map_status(self):
        """Update all game panels when webmap status changes"""
        try:
            panel_cog = self.bot.get_cog('GamePanelCog')
            if not panel_cog:
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
    # cogs/web_map.py

    async def get_final_map_url(self) -> tuple[str, str]:
        """
        Get the final, user-facing map URL.
        This method checks for overrides, then attempts to detect the external IP.
        Returns the final URL and an optional note.
        """
        # 1. Check for an explicit IP/domain override
        if self.external_ip_override:
            url = f"http://{self.external_ip_override}:{self.port}"
            note = f"Map available at your custom address."
            return url, note

        # 2. If no override, try to detect the external IP
        try:
            external_ip = await self._get_external_ip()
            if external_ip:
                url = f"http://{external_ip}:{self.port}"
                note = "URL is based on auto-detected server IP."
                return url, note
        except Exception as e:
            print(f"Failed to get external IP for panel: {e}")

        # 3. Fallback if override is not set and detection fails
        url = f"http://http://184.64.30.214:8090/"
        note = "Could not determine server IP. Admin should use `/webmap_set_ip`."
        return url, note
        
async def setup(bot):
    await bot.add_cog(WebMapCog(bot))