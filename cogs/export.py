# cogs/export.py
import discord
from discord.ext import commands
from discord import app_commands
import io
import zipfile
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import base64

class ExportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="export", description="Export galaxy data as an interactive web encyclopedia")
    @app_commands.describe(
        export_type="Type of export to generate",
        include_logs="Include location logs and guestbooks",
        include_news="Include recent news broadcasts"
    )
    @app_commands.choices(export_type=[
        app_commands.Choice(name="Interactive Web Wiki", value="web"),
        app_commands.Choice(name="Markdown Documentation", value="markdown"),
        app_commands.Choice(name="Both Formats", value="both")
    ])
    async def export_galaxy(self, interaction: discord.Interaction,
                          export_type: str = "web",
                          include_logs: bool = True,
                          include_news: bool = True):
        """Export galaxy data in various formats"""

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if export_type == "web":
                zip_buffer = await self._create_web_export(interaction, include_logs, include_news)
                filename = f"Galaxy_Wiki_{datetime.now().strftime('%Y%m%d')}.zip"
            elif export_type == "markdown":
                zip_buffer = await self._create_markdown_export(interaction, include_logs, include_news)
                filename = f"Galaxy_Docs_{datetime.now().strftime('%Y%m%d')}.zip"
            else:  # both
                zip_buffer = await self._create_combined_export(interaction, include_logs, include_news)
                filename = f"Galaxy_Complete_{datetime.now().strftime('%Y%m%d')}.zip"

            await interaction.followup.send(
                "✅ **Export Complete!**\nYour galaxy encyclopedia has been generated.",
                file=discord.File(zip_buffer, filename=filename),
                ephemeral=True
            )

        except Exception as e:
            import traceback
            print(f"Export error: {traceback.format_exc()}")
            await interaction.followup.send(f"❌ Export failed: {str(e)}", ephemeral=True)

    async def _create_web_export(self, interaction: discord.Interaction,
                                include_logs: bool, include_news: bool) -> io.BytesIO:
        """Create an interactive web-based wiki export"""
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            await interaction.edit_original_response(content="⏳ Generating interactive wiki... (1/6)")
            data = await self._gather_all_data(include_logs, include_news)

            await interaction.edit_original_response(content="⏳ Creating HTML structure... (2/6)")
            html_content = self._generate_main_html(data)
            zip_file.writestr("index.html", html_content)

            await interaction.edit_original_response(content="⏳ Styling interface... (3/6)")
            css_content = self._generate_css()
            zip_file.writestr("assets/css/style.css", css_content)

            await interaction.edit_original_response(content="⏳ Adding interactivity... (4/6)")
            js_content = self._generate_javascript(data)
            zip_file.writestr("assets/js/wiki.js", js_content)

            await interaction.edit_original_response(content="⏳ Compiling data... (5/6)")
            json_data = json.dumps(data, indent=2, default=str)
            zip_file.writestr("assets/data/galaxy_data.json", json_data)

            await interaction.edit_original_response(content="⏳ Generating maps... (6/6)")
            await self._add_maps_to_zip(zip_file)

            self._add_web_assets(zip_file)

        zip_buffer.seek(0)
        return zip_buffer

    async def _gather_all_data(self, include_logs: bool, include_news: bool) -> Dict:
        """Gather all galaxy data into a structured dictionary"""
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)

        galaxy_info_tuple = self.db.execute_query("SELECT name, start_date, time_scale_factor, is_time_paused FROM galaxy_info WHERE galaxy_id = 1", fetch='one')
        if not galaxy_info_tuple:
            raise Exception("No galaxy data found!")

        galaxy_name, start_date, time_scale, is_paused = galaxy_info_tuple
        current_time = time_system.format_ingame_datetime(time_system.calculate_current_ingame_time())

        locations = self._fetch_locations()
        corridors = self._fetch_corridors()
        npcs = self._fetch_npcs()
        sub_locations = self._fetch_sub_locations()
        logs = self._fetch_logs() if include_logs else []
        news = self._fetch_recent_news() if include_news else []
        stats = self._calculate_statistics(locations, corridors, npcs)

        return {
            "galaxy": {
                "name": galaxy_name,
                "start_date": start_date,
                "current_time": current_time,
                "time_scale": time_scale,
                "is_paused": bool(is_paused)
            },
            "locations": locations,
            "corridors": corridors,
            "npcs": npcs,
            "sub_locations": sub_locations,
            "logs": logs,
            "news": news,
            "statistics": stats,
            "export_date": datetime.now().isoformat()
        }

    def _fetch_locations(self) -> List[Dict]:
        """Fetch all locations with complete information"""
        # CORRECTED: Removed non-existent 'danger_level' column. Danger level is on corridors and jobs, not locations.
        # CORRECTED: The gate_status column is TEXT, not BOOLEAN, so it's handled as such.
        locations = self.db.execute_query("""
            SELECT
                location_id, name, location_type, description, wealth_level,
                population, x_coordinate, y_coordinate, system_name, established_date,
                has_jobs, has_shops, has_medical, has_repairs, has_fuel,
                has_upgrades, has_black_market, is_derelict, gate_status, faction
            FROM locations
            ORDER BY location_type, name
        """, fetch='all')

        location_list = []
        for loc in locations:
            location_dict = {
                "id": loc[0],
                "name": loc[1],
                "type": loc[2],
                "description": loc[3],
                "wealth_level": loc[4],
                "population": loc[5],
                "coordinates": {"x": loc[6], "y": loc[7]},
                "system": loc[8],
                "established": loc[9],
                "services": {
                    "jobs": bool(loc[10]),
                    "shops": bool(loc[11]),
                    "medical": bool(loc[12]),
                    "repairs": bool(loc[13]),
                    "fuel": bool(loc[14]),
                    "upgrades": bool(loc[15]),
                    "black_market": bool(loc[16])
                },
                "is_derelict": bool(loc[17]),
                "gate_status": loc[18],
                "faction": loc[19],
                "danger_level": 0 # Default value to prevent JS errors, as this field is not in the locations table.
            }

            # CORRECTED: The sub_locations query used non-existent columns (entry_fee, is_hidden)
            # and the wrong foreign key (location_id instead of parent_location_id).
            sub_locs = self.db.execute_query("""
                SELECT name, sub_type, description, is_active
                FROM sub_locations
                WHERE parent_location_id = ?
            """, (loc[0],), fetch='all')

            location_dict["sub_locations"] = [
                {
                    "name": sl[0],
                    "type": sl[1],
                    "description": sl[2],
                    "is_active": bool(sl[3])
                }
                for sl in sub_locs
            ]

            location_list.append(location_dict)

        return location_list

    def _fetch_corridors(self) -> List[Dict]:
        """Fetch all corridors with complete information"""
        # CORRECTED: Renamed origin_id/destination_id to origin_location/destination_location to match the schema.
        # CORRECTED: Removed non-existent columns 'has_gate' and 'min_ship_class'.
        corridors = self.db.execute_query("""
            SELECT
                c.corridor_id, c.name, c.origin_location, c.destination_location,
                c.travel_time, c.fuel_cost, c.danger_level, c.is_active,
                l1.name as origin_name, l2.name as destination_name
            FROM corridors c
            JOIN locations l1 ON c.origin_location = l1.location_id
            JOIN locations l2 ON c.destination_location = l2.location_id
            ORDER BY c.name
        """, fetch='all')

        return [
            {
                "id": c[0],
                "name": c[1],
                "origin": {"id": c[2], "name": c[8]},
                "destination": {"id": c[3], "name": c[9]},
                "travel_time": c[4],
                "fuel_cost": c[5],
                "danger_level": c[6],
                "is_active": bool(c[7]),
                "has_gate": False, # Default value, not in schema
                "min_ship_class": None # Default value, not in schema
            }
            for c in corridors
        ]

    def _fetch_npcs(self) -> Dict:
        """Fetch all NPCs organized by type"""
        # Static NPCs
        # CORRECTED: Removed non-existent columns 'backstory' and 'dialogue_style'.
        static_npcs = self.db.execute_query("""
            SELECT
                s.npc_id, s.location_id, s.name, s.age, s.occupation,
                s.personality, s.trade_specialty,
                l.name as location_name
            FROM static_npcs s
            JOIN locations l ON s.location_id = l.location_id
            ORDER BY l.name, s.name
        """, fetch='all')

        # Dynamic NPCs
        # CORRECTED: Removed non-existent columns 'personality', 'trading_preference', 'faction_alignment', and 'wanted_level'.
        # The 'alignment' column is fetched instead.
        dynamic_npcs = self.db.execute_query("""
            SELECT
                d.npc_id, d.name, d.callsign, d.age, d.ship_name, d.ship_type,
                d.current_location, d.alignment,
                l.name as location_name
            FROM dynamic_npcs d
            LEFT JOIN locations l ON d.current_location = l.location_id
            ORDER BY d.callsign
        """, fetch='all')

        return {
            "static": [
                {
                    "id": s[0],
                    "location": {"id": s[1], "name": s[7]},
                    "name": s[2],
                    "age": s[3],
                    "occupation": s[4],
                    "personality": s[5],
                    "backstory": "No data available.", # Default value
                    "trade_specialty": s[6],
                    "dialogue_style": "normal" # Default value
                }
                for s in static_npcs
            ],
            "dynamic": [
                {
                    "id": d[0],
                    "name": d[1],
                    "callsign": d[2],
                    "age": d[3],
                    "ship": {"name": d[4], "type": d[5]},
                    "current_location": {"id": d[6], "name": d[8]} if d[6] else None,
                    "personality": "No data available.", # Default value
                    "trading_preference": "any", # Default value
                    "faction": d[7], # Using the 'alignment' field
                    "wanted_level": 0 # Default value
                }
                for d in dynamic_npcs
            ]
        }

    def _fetch_sub_locations(self) -> List[Dict]:
        """Fetch all sub-locations"""
        # CORRECTED: Query uses the correct foreign key 'parent_location_id'.
        # CORRECTED: Query selects existing columns, removing non-existent ones like 'entry_fee', 'is_hidden', 'required_reputation'.
        sub_locations = self.db.execute_query("""
            SELECT
                s.sub_location_id, s.parent_location_id, s.name, s.description,
                s.sub_type, s.is_active,
                l.name as parent_location
            FROM sub_locations s
            JOIN locations l ON s.parent_location_id = l.location_id
            ORDER BY l.name, s.name
        """, fetch='all')

        return [
            {
                "id": s[0],
                "parent_location": {"id": s[1], "name": s[6]},
                "name": s[2],
                "description": s[3],
                "type": s[4],
                "is_active": bool(s[5]),
                "entry_fee": 0, # Default value
                "is_hidden": not bool(s[5]), # Infer from is_active for now
                "required_reputation": 0 # Default value
            }
            for s in sub_locations
        ]

    def _fetch_logs(self) -> List[Dict]:
        """Fetch location logs"""
        # This query was already correct and required no changes.
        logs = self.db.execute_query("""
            SELECT
                l.log_id, l.location_id, l.author_name, l.message,
                l.posted_at, l.is_generated,
                loc.name as location_name
            FROM location_logs l
            JOIN locations loc ON l.location_id = loc.location_id
            ORDER BY l.posted_at DESC
            LIMIT 500
        """, fetch='all')

        return [
            {
                "id": l[0],
                "location": {"id": l[1], "name": l[6]},
                "author": l[2],
                "message": l[3],
                "posted_at": l[4],
                "is_generated": bool(l[5])
            }
            for l in logs
        ]

    def _fetch_recent_news(self) -> List[Dict]:
        """Fetch recent news broadcasts"""
        # CORRECTED: Table name is 'news_queue', not 'news_archive'.
        # CORRECTED: Column is 'scheduled_delivery', not 'actual_delivery'.
        # CORRECTED: Added 'WHERE is_delivered = 1' to get only sent news.
        news = self.db.execute_query("""
            SELECT
                news_id, news_type, title, description, location_id,
                scheduled_delivery, delay_hours, event_data
            FROM news_queue
            WHERE is_delivered = true
            ORDER BY scheduled_delivery DESC
            LIMIT 100
        """, fetch='all')

        news_list = []
        for n in news:
            news_dict = {
                "id": n[0],
                "type": n[1],
                "title": n[2],
                "description": n[3],
                "location_id": n[4],
                "delivered_at": n[5], # Mapped from scheduled_delivery
                "delay_hours": n[6]
            }

            if n[7]:
                try:
                    news_dict["event_data"] = json.loads(n[7])
                except:
                    news_dict["event_data"] = None

            news_list.append(news_dict)

        return news_list

    def _calculate_statistics(self, locations: List[Dict], corridors: List[Dict],
                            npcs: Dict) -> Dict:
        """Calculate galaxy statistics"""
        location_types = {}
        total_population = 0
        wealth_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for loc in locations:
            loc_type = loc["type"]
            location_types[loc_type] = location_types.get(loc_type, 0) + 1
            if loc["population"]:
                total_population += loc["population"]
            if loc["wealth_level"] in wealth_distribution:
                wealth_distribution[loc["wealth_level"]] += 1

        active_corridors = sum(1 for c in corridors if c["is_active"])
        gated_corridors = sum(1 for c in corridors if c.get("has_gate", False))
        total_static_npcs = len(npcs["static"])
        total_dynamic_npcs = len(npcs["dynamic"])

        return {
            "locations": {
                "total": len(locations),
                "by_type": location_types,
                "total_population": total_population,
                "wealth_distribution": wealth_distribution
            },
            "corridors": {
                "total": len(corridors),
                "active": active_corridors,
                "dormant": len(corridors) - active_corridors,
                "gated": gated_corridors
            },
            "npcs": {
                "static": total_static_npcs,
                "dynamic": total_dynamic_npcs,
                "total": total_static_npcs + total_dynamic_npcs
            }
        }
    
    # ... The rest of the file (_generate_main_html, _generate_css, etc.) remains unchanged ...
    # NOTE: Since some data fields were removed from the backend queries (e.g., npc.backstory),
    # the Javascript functions might still try to access them. I have added default values
    # to the dictionaries to prevent the export from failing, but the generated web wiki
    # will show "No data available" or similar placeholders in those fields.
    
    def _generate_main_html(self, data: Dict) -> str:
        """Generate the main HTML file for the wiki"""
        galaxy_name = data["galaxy"]["name"]
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{galaxy_name} - Galactic Encyclopedia</title>
    <link rel="stylesheet" href="assets/css/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono:wght@400&family=Tektur:wght@400;500;700;900&display=swap" rel="stylesheet">
</head>
<body>
    <div class="scanlines"></div>
    <div class="static-overlay"></div>
    
    <header id="main-header">
        <div class="header-content">
            <div class="terminal-indicator">
                <div class="power-light"></div>
                <span class="terminal-id">WIKI-7742</span>
            </div>
            <h1>{galaxy_name}</h1>
            <div class="subtitle">GALACTIC ENCYCLOPEDIA</div>
        </div>
        <nav class="main-nav">
            <button class="nav-btn active" data-section="overview">Overview</button>
            <button class="nav-btn" data-section="locations">Locations</button>
            <button class="nav-btn" data-section="corridors">Corridors</button>
            <button class="nav-btn" data-section="inhabitants">Inhabitants</button>
            <button class="nav-btn" data-section="logs">Logs & History</button>
            <button class="nav-btn" data-section="news">News Archive</button>
            <button class="nav-btn" data-section="search">Search</button>
        </nav>
    </header>

    <main id="content-area">
        <section id="overview" class="content-section active">
            <h2>Galaxy Overview</h2>
            <div class="info-grid">
                <div class="info-card">
                    <h3>Basic Information</h3>
                    <div class="info-item">
                        <span class="label">Galaxy Name:</span>
                        <span class="value">{data["galaxy"]["name"]}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Genesis Date:</span>
                        <span class="value">{data["galaxy"]["start_date"]}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Current Time:</span>
                        <span class="value">{data["galaxy"]["current_time"]}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Time Scale:</span>
                        <span class="value">{data["galaxy"]["time_scale"]}x</span>
                    </div>
                </div>
                
                <div class="info-card">
                    <h3>Statistics</h3>
                    <div class="info-item">
                        <span class="label">Total Locations:</span>
                        <span class="value">{data["statistics"]["locations"]["total"]}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Active Corridors:</span>
                        <span class="value">{data["statistics"]["corridors"]["active"]}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Total Population:</span>
                        <span class="value">{data["statistics"]["locations"]["total_population"]:,}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Total NPCs:</span>
                        <span class="value">{data["statistics"]["npcs"]["total"]}</span>
                    </div>
                </div>
            </div>
            
            <div class="map-container">
                <h3>Galaxy Map</h3>
                <img src="assets/maps/galaxy_standard.png" alt="Galaxy Map" class="galaxy-map" id="overview-map">
                <div class="map-controls">
                    <button class="map-btn" data-map="standard">Standard</button>
                    <button class="map-btn" data-map="wealth">Wealth</button>
                    <button class="map-btn" data-map="danger">Danger</button>
                    <button class="map-btn" data-map="infrastructure">Infrastructure</button>
                    <button class="map-btn" data-map="connections">Connections</button>
                </div>
            </div>
        </section>

        <section id="locations" class="content-section">
            <h2>Locations</h2>
            <div class="filter-bar">
                <select id="location-type-filter" class="filter-select">
                    <option value="all">All Types</option>
                    <option value="space_station">Space Stations</option>
                    <option value="colony">Colonies</option>
                    <option value="outpost">Outposts</option>
                    <option value="gate">Gates</option>
                </select>
                <select id="wealth-filter" class="filter-select">
                    <option value="all">All Wealth Levels</option>
                    <option value="1">Poor (1)</option>
                    <option value="2">Modest (2)</option>
                    <option value="3">Average (3)</option>
                    <option value="4">Wealthy (4)</option>
                    <option value="5">Rich (5)</option>
                </select>
                <input type="text" id="location-search" class="search-input" placeholder="Search locations...">
            </div>
            <div id="locations-grid" class="locations-grid">
                </div>
        </section>

        <section id="corridors" class="content-section">
            <h2>Travel Corridors</h2>
            <div class="filter-bar">
                <select id="corridor-status-filter" class="filter-select">
                    <option value="all">All Corridors</option>
                    <option value="active">Active Only</option>
                    <option value="dormant">Dormant Only</option>
                    <option value="gated">Gated Only</option>
                </select>
                <input type="text" id="corridor-search" class="search-input" placeholder="Search corridors...">
            </div>
            <div id="corridors-list" class="corridors-list">
                </div>
        </section>

        <section id="inhabitants" class="content-section">
            <h2>Known Inhabitants</h2>
            <div class="tab-bar">
                <button class="tab-btn active" data-tab="static">Static NPCs</button>
                <button class="tab-btn" data-tab="dynamic">Dynamic NPCs</button>
            </div>
            <div id="npcs-container">
                <div id="static-npcs" class="npc-grid active">
                    </div>
                <div id="dynamic-npcs" class="npc-grid">
                    </div>
            </div>
        </section>

        <section id="logs" class="content-section">
            <h2>Location Logs & Guestbooks</h2>
            <div id="logs-container" class="logs-container">
                </div>
        </section>

        <section id="news" class="content-section">
            <h2>Galactic News Archive</h2>
            <div id="news-container" class="news-container">
                </div>
        </section>

        <section id="search" class="content-section">
            <h2>Universal Search</h2>
            <div class="search-container">
                <input type="text" id="universal-search" class="search-input large" placeholder="Search everything...">
                <button id="search-btn" class="search-button">Search</button>
            </div>
            <div id="search-results" class="search-results">
                </div>
        </section>
    </main>

    <div id="detail-modal" class="modal">
        <div class="modal-content">
            <span class="close-modal">&times;</span>
            <div id="modal-body">
                </div>
        </div>
    </div>

    <script src="assets/js/wiki.js"></script>
    <script>
        // Initialize with data
        window.galaxyData = {json.dumps(data, default=str)};
    </script>
</body>
</html>'''

    def _generate_css(self) -> str:
        """Generate CSS for the wiki"""
        return '''/* Galaxy Wiki CSS - Based on Web Map Terminal Style */
:root {
    --primary-color: #00ffff;
    --secondary-color: #00cccc;
    --accent-color: #0088cc;
    --warning-color: #ff8800;
    --success-color: #00ff88;
    --error-color: #ff3333;
    
    --primary-bg: #000814;
    --secondary-bg: #001d3d;
    --card-bg: rgba(0, 29, 61, 0.8);
    --border-color: rgba(0, 255, 255, 0.3);
    
    --text-primary: #ffffff;
    --text-secondary: #b0b0b0;
    --text-muted: #666666;
    
    --shadow-glow: 0 0 20px rgba(0, 255, 255, 0.5);
    --shadow-dark: 0 4px 10px rgba(0, 0, 0, 0.8);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Share Tech Mono', monospace;
    background-color: var(--primary-bg);
    color: var(--text-primary);
    overflow-x: hidden;
    min-height: 100vh;
}

/* Scanlines Effect */
.scanlines {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: repeating-linear-gradient(
        0deg,
        rgba(0, 255, 255, 0.03) 0px,
        transparent 1px,
        transparent 2px,
        rgba(0, 255, 255, 0.03) 3px
    );
    pointer-events: none;
    z-index: 1000;
    animation: scanlines 8s linear infinite;
}

@keyframes scanlines {
    0% { background-position: 0 0; }
    100% { background-position: 0 10px; }
}

/* Static Overlay */
.static-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: url('data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><filter id="noiseFilter"><feTurbulence type="turbulence" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch"/></filter><rect width="100%" height="100%" filter="url(%23noiseFilter)" opacity="0.02"/></svg>');
    pointer-events: none;
    z-index: 999;
    mix-blend-mode: overlay;
}

/* Header */
#main-header {
    background: linear-gradient(145deg, rgba(0, 29, 61, 0.95), rgba(0, 8, 20, 0.95));
    border-bottom: 2px solid var(--primary-color);
    padding: 1rem 2rem;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: var(--shadow-glow), var(--shadow-dark);
}

.header-content {
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-bottom: 1rem;
}

.terminal-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.power-light {
    width: 12px;
    height: 12px;
    background: var(--success-color);
    border-radius: 50%;
    box-shadow: 0 0 10px var(--success-color);
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.terminal-id {
    font-size: 0.8rem;
    color: var(--text-secondary);
    text-transform: uppercase;
}

h1 {
    font-family: 'Tektur', sans-serif;
    font-size: 2rem;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    background: linear-gradient(45deg, var(--primary-color), var(--accent-color));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 30px var(--primary-color);
}

.subtitle {
    font-size: 0.9rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3em;
}

/* Navigation */
.main-nav {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}

.nav-btn, .tab-btn {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    padding: 0.5rem 1rem;
    font-family: inherit;
    font-size: 0.9rem;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.nav-btn:hover, .tab-btn:hover {
    background: var(--secondary-bg);
    border-color: var(--primary-color);
    box-shadow: 0 0 15px var(--primary-color);
    transform: translateY(-2px);
}

.nav-btn.active, .tab-btn.active {
    background: linear-gradient(145deg, var(--primary-color), var(--secondary-color));
    color: var(--primary-bg);
    border-color: var(--primary-color);
    box-shadow: 0 0 20px var(--primary-color);
}

/* Content Sections */
.content-section {
    display: none;
    padding: 2rem;
    animation: fadeIn 0.5s ease;
}

.content-section.active {
    display: block;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

h2 {
    font-family: 'Tektur', sans-serif;
    font-size: 1.8rem;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
    color: var(--primary-color);
    text-shadow: 0 0 20px var(--primary-color);
}

h3 {
    font-family: 'Tektur', sans-serif;
    font-size: 1.3rem;
    text-transform: uppercase;
    margin-bottom: 1rem;
    color: var(--secondary-color);
}

/* Info Grid */
.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.info-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: var(--shadow-dark);
}

.info-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.info-item:last-child {
    border-bottom: none;
}

.label {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.value {
    color: var(--primary-color);
    font-weight: bold;
}

/* Map Container */
.map-container {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 2rem;
}

.galaxy-map {
    width: 100%;
    height: auto;
    border: 2px solid var(--border-color);
    border-radius: 4px;
    margin-bottom: 1rem;
}

.map-controls {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    flex-wrap: wrap;
}

.map-btn {
    background: var(--secondary-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    padding: 0.4rem 0.8rem;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.map-btn:hover {
    background: var(--primary-color);
    color: var(--primary-bg);
}

/* Filter Bar */
.filter-bar {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}

.filter-select, .search-input {
    background: var(--secondary-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    padding: 0.5rem 1rem;
    font-family: inherit;
    font-size: 0.9rem;
    border-radius: 4px;
}

.search-input {
    flex: 1;
    min-width: 200px;
}

.search-input.large {
    font-size: 1.1rem;
    padding: 0.75rem 1.5rem;
}

/* Locations Grid */
.locations-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1rem;
}

.location-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.location-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 0 20px var(--primary-color);
    border-color: var(--primary-color);
}

.location-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.location-name {
    font-size: 1.1rem;
    color: var(--primary-color);
    font-weight: bold;
}

.location-type {
    font-size: 0.8rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    background: rgba(0, 255, 255, 0.1);
    border: 1px solid var(--border-color);
    border-radius: 4px;
}

.location-details {
    font-size: 0.9rem;
    color: var(--text-secondary);
    line-height: 1.5;
}

.services-list {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
    flex-wrap: wrap;
}

.service-tag {
    font-size: 0.7rem;
    padding: 0.2rem 0.4rem;
    background: rgba(0, 255, 136, 0.2);
    border: 1px solid var(--success-color);
    border-radius: 3px;
    color: var(--success-color);
}

/* Corridors List */
.corridors-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.corridor-item {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    transition: all 0.3s ease;
}

.corridor-item:hover {
    background: var(--secondary-bg);
    border-color: var(--primary-color);
    box-shadow: 0 0 15px var(--primary-color);
}

.corridor-info {
    flex: 1;
}

.corridor-name {
    font-size: 1rem;
    color: var(--primary-color);
    margin-bottom: 0.25rem;
}

.corridor-route {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.corridor-stats {
    display: flex;
    gap: 1rem;
    align-items: center;
    font-size: 0.85rem;
}

.corridor-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.stat-label {
    font-size: 0.7rem;
    color: var(--text-muted);
}

.stat-value {
    color: var(--primary-color);
    font-weight: bold;
}

.status-badge {
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font-size: 0.8rem;
    text-transform: uppercase;
}

.status-active {
    background: rgba(0, 255, 136, 0.2);
    border: 1px solid var(--success-color);
    color: var(--success-color);
}

.status-dormant {
    background: rgba(255, 136, 0, 0.2);
    border: 1px solid var(--warning-color);
    color: var(--warning-color);
}

/* NPC Grid */
.npc-grid {
    display: none;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
}

.npc-grid.active {
    display: grid;
}

.npc-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.npc-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 0 15px var(--primary-color);
    border-color: var(--primary-color);
}

.npc-name {
    font-size: 1.1rem;
    color: var(--primary-color);
    margin-bottom: 0.5rem;
}

.npc-details {
    font-size: 0.85rem;
    color: var(--text-secondary);
    line-height: 1.4;
}

.npc-location {
    margin-top: 0.5rem;
    font-size: 0.8rem;
    color: var(--accent-color);
}

/* Logs Container */
.logs-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.log-entry {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 1rem;
}

.log-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.log-author {
    color: var(--primary-color);
    font-weight: bold;
}

.log-location {
    color: var(--accent-color);
}

.log-date {
    color: var(--text-muted);
    font-size: 0.8rem;
}

.log-message {
    color: var(--text-secondary);
    line-height: 1.5;
    font-style: italic;
}

/* News Container */
.news-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.news-item {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.news-item:hover {
    border-color: var(--primary-color);
    box-shadow: 0 0 15px var(--primary-color);
}

.news-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}

.news-title {
    font-size: 1.2rem;
    color: var(--primary-color);
}

.news-type {
    font-size: 0.8rem;
    padding: 0.3rem 0.6rem;
    background: rgba(0, 136, 204, 0.2);
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    color: var(--accent-color);
    text-transform: uppercase;
}

.news-body {
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: 0.5rem;
}

.news-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    color: var(--text-muted);
}

/* Search */
.search-container {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
}

.search-button {
    background: linear-gradient(145deg, var(--primary-color), var(--secondary-color));
    border: none;
    color: var(--primary-bg);
    padding: 0.75rem 2rem;
    font-family: inherit;
    font-size: 1rem;
    font-weight: bold;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.3s ease;
}

.search-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 20px var(--primary-color);
}

.search-results {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.search-result {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.search-result:hover {
    border-color: var(--primary-color);
    box-shadow: 0 0 15px var(--primary-color);
}

.result-type {
    font-size: 0.8rem;
    color: var(--accent-color);
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}

.result-title {
    font-size: 1.1rem;
    color: var(--primary-color);
    margin-bottom: 0.5rem;
}

.result-snippet {
    font-size: 0.9rem;
    color: var(--text-secondary);
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(5px);
}

.modal-content {
    background: var(--secondary-bg);
    margin: 5% auto;
    padding: 2rem;
    border: 2px solid var(--primary-color);
    border-radius: 8px;
    width: 90%;
    max-width: 800px;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 0 50px var(--primary-color);
    position: relative;
}

.close-modal {
    position: absolute;
    top: 1rem;
    right: 1rem;
    font-size: 2rem;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.3s ease;
}

.close-modal:hover {
    color: var(--primary-color);
    text-shadow: 0 0 10px var(--primary-color);
}

/* Responsive */
@media (max-width: 768px) {
    #main-header {
        padding: 1rem;
    }

    h1 {
        font-size: 1.5rem;
    }

    .main-nav {
        gap: 0.5rem;
    }

    .nav-btn {
        font-size: 0.8rem;
        padding: 0.4rem 0.8rem;
    }

    .content-section {
        padding: 1rem;
    }

    .info-grid {
        grid-template-columns: 1fr;
    }

    .filter-bar {
        flex-direction: column;
    }

    .locations-grid {
        grid-template-columns: 1fr;
    }

    .corridor-item {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }

    .corridor-stats {
        width: 100%;
        justify-content: space-between;
    }
}

/* Loading Animation */
.loading {
    display: inline-block;
    position: relative;
    width: 80px;
    height: 80px;
}

.loading:after {
    content: " ";
    display: block;
    border-radius: 50%;
    width: 0;
    height: 0;
    margin: 8px;
    box-sizing: border-box;
    border: 32px solid var(--primary-color);
    border-color: var(--primary-color) transparent var(--primary-color) transparent;
    animation: loading 1.2s infinite;
}

@keyframes loading {
    0% {
        transform: rotate(0);
        animation-timing-function: cubic-bezier(0.55, 0.055, 0.675, 0.19);
    }
    50% {
        transform: rotate(900deg);
        animation-timing-function: cubic-bezier(0.215, 0.61, 0.355, 1);
    }
    100% {
        transform: rotate(1800deg);
    }
}'''

    def _generate_javascript(self, data: Dict) -> str:
        """Generate JavaScript for the wiki"""
        return '''// Galaxy Wiki JavaScript
class GalaxyWiki {
    constructor(data) {
        this.data = data;
        this.currentSection = 'overview';
        this.init();
    }

    init() {
        // Navigation
        this.setupNavigation();
        
        // Map controls
        this.setupMapControls();
        
        // Filters and search
        this.setupFilters();
        
        // Modal
        this.setupModal();
        
        // Populate initial content
        this.populateContent();
    }

    setupNavigation() {
        const navButtons = document.querySelectorAll('.nav-btn');
        navButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.target.dataset.section;
                this.switchSection(section);
            });
        });

        // Tab navigation for NPCs
        const tabButtons = document.querySelectorAll('.tab-btn');
        tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.target.dataset.tab;
                this.switchNPCTab(tab);
            });
        });
    }

    switchSection(section) {
        // Update navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.section === section);
        });

        // Update content
        document.querySelectorAll('.content-section').forEach(sec => {
            sec.classList.toggle('active', sec.id === section);
        });

        this.currentSection = section;

        // Populate section-specific content if needed
        if (section === 'locations' && !this.locationsPopulated) {
            this.populateLocations();
            this.locationsPopulated = true;
        } else if (section === 'corridors' && !this.corridorsPopulated) {
            this.populateCorridors();
            this.corridorsPopulated = true;
        } else if (section === 'inhabitants' && !this.npcsPopulated) {
            this.populateNPCs();
            this.npcsPopulated = true;
        } else if (section === 'logs' && !this.logsPopulated) {
            this.populateLogs();
            this.logsPopulated = true;
        } else if (section === 'news' && !this.newsPopulated) {
            this.populateNews();
            this.newsPopulated = true;
        }
    }

    switchNPCTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });

        document.getElementById('static-npcs').classList.toggle('active', tab === 'static');
        document.getElementById('dynamic-npcs').classList.toggle('active', tab === 'dynamic');
    }

    setupMapControls() {
        const mapButtons = document.querySelectorAll('.map-btn');
        mapButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mapType = e.target.dataset.map;
                const mapImg = document.getElementById('overview-map');
                mapImg.src = `assets/maps/galaxy_${mapType}.png`;
            });
        });
    }

    setupFilters() {
        // Location filters
        const locationTypeFilter = document.getElementById('location-type-filter');
        const wealthFilter = document.getElementById('wealth-filter');
        const locationSearch = document.getElementById('location-search');

        if (locationTypeFilter) {
            locationTypeFilter.addEventListener('change', () => this.filterLocations());
            wealthFilter.addEventListener('change', () => this.filterLocations());
            locationSearch.addEventListener('input', () => this.filterLocations());
        }

        // Corridor filters
        const corridorStatusFilter = document.getElementById('corridor-status-filter');
        const corridorSearch = document.getElementById('corridor-search');

        if (corridorStatusFilter) {
            corridorStatusFilter.addEventListener('change', () => this.filterCorridors());
            corridorSearch.addEventListener('input', () => this.filterCorridors());
        }

        // Universal search
        const universalSearch = document.getElementById('universal-search');
        const searchBtn = document.getElementById('search-btn');

        if (universalSearch) {
            searchBtn.addEventListener('click', () => this.performUniversalSearch());
            universalSearch.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.performUniversalSearch();
            });
        }
    }

    setupModal() {
        const modal = document.getElementById('detail-modal');
        const closeBtn = document.querySelector('.close-modal');

        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    populateContent() {
        // Statistics are already in the HTML
        // Just populate the sections as they're accessed
    }

    populateLocations() {
        const grid = document.getElementById('locations-grid');
        grid.innerHTML = '';

        this.data.locations.forEach(location => {
            const card = this.createLocationCard(location);
            grid.appendChild(card);
        });
    }

    createLocationCard(location) {
        const card = document.createElement('div');
        card.className = 'location-card';
        card.dataset.type = location.type;
        card.dataset.wealth = location.wealth_level;
        card.dataset.name = location.name.toLowerCase();

        const services = [];
        if (location.services.jobs) services.push('Jobs');
        if (location.services.shops) services.push('Shop');
        if (location.services.medical) services.push('Medical');
        if (location.services.repairs) services.push('Repairs');
        if (location.services.fuel) services.push('Fuel');
        if (location.services.upgrades) services.push('Upgrades');
        if (location.services.black_market) services.push('Black Market');

        card.innerHTML = `
            <div class="location-header">
                <div class="location-name">${location.name}</div>
                <div class="location-type">${location.type.replace(/_/g, ' ')}</div>
            </div>
            <div class="location-details">
                <div>System: ${location.system}</div>
                <div>Population: ${location.population ? location.population.toLocaleString() : 'Unknown'}</div>
                <div>Wealth Level: ${'⭐'.repeat(location.wealth_level || 0)}</div>
                ${location.docking_fee ? `<div>Docking Fee: ${location.docking_fee} credits</div>` : ''}
            </div>
            ${services.length > 0 ? `
                <div class="services-list">
                    ${services.map(s => `<span class="service-tag">${s}</span>`).join('')}
                </div>
            ` : ''}
        `;

        card.addEventListener('click', () => this.showLocationDetails(location));
        return card;
    }

    populateCorridors() {
        const list = document.getElementById('corridors-list');
        list.innerHTML = '';

        this.data.corridors.forEach(corridor => {
            const item = this.createCorridorItem(corridor);
            list.appendChild(item);
        });
    }

    createCorridorItem(corridor) {
        const item = document.createElement('div');
        item.className = 'corridor-item';
        item.dataset.status = corridor.is_active ? 'active' : 'dormant';
        item.dataset.gated = corridor.has_gate ? 'true' : 'false';
        item.dataset.name = corridor.name.toLowerCase();

        item.innerHTML = `
            <div class="corridor-info">
                <div class="corridor-name">${corridor.name}</div>
                <div class="corridor-route">${corridor.origin.name} → ${corridor.destination.name}</div>
            </div>
            <div class="corridor-stats">
                <div class="corridor-stat">
                    <span class="stat-label">Travel Time</span>
                    <span class="stat-value">${corridor.travel_time} min</span>
                </div>
                <div class="corridor-stat">
                    <span class="stat-label">Fuel Cost</span>
                    <span class="stat-value">${corridor.fuel_cost}</span>
                </div>
                <div class="corridor-stat">
                    <span class="stat-label">Danger</span>
                    <span class="stat-value">${corridor.danger_level}/5</span>
                </div>
                <span class="status-badge status-${corridor.is_active ? 'active' : 'dormant'}">
                    ${corridor.is_active ? 'Active' : 'Dormant'}
                </span>
            </div>
        `;

        item.addEventListener('click', () => this.showCorridorDetails(corridor));
        return item;
    }

    populateNPCs() {
        // Static NPCs
        const staticGrid = document.getElementById('static-npcs');
        staticGrid.innerHTML = '';

        this.data.npcs.static.forEach(npc => {
            const card = this.createStaticNPCCard(npc);
            staticGrid.appendChild(card);
        });

        // Dynamic NPCs
        const dynamicGrid = document.getElementById('dynamic-npcs');
        dynamicGrid.innerHTML = '';

        this.data.npcs.dynamic.forEach(npc => {
            const card = this.createDynamicNPCCard(npc);
            dynamicGrid.appendChild(card);
        });
    }

    createStaticNPCCard(npc) {
        const card = document.createElement('div');
        card.className = 'npc-card';

        card.innerHTML = `
            <div class="npc-name">${npc.name}</div>
            <div class="npc-details">
                <div>Age: ${npc.age}</div>
                <div>Occupation: ${npc.occupation}</div>
                <div>Personality: ${npc.personality}</div>
                ${npc.trade_specialty ? `<div>Specialty: ${npc.trade_specialty}</div>` : ''}
            </div>
            <div class="npc-location">📍 ${npc.location.name}</div>
        `;

        card.addEventListener('click', () => this.showNPCDetails(npc, 'static'));
        return card;
    }

    createDynamicNPCCard(npc) {
        const card = document.createElement('div');
        card.className = 'npc-card';

        card.innerHTML = `
            <div class="npc-name">${npc.callsign}</div>
            <div class="npc-details">
                <div>Real Name: ${npc.name}</div>
                <div>Ship: ${npc.ship.name} (${npc.ship.type})</div>
                <div>Faction: ${npc.faction || 'Independent'}</div>
                ${npc.wanted_level ? `<div>Wanted Level: ${'⚠️'.repeat(npc.wanted_level)}</div>` : ''}
            </div>
            <div class="npc-location">📍 ${npc.current_location ? npc.current_location.name : 'In Transit'}</div>
        `;

        card.addEventListener('click', () => this.showNPCDetails(npc, 'dynamic'));
        return card;
    }

    populateLogs() {
        const container = document.getElementById('logs-container');
        container.innerHTML = '';

        if (this.data.logs.length === 0) {
            container.innerHTML = '<p>No logs available.</p>';
            return;
        }

        // Group logs by location
        const logsByLocation = {};
        this.data.logs.forEach(log => {
            const locName = log.location.name;
            if (!logsByLocation[locName]) {
                logsByLocation[locName] = [];
            }
            logsByLocation[locName].push(log);
        });

        Object.entries(logsByLocation).forEach(([location, logs]) => {
            const section = document.createElement('div');
            section.className = 'location-logs-section';
            section.innerHTML = `<h3>${location}</h3>`;

            logs.forEach(log => {
                const entry = this.createLogEntry(log);
                section.appendChild(entry);
            });

            container.appendChild(section);
        });
    }

    createLogEntry(log) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';

        const date = new Date(log.posted_at).toLocaleDateString();

        entry.innerHTML = `
            <div class="log-header">
                <span class="log-author">${log.author}</span>
                <span class="log-date">${date}</span>
            </div>
            <div class="log-message">"${log.message}"</div>
        `;

        return entry;
    }

    populateNews() {
        const container = document.getElementById('news-container');
        container.innerHTML = '';

        if (this.data.news.length === 0) {
            container.innerHTML = '<p>No news available.</p>';
            return;
        }

        this.data.news.forEach(news => {
            const item = this.createNewsItem(news);
            container.appendChild(item);
        });
    }

    createNewsItem(news) {
        const item = document.createElement('div');
        item.className = 'news-item';

        const date = new Date(news.delivered_at).toLocaleDateString();

        item.innerHTML = `
            <div class="news-header">
                <div class="news-title">${news.title}</div>
                <span class="news-type">${news.type.replace(/_/g, ' ')}</span>
            </div>
            <div class="news-body">${news.description}</div>
            <div class="news-footer">
                <span>Delivered: ${date}</span>
                <span>Delay: ${news.delay_hours.toFixed(1)} hours</span>
            </div>
        `;

        item.addEventListener('click', () => this.showNewsDetails(news));
        return item;
    }

    filterLocations() {
        const typeFilter = document.getElementById('location-type-filter').value;
        const wealthFilter = document.getElementById('wealth-filter').value;
        const searchTerm = document.getElementById('location-search').value.toLowerCase();

        const cards = document.querySelectorAll('.location-card');
        cards.forEach(card => {
            const matchesType = typeFilter === 'all' || card.dataset.type === typeFilter;
            const matchesWealth = wealthFilter === 'all' || card.dataset.wealth === wealthFilter;
            const matchesSearch = searchTerm === '' || card.dataset.name.includes(searchTerm);

            card.style.display = matchesType && matchesWealth && matchesSearch ? 'block' : 'none';
        });
    }

    filterCorridors() {
        const statusFilter = document.getElementById('corridor-status-filter').value;
        const searchTerm = document.getElementById('corridor-search').value.toLowerCase();

        const items = document.querySelectorAll('.corridor-item');
        items.forEach(item => {
            let matchesStatus = false;
            if (statusFilter === 'all') {
                matchesStatus = true;
            } else if (statusFilter === 'active') {
                matchesStatus = item.dataset.status === 'active';
            } else if (statusFilter === 'dormant') {
                matchesStatus = item.dataset.status === 'dormant';
            } else if (statusFilter === 'gated') {
                matchesStatus = item.dataset.gated === 'true';
            }

            const matchesSearch = searchTerm === '' || item.dataset.name.includes(searchTerm);

            item.style.display = matchesStatus && matchesSearch ? 'flex' : 'none';
        });
    }

    performUniversalSearch() {
        const searchTerm = document.getElementById('universal-search').value.toLowerCase();
        if (!searchTerm) return;

        const results = [];

        // Search locations
        this.data.locations.forEach(loc => {
            if (loc.name.toLowerCase().includes(searchTerm) ||
                loc.description.toLowerCase().includes(searchTerm) ||
                loc.system.toLowerCase().includes(searchTerm)) {
                results.push({
                    type: 'Location',
                    title: loc.name,
                    snippet: loc.description.substring(0, 150) + '...',
                    data: loc,
                    category: 'location'
                });
            }
        });

        // Search corridors
        this.data.corridors.forEach(corridor => {
            if (corridor.name.toLowerCase().includes(searchTerm)) {
                results.push({
                    type: 'Corridor',
                    title: corridor.name,
                    snippet: `${corridor.origin.name} → ${corridor.destination.name}`,
                    data: corridor,
                    category: 'corridor'
                });
            }
        });

        // Search NPCs
        this.data.npcs.static.forEach(npc => {
            if (npc.name.toLowerCase().includes(searchTerm) ||
                npc.occupation.toLowerCase().includes(searchTerm)) {
                results.push({
                    type: 'Static NPC',
                    title: npc.name,
                    snippet: `${npc.occupation} at ${npc.location.name}`,
                    data: npc,
                    category: 'static_npc'
                });
            }
        });

        this.data.npcs.dynamic.forEach(npc => {
            if (npc.name.toLowerCase().includes(searchTerm) ||
                npc.callsign.toLowerCase().includes(searchTerm) ||
                npc.ship.name.toLowerCase().includes(searchTerm)) {
                results.push({
                    type: 'Dynamic NPC',
                    title: npc.callsign,
                    snippet: `${npc.ship.type} pilot`,
                    data: npc,
                    category: 'dynamic_npc'
                });
            }
        });

        // Display results
        this.displaySearchResults(results);
    }

    displaySearchResults(results) {
        const container = document.getElementById('search-results');
        container.innerHTML = '';

        if (results.length === 0) {
            container.innerHTML = '<p>No results found.</p>';
            return;
        }

        results.forEach(result => {
            const item = document.createElement('div');
            item.className = 'search-result';

            item.innerHTML = `
                <div class="result-type">${result.type}</div>
                <div class="result-title">${result.title}</div>
                <div class="result-snippet">${result.snippet}</div>
            `;

            item.addEventListener('click', () => {
                switch (result.category) {
                    case 'location':
                        this.showLocationDetails(result.data);
                        break;
                    case 'corridor':
                        this.showCorridorDetails(result.data);
                        break;
                    case 'static_npc':
                        this.showNPCDetails(result.data, 'static');
                        break;
                    case 'dynamic_npc':
                        this.showNPCDetails(result.data, 'dynamic');
                        break;
                }
            });

            container.appendChild(item);
        });
    }

    showLocationDetails(location) {
        const modal = document.getElementById('detail-modal');
        const modalBody = document.getElementById('modal-body');

        const services = [];
        Object.entries(location.services).forEach(([service, available]) => {
            if (available) services.push(service.charAt(0).toUpperCase() + service.slice(1));
        });

        modalBody.innerHTML = `
            <h2>${location.name}</h2>
            <div class="detail-grid">
                <div class="detail-section">
                    <h3>Basic Information</h3>
                    <p><strong>Type:</strong> ${location.type.replace(/_/g, ' ')}</p>
                    <p><strong>System:</strong> ${location.system}</p>
                    <p><strong>Coordinates:</strong> ${location.coordinates.x}, ${location.coordinates.y}</p>
                    <p><strong>Established:</strong> ${location.established || 'Unknown'}</p>
                </div>
                <div class="detail-section">
                    <h3>Demographics</h3>
                    <p><strong>Population:</strong> ${location.population ? location.population.toLocaleString() : 'Unknown'}</p>
                    <p><strong>Wealth Level:</strong> ${'⭐'.repeat(location.wealth_level || 0)}</p>
                    <p><strong>Danger Level:</strong> ${location.danger_level || 0}/5</p>
                    ${location.docking_fee ? `<p><strong>Docking Fee:</strong> ${location.docking_fee} credits</p>` : ''}
                </div>
            </div>
            <div class="detail-section">
                <h3>Description</h3>
                <p>${location.description}</p>
            </div>
            ${services.length > 0 ? `
                <div class="detail-section">
                    <h3>Available Services</h3>
                    <div class="services-grid">
                        ${services.map(s => `<span class="service-bubble">${s}</span>`).join('')}
                    </div>
                </div>
            ` : ''}
            ${location.sub_locations && location.sub_locations.length > 0 ? `
                <div class="detail-section">
                    <h3>Sub-Locations</h3>
                    <div class="sub-locations-list">
                        ${location.sub_locations.map(sub => `
                            <div class="sub-location-detail">
                                <strong>${sub.name}</strong>
                                ${sub.entry_fee ? ` (Entry: ${sub.entry_fee} credits)` : ''}
                                ${sub.is_hidden ? ' 🔒' : ''}
                                <p>${sub.description}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        `;

        modal.style.display = 'block';
    }

    showCorridorDetails(corridor) {
        const modal = document.getElementById('detail-modal');
        const modalBody = document.getElementById('modal-body');

        modalBody.innerHTML = `
            <h2>${corridor.name}</h2>
            <div class="detail-grid">
                <div class="detail-section">
                    <h3>Route Information</h3>
                    <p><strong>Origin:</strong> ${corridor.origin.name}</p>
                    <p><strong>Destination:</strong> ${corridor.destination.name}</p>
                    <p><strong>Status:</strong> ${corridor.is_active ? 'Active' : 'Dormant'}</p>
                    <p><strong>Gate Access:</strong> ${corridor.has_gate ? 'Yes' : 'No'}</p>
                </div>
                <div class="detail-section">
                    <h3>Travel Statistics</h3>
                    <p><strong>Travel Time:</strong> ${corridor.travel_time} minutes</p>
                    <p><strong>Fuel Cost:</strong> ${corridor.fuel_cost} units</p>
                    <p><strong>Danger Level:</strong> ${corridor.danger_level}/5</p>
                    ${corridor.min_ship_class ? `<p><strong>Min Ship Class:</strong> ${corridor.min_ship_class}</p>` : ''}
                </div>
            </div>
        `;

        modal.style.display = 'block';
    }

    showNPCDetails(npc, type) {
        const modal = document.getElementById('detail-modal');
        const modalBody = document.getElementById('modal-body');

        if (type === 'static') {
            modalBody.innerHTML = `
                <h2>${npc.name}</h2>
                <div class="detail-section">
                    <h3>Personal Information</h3>
                    <p><strong>Age:</strong> ${npc.age}</p>
                    <p><strong>Occupation:</strong> ${npc.occupation}</p>
                    <p><strong>Location:</strong> ${npc.location.name}</p>
                    <p><strong>Personality:</strong> ${npc.personality}</p>
                    ${npc.trade_specialty ? `<p><strong>Trade Specialty:</strong> ${npc.trade_specialty}</p>` : ''}
                    ${npc.dialogue_style ? `<p><strong>Speaking Style:</strong> ${npc.dialogue_style}</p>` : ''}
                </div>
                ${npc.backstory ? `
                    <div class="detail-section">
                        <h3>Backstory</h3>
                        <p>${npc.backstory}</p>
                    </div>
                ` : ''}
            `;
        } else {
            modalBody.innerHTML = `
                <h2>${npc.callsign}</h2>
                <div class="detail-grid">
                    <div class="detail-section">
                        <h3>Personal Information</h3>
                        <p><strong>Real Name:</strong> ${npc.name}</p>
                        <p><strong>Age:</strong> ${npc.age}</p>
                        <p><strong>Personality:</strong> ${npc.personality}</p>
                        <p><strong>Current Location:</strong> ${npc.current_location ? npc.current_location.name : 'In Transit'}</p>
                    </div>
                    <div class="detail-section">
                        <h3>Ship Information</h3>
                        <p><strong>Ship Name:</strong> ${npc.ship.name}</p>
                        <p><strong>Ship Type:</strong> ${npc.ship.type}</p>
                        <p><strong>Trading Preference:</strong> ${npc.trading_preference || 'None'}</p>
                        <p><strong>Faction:</strong> ${npc.faction || 'Independent'}</p>
                        ${npc.wanted_level ? `<p><strong>Wanted Level:</strong> ${'⚠️'.repeat(npc.wanted_level)}</p>` : ''}
                    </div>
                </div>
            `;
        }

        modal.style.display = 'block';
    }

    showNewsDetails(news) {
        const modal = document.getElementById('detail-modal');
        const modalBody = document.getElementById('modal-body');

        const date = new Date(news.delivered_at).toLocaleString();

        modalBody.innerHTML = `
            <h2>${news.title}</h2>
            <div class="news-meta">
                <span class="news-type-large">${news.type.replace(/_/g, ' ')}</span>
                <span class="news-date">${date}</span>
            </div>
            <div class="detail-section">
                <p>${news.description}</p>
            </div>
            <div class="detail-section">
                <h3>Transmission Details</h3>
                <p><strong>News Delay:</strong> ${news.delay_hours.toFixed(1)} hours</p>
                ${news.location_id ? `<p><strong>Origin Location ID:</strong> ${news.location_id}</p>` : ''}
            </div>
            ${news.event_data ? `
                <div class="detail-section">
                    <h3>Additional Data</h3>
                    <pre>${JSON.stringify(news.event_data, null, 2)}</pre>
                </div>
            ` : ''}
        `;

        modal.style.display = 'block';
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (window.galaxyData) {
        window.galaxyWiki = new GalaxyWiki(window.galaxyData);
    }
});'''

    def _add_web_assets(self, zip_file: zipfile.ZipFile):
        """Add additional CSS for modal and detail views"""
        additional_css = '''
/* Additional styles for detail views */
.detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-bottom: 1.5rem;
}

.detail-section {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 1rem;
}

.detail-section h3 {
    margin-bottom: 0.75rem;
}

.detail-section p {
    margin-bottom: 0.5rem;
    line-height: 1.5;
}

.services-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.service-bubble {
    background: rgba(0, 255, 136, 0.2);
    border: 1px solid var(--success-color);
    color: var(--success-color);
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.85rem;
}

.sub-locations-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.sub-location-detail {
    background: rgba(0, 0, 0, 0.3);
    padding: 0.75rem;
    border-radius: 4px;
    border-left: 3px solid var(--accent-color);
}

.sub-location-detail p {
    margin-top: 0.25rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.news-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
}

.news-type-large {
    font-size: 1rem;
    padding: 0.4rem 0.8rem;
    background: rgba(0, 136, 204, 0.2);
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    color: var(--accent-color);
    text-transform: uppercase;
}

.news-date {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

pre {
    background: rgba(0, 0, 0, 0.5);
    padding: 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.location-logs-section {
    margin-bottom: 2rem;
}

.location-logs-section h3 {
    margin-bottom: 1rem;
    color: var(--accent-color);
}'''
        
        existing_css = self._generate_css()
        zip_file.writestr("assets/css/style.css", existing_css + additional_css)

    async def _add_maps_to_zip(self, zip_file: zipfile.ZipFile):
        """Generate and add galaxy maps to the zip file"""
        galaxy_cog = self.bot.get_cog('GalaxyGeneratorCog')
        if not galaxy_cog:
            return
        
        map_styles = ["standard", "wealth", "danger", "infrastructure", "connections"]
        for style in map_styles:
            try:
                map_buffer = await galaxy_cog._generate_visual_map(
                    map_style=style, 
                    show_labels=True, 
                    highlight_player=None
                )
                if map_buffer:
                    zip_file.writestr(f"assets/maps/galaxy_{style}.png", map_buffer.getvalue())
            except Exception as e:
                print(f"Failed to generate {style} map: {e}")

    async def _create_markdown_export(self, interaction: discord.Interaction,
                                    include_logs: bool, include_news: bool) -> io.BytesIO:
        """Create a markdown documentation export (fallback to existing method)"""
        admin_cog = self.bot.get_cog('AdminCog')
        if admin_cog and hasattr(admin_cog, '_perform_export'):
            return await admin_cog._perform_export(interaction)
        else:
            await interaction.followup.send("Markdown export is currently unavailable.", ephemeral=True)
            raise Exception("AdminCog not found or is missing the _perform_export method.")


    async def _create_combined_export(self, interaction: discord.Interaction,
                                    include_logs: bool, include_news: bool) -> io.BytesIO:
        """Create both web and markdown exports in one zip"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            await interaction.edit_original_response(content="⏳ Creating web wiki...")
            web_buffer = await self._create_web_export(interaction, include_logs, include_news)
            web_buffer.seek(0)
            
            with zipfile.ZipFile(web_buffer, 'r') as web_zip:
                for file_info in web_zip.filelist:
                    data = web_zip.read(file_info.filename)
                    zip_file.writestr(f"web_wiki/{file_info.filename}", data)
            
            await interaction.edit_original_response(content="⏳ Creating markdown docs...")
            try:
                md_buffer = await self._create_markdown_export(interaction, include_logs, include_news)
                md_buffer.seek(0)
                
                with zipfile.ZipFile(md_buffer, 'r') as md_zip:
                    for file_info in md_zip.filelist:
                        data = md_zip.read(file_info.filename)
                        zip_file.writestr(f"markdown_docs/{file_info.filename}", data)
            except Exception as e:
                print(f"Could not generate markdown docs: {e}")


            readme_content = """# Galaxy Export

This export contains two versions of your galaxy encyclopedia:

## 📁 web_wiki/
An interactive HTML/CSS/JavaScript wiki that can be opened in any web browser.
To use, extract the files and open `index.html` in your browser.

## 📁 markdown_docs/
Traditional markdown documentation. This may be empty if the AdminCog is not available.

Generated on: {}
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            zip_file.writestr("README.md", readme_content)
        
        zip_buffer.seek(0)
        return zip_buffer

async def setup(bot):
    await bot.add_cog(ExportCog(bot))