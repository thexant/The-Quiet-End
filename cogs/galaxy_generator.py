# cogs/galaxy_generator.py - Fixed to align with gate lore
import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import re
import io
import asyncio
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timedelta
from utils.history_generator import HistoryGenerator
import collections

class GalaxyGeneratorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.auto_shift_task = None
        # Lore-appropriate name lists
        self.location_prefixes = [
            "New", "Port", "Fort", "Station", "Haven", "Base", "Settlement", "Camp", "Depot", "Site", "Base", "Platform", "Node", "Sector", "Post", "Module", "Annex", "Hub", "Relay", "Point", "Grid", "Tower", "Gate", "Bay", "Field", "Range", "Line", "Span", "Strip", "Arc", "Ring", "Block", "Shaft", "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Omega", "One", "Two", "Three", "Four", "Five", "Seven", "Nine", "Eleven", "Twelve", "Thirteen", "Seventeen", "Twenty-One", "Thirty-Two", "Forty-Six", "Seventy-Nine", "Ninety-Two", "Hundred", "New", "Old", "Greater", "Lower", "Eastern", "Western", "Northern", "Southern", "Central", "Neo", "Nova", "Terra", "Sol", "Olympus", "Atlas", "Edison", "Armstrong", "Mariner", "Galilei", "Tsiolkovsky", "Copernicus", "Daedalus", "Ares", "Apollo", "Hawking", "Kepler", "Curie", "Newton", "RX", "TX", "DV", "LN", "KX", "ZC", "MA", "TR", "GR", "PS", "UT", "EX", "CN", "DS", "ST", "SV", "CT", "MR", "RQ", "OB", "AO", "R-12", "X-9", "L-6", "V-8", "Z-21", "Dust", "Iron", "Dry", "Red", "Cold", "Ash", "Pale", "Deep", "High", "Low", "Broad", "Long", "Short", "Twin", "Silent", "Black", "White", "Golden", "Blue", "Crimson", "Silver", "Steel", "Hollow", "Quiet", "Radiant", "Clear", "Distant", "Unity", "Liberty", "Honor", "Glory", "Triumph", "Vanguard", "Endeavor", "Providence", "Resolve", "Bastion", "Shelter", "Sentinel", "Frontier", "Justice", "Paragon", "Haven", "Echo", "Pulse", "Vision", "Legacy", "Anchor", "Mighty", "Venan's", "Darwich", "Humanity's", "Elephant's", "Vetaso's", "Darwin's"

        ]
        
        self.location_names = [
            "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Theta", "Sigma",
            "Meridian", "Horizon", "Pinnacle", "Terminus", "Nexus", "Beacon", "Anchor",
            "Magnus", "Prima", "Ultima", "Central", "Venan", "Core", "Edge", "Frontier",
            "Hope", "Unity", "Liberty", "Victory", "Genesis", "Phoenix", "Titan", "Freedom", "Foothold", "Establisment", "Centra", "Rescour", "Search",
            "Aurora", "Vega", "Sirius", "Proxima", "Centauri", "Kepler", "Nova", "Horizon", "Summit", "Providence", "Concord", "Harmony", "Unity", "Endeavor", "Victory", "Legacy", "Liberty", "Triumph", "Vanguard", "Beacon", "Hope", "Solace", "Foundation", "Promise", "Shelter", "Keystone", "Resolve", "Radiance", "Dawn", "Ascent", "Haven", "Bastion", "Frontier", "Serenity", "Reliance", "Compass", "Steward", "Sector", "Junction", "Node", "Array", "Grid", "Module", "Span", "Stack", "Gate", "Point", "Line", "Cross", "Ring", "Core", "Bay", "Depot", "Yard", "Block", "Shaft", "Ramp", "Dock", "Platform", "Terminal", "Entry", "Outlet", "Access", "Conduit", "Loop", "Run", "Segment", "Strip", "Ridge", "Valley", "Crater", "Steppe", "Rise", "Plain", "Bluff", "Mesa", "Basin", "Reach", "Range", "Slope", "Crest", "Shoal", "Shelf", "Terrace", "Divide", "Edge", "Belt", "Pass", "Spur", "Field", "Channel", "Drop", "Gap", "Flat", "Pit", "Aurora", "Solstice", "Polaris", "Meridian", "Zenith", "Orbit", "Eclipse", "Nova", "Atlas", "Luna", "Borealis", "Titan", "Terra", "Zephyr", "Helios", "Aether", "Vesper", "Nebula", "Corona", "Drift", "Pulse", "Echo", "Forge", "Relay", "Station", "Works", "Hub", "Foundry", "Yard", "Engine", "Hangar", "Mill", "Plant", "Stack", "Lift", "Armature", "Buffer", "Crane", "Spindle", "Clamp", "Array", "Socket", "Link", "Dock", "Bay", "Splendor", "Ashen", "Axle", "Barren", "Bastille", "Beacon", "Bellow", "Blight", "Blink", "Bluff", "Brimstone", "Bristle", "Brood", "Burn", "Cairn", "Cauldron", "Cellar", "Ganymede", "Clamp", "Clay", "Cloak", "Coil", "Coldiron", "Crag", "Creep", "Crest", "Crucible", "Crypt", "Current", "Cut", "Dagger", "Damper", "Dark", "Decay", "Deep", "Ditch", "Dredge", "Dross", "Duct", "Ember", "Ender", "Fell", "Fissure", "Flak", "Flicker", "Flood", "Flume", "Fold", "Forage", "Forge", "Fragment", "Gash", "Ghost", "Glare", "Glint", "Glitch", "Gorge", "Graft", "Grind", "Gutter", "Hallow", "Hinge", "Hollow", "Husk", "Huskline", "Icefall", "Ironline", "Junction", "Knuckle", "Lantern", "Lastlight", "Latch", "Ledge", "Link", "Loom", "Lurk", "Magma", "Mantle", "Maul", "Mire", "Mold", "Murk", "Nest", "Niche", "Nimbus", "Nox", "Outset", "Pale", "Path", "Pith", "Pit", "Plinth", "Plume", "Quench", "Quill", "Rack", "Rasp", "Ravine", "Reclaim", "Redoubt", "Refuge", "Relay", "Remnant", "Ridge", "Rift", "Ring", "Roost", "Rot", "Scald", "Scar", "Scour", "Scrim", "Scrub", "Seep", "Shackle", "Shard", "Shatter", "Shear", "Shiver", "Shroud", "Shunt", "Signal", "Silt", "Sink", "Slag", "Sluice", "Smelt", "Solum", "Span", "Spindle", "Spire", "Spoil", "Stain", "Stake", "Static", "Stead", "Stem", "Stitch", "Strand", "Stray", "Strut", "Sump", "Tether", "Thresh", "Thrush", "Tint", "Tithe", "Trace", "Trough", "Truss", "Tusk", "Vault", "Verge", "Vessel", "Vise", "Wake", "Waste", "Watch", "Whisk", "Wick", "Wither", "Wrack"

        ]
        
        self.system_names = [
            "Altair", "Vega", "Deneb", "Rigel", "Regalis", "Betelgeuse", "Antares", "Pollux", "Castor", "Spica", "Regulus", "Aldebaran", "Arcturus", "Capella", "Procyon", "Canopus", "Achernar", "Hadar", "Mimosa", "Acrux", "Shaula", "Elnath", "Miaplacidus", "Alnilam", "Alnair", "Alioth", "Dubhe", "Mirfak", "Wezen", "Sargas", "Kaus", "Avior", "A-14", "92-Alpha", "X-47", "Illuzhe", "Tullifer", 
            "Merak", "Alkaid", "Alcor", "Venan", "Alpheratz", "Ankaa", "Rasalhague", "Fomalhaut", "Markab", "Zubenelgenubi", "Zubeneschamali", "Algol", "Diphda", "Menkar", "Caph", "Ruchbah", "Schedar", "Menkalinan", "Eltanin", "Rastaban", "Thuban", "Kochab", "MacGregor", "Polaris", "Saiph", "Mintaka", "Tegmine", "Kitalpha", "Nashira", "Nunki", "Ascella", "Alphard", "Corvus", "Almach", "Izar", "Sirius", "Altinak", "Kornephoros", "Algieba", "Porrima", "Spindle", "Yildun", "Enif", "Alrescha", "Hydor", "Furud", "Alphirk", "Navi", "Sadalmelik", "Sadalsuud", "Ancha", "Tarazed", "Denebola", "Kraz", "Adhafera", "Talitha", "Maia", "Celaeno", "Electra", "Taygeta", "Merope", "Alcyone", "Pleione", "Atlas", "Sterope", "Larawag", "Nihal", "Tureis", "Muliphein", "Aludra", "Suhail", "Azha", "Baten", "Tania", "Cursa", "Kaffaljidhma", "Azelfafage", "Alhena", "Rasalgethi", "Alrakis", "Zaurak", "Jabbah", "Okul", "Tabit", "Yed", "Unuk", "Gienah", "Sabik", "Peacock", "Biham", "Casper", "Zaurak", "Bunda", "Atria", "Becrux", "Marfik", "Nash", "Aljanah", "Homam", "Heze", "Rotanev", "Sadalbari", "Tejat", "Teegarden", "Wolf", "Luyten", "Barnard", "Gliese", "Lacaille", "Kapteyn", "Ross", "Felta", "Vetas", "Langvar", "Purin", "Thexantul"

        ]
        
        self.corridor_names = [
            "Passage", "Route", "Lane", "Conduit", "Channel", "Gateway", "Bridge", "Link", "Path", "Throughway", "Junction", "Crossing", "Transit", "Drift", "Streamway", "Threadway", "Sliptube", "Manor", "Avenue", "Freeway", "Highway", "Artery", "Nerve", "Pipe", "Cylinder", "Trunk",
            "Span", "Thread", "Splice", "Corridor", "Threadline", "Causeway", "Way", "Tract", "Strand", "Slip", "Breach", "Merge", "Traverse", "Trace", "Stretch", "Fork", "Outlet", "Run", "Cut", "Divide", "Chasm", "Seam", "Flow", "Bend", "Vein", "Strait", "Arc", "Slide", "Reach", "Pass", "Course", "Cradle", "Weave", "Threadway", "Fold", "Pull", "Ridge", "Flux", "Spur", "Joint", "Gap", "Threadpath", "Track", "Tether", "Lift", "Ramp", "Spindle", "Groove", "Trail", "Wane", "Push", "Skein", "Ribbon", "Circuit"

        ]
        
        self.gate_names = [
            "Gate", "Portal", "Threshold", "Aperture", "Junction", "Hub", "Transit Point", "Lock", "Array", "Span", "Entry", "Access Point", "Anchor", "Bridgehead", "Nexus", "Entry Point", "Gateway", "Clamp",  "Coupler", "Link Point", "Staging Point", "Terminal", "Interface", "Aligner", "Valve", "Pylon", "Support Frame", "Corridor Dock", "Transfer Node", "Inlet", "Alignment Frame", "Convergence", "Transit Frame", "Hardpoint", "Transit Ring", "Vector Dock", "Intersection", "Perch", "Mount", "Manifold", "Cradle", "Routing Point", "Connective Node", "Anchor Frame"

        ]
        self.galaxy_names = [
            "OH 6K", "Astraeus Cloud", "Kentaurus Cloud", "Delta Miriandynus", "Gamma Dioscuri", "HJ-315", "LS 62C", "Iris Galaxy",
            "ZS-03", "Crown Galaxy", "Amphiaraus Galaxy", "Acallaris Nebula", "Lyra Polystratus", "Virgo Arcturus", "Euthenia", "SH 68I",
            "JL-08", "Nemesis Cloud", "Asteropiaos Cloud", "Pavo Kentaurus", "Gamma Borysthenis", "Crux Nemesi", "OIM-90G", "UH-033",
            "Peppura Cloud", "Acallaris Galaxy", "Zeta Arcturus", "Zagreus Galaxy", "Delta Draconis", "JKL 91B", "TM-52", "Peleus",
            "ABL-78I", "RZ-369", "Boreas Stellar Collection", "Ursa Nebula", "Upsilon Alatheia", "HV-232", "Andromeda Galaxy", "Milky Way Galaxy",
            "Orions Cloud", "Euphorion Asteris", "Europa Nebula", "TU-54", "UBV-67", "Virgo Delta", "Venan Gemini", "Lambda Eusebeia", "Serpent Nebula",
            "Argo Nebulae", "Crawleb Cloud", "ELT-45X Galaxy"
        ]
        
    def start_auto_shift_task(self):
        """Starts the auto shift task if not running."""
        if self.auto_shift_task is None or self.auto_shift_task.done():
            self.auto_shift_task = self.bot.loop.create_task(self._auto_corridor_shift_loop())
            print("🌌 Started automatic corridor shift task.")

    def stop_auto_shift_task(self):
        """Stops/Cancels the auto shift task."""
        if self.auto_shift_task and not self.auto_shift_task.done():
            self.auto_shift_task.cancel()
            print("🌌 Cancelled automatic corridor shift task.")

    async def cog_load(self):
        """Called when the cog is loaded"""
        self.start_auto_shift_task()

    async def cog_unload(self):
        """Clean up background tasks when cog is unloaded"""
        self.stop_auto_shift_task()
            
    
    galaxy_group = app_commands.Group(name="galaxy", description="Galaxy generation and mapping")
    async def _auto_corridor_shift_loop(self):
        """Background task for automatic corridor shifts"""
        try:
            # Wait for bot to be ready
            await self.bot.wait_until_ready()
            
            # Initial delay before first shift (2-6 hours)
            initial_delay = random.randint(7200, 21600)  # 2-6 hours in seconds
            print(f"🌌 Auto corridor shifts will begin in {initial_delay//3600:.1f} hours")
            await asyncio.sleep(initial_delay)
            
            while not self.bot.is_closed():
                try:
                    # Check if galaxy exists
                    location_count = self.db.execute_query(
                        "SELECT COUNT(*) FROM locations",
                        fetch='one'
                    )[0]
                    
                    if location_count > 0:
                        await self._execute_automatic_shift()
                    
                    # Schedule next shift (6-24 hours)
                    next_shift = random.randint(21600, 86400)  # 6-24 hours
                    hours = next_shift / 3600
                    print(f"🌌 Next automatic corridor shift in {hours:.1f} hours")
                    await asyncio.sleep(next_shift)
                    
                except Exception as e:
                    print(f"❌ Error in auto corridor shift: {e}")
                    # Wait 30 minutes before trying again on error
                    await asyncio.sleep(1800)
                    
        except asyncio.CancelledError:
            print("🌌 Auto corridor shift task cancelled")
        except Exception as e:
            print(f"❌ Fatal error in auto corridor shift loop: {e}")

    async def _execute_automatic_shift(self):
        """Execute an automatic corridor shift"""
        try:
            # Random intensity (weighted toward lower values)
            intensity_weights = [0.4, 0.3, 0.2, 0.08, 0.02]  # Favor intensity 1-2
            intensity = random.choices(range(1, 6), weights=intensity_weights)[0]
            
            print(f"🌌 Executing automatic corridor shift (intensity {intensity})")
            
            results = await self._execute_corridor_shifts(intensity)
            
            # Log the results
            if results['activated'] or results['deactivated']:
                print(f"🌌 Auto-shift complete: +{results['activated']} routes, -{results['deactivated']} routes")
            
            # Check if we need to notify anyone
            if results['activated'] + results['deactivated'] >= 3:
                await self._broadcast_major_shift_alert(intensity, results)
            
            # Validate connectivity after shift
            connectivity_issues = await self._check_critical_connectivity_issues()
            if connectivity_issues:
                print(f"⚠️ Connectivity issues detected post-shift: {connectivity_issues}")
                # Auto-fix critical issues
                await self._auto_fix_critical_connectivity()
        
        except Exception as e:
            print(f"❌ Error executing automatic shift: {e}")

    async def _broadcast_major_shift_alert(self, intensity: int, results: Dict):
        """Broadcast alerts about major corridor shifts to configured channels"""
        
        # Get notification channels from server config
        guilds_with_config = self.db.execute_query(
            "SELECT guild_id FROM server_config WHERE setup_completed = 1",
            fetch='all'
        )
        
        embed = discord.Embed(
            title="🌌 Major Corridor Shift Detected",
            description=f"Significant changes to galactic infrastructure have been detected.",
            color=0x800080
        )
        
        embed.add_field(
            name="Shift Magnitude", 
            value=f"Intensity {intensity}/5", 
            inline=True
        )
        
        changes = []
        if results['activated']:
            changes.append(f"🟢 {results['activated']} new routes opened")
        if results['deactivated']:
            changes.append(f"🔴 {results['deactivated']} routes collapsed")
        
        if changes:
            embed.add_field(
                name="Infrastructure Changes",
                value="\n".join(changes),
                inline=False
            )
        
        embed.add_field(
            name="Advisory",
            value="• Check `/travel routes` for updated route availability\n• Travelers in transit are unaffected\n• New opportunities for exploration may have opened",
            inline=False
        )
        
        embed.set_footer(text="Automatic corridor shifts occur every 6-24 hours")
        
        # Send to all configured guilds
        for guild_id_tuple in guilds_with_config:
            guild_id = guild_id_tuple[0]
            guild = self.bot.get_guild(guild_id)
            
            if guild:
                # Try to find a good channel to post in
                target_channel = None
                
                # Look for announcements/general channels
                for channel in guild.text_channels:
                    if any(name in channel.name.lower() for name in ['announcement', 'general', 'news', 'galaxy', 'rpg']):
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break
                
                # Fallback to first available channel
                if not target_channel:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break
                
                if target_channel:
                    try:
                        await target_channel.send(embed=embed)
                        print(f"📢 Sent shift alert to {guild.name}#{target_channel.name}")
                    except Exception as e:
                        print(f"❌ Failed to send shift alert to {guild.name}: {e}")

    async def _check_critical_connectivity_issues(self) -> str:
        """Check for critical connectivity issues that need immediate fixing"""
        
        locations = self.db.execute_query(
            "SELECT location_id FROM locations",
            fetch='all'
        )
        
        if not locations:
            return ""
        
        # Build connectivity graph
        graph = {loc[0]: set() for loc in locations}
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = 1",
            fetch='all'
        )
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        # Check for critical issues
        issues = []
        
        # Multiple components (fragmentation)
        if len(components) > 1:
            largest = max(components, key=len)
            isolated_count = sum(len(comp) for comp in components if comp != largest)
            issues.append(f"{len(components)} disconnected clusters ({isolated_count} isolated locations)")
        
        # Locations with no connections
        no_connections = [loc_id for loc_id in graph if len(graph[loc_id]) == 0]
        if no_connections:
            issues.append(f"{len(no_connections)} completely isolated locations")
        
        return "; ".join(issues) if issues else ""

    async def _auto_fix_critical_connectivity(self):
        """Automatically fix critical connectivity issues"""
        print("🔧 Auto-fixing critical connectivity issues...")
        
        # Get all locations
        all_locations_data = self.db.execute_query(
            "SELECT location_id, name, location_type, x_coord, y_coord, wealth_level FROM locations",
            fetch='all'
        )
        
        # Convert to dict format
        all_locations = []
        for loc_id, name, loc_type, x, y, wealth in all_locations_data:
            all_locations.append({
                'id': loc_id,
                'name': name, 
                'type': loc_type,
                'x_coord': x,
                'y_coord': y,
                'wealth_level': wealth
            })
        
        # Find disconnected components
        graph = {loc['id']: set() for loc in all_locations}
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = 1",
            fetch='all'
        )
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        if len(components) <= 1:
            return  # No fragmentation to fix
        
        # Connect all components to the largest one
        largest_component = max(components, key=len)
        fixes_applied = 0
        
        for component in components:
            if component == largest_component:
                continue
            
            # Find best connection between this component and largest
            best_distance = float('inf')
            best_corridor_id = None
            
            # First try to activate an existing dormant corridor
            for loc_id_a in component:
                for loc_id_b in largest_component:
                    dormant_corridor = self.db.execute_query(
                        "SELECT corridor_id FROM corridors WHERE origin_location = ? AND destination_location = ? AND is_active = 0",
                        (loc_id_a, loc_id_b),
                        fetch='one'
                    )
                    
                    if dormant_corridor:
                        best_corridor_id = dormant_corridor[0]
                        break
                
                if best_corridor_id:
                    break
            
            # If found dormant corridor, activate it
            if best_corridor_id:
                self.db.execute_query(
                    "UPDATE corridors SET is_active = 1 WHERE corridor_id = ?",
                    (best_corridor_id,)
                )
                fixes_applied += 1
                print(f"🔧 Activated dormant corridor to reconnect isolated cluster")
            else:
                # Create new corridor as emergency measure
                component_locs = [loc for loc in all_locations if loc['id'] in component]
                largest_locs = [loc for loc in all_locations if loc['id'] in largest_component]
                
                # Find closest pair
                best_connection = None
                for loc_a in component_locs:
                    for loc_b in largest_locs:
                        distance = self._calculate_distance(loc_a, loc_b)
                        if distance < best_distance:
                            best_distance = distance
                            best_connection = (loc_a, loc_b)
                
                if best_connection and best_distance < 150:  # Don't create extremely long emergency corridors
                    loc_a, loc_b = best_connection
                    name = f"Emergency Link {loc_a['name']}-{loc_b['name']}"
                    fuel_cost = max(15, int(best_distance * 0.8) + 10)
                    danger = 4  # Emergency corridors are dangerous
                    travel_time = self._calculate_ungated_route_time(best_distance)
                    
                    # Create bidirectional emergency corridor
                    self.db.execute_query(
                        '''INSERT INTO corridors 
                           (name, origin_location, destination_location, travel_time, fuel_cost, 
                            danger_level, is_active, is_generated)
                           VALUES (?, ?, ?, ?, ?, ?, 1, 1)''',
                        (name, loc_a['id'], loc_b['id'], travel_time, fuel_cost, danger)
                    )
                    
                    self.db.execute_query(
                        '''INSERT INTO corridors 
                           (name, origin_location, destination_location, travel_time, fuel_cost, 
                            danger_level, is_active, is_generated)
                           VALUES (?, ?, ?, ?, ?, ?, 1, 1)''',
                        (f"{name} Return", loc_b['id'], loc_a['id'], travel_time, fuel_cost, danger)
                    )
                    
                    fixes_applied += 1
                    print(f"🆘 Created emergency corridor: {loc_a['name']} ↔ {loc_b['name']}")
        
        if fixes_applied > 0:
            print(f"🔧 Applied {fixes_applied} connectivity fixes")
    @galaxy_group.command(name="generate", description="Generate a new galaxy - this marks the beginning of galactic history")
    @app_commands.describe(
        num_locations="Number of major locations to generate (10-500, random if not specified)",
        clear_existing="Whether to clear existing generated locations first",
        galaxy_name="Name for your galaxy (random if not specified)",
        start_date="Galaxy start date (DD-MM-YYYY format, random 2700-2799 if not specified)"
    )
    async def generate_galaxy(self, interaction: discord.Interaction, 
                             num_locations: int = None, 
                             clear_existing: bool = False,
                             galaxy_name: str = None,
                             start_date: str = None):
        black_markets = 0
        federal_depots = 0
        corridor_routes = []  # Make sure this is accessible                     
        # Generate random values for unspecified parameters
        if num_locations is None:
            num_locations = random.randint(50, 150)
            print(f"🎲 Randomly selected {num_locations} locations to generate")

        if galaxy_name is None:
            galaxy_name = random.choice(self.galaxy_names)
            print(f"🎲 Randomly selected galaxy name: {galaxy_name}")

        if start_date is None:
            # Generate random date between 2700-2799
            year = random.randint(2700, 2799)
            month = random.randint(1, 12)
            # Handle different days per month
            if month in [1, 3, 5, 7, 8, 10, 12]:
                day = random.randint(1, 31)
            elif month in [4, 6, 9, 11]:
                day = random.randint(1, 30)
            else:  # February
                day = random.randint(1, 28)
            start_date = f"{day:02d}-{month:02d}-{year}"
            print(f"🎲 Randomly selected start date: {start_date}")
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if num_locations < 3 or num_locations > 9999:
            await interaction.response.send_message("Number of locations must be between 10 and 500.", ephemeral=True)
            return
        
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        try:
            if re.match(r'^\d{4}$', start_date):
                start_date_obj = datetime(int(start_date), 1, 1)
                start_date = f"01-01-{start_date}"
            elif re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', start_date):
                start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            else:
                raise ValueError("Invalid date format")
        except ValueError:
            await interaction.response.send_message("Invalid date format. Use DD-MM-YYYY or YYYY.", ephemeral=True)
            return

        if not (2700 <= start_date_obj.year <= 2799):
            await interaction.response.send_message("Start date year must be between 2700 and 2799.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        progress_msg = await interaction.followup.send("🌌 **Galaxy Generation Started**\n⏳ Pausing background tasks...", ephemeral=True)
        
        # Stop ALL background tasks more thoroughly
        print("🛑 Stopping all background tasks aggressively...")
        self.bot.stop_background_tasks()

        # Stop status updater specifically
        status_updater_cog = self.bot.get_cog('StatusUpdaterCog')
        if status_updater_cog:
            status_updater_cog.update_status_channels.cancel()
            print("🛑 Stopped status updater")

        # Stop channel manager background tasks specifically
        channel_manager = getattr(self.bot, 'channel_manager', None)
        if channel_manager:
            channel_manager.auto_cleanup_enabled = False
            print("🛑 Disabled channel manager auto-cleanup")

        # Also stop any cog-specific tasks
        events_cog = self.bot.get_cog('EventsCog')
        if events_cog:
            events_cog.stop_all_tasks()

        # Give more time for tasks to actually stop
        await asyncio.sleep(3.0)
        
        # Initialize safe defaults for all variables
        major_locations = []
        gates = []
        corridors = []
        corridor_routes = []
        black_markets = 0
        federal_depots = 0
        total_homes = 0
        total_sub_locations = 0
        built_repeaters = 0
        log_books_created = 0
        total_history_events = 0
        
        try:
            # Phase 1: Galaxy setup and locations (single transaction)
            conn = self.db.begin_transaction()
            try:
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🗑️ Setting up galaxy...")
                
                # Galaxy info and clearing
                current_time = datetime.now()
                self.db.execute_in_transaction(conn,
                    """INSERT OR REPLACE INTO galaxy_info 
                       (galaxy_id, name, start_date, time_scale_factor, time_started_at, is_time_paused, current_ingame_time) 
                       VALUES (1, ?, ?, 4.0, ?, 0, ?)""",
                    (galaxy_name, start_date, current_time.isoformat(), start_date_obj.isoformat())
                )
                
                if clear_existing:
                    await self._clear_existing_galaxy_data(conn)
                await asyncio.sleep(0.5)
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🏭 Creating major locations...")
                major_locations = await self._generate_major_locations(conn, num_locations, start_date_obj.year)
                
                self.db.commit_transaction(conn)
                conn = None
                # Force WAL checkpoint to ensure data is written
                self.db.execute_query("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception as e:
                if conn:
                    self.db.rollback_transaction(conn)
                raise
            
            await asyncio.sleep(1.0)
            await asyncio.sleep(0.5)
                
            # Phase 2: Routes and infrastructure (separate transactions to avoid locks)
            try:
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🛣️ Planning active corridor routes...")
                corridor_routes = await self._plan_corridor_routes(major_locations)
                
                if not corridor_routes:
                    print("⚠️ No corridor routes generated, creating emergency connections...")
                    # Create at least one route to prevent complete isolation
                    if len(major_locations) >= 2:
                        corridor_routes = [{
                            'from': major_locations[0],
                            'to': major_locations[1], 
                            'importance': 'critical',
                            'distance': self._calculate_distance(major_locations[0], major_locations[1])
                        }]
                
                await asyncio.sleep(0.1)
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🚪 Generating transit gates...")
                gates = await self._generate_gates_for_routes(None, corridor_routes, major_locations)
                
                all_locations = major_locations + gates
                await asyncio.sleep(0.1)
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🌉 Creating active corridor network...")
                corridors = await self._create_corridors(None, corridor_routes, all_locations)
                
                # Force checkpoint to ensure data is written
                self.db.execute_query("PRAGMA wal_checkpoint(PASSIVE)")
                await asyncio.sleep(1.0)

            except Exception as e:
                print(f"❌ Error in Phase 2: {e}")
                raise
                
            if 'all_locations' not in locals():
                all_locations = major_locations + gates
                print(f"📍 Defined all_locations: {len(major_locations)} major + {len(gates)} gates = {len(all_locations)} total")
                
            # Allow other tasks to run
            await asyncio.sleep(0.5)
            
            # Phase 3: Additional features (separate transaction with better yielding)
            conn = self.db.begin_transaction()
            try:
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🎭 Establishing facilities...")
                black_markets = await self._generate_black_markets(conn, major_locations)
                federal_depots = await self._assign_federal_supplies(conn, major_locations)
                
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n🏢 Creating infrastructure...")
                total_sub_locations = await self._generate_sub_locations_for_all_locations(conn, all_locations)
                
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n📡 Installing systems...")
                built_repeaters = await self._generate_built_in_repeaters(conn, all_locations)
                
                # Commit this transaction before log generation
                self.db.commit_transaction(conn)
                conn = None
                self.db.execute_query("PRAGMA wal_checkpoint(PASSIVE)")
                await asyncio.sleep(1.0)

                # Generate logs in separate transaction
                await progress_msg.edit(content="🌌 **Galaxy Generation**\n📜 Creating location log books...")
                try:
                    # Don't pass a connection since _generate_initial_location_logs manages its own
                    log_books_created = await self._generate_initial_location_logs(None, all_locations, start_date_obj)
                except Exception as e:
                    print(f"⚠️ Log generation failed: {e}")
                    log_books_created = 0  # Continue even if log generation fails
                
                # Force checkpoint before dormant corridor generation
                self.db.execute_query("PRAGMA wal_checkpoint(TRUNCATE)")
                await asyncio.sleep(2.0)
                
                try:
                    # Generate dormant corridors (this now handles its own transactions)
                    await progress_msg.edit(content="🌌 **Galaxy Generation**\n🌫️ Creating dormant corridors...")
                    if corridor_routes:  # Only if we have active routes
                        await self._create_dormant_corridors(None, all_locations, corridor_routes)
                        print("✅ Dormant corridor generation completed")
                    else:
                        print("⚠️ Skipping dormant corridors - no active routes to base them on")
                    
                    await asyncio.sleep(1.0)
                    
                except Exception as dormant_error:
                    print(f"⚠️ Dormant corridor generation failed: {dormant_error}")
                    print("   Continuing with galaxy generation...")
                
                await asyncio.sleep(1.0)

            except Exception as e:
                if conn:
                    self.db.rollback_transaction(conn)
                raise
                
            await asyncio.sleep(0.5)
            
            # Phase 4: NPC Generation (completely outside any transaction)
            await progress_msg.edit(content="🌌 **Galaxy Generation**\n🤖 Populating with inhabitants...")

            # Ensure ALL transactions are committed before NPC generation
            await asyncio.sleep(0.5)  # Give time for any pending operations

            # Now generate NPCs without any active transactions
            await self._create_npcs_outside_transaction(all_locations, progress_msg)

            # Add another delay before history generation
            await asyncio.sleep(0.5)
            
            # Step 8: Generate homes for colonies and space stations
            await progress_msg.edit(content="🌌 **Galaxy Generation**\n🏠 Creating residential properties...")
            total_homes = await self._generate_homes_for_locations(major_locations)
            
            # Post-generation tasks (outside transactions)
            npc_cog = self.bot.get_cog('NPCCog')
            if npc_cog:
                await npc_cog.spawn_initial_dynamic_npcs()

            # Generate history outside transaction to avoid deadlock
            await progress_msg.edit(content="🌌 **Galaxy Generation**\n📚 Documenting galactic history...")
            history_gen = HistoryGenerator(self.bot)
            total_history_events = await history_gen.generate_galaxy_history(start_date_obj.year, start_date_obj.strftime('%Y-%m-%d'))

            await progress_msg.edit(content="🌌 **Galaxy Generation**\n✅ **Generation Complete!**")

        except Exception as e:
            print(f"❌ Error during galaxy generation: {e}")
            import traceback
            traceback.print_exc()
            # Continue to try sending an embed even if generation partially failed

        # MOVED: Embed creation and sending outside of try blocks with safe defaults
        try:
            # Ensure all variables are properly defined with safe defaults
            total_locations_generated = len(major_locations) + len(gates)
            total_infrastructure = total_locations_generated

            # Add randomization info
            randomized_info = []
            if num_locations is None:
                randomized_info.append("Number of locations")
            if galaxy_name is None:
                randomized_info.append("Galaxy name")
            if start_date is None:
                randomized_info.append("Start date")

            randomized_text = f"\n*Randomly generated: {', '.join(randomized_info)}*" if randomized_info else ""

            # Create and send the embed
            embed = discord.Embed(
                title=f"🌌 {galaxy_name} - Creation Complete",
                description=f"Successfully generated {total_locations_generated} major locations plus {len(gates)} transit gates ({total_infrastructure} total infrastructure) and {len(corridors)} corridors.\n**Galactic Era Begins:** {start_date_obj.strftime('%d-%m-%Y')} 00:00 ISST{randomized_text}",
                color=0x00ff00
            )

            # Count major location types safely
            location_counts = {'colony': 0, 'space_station': 0, 'outpost': 0}
            for loc in major_locations:
                location_counts[loc['type']] += 1

            location_text = "\n".join([f"{t.replace('_', ' ').title()}s: {c}" for t, c in location_counts.items()])
            location_text += f"\n**Total Major Locations: {total_locations_generated}**"
            location_text += f"\nTransit Gates: {len(gates)} (additional infrastructure)"
            if black_markets > 0:
                location_text += f"\nBlack Markets: {black_markets} (outlaw)"
            if federal_depots > 0:
                location_text += f"\nFederal Supply Depots: {federal_depots} (government)"

            embed.add_field(name="Infrastructure Generated", value=location_text, inline=True)

            # Count corridor types safely
            gated_routes = len([r for r in corridor_routes if r.get('has_gates', False)])
            ungated_routes = len(corridor_routes) - gated_routes
            estimated_corridors = (gated_routes * 6) + (ungated_routes * 2)
            corridor_text = f"Total Routes: {len(corridor_routes)}\nGated Routes (Safe): {gated_routes}\nUngated Routes (Risky): {ungated_routes}\nTotal Corridor Segments: {estimated_corridors}"
            embed.add_field(name="Corridor Network", value=corridor_text, inline=True)

            embed.add_field(name="", value="", inline=True)  # Spacer

            embed.add_field(
                name="⏰ Inter-Solar Standard Time (ISST)",
                value=f"**Galaxy Start:** {start_date} 00:00 ISST\n**Time Scale:** 4x speed (6 hours real = 1 day in-game)\n**Status:** ✅ Active",
                inline=False
            )

            embed.add_field(
                name="📅 Historical Timeline",
                value=f"Galaxy Start Date: {start_date_obj.strftime('%d-%m-%Y')}\nIn-game time flows at 4x speed\nUse `/date` to check current galactic time",
                inline=False
            )
            
            embed.add_field(
                name="🏠 Residential Properties",
                value=f"{total_homes} homes generated",
                inline=True
            )

            # Ensure galactic news channel is configured and send connection announcement
            await self._ensure_galactic_news_setup(interaction.guild, galaxy_name)

            # Send the success embed
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as embed_error:
            # If embed creation fails, send a simple success message
            print(f"❌ Error creating success embed: {embed_error}")
            try:
                await interaction.followup.send(
                    f"✅ **Galaxy Generation Complete!**\n"
                    f"Galaxy '{galaxy_name}' has been successfully generated.\n"
                    f"Generated {len(major_locations)} major locations with transit infrastructure.\n"
                    f"Start date: {start_date_obj.strftime('%d-%m-%Y')} 00:00 ISST", 
                    ephemeral=True
                )
            except Exception as fallback_error:
                print(f"❌ Error sending fallback message: {fallback_error}")

        # Restart background tasks in finally block to ensure they always restart
        try:
            await progress_msg.edit(content="🔄 **Galaxy Generation**\n🔄 Resuming background tasks...")
            # Longer delay before restarting
            await asyncio.sleep(2.0)

            # Restart background tasks
            print("🔄 Restarting background tasks...")
            self.bot.start_background_tasks()

            status_updater_cog = self.bot.get_cog('StatusUpdaterCog')
            if status_updater_cog:
                # Check if the task exists and use correct Loop methods
                if hasattr(status_updater_cog, 'update_status_channels'):
                    task_loop = status_updater_cog.update_status_channels
                    # Use is_running() instead of done() for discord.ext.tasks.Loop
                    if not task_loop.is_running():
                        try:
                            task_loop.restart()
                            print("🔄 Restarted status updater")
                        except Exception as restart_error:
                            print(f"⚠️ Could not restart status updater: {restart_error}")
                    else:
                        print("🔄 Status updater already running")
                else:
                    print("⚠️ Status updater task not found")

            # Re-enable channel manager cleanup
            channel_manager = getattr(self.bot, 'channel_manager', None)
            if channel_manager:
                channel_manager.auto_cleanup_enabled = True
                print("🔄 Re-enabled channel manager auto-cleanup")
        except Exception as restart_error:
            print(f"❌ Error restarting background tasks: {restart_error}")

    async def _create_earth(self, conn, start_year: int) -> Dict[str, Any]:
        """Creates the static Earth location within a transaction."""
        description = (
            "Earth still exists but is a hollowed-out symbol more than a paradise. Centuries of overuse, industrial exploitation, "
            "and political decay have rendered the planet nearly unable to system natural ecosystems. It supports its population "
            "consisting of a shrinking bureaucratic core and the wealthy only through imports from its colonies, yet its ability to govern or support "
            "those colonies is minimal. Some colonies remain loyal out of habit or necessity; others are functionally independent, and some actively oppose "
            "Earth’s influence, which now functions more like inertia than active control."
        )
        location = {
            'name': "Earth", 'type': 'colony', 'x_coord': 0, 'y_coord': 0,
            'system_name': "Sol", 'description': description, 'wealth_level': 10,
            'population': random.randint(50000, 100000),
            'established_date': f"{start_year - 4000}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            'has_jobs': True, 'has_shops': True, 'has_medical': True, 'has_repairs': True,
            'has_fuel': True, 'has_upgrades': True, 'has_black_market': False,
            'is_generated': True, 'is_derelict': False, 'has_shipyard': True
        }
        location['id'] = self._save_location_to_db(conn, location)
        print("🌍 Created static location: Earth in Sol system.")
        return location
    async def _create_npcs_outside_transaction(self, all_locations: List[Dict], progress_msg=None):
        """Create NPCs with better transaction isolation"""
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            print("❌ NPCCog not found, skipping NPC creation.")
            return
        
        total_npcs_created = 0
        batch_size = 50  # Smaller batches
        current_batch = []
        
        # Pre-fetch all location data to avoid queries during generation
        location_data_map = {}
        for location in all_locations:
            location_data_map[location['id']] = {
                'population': location.get('population', 100),
                'type': location['type'],
                'wealth_level': location['wealth_level'],
                'has_black_market': location.get('has_black_market', False)
            }
        
        for i, location in enumerate(all_locations):
            if progress_msg and i % 10 == 0:
                percent_complete = (i / len(all_locations)) * 100
                await progress_msg.edit(
                    content=f"🌌 **Galaxy Generation**\n🤖 Populating with inhabitants... ({percent_complete:.0f}%)"
                )
                # Yield control
                await asyncio.sleep(0.05)
            
            # Get NPC data without database calls
            npc_data_list = npc_cog.generate_static_npc_batch_data(
                location['id'],
                location_data_map[location['id']]['population'],
                location_data_map[location['id']]['type'],
                location_data_map[location['id']]['wealth_level'],
                location_data_map[location['id']]['has_black_market']
            )
            
            current_batch.extend(npc_data_list)
            
            # Insert batch when it reaches size limit
            if len(current_batch) >= batch_size:
                # Use a completely new connection for each batch
                try:
                    # Direct insert without transaction wrapper
                    self.db.execute_query(
                        '''INSERT INTO static_npcs 
                           (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        current_batch,
                        many=True
                    )
                    
                    total_npcs_created += len(current_batch)
                    print(f"🤖 Created {len(current_batch)} static NPCs (total: {total_npcs_created})...")
                    current_batch = []
                    
                    # Longer yield between batches
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"❌ Error creating NPC batch: {e}")
                    current_batch = []  # Clear failed batch
                    await asyncio.sleep(0.5)  # Wait before continuing
        
        # Insert remaining NPCs
        if current_batch:
            try:
                self.db.execute_query(
                    '''INSERT INTO static_npcs 
                       (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    current_batch,
                    many=True
                )
                total_npcs_created += len(current_batch)
            except Exception as e:
                print(f"❌ Error creating final NPC batch: {e}")
        
        print(f"🤖 Total NPCs created: {total_npcs_created}")
    
    def _cleanup_large_arrays(self):
        """Clear large arrays from memory to prevent buildup"""
        # Force garbage collection of large message arrays
        import gc
        gc.collect()
        
    async def _generate_major_locations(self, conn, num_locations: int, start_year: int) -> List[Dict]:
        """Generate colonies, space stations, and outposts within a transaction."""
        distributions = {'colony': 0.30, 'space_station': 0.35, 'outpost': 0.40}
        major_locations = []
        used_names = set()
        used_systems = set()

        earth_location = await self._create_earth(conn, start_year)
        major_locations.append(earth_location)
        used_names.add(earth_location['name'])
        used_systems.add(earth_location['system_name'])

        for i in range(num_locations - 1):  # -1 because Earth is included
            loc_type = random.choices(list(distributions.keys()), list(distributions.values()))[0]
            name = self._generate_unique_name(loc_type, used_names)
            used_names.add(name)
            system = self._generate_unique_system(used_systems)
            used_systems.add(system)

            establishment_year = start_year - random.randint(5, 350)
            establishment_date = f"{establishment_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
            
            location_data = self._create_location_data(name, loc_type, system, establishment_date)
            location_id = self._save_location_to_db(conn, location_data)
            location_data['id'] = location_id
            major_locations.append(location_data)
            
            # Yield control every 10 locations
            if i % 10 == 0:
                await asyncio.sleep(0)
                
        return major_locations
    async def _create_npcs_for_galaxy(self, conn):
        """Creates NPCs for all locations within the transaction."""
        npc_cog = self.bot.get_cog('NPCCog')
        if not npc_cog:
            print("❌ NPCCog not found, skipping NPC creation.")
            return

        # Get location data needed for NPC generation
        all_locations = self.db.execute_in_transaction(conn,
            "SELECT location_id, population, location_type, wealth_level, has_black_market FROM locations",
            fetch='all'
        )
        
        npcs_to_insert = []
        locations_processed = 0
        
        for loc_id, pop, loc_type, wealth, has_black_market in all_locations:
            # Pass all required data to avoid database calls within the method
            npc_data_list = npc_cog.generate_static_npc_batch_data(
                loc_id, pop, loc_type, wealth, has_black_market
            )
            npcs_to_insert.extend(npc_data_list)
            locations_processed += 1
            
            # Batch insert every 50 locations to avoid memory issues
            if locations_processed % 50 == 0:
                if npcs_to_insert:
                    query = '''INSERT INTO static_npcs 
                               (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                    self.db.executemany_in_transaction(conn, query, npcs_to_insert)
                    print(f"🤖 Created {len(npcs_to_insert)} static NPCs (batch {locations_processed // 50})...")
                    npcs_to_insert = []  # Clear the list
                
                # Yield control to event loop
                await asyncio.sleep(0)
        
        # Insert any remaining NPCs
        if npcs_to_insert:
            query = '''INSERT INTO static_npcs 
                       (location_id, name, age, occupation, personality, alignment, hp, max_hp, combat_rating, credits) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            self.db.executemany_in_transaction(conn, query, npcs_to_insert)
            print(f"🤖 Created {len(npcs_to_insert)} static NPCs (final batch).")
    
    async def _generate_black_markets(self, conn, major_locations: List[Dict]) -> int:
        """
        Enhanced black market generation using the proper item system from item_config.py
        """
        from item_config import ItemConfig
        
        black_markets_created = 0
        locations_to_flag = []
        items_to_insert = []

        # Get black market appropriate items from the proper item system
        def get_black_market_items():
            """Get items appropriate for black markets"""
            black_market_items = []
            
            # Medical items (illegal/unregulated)
            medical_items = ItemConfig.get_items_by_type("medical")
            for item in medical_items:
                item_data = ItemConfig.get_item_definition(item)
                if item_data.get("rarity") in ["uncommon", "rare"]:  # Harder to get legally
                    black_market_items.append((item, "medical", "Unregulated medical supplies"))
            
            # Equipment items (illegal/modified)
            equipment_items = ItemConfig.get_items_by_type("equipment")
            for item in equipment_items:
                item_data = ItemConfig.get_item_definition(item)
                if item_data.get("rarity") in ["rare", "legendary"]:  # Military/restricted
                    black_market_items.append((item, "equipment", "Military surplus or stolen equipment"))
            
            # Upgrade items (illegal modifications)
            upgrade_items = ItemConfig.get_items_by_type("upgrade")
            for item in upgrade_items:
                black_market_items.append((item, "upgrade", "Unlicensed ship modifications"))
            
            # Special black market exclusives (add to ItemConfig.py)
            exclusive_items = [
                ("Forged Transit Papers", "documents", "Fake identification documents"),
                ("Identity Scrubber", "service", "Erases identity records - illegal but effective"),
                ("Stolen Data Chips", "data", "Information of questionable origin"),
                ("Unmarked Credits", "currency", "Untraceable digital currency"),
                ("Weapon System Override", "software", "Bypasses weapon safety protocols"),
                ("Neural Interface Hack", "software", "Illegal consciousness enhancement"),
            ]
            black_market_items.extend(exclusive_items)
            
            return black_market_items

        black_market_item_pool = get_black_market_items()

        for location in major_locations:
            black_market_chance = 0.0
            
            # Enhanced spawn logic (as before)
            if location['wealth_level'] <= 2:
                black_market_chance = 0.35
            elif location['wealth_level'] <= 3:
                black_market_chance = 0.25
            elif location['wealth_level'] <= 4:
                black_market_chance = 0.15
            elif location['wealth_level'] == 5:
                black_market_chance = 0.08
            elif location['wealth_level'] == 6:
                black_market_chance = 0.03
            
            # Location type modifiers
            if location['type'] == 'outpost':
                black_market_chance *= 1.5
            elif location['type'] == 'space_station':
                black_market_chance *= 0.7
            elif location['type'] == 'colony':
                black_market_chance *= 1.0
            
            # Population modifiers
            if location['population'] < 100:
                black_market_chance *= 1.3
            elif location['population'] > 1000:
                black_market_chance *= 0.8
                
            if location.get('is_derelict', False):
                black_market_chance = 0.60
            
            black_market_chance = min(black_market_chance, 0.60)
            
            if black_market_chance > 0 and random.random() < black_market_chance:
                
                market_type = 'underground' if location['wealth_level'] <= 2 else 'discrete'
                reputation_required = random.randint(0, 2) if location['wealth_level'] <= 2 else random.randint(1, 4)
                
                market_id = self.db.execute_in_transaction(
                    conn,
                    '''INSERT INTO black_markets (location_id, market_type, reputation_required, is_hidden)
                       VALUES (?, ?, ?, 1)''',
                    (location['id'], market_type, reputation_required),
                    fetch='lastrowid'
                )
                
                if market_id:
                    black_markets_created += 1
                    locations_to_flag.append((location['id'],))
                    
                    # Generate items using proper item system
                    item_count = random.randint(3, 6)
                    selected_items = random.sample(black_market_item_pool, min(item_count, len(black_market_item_pool)))
                    
                    for item_name, item_type, description in selected_items:
                        # Get proper item data if it exists in ItemConfig
                        item_data = ItemConfig.get_item_definition(item_name)
                        
                        if item_data:
                            # Use ItemConfig pricing with black market markup
                            base_price = item_data.get("base_value", 100)
                            markup_multiplier = random.uniform(1.5, 3.0)  # 50-200% markup
                            final_price = int(base_price * markup_multiplier)
                            stock = 1 if item_data.get("rarity") in ["rare", "legendary"] else random.randint(1, 3)
                        else:
                            # Fallback for exclusive items
                            final_price = random.randint(1000, 5000)
                            stock = random.randint(1, 2)
                        
                        items_to_insert.append(
                            (market_id, item_name, item_type, final_price, description, stock)
                        )
                    
                    print(f"🕴️  Created {market_type} black market at {location['name']}")

        # Bulk database operations
        if locations_to_flag:
            self.db.executemany_in_transaction(
                conn,
                "UPDATE locations SET has_black_market = 1 WHERE location_id = ?",
                locations_to_flag
            )
        
        if items_to_insert:
            # Update the black_market_items table to include stock
            self.db.executemany_in_transaction(
                conn,
                '''INSERT INTO black_market_items (market_id, item_name, item_type, price, description, stock)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                items_to_insert
            )
            
        return black_markets_created
        
    async def _safe_transaction_wrapper(self, operation_name: str, operation_func, *args, **kwargs):
        """Safely execute database operations with proper error handling"""
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                result = await operation_func(*args, **kwargs)
                return result
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database locked during {operation_name}, retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"❌ Error in {operation_name}: {e}")
                    raise
                    
    def _create_location_data(self, name: str, loc_type: str, system: str, establishment_date: str) -> Dict:
        """Create location data with varied and flavorful descriptions"""
        import random, math

        # Generate coordinates in a galaxy-like distribution
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(10, 90)
        
        # Add spiral arm effect
        spiral_factor = radius / 90.0
        angle += spiral_factor * math.pi * 0.5
        
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        
        # Determine base properties by type
        # Check for derelict status first (5% chance)
        is_derelict = random.random() < 0.05

        if is_derelict:
            # Derelict locations have very low wealth and population
            wealth = 0
            population = 0
            description = self._generate_derelict_description(name, loc_type, system, establishment_date)
        else:
            # Normal location generation
            if loc_type == 'colony':
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(80, 500) * (wealth + 2)
                description = self._generate_colony_description(name, system, establishment_date, wealth, population)
            elif loc_type == 'space_station':
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(50, 350) * wealth
                description = self._generate_station_description(name, system, establishment_date, wealth, population)
            elif loc_type == 'gate':
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(3, 15)
                description = self._generate_station_description(name, system, establishment_date, wealth, population)
            else:  # outpost
                wealth = min(random.randint(1, 10), random.randint(1, 10))
                population = random.randint(5, 50)
                description = self._generate_outpost_description(name, system, establishment_date, wealth, population)
        
        # Build the dict with derelict-aware defaults
        if is_derelict:
            # Derelict locations have minimal or no services
            loc = {
                'name': name,
                'type': loc_type,
                'x_coord': x,
                'y_coord': y,
                'system_name': system,
                'description': description,
                'wealth_level': wealth,
                'population': population,
                'established_date': establishment_date,
                'has_jobs': False,
                'has_shops': False,
                'has_medical': False,
                'has_repairs': False,
                'has_fuel': False,   
                'has_upgrades': False,
                'has_black_market': False,
                'is_generated': True,
                'is_derelict': True
            }
        else:
            # Normal location defaults
            loc = {
                'name': name,
                'type': loc_type,
                'x_coord': x,
                'y_coord': y,
                'system_name': system,
                'description': description,
                'wealth_level': wealth,
                'population': population,
                'established_date': establishment_date,
                'has_jobs': True,
                'has_shops': True,
                'has_medical': True,
                'has_repairs': True,
                'has_fuel': True,
                'has_upgrades': False,
                'has_black_market': False,
                'is_generated': True,
                'is_derelict': False
            }
        
        # Apply random service removals
        if loc_type == 'colony' and random.random() < 0.10:
            loc['has_jobs'] = False
        if loc_type == 'outpost' and random.random() < 0.20:
            loc['has_shops'] = False
        if loc_type == 'space_station' and random.random() < 0.05:
            loc['has_medical'] = False
        if loc_type == 'space_station' and wealth >= 6:
            loc['has_shipyard'] = random.random() < 0.4  # 40% chance for wealthy stations
        elif loc_type == 'colony' and wealth >= 7:
            loc['has_shipyard'] = random.random() < 0.3  # 30% chance for very wealthy colonies
        else:
            loc['has_shipyard'] = False
        return loc
    def _generate_derelict_description(self, name: str, location_type: str, system: str, establishment_date: str) -> str:
        """Generate descriptions for abandoned/derelict locations"""
        year = establishment_date[:4] if establishment_date else "unknown"
        
        if location_type == 'colony':
            openings = [
                f"The abandoned {name} colony drifts silent in {system}, its lights long since extinguished since {year}.",
                f"Once a thriving settlement, {name} now stands as a haunting monument to failed dreams in {system}.",
                f"Derelict since catastrophe struck in {year}, {name} colony remains a ghost town in {system}.",
                f"The skeletal remains of {name} colony cling to life support, its population fled from {system}.",
            ]
        elif location_type == 'space_station':
            openings = [
                f"The derelict {name} station tumbles slowly through {system}, its corridors echoing with memories of {year}.",
                f"Emergency power barely keeps {name} station from becoming space debris in {system}.",
                f"Abandoned since {year}, {name} station serves as a grim reminder of {system}'s dangers.",
                f"The gutted hulk of {name} drifts powerless through {system}, atmosphere leaking into the void.",
            ]
        else:  # outpost
            openings = [
                f"The deserted {name} outpost barely maintains life support in the hostile {system} frontier.",
                f"Long abandoned, {name} outpost stands as a lonely beacon of failure in {system}.",
                f"The automated systems of {name} continue their lonely vigil in {system} since {year}.",
                f"Stripped and abandoned, {name} outpost offers only shelter from {system}'s unforgiving void.",
            ]
        
        conditions = [
            "Scavenged equipment lies scattered throughout the facility.",
            "Emergency life support operates on backup power with failing systems.",
            "Makeshift repairs hold together what looters haven't already taken.",
            "Automated distress beacons still broadcast on abandoned frequencies.",
            "Hull breaches sealed with emergency patches tell stories of desperation.",
            "The few remaining inhabitants live like ghosts among the ruins."
        ]
        
        return f"{random.choice(openings)} {random.choice(conditions)}"
    def _generate_colony_description(self, name: str, system: str, establishment_date: str, wealth: int, population: int) -> str:
        """Generate varied colony descriptions based on wealth and character"""
        year = establishment_date[:4]
        
        # Opening templates based on wealth and character
        if wealth >= 7:  # Wealthy colonies
            openings = [
                f"The prosperous colony of {name} dominates the {system} system, its gleaming spires visible from orbit since {year}.",
                f"{name} stands as a crown jewel of human expansion in {system}, established {year} during the great colonial boom.",
                f"Renowned throughout the sector, {name} has been the economic heart of {system} since its founding in {year}.",
                f"The influential {name} colony commands respect across {system}, its wealth evident in every polished surface since {year}.",
                f"Since {year}, {name} has transformed from a modest settlement into {system}'s premier colonial destination."
            ]
        elif wealth >= 4:  # Average colonies
            openings = [
                f"The steady colony of {name} has weathered {system}'s challenges since its establishment in {year}.",
                f"Founded in {year}, {name} serves as a reliable anchor point in the {system} system.",
                f"{name} colony has grown methodically since {year}, becoming an integral part of {system}'s infrastructure.",
                f"Established {year}, {name} represents the determined spirit of {system} system colonization.",
                f"The industrious settlement of {name} has maintained steady growth in {system} since {year}."
            ]
        else:  # Poor colonies
            openings = [
                f"The struggling colony of {name} barely clings to survival in the harsh {system} system since {year}.",
                f"Founded in {year} during harder times, {name} endures the daily challenges of life in {system}.",
                f"{name} colony scratches out a meager existence in {system}, its founders' {year} dreams long faded.",
                f"The frontier outpost of {name} has survived against the odds in {system} since {year}.",
                f"Established {year}, {name} remains a testament to human stubbornness in the unforgiving {system} system."
            ]
        
        # Specialization and character details
        specializations = []
        
        if wealth >= 6:
            specializations.extend([
                "Its advanced hydroponics bays produce exotic foods exported across the sector.",
                "Massive automated factories churn out precision components for starship construction.",
                "The colony's renowned research facilities attract scientists from across human space.",
                "Gleaming residential towers house workers in climate-controlled luxury.",
                "State-of-the-art mining operations extract rare minerals from the system's asteroids.",
                "Its prestigious academy trains the next generation of colonial administrators.",
                "Sophisticated atmospheric processors maintain perfect environmental conditions.",
                "The colony's cultural centers showcase the finest arts from across the frontier."
            ])
        elif wealth >= 3:
            specializations.extend([
                "Sprawling agricultural domes provide essential food supplies for the region.",
                "Its workshops produce reliable tools and equipment for neighboring settlements.",
                "The colony's medical facilities serve patients from across the system.",
                "Modest but efficient factories manufacture basic goods for local trade.",
                "Its transportation hub connects remote outposts throughout the system.",
                "The settlement's technical schools train skilled workers for the colonial workforce.",
                "Basic atmospheric processing keeps the colony's air breathable and stable.",
                "Local markets bustle with traders from throughout the system."
            ])
        else:
            specializations.extend([
                "Makeshift shelters cobbled from salvaged ship parts house the struggling population.",
                "Its jury-rigged life support systems require constant maintenance to function.",
                "The colony's single cantina serves as meeting hall, market, and social center.",
                "Desperate miners work dangerous claims hoping to strike it rich.",
                "Patched atmospheric domes leak precious air into the void of space.",
                "The settlement's workshop repairs anything for anyone willing to pay.",
                "Its ramshackle structures huddle together against the system's harsh environment.",
                "Basic hydroponics barely provide enough nutrition to keep colonists alive."
            ])
        
        # Environmental and atmospheric details
        environments = []
        
        if population > 2000:
            environments.extend([
                "Streets teem with activity as thousands go about their daily business.",
                "The colony's districts each maintain their own distinct character and culture.",
                "Public transport systems efficiently move citizens between residential and work areas.",
                "Multiple shifts ensure the colony operates continuously around the clock."
            ])
        elif population > 500:
            environments.extend([
                "The community maintains a close-knit atmosphere where everyone knows their neighbors.",
                "Well-worn paths connect the various sections of the growing settlement.",
                "Regular town meetings in the central plaza keep citizens informed and involved.",
                "The colony's compact layout makes everything accessible within a short walk."
            ])
        else:
            environments.extend([
                "Every resident plays multiple roles to keep the small community functioning.",
                "The tight-knit population faces each challenge together as an extended family.",
                "Simple prefab structures cluster around the central life support facility.",
                "Harsh conditions forge unbreakable bonds between the hardy colonists."
            ])
        
        # Combine elements
        opening = random.choice(openings)
        specialization = random.choice(specializations)
        environment = random.choice(environments)
        
        return f"{opening} {specialization} {environment}"

    def _generate_station_description(self, name: str, system: str, establishment_date: str, wealth: int, population: int) -> str:
        """Generate varied space station descriptions"""
        year = establishment_date[:4]
        
        # Station type and opening based on wealth
        if wealth >= 8:  # Premium stations
            openings = [
                f"The magnificent {name} orbital complex has served as {system}'s premier space facility since {year}.",
                f"Gleaming in {system}'s starlight, {name} station represents the pinnacle of orbital engineering since {year}.",
                f"The prestigious {name} facility has commanded {system}'s spacelanes since its construction in {year}.",
                f"Since {year}, {name} has stood as the crown jewel of {system}'s orbital infrastructure.",
                f"The luxurious {name} station has catered to the sector's elite since its inauguration in {year}."
            ]
        elif wealth >= 5:  # Standard stations
            openings = [
                f"The reliable {name} orbital platform has anchored {system}'s space traffic since {year}.",
                f"Established {year}, {name} station serves as a crucial waypoint in the {system} system.",
                f"The sturdy {name} facility has weathered {system}'s challenges since its construction in {year}.",
                f"Since {year}, {name} has maintained steady operations in {system}'s orbital space.",
                f"The practical {name} station fulfills its role in {system} with quiet efficiency since {year}."
            ]
        else:  # Budget stations
            openings = [
                f"The aging {name} station barely maintains operations in {system} since its rushed construction in {year}.",
                f"Built on a shoestring budget in {year}, {name} somehow keeps functioning in {system}.",
                f"The patchwork {name} facility cobbles together services for {system} travelers since {year}.",
                f"Since {year}, {name} has scraped by on minimal funding in the {system} system.",
                f"The no-frills {name} station provides basic services to {system} with stubborn persistence since {year}."
            ]
        
        # Station functions and features
        functions = []
        
        if wealth >= 7:
            functions.extend([
                "Its premium docking bays accommodate the largest luxury liners and corporate vessels.",
                "Exclusive shopping promenades offer rare goods from across human space.",
                "The station's diplomatic quarters host high-level negotiations between star systems.",
                "State-of-the-art laboratories conduct cutting-edge research in zero gravity.",
                "Luxurious entertainment districts provide refined pleasures for wealthy travelers.",
                "Advanced medical facilities offer treatments unavailable on planetary surfaces.",
                "The station's concert halls feature renowned performers from across the galaxy.",
                "Private quarters rival the finest hotels on any core world."
            ])
        elif wealth >= 4:
            functions.extend([
                "Standard docking facilities efficiently handle routine cargo and passenger traffic.",
                "The station's markets provide essential supplies for ships and crews.",
                "Its maintenance bays offer reliable repairs for most classes of spacecraft.",
                "Central administration coordinates shipping schedules throughout the system.",
                "The facility's recreational areas help travelers unwind between journeys.",
                "Medical stations provide standard healthcare for spacers and visitors.",
                "Its communications arrays relay messages across the system's trade networks.",
                "Cargo holds temporarily store goods in transit between distant worlds."
            ])
        else:
            functions.extend([
                "Cramped docking clamps barely accommodate visiting ships safely.",
                "The station's single cantina doubles as marketplace and meeting hall.",
                "Its makeshift repair bay handles emergency fixes with salvaged parts.",
                "A skeleton crew keeps critical life support and docking systems operational.",
                "Basic sleeping quarters offer little more than a bunk and storage locker.",
                "The station's medical bay consists of a first aid kit and prayer.",
                "Jury-rigged communications equipment sometimes connects to the outside galaxy.",
                "Cargo areas serve double duty as additional living space when needed."
            ])
        
        # Operational details
        operations = []
        
        if population > 5000:
            operations.extend([
                "Multiple shifts ensure the massive facility operates continuously.",
                "Thousands of workers maintain the complex's countless systems and services.",
                "The station's districts each specialize in different aspects of space commerce.",
                "Advanced automation handles routine tasks while humans focus on complex decisions."
            ])
        elif population > 1000:
            operations.extend([
                "A dedicated crew keeps all essential systems running smoothly.",
                "The station's compact design allows efficient movement throughout the facility.",
                "Department heads coordinate closely to maintain optimal operations.",
                "Regular maintenance schedules keep the aging infrastructure functional."
            ])
        else:
            operations.extend([
                "A small but determined crew performs multiple duties to keep operations running.",
                "Every person aboard plays crucial roles in the station's survival.",
                "Makeshift solutions and creative repairs keep the facility marginally operational.",
                "The skeleton crew works around the clock to maintain basic services."
            ])
        
        opening = random.choice(openings)
        function = random.choice(functions)
        operation = random.choice(operations)
        
        return f"{opening} {function} {operation}"
    async def _find_route_to_destination(self, start_location_id: int, end_location_id: int, max_jumps: int = 5) -> Optional[List[int]]:
        """
        Finds a route between two locations using a Breadth-First Search (BFS) algorithm.
        Returns a list of location_ids representing the path, or None if no path is found within max_jumps.
        """
        if start_location_id == end_location_id:
            return [start_location_id]

        # Fetch all active corridors to build the graph
        corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = 1",
            fetch='all'
        )

        graph = {}
        for origin, dest in corridors:
            if origin not in graph:
                graph[origin] = []
            if dest not in graph:
                graph[dest] = []
            graph[origin].append(dest)
            graph[dest].append(origin) # Assuming bidirectional corridors for pathfinding

        # BFS initialization
        queue = collections.deque([(start_location_id, [start_location_id])])
        visited = {start_location_id}

        while queue:
            current_location, path = queue.popleft()

            if current_location == end_location_id:
                return path

            if len(path) - 1 >= max_jumps: # Check jump limit
                continue

            for neighbor in graph.get(current_location, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    queue.append((neighbor, new_path))
        
        return None # No path found
    def _generate_outpost_description(self, name: str, system: str, establishment_date: str, wealth: int, population: int) -> str:
        """Generate varied outpost descriptions"""
        year = establishment_date[:4]
        
        # Outpost character based on wealth
        if wealth >= 4:  # Well-funded outposts
            openings = [
                f"The well-equipped {name} outpost has monitored {system}'s frontier since {year}.",
                f"Established {year}, {name} serves as a reliable beacon in the {system} system's remote reaches.",
                f"The strategic {name} facility has maintained its watch over {system} since {year}.",
                f"Since {year}, {name} has provided essential services to {system}'s far-flung territories.",
                f"The efficient {name} outpost has safeguarded {system}'s periphery since its establishment in {year}."
            ]
        else:  # Basic outposts
            openings = [
                f"The isolated {name} outpost clings to existence in {system}'s hostile frontier since {year}.",
                f"Built from necessity in {year}, {name} barely maintains a foothold in the {system} system.",
                f"The remote {name} facility has endured {system}'s challenges through determination since {year}.",
                f"Since {year}, {name} has scraped by on the edge of civilization in {system}.",
                f"The hardy {name} outpost refuses to surrender to {system}'s unforgiving environment since {year}."
            ]
        
        # Purpose and function
        purposes = []
        
        if wealth >= 3:
            purposes.extend([
                "Its sensor arrays provide early warning of corridor shifts and spatial anomalies.",
                "The outpost's communication relay connects isolated settlements to the wider galaxy.",
                "Well-stocked supply depot offers emergency provisions to stranded travelers.",
                "Its research station monitors local stellar phenomena and space weather.",
                "The facility serves as a customs checkpoint for traffic entering the system.",
                "Emergency medical facilities provide critical care for spacers in distress.",
                "Its maintenance shop handles urgent repairs for ships damaged in transit.",
                "The outpost's staff coordinates search and rescue operations throughout the region."
            ])
        else:
            purposes.extend([
                "A basic radio beacon helps lost ships find their way to safety.",
                "The outpost's fuel depot provides emergency refueling for desperate travelers.",
                "Its small workshop attempts repairs with whatever spare parts are available.",
                "Emergency shelters offer minimal protection from the system's harsh environment.",
                "The facility's medical kit treats injuries when no other help is available.",
                "Basic atmospheric processors maintain breathable air for the tiny crew.",
                "Its food supplies stretch to feed unexpected visitors in emergencies.",
                "The outpost serves as a final waypoint before entering the deep frontier."
            ])
        
        # Living conditions and atmosphere
        conditions = []
        
        if population > 30:
            conditions.extend([
                "The expanded crew maintains professional standards despite their isolation.",
                "Regular supply runs keep the outpost well-stocked and connected to civilization.",
                "Multiple shifts ensure someone is always monitoring the frontier zones.",
                "The facility's rec room provides essential social space for the resident staff."
            ])
        elif population > 10:
            conditions.extend([
                "A tight-knit crew has formed an almost familial bond over years of isolation.",
                "The small team rotates duties to prevent anyone from feeling overwhelmed.",
                "Shared meals and stories help maintain morale through the long watches.",
                "Everyone pulls together when emergencies strike the remote facility."
            ])
        else:
            conditions.extend([
                "A lone operator or tiny crew maintains the facility through sheer determination.",
                "The isolation weighs heavily on those who choose to serve in such remote postings.",
                "Every supply delivery is a major event breaking the endless routine.",
                "The skeleton crew relies on automation to handle most routine tasks."
            ])
        
        opening = random.choice(openings)
        purpose = random.choice(purposes)
        condition = random.choice(conditions)
        
        return f"{opening} {purpose} {condition}"

        self.db.execute_query(
            '''INSERT INTO locations 
               (name, location_type, description, wealth_level, population,
                x_coord, y_coord, system_name, established_date, has_jobs, has_shops, has_medical, 
                has_repairs, has_fuel, has_upgrades, has_black_market, is_generated, is_derelict) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (location['name'], location['type'], location['description'], 
             location['wealth_level'], location['population'], location['x_coord'], 
             location['y_coord'], location['system_name'], location['established_date'],
             location['has_jobs'], location['has_shops'], location['has_medical'], 
             location['has_repairs'], location['has_fuel'], location['has_upgrades'],
             location['has_black_market'], location['is_generated'], location['is_derelict'])
        )
            
        return self.db.execute_query(
            "SELECT location_id FROM locations WHERE name = ? ORDER BY location_id DESC LIMIT 1",
            (location['name'],),
            fetch='one'
        )[0]
        
    async def _assign_federal_supplies(self, conn, major_locations: List[Dict]) -> int:
        """
        Enhanced federal supply depot assignment with actual item implementation
        """
        from item_config import ItemConfig
        
        locations_to_update = []
        federal_items_to_insert = []
        
        # Define what federal depots actually offer
        def get_federal_supply_items():
            """Get items that federal depots should stock"""
            federal_items = []
            
            # High-quality medical supplies
            medical_items = ItemConfig.get_items_by_type("medical")
            for item in medical_items:
                federal_items.append((item, "medical", "Federal medical supplies"))
            
            # Military-grade equipment
            equipment_items = ItemConfig.get_items_by_type("equipment") 
            for item in equipment_items:
                item_data = ItemConfig.get_item_definition(item)
                if item_data.get("rarity") in ["uncommon", "rare"]:
                    federal_items.append((item, "equipment", "Military surplus equipment"))
            
            # Premium fuel
            fuel_items = ItemConfig.get_items_by_type("fuel")
            for item in fuel_items:
                federal_items.append((item, "fuel", "Federal fuel reserves"))
            
            # Authorized upgrades
            upgrade_items = ItemConfig.get_items_by_type("upgrade")
            for item in upgrade_items:
                federal_items.append((item, "upgrade", "Authorized ship modifications"))
            
            # Federal exclusives
            exclusive_items = [
                ("Federal ID Card", "documents", "Official federal identification"),
                ("Military Rations", "consumable", "High-quality preserved food"),
                ("Federal Comm Codes", "data", "Access to federal communication networks"),
                ("Loyalty Certification", "documents", "Proof of federal allegiance"),
                ("Federal Permit", "documents", "Authorization for restricted activities"),
            ]
            federal_items.extend(exclusive_items)
            
            return federal_items

        federal_item_pool = get_federal_supply_items()

        for location in major_locations:
            federal_chance = 0.0
            
            # Enhanced spawn logic (as before)
            if location['wealth_level'] >= 9:
                federal_chance = 0.40
            elif location['wealth_level'] >= 8:
                federal_chance = 0.30
            elif location['wealth_level'] >= 7:
                federal_chance = 0.20
            elif location['wealth_level'] == 6:
                federal_chance = 0.12
            elif location['wealth_level'] == 5:
                federal_chance = 0.05
            
            # Location type modifiers
            if location['type'] == 'space_station':
                federal_chance *= 1.4
            elif location['type'] == 'colony':
                federal_chance *= 1.0
            elif location['type'] == 'outpost':
                federal_chance *= 0.6
                
            # Population modifiers
            if location['population'] > 2000:
                federal_chance *= 1.3
            elif location['population'] > 1000:
                federal_chance *= 1.1
            elif location['population'] < 200:
                federal_chance *= 0.7
                
            # Special cases
            if location['name'] == 'Earth':
                federal_chance = 1.0
                
            if location.get('has_black_market', False) or location.get('is_derelict', False):
                federal_chance = 0.0
            
            if location['name'] != 'Earth':
                federal_chance = min(federal_chance, 0.50)
            
            if federal_chance > 0 and random.random() < federal_chance:
                gets_shipyard = location.get('has_shipyard', False)
                if not gets_shipyard and location['wealth_level'] >= 8:
                    gets_shipyard = random.random() < 0.8
                elif not gets_shipyard and location['wealth_level'] >= 6:
                    gets_shipyard = random.random() < 0.5
                    
                locations_to_update.append((
                    True,  # has_federal_supplies
                    True,  # has_upgrades
                    gets_shipyard,  # has_shipyard
                    location['id']
                ))
                
                # Generate federal supply items
                item_count = random.randint(4, 8)  # Federal depots are well-stocked
                selected_items = random.sample(federal_item_pool, min(item_count, len(federal_item_pool)))
                
                for item_name, item_type, description in selected_items:
                    item_data = ItemConfig.get_item_definition(item_name)
                    
                    if item_data:
                        # Federal pricing - slight discount from base value
                        base_price = item_data.get("base_value", 100)
                        federal_discount = random.uniform(0.8, 0.9)  # 10-20% discount
                        final_price = int(base_price * federal_discount)
                        stock = random.randint(3, 8)  # Well-stocked
                    else:
                        # Exclusive items
                        final_price = random.randint(500, 2000)
                        stock = random.randint(2, 5)
                    
                    federal_items_to_insert.append(
                        (location['id'], item_name, item_type, final_price, description, stock, "federal")
                    )
                
                print(f"🏛️  Created federal depot at {location['name']}")
        
        # Database operations
        if locations_to_update:
            update_query = """UPDATE locations SET 
                                has_federal_supplies = ?, 
                                has_upgrades = ?, 
                                has_shipyard = ? 
                              WHERE location_id = ?"""
            self.db.executemany_in_transaction(conn, update_query, locations_to_update)
        
        # Insert federal supply items into shop_items table with federal tag
        if federal_items_to_insert:
            self.db.executemany_in_transaction(
                conn,
                '''INSERT INTO shop_items (location_id, item_name, item_type, price, description, stock, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                federal_items_to_insert
            )
            
        return len(locations_to_update)
        
    def update_location_alignment_rules(self):
        """Update locations to enforce alignment-based spawning rules"""
        
        # Mark high-wealth locations as federal/loyal zones
        self.db.execute_query(
            """UPDATE locations 
               SET has_federal_supplies = 1 
               WHERE wealth_level >= 8 AND has_black_market = 0""",
        )
        
        # Mark low-wealth black market locations as bandit zones  
        self.db.execute_query(
            """UPDATE locations 
               SET has_black_market = 1 
               WHERE wealth_level <= 3 AND has_federal_supplies = 0 AND random() % 10 = 0""",
        )
        
        print("✅ Updated location alignment rules")

    def enforce_npc_alignment_at_location(self, location_id: int):
        """Ensure NPCs at a location match its alignment requirements"""
        
        # Get location requirements
        location_data = self.db.execute_query(
            """SELECT has_black_market, has_federal_supplies, wealth_level 
               FROM locations WHERE location_id = ?""",
            (location_id,),
            fetch='one'
        )
        
        if not location_data:
            return
        
        has_black_market, has_federal_supplies, wealth_level = location_data
        
        # Determine required alignment
        required_alignment = None
        if has_black_market:
            required_alignment = "bandit"
        elif has_federal_supplies or wealth_level >= 8:
            required_alignment = "loyal"
        
        if required_alignment:
            # Update static NPCs to match required alignment
            wrong_npcs = self.db.execute_query(
                """SELECT npc_id FROM static_npcs 
                   WHERE location_id = ? AND alignment != ? AND is_alive = 1""",
                (location_id, required_alignment),
                fetch='all'
            )
            
            for (npc_id,) in wrong_npcs:
                # Kill wrong-aligned NPCs and schedule respawn with correct alignment
                self.db.execute_query(
                    "UPDATE static_npcs SET is_alive = 0 WHERE npc_id = ?",
                    (npc_id,)
                )
                
                # Schedule respawn with correct alignment
                respawn_time = datetime.now() + timedelta(minutes=random.randint(30, 120))
                self.db.execute_query(
                    """INSERT INTO npc_respawn_queue 
                       (original_npc_id, location_id, scheduled_respawn_time, npc_data)
                       VALUES (?, ?, ?, ?)""",
                    (npc_id, location_id, respawn_time.isoformat(), f"alignment:{required_alignment}")
                )
            
            # Update dynamic NPCs that shouldn't be here
            self.db.execute_query(
                """UPDATE dynamic_npcs 
                   SET current_location = NULL, destination_location = NULL
                   WHERE current_location = ? AND alignment != ? AND is_alive = 1""",
                (location_id, required_alignment)
            )
    # =================================================================================
    # OPTIMIZED CORRIDOR PLANNING (REPLACEMENT FOR _plan_corridor_routes and helpers)
    # =================================================================================

# In _plan_corridor_routes method, replace the existing method with proper variable handling:

    async def _plan_corridor_routes(self, major_locations: List[Dict]) -> List[Dict]:
        """
        Plans logical corridor routes with improved connectivity and performance for large galaxies.
        This optimized version uses a spatial grid to accelerate proximity searches,
        avoiding O(n^2) complexity issues that cause hangs.
        """
        if not major_locations:
            return []

        num_locs = len(major_locations)
        print(f"🛣️ Planning routes for {num_locs} locations using spatial grid optimization...")

        # Step 0: Create the spatial grid for efficient lookups.
        grid_size = 75
        spatial_grid = self._create_spatial_grid(major_locations, grid_size)
        location_map = {loc['id']: loc for loc in major_locations}
        
        # Use a set to track created connections (as pairs of sorted IDs) to avoid duplicates.
        connected_pairs = set()
        routes = []

        # Step tracking variables
        total_steps = 5
        current_step = 0

        # Step 1: Create a Minimum Spanning Tree (MST) to ensure base connectivity.
        current_step += 1
        print("  - Step 1/5: Building Minimum Spanning Tree...")
        mst_routes = await self._create_mst_optimized(major_locations, location_map, connected_pairs)
        routes.extend(mst_routes)
        
        # Yield and progress for Step 1
        await asyncio.sleep(0.2)
        if num_locs > 100:
            print(f"  ✓ Step 1/5 complete - {len(mst_routes)} MST routes created")
            
        # Step 2: Add hub connections (stations to high-value colonies).
        current_step += 1
        print("  - Step 2/5: Creating hub connections...")
        hub_routes = await self._create_hub_connections_optimized(major_locations, location_map, spatial_grid, grid_size, connected_pairs)
        routes.extend(hub_routes)
        
        # Yield and progress for Step 2
        await asyncio.sleep(0.15)
        if num_locs > 100:
            print(f"  ✓ Step 2/5 complete - {len(hub_routes)} hub routes created")
            
        # Step 3: Add redundant connections for resilience.
        current_step += 1
        print("  - Step 3/5: Adding redundant connections...")
        redundant_routes = await self._add_redundant_connections_optimized(major_locations, location_map, spatial_grid, grid_size, connected_pairs)
        routes.extend(redundant_routes)
        
        # Yield and progress for Step 3
        await asyncio.sleep(0.15)
        if num_locs > 100:
            print(f"  ✓ Step 3/5 complete - {len(redundant_routes)} redundant routes created")
            
        # Step 4: Create long-range "bridge" connections to link distant regions.
        current_step += 1
        print("  - Step 4/5: Forging long-range bridges...")
        bridge_routes = await self._create_regional_bridges_optimized(major_locations, location_map, spatial_grid, connected_pairs)
        routes.extend(bridge_routes)
        
        # Yield and progress for Step 4
        await asyncio.sleep(0.1)
        if num_locs > 100:
            print(f"  ✓ Step 4/5 complete - {len(bridge_routes)} bridge routes created")
            
        # Step 5: Final validation and fixing of any isolated clusters.
        current_step += 1
        print("  - Step 5/5: Validating and fixing connectivity...")
        final_routes = await self._validate_and_fix_connectivity_optimized(major_locations, routes, location_map)
        
        print(f"✅ Route planning complete. Total unique routes planned: {len(final_routes)}")
        return final_routes

    def _create_spatial_grid(self, locations: List[Dict], grid_size: int) -> Dict[Tuple[int, int], List[Dict]]:
        """
        Partitions locations into a grid for efficient spatial queries.
        Returns a dictionary where keys are (grid_x, grid_y) tuples and values are lists of locations.
        """
        grid = {}
        for loc in locations:
            grid_x = int(loc['x_coord'] // grid_size)
            grid_y = int(loc['y_coord'] // grid_size)
            if (grid_x, grid_y) not in grid:
                grid[(grid_x, grid_y)] = []
            grid[(grid_x, grid_y)].append(loc)
        return grid

    def _get_nearby_cells(self, grid_x: int, grid_y: int, radius: int = 1) -> List[Tuple[int, int]]:
        """
        Gets the coordinates of grid cells within a given radius of a central cell.
        """
        cells = []
        for i in range(-radius, radius + 1):
            for j in range(-radius, radius + 1):
                cells.append((grid_x + i, grid_y + j))
        return cells

    async def _create_mst_optimized(self, locations: List[Dict], location_map: Dict, connected_pairs: set) -> List[Dict]:
        """Creates a Minimum Spanning Tree using Prim's algorithm with a priority queue (heapq)."""
        if not locations:
            return []
        
        import heapq

        routes = []
        start_node_id = locations[0]['id']
        nodes_to_visit = [(0, start_node_id, start_node_id)]
        visited = set()
        nodes_processed = 0

        while nodes_to_visit and len(visited) < len(locations):
            distance, current_node_id, from_node_id = heapq.heappop(nodes_to_visit)

            if current_node_id in visited:
                continue
            
            visited.add(current_node_id)
            nodes_processed += 1

            # Add a route if it's not the starting node
            if current_node_id != from_node_id:
                from_loc = location_map[from_node_id]
                to_loc = location_map[current_node_id]
                
                pair = tuple(sorted((from_node_id, current_node_id)))
                if pair not in connected_pairs:
                    routes.append({
                        'from': from_loc,
                        'to': to_loc,
                        'importance': 'critical',
                        'distance': distance
                    })
                    connected_pairs.add(pair)

            # Find neighbors and add them to the priority queue
            current_loc = location_map[current_node_id]
            for other_loc in locations:
                if other_loc['id'] not in visited:
                    dist = self._calculate_distance(current_loc, other_loc)
                    heapq.heappush(nodes_to_visit, (dist, other_loc['id'], current_node_id))
            
            # Yield control periodically
            if nodes_processed % 5 == 0:
                await asyncio.sleep(0)
        
        return routes

    async def _create_hub_connections_optimized(self, locations: List[Dict], location_map: Dict, spatial_grid: Dict, grid_size: int, connected_pairs: set) -> List[Dict]:
        """
        Creates hub connections from space stations to nearby wealthy colonies using the spatial grid.
        """
        routes = []
        stations = [loc for loc in locations if loc['type'] == 'space_station']
        wealthy_colonies = [loc for loc in locations if loc['type'] == 'colony' and loc['wealth_level'] >= 6]

        if not stations or not wealthy_colonies:
            return []

        for station in stations:
            # Connect to 2-4 nearby wealthy colonies.
            nearby_colonies = []
            grid_x = int(station['x_coord'] // grid_size)
            grid_y = int(station['y_coord'] // grid_size)
            
            # Search in an expanding radius of grid cells.
            for radius in range(3): # Search up to 2 cells away
                cells_to_check = self._get_nearby_cells(grid_x, grid_y, radius)
                for cell_coord in cells_to_check:
                    if cell_coord in spatial_grid:
                        for loc in spatial_grid[cell_coord]:
                            if loc['type'] == 'colony' and loc['wealth_level'] >= 6:
                                nearby_colonies.append(loc)
                if len(nearby_colonies) >= 5: # Found enough candidates
                    break
            
            # Sort by distance and pick the closest ones.
            nearby_colonies.sort(key=lambda c: self._calculate_distance(station, c))
            
            connections_made = 0
            for colony in nearby_colonies:
                if connections_made >= random.randint(2, 4):
                    break
                
                pair = tuple(sorted((station['id'], colony['id'])))
                if pair not in connected_pairs:
                    routes.append({
                        'from': station,
                        'to': colony,
                        'importance': 'high',
                        'distance': self._calculate_distance(station, colony)
                    })
                    connected_pairs.add(pair)
                    connections_made += 1
        return routes
        
    async def _add_redundant_connections_optimized(self, locations: List[Dict], location_map: Dict, spatial_grid: Dict, grid_size: int, connected_pairs: set) -> List[Dict]:
        """
        Adds redundant connections to locations with low connectivity using the spatial grid.
        """
        routes = []
        
        # First, build a connectivity map.
        connectivity_map = {loc['id']: 0 for loc in locations}
        for pair in connected_pairs:
            connectivity_map[pair[0]] += 1
            connectivity_map[pair[1]] += 1
            
        # Identify locations with 1 or 2 connections.
        low_connectivity_locs = [loc for loc in locations if connectivity_map[loc['id']] <= 2]
        
        print(f"    Adding redundant connections for {len(low_connectivity_locs)} low-connectivity locations...")
        
        processed = 0
        for loc in low_connectivity_locs:
            # Yield control every 10 locations
            if processed % 10 == 0:
                await asyncio.sleep(0.01)
            
            # Find 1-2 nearby locations to connect to.
            nearby_candidates = []
            grid_x = int(loc['x_coord'] // grid_size)
            grid_y = int(loc['y_coord'] // grid_size)

            # Search nearby grid cells with expanding radius if needed
            max_candidates = 20  # Limit candidates to prevent hanging
            for radius in range(1, 4):  # Try expanding radius if not enough candidates
                if len(nearby_candidates) >= max_candidates:
                    break
                    
                cells_to_check = self._get_nearby_cells(grid_x, grid_y, radius=radius)
                for cell_coord in cells_to_check:
                    if cell_coord in spatial_grid:
                        for candidate in spatial_grid[cell_coord]:
                            if candidate['id'] != loc['id']:
                                # Quick distance check before adding to candidates
                                distance = self._calculate_distance(loc, candidate)
                                if distance < 100:  # Pre-filter by distance
                                    nearby_candidates.append(candidate)
                                    if len(nearby_candidates) >= max_candidates:
                                        break
                        if len(nearby_candidates) >= max_candidates:
                            break
                
                # If we found some candidates, don't expand radius unnecessarily
                if len(nearby_candidates) >= 5:
                    break
            
            # Sort by distance (but limit to reasonable number)
            nearby_candidates = nearby_candidates[:max_candidates]
            nearby_candidates.sort(key=lambda c: self._calculate_distance(loc, c))
            
            connections_to_add = max(0, min(2, 2 - connectivity_map[loc['id']]))  # Ensure non-negative
            connections_made = 0
            
            for target in nearby_candidates:
                if connections_made >= connections_to_add:
                    break
                
                pair = tuple(sorted((loc['id'], target['id'])))
                if pair not in connected_pairs:
                    distance = self._calculate_distance(loc, target)
                    if distance < 100: # Avoid overly long redundant links
                        routes.append({
                            'from': loc,
                            'to': target,
                            'importance': 'low',
                            'distance': distance
                        })
                        connected_pairs.add(pair)
                        # Update connectivity map for future iterations in this loop
                        connectivity_map[loc['id']] += 1
                        connectivity_map[target['id']] += 1
                        connections_made += 1
            
            processed += 1
            
            # Progress reporting for large galaxies
            if len(low_connectivity_locs) > 50 and processed % 25 == 0:
                progress = (processed / len(low_connectivity_locs)) * 100
                print(f"      Redundant connections progress: {progress:.0f}% ({processed}/{len(low_connectivity_locs)})")
        
        print(f"    Added {len(routes)} redundant connections")
        return routes

    async def _create_regional_bridges_optimized(self, locations: List[Dict], location_map: Dict, spatial_grid: Dict, connected_pairs: set) -> List[Dict]:
        """
        Creates long-range "bridge" connections between distant but important locations.
        """
        routes = []
        # Identify important locations (stations or very wealthy colonies) as potential anchors.
        anchors = [loc for loc in locations if loc['type'] == 'space_station' or loc['wealth_level'] >= 8]
        if len(anchors) < 4: # Not enough anchors to create meaningful bridges
            return []

        # For each anchor, find a distant anchor to connect to.
        for anchor in anchors:
            # Sort other anchors by distance, from farthest to closest.
            distant_anchors = sorted(anchors, key=lambda a: self._calculate_distance(anchor, a), reverse=True)
            
            # Try to connect to the farthest one that isn't already connected.
            for target_anchor in distant_anchors:
                if anchor['id'] == target_anchor['id']:
                    continue
                
                pair = tuple(sorted((anchor['id'], target_anchor['id'])))
                if pair not in connected_pairs:
                    routes.append({
                        'from': anchor,
                        'to': target_anchor,
                        'importance': 'medium',
                        'distance': self._calculate_distance(anchor, target_anchor)
                    })
                    connected_pairs.add(pair)
                    break # Move to the next anchor
        return routes

    async def _validate_and_fix_connectivity_optimized(self, all_locations: List[Dict], routes: List[Dict], location_map: Dict) -> List[Dict]:
        """
        Validates overall connectivity and adds connections to fix any isolated clusters.
        """
        if not all_locations:
            return []
            
        # Build adjacency list from the routes planned so far.
        graph = {loc['id']: set() for loc in all_locations}
        for route in routes:
            from_id, to_id = route['from']['id'], route['to']['id']
            graph[from_id].add(to_id)
            graph[to_id].add(from_id)
        
        # Find all connected components (clusters of locations) using Breadth-First Search.
        visited = set()
        components = []
        for loc in all_locations:
            if loc['id'] not in visited:
                component = set()
                q = [loc['id']]
                visited.add(loc['id'])
                component.add(loc['id'])
                
                head = 0
                while head < len(q):
                    current_id = q[head]
                    head += 1
                    for neighbor_id in graph[current_id]:
                        if neighbor_id not in visited:
                            visited.add(neighbor_id)
                            component.add(neighbor_id)
                            q.append(neighbor_id)
                components.append(list(component))
        
        # If there's more than one component, the galaxy is fragmented. We must connect them.
        if len(components) > 1:
            print(f"🔧 Found {len(components)} disconnected components, fixing connectivity...")
            
            # Sort components by size to connect smaller ones to the largest one.
            components.sort(key=len, reverse=True)
            main_component = components[0]
            
            for i in range(1, len(components)):
                isolated_component = components[i]
                
                # Find the closest pair of locations between the main component and the isolated one.
                best_connection = None
                min_dist = float('inf')
                
                # To avoid n*m checks, we check a sample from each component.
                sample_main = random.sample(main_component, min(len(main_component), 30))
                sample_isolated = random.sample(isolated_component, min(len(isolated_component), 30))

                for main_loc_id in sample_main:
                    for iso_loc_id in sample_isolated:
                        dist = self._calculate_distance(location_map[main_loc_id], location_map[iso_loc_id])
                        if dist < min_dist:
                            min_dist = dist
                            best_connection = (location_map[main_loc_id], location_map[iso_loc_id])
                
                if best_connection:
                    from_loc, to_loc = best_connection
                    print(f"🌉 Added emergency bridge connection: {from_loc['name']} ↔ {to_loc['name']}")
                    routes.append({
                        'from': from_loc,
                        'to': to_loc,
                        'importance': 'critical',
                        'distance': min_dist
                    })
                    # Add these new connections to the graph to merge the components for the next iteration.
                    graph[from_loc['id']].add(to_loc['id'])
                    graph[to_loc['id']].add(from_loc['id'])
                    # Conceptually merge the components for the next loop
                    main_component.extend(isolated_component)

        return routes
        
    async def _generate_homes_for_locations(self, locations: List[Dict]) -> int:
        """Generate homes for colonies and space stations"""
        total_homes = 0
        
        for location in locations:
            if location.get('is_derelict', False):
                continue  # No homes in derelict locations
                
            homes_to_generate = 0
            home_type = None
            
            if location['type'] == 'colony':
                # 15% chance for colonies
                if random.random() < 0.45:
                    homes_to_generate = random.randint(1, 5)
                    home_type = "Colonist Dwelling"
            elif location['type'] == 'space_station':
                # 5% chance for space stations
                if random.random() < 0.35:
                    homes_to_generate = random.randint(1, 3)
                    home_type = "Residential Unit"
            
            if homes_to_generate > 0:
                for i in range(homes_to_generate):
                    # Generate unique home number
                    home_number = random.randint(100, 999)
                    home_name = f"{home_type} {home_number}"
                    
                    # Calculate price based on wealth
                    base_price = 15000 if location['type'] == 'colony' else 9000
                    wealth_multiplier = max(0.5, location['wealth_level'] / 5)
                    price = int(base_price * wealth_multiplier)
                    
                    # Generate interior description
                    if location['type'] == 'colony':
                        interior_descriptions = [
                            "A cozy dwelling with synthetic wood floors and a view of the colony plaza.",
                            "A modest home featuring efficient space utilization and modern amenities.",
                            "A comfortable residence with climate-controlled rooms and a small garden area.",
                            "A well-maintained dwelling with panoramic windows overlooking the colony.",
                            "A compact but elegant home with customizable lighting and temperature controls."
                        ]
                    else:  # space station
                        interior_descriptions = [
                            "A sleek residential unit with anti-gravity fixtures and stellar views.",
                            "A modern living space featuring advanced life support and entertainment systems.",
                            "A comfortable unit with adjustable artificial gravity and mood lighting.",
                            "An efficient residential module with space-saving design and holographic windows.",
                            "A premium unit offering panoramic viewports and state-of-the-art amenities."
                        ]
                    
                    interior_desc = random.choice(interior_descriptions)
                    
                    # Generate random activities (2-4 per home)
                    from utils.home_activities import HomeActivityManager
                    activity_manager = HomeActivityManager(self.bot)
                    num_activities = random.randint(2, 4)
                    activities = activity_manager.generate_random_activities(num_activities)
                    
                    # Calculate value modifier based on activities
                    value_modifier = 1.0 + (len(activities) * 0.05)
                    
                    # Insert home into database
                    self.db.execute_query(
                        '''INSERT INTO location_homes 
                           (location_id, home_type, home_name, price, interior_description, 
                            activities, value_modifier, is_available)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1)''',
                        (location['id'], home_type, home_name, price, interior_desc,
                         ','.join(activities), value_modifier)
                    )

                    # Get the home_id of the just-inserted home
                    home_id = self.db.execute_query(
                        '''SELECT home_id FROM location_homes 
                           WHERE location_id = ? AND home_name = ? 
                           ORDER BY home_id DESC LIMIT 1''',
                        (location['id'], home_name),
                        fetch='one'
                    )[0]
                    
                    # Insert activities
                    for activity_type in activities:
                        activity_data = activity_manager.activity_types.get(activity_type, {})
                        self.db.execute_query(
                            '''INSERT INTO home_activities 
                               (home_id, activity_type, activity_name)
                               VALUES (?, ?, ?)''',
                            (home_id, activity_type, activity_data.get('name', activity_type))
                        )
                    
                    total_homes += 1
        
        return total_homes
        
    async def _simulate_gate_movements(self, intensity: int) -> Dict:
        """Simulate the movement of gates during corridor shifts"""
        
        results = {
            'gates_moved': 0,
            'gates_abandoned': 0,
            'new_gate_locations': 0,
            'affected_gates': []
        }
        
        # Get all active gates
        active_gates = self.db.execute_query(
            "SELECT location_id, name, x_coord, y_coord FROM locations WHERE location_type = 'gate' AND gate_status = 'active'",
            fetch='all'
        )
        
        if not active_gates:
            return results
        
        # Calculate how many gates might be affected based on intensity
        max_affected = min(len(active_gates) // (6 - intensity), len(active_gates) // 2)
        gates_to_affect = random.sample(active_gates, min(max_affected, random.randint(0, max_affected)))
        
        for gate in gates_to_affect:
            gate_id, gate_name, gate_x, gate_y = gate
            
            # Determine what happens to this gate
            fate_roll = random.random()
            
            if fate_roll < 0.4:  # 40% chance - Gate relocates
                # Find a new location for the gate
                new_x = gate_x + random.uniform(-20, 20)
                new_y = gate_y + random.uniform(-20, 20)
                
                # Update gate position and status
                self.db.execute_query(
                    "UPDATE locations SET x_coord = ?, y_coord = ?, gate_status = 'active' WHERE location_id = ?",
                    (new_x, new_y, gate_id)
                )
                
                # Update any corridors connected to this gate
                await self._update_gate_corridor_distances(gate_id, new_x, new_y)
                
                results['gates_moved'] += 1
                results['affected_gates'].append(f"🔄 {gate_name} relocated to new coordinates")
                print(f"🔄 Gate {gate_name} moved to new position ({new_x:.1f}, {new_y:.1f})")
                
            elif fate_roll < 0.7:  # 30% chance - Gate becomes unused but remains
                self.db.execute_query(
                    "UPDATE locations SET gate_status = 'unused' WHERE location_id = ?",
                    (gate_id,)
                )
                
                # Deactivate corridors connected to this gate
                self.db.execute_query(
                    "UPDATE corridors SET is_active = 0 WHERE origin_location = ? OR destination_location = ?",
                    (gate_id, gate_id)
                )
                
                results['gates_abandoned'] += 1
                results['affected_gates'].append(f"⚫ {gate_name} became unused")
                print(f"⚫ Gate {gate_name} became unused")
                
            # 30% chance - Gate remains active and in place (no change)
        
        return results

    async def _update_gate_corridor_distances(self, gate_id: int, new_x: float, new_y: float):
        """Update travel times and fuel costs for corridors connected to a moved gate"""
        
        # Get all corridors connected to this gate
        connected_corridors = self.db.execute_query(
            """SELECT c.corridor_id, c.origin_location, c.destination_location,
                      l1.x_coord as origin_x, l1.y_coord as origin_y,
                      l2.x_coord as dest_x, l2.y_coord as dest_y
               FROM corridors c
               JOIN locations l1 ON c.origin_location = l1.location_id
               JOIN locations l2 ON c.destination_location = l2.location_id
               WHERE c.origin_location = ? OR c.destination_location = ?""",
            (gate_id, gate_id),
            fetch='all'
        )
        
        for corridor in connected_corridors:
            corridor_id, origin_id, dest_id, origin_x, origin_y, dest_x, dest_y = corridor
            
            # Use new coordinates if this gate moved
            if origin_id == gate_id:
                origin_x, origin_y = new_x, new_y
            if dest_id == gate_id:
                dest_x, dest_y = new_x, new_y
            
            # Recalculate distance and update corridor properties
            distance = math.sqrt((dest_x - origin_x)**2 + (dest_y - origin_y)**2)
            travel_time = max(180, int(distance * 3))  # Minimum 3 minutes
            fuel_cost = max(10, int(distance * 0.5))
            
            self.db.execute_query(
                "UPDATE corridors SET travel_time = ?, fuel_cost = ? WHERE corridor_id = ?",
                (travel_time, fuel_cost, corridor_id)
            )
    def _create_minimum_spanning_tree(self, locations: List[Dict]) -> List[Dict]:
        """Create minimum spanning tree to ensure all locations are connected"""
        if not locations:
            return []
        
        routes = []
        connected = {locations[0]['id']}  # Start with first location
        unconnected = {loc['id']: loc for loc in locations[1:]}
        
        while unconnected:
            best_distance = float('inf')
            best_connection = None
            
            # Find shortest connection from connected to unconnected
            for connected_id in connected:
                connected_loc = next(loc for loc in locations if loc['id'] == connected_id)
                
                for unconnected_id, unconnected_loc in unconnected.items():
                    distance = self._calculate_distance(connected_loc, unconnected_loc)
                    if distance < best_distance:
                        best_distance = distance
                        best_connection = (connected_loc, unconnected_loc)
            
            if best_connection:
                from_loc, to_loc = best_connection
                routes.append({
                    'from': from_loc,
                    'to': to_loc,
                    'importance': 'medium',
                    'distance': best_distance
                })
                connected.add(to_loc['id'])
                del unconnected[to_loc['id']]
        
        return routes

    def _create_hub_connections(self, stations: List[Dict], colonies: List[Dict]) -> List[Dict]:
        """Create hub connections between stations and high-value colonies"""
        routes = []
        
        for station in stations:
            # Connect each station to 2-4 nearby high-value colonies
            wealthy_colonies = [c for c in colonies if c['wealth_level'] >= 6]
            nearby_wealthy = self._find_nearby_locations(station, wealthy_colonies, max_distance=70)
            
            connection_count = min(len(nearby_wealthy), random.randint(2, 4))
            for colony in nearby_wealthy[:connection_count]:
                routes.append({
                    'from': station,
                    'to': colony,
                    'importance': 'high',
                    'distance': self._calculate_distance(station, colony)
                })
        
        return routes

    def _create_regional_bridges(self, all_locations: List[Dict], existing_routes: List[Dict]) -> List[Dict]:
        """Create bridge connections between different regions of the galaxy"""
        routes = []
        
        # Analyze spatial distribution to identify regions
        regions = self._identify_spatial_regions(all_locations)
        
        # Create cross-regional connections
        for i, region_a in enumerate(regions):
            for j, region_b in enumerate(regions[i+1:], i+1):
                # Find best connection points between regions
                best_connections = self._find_best_inter_region_connections(region_a, region_b)
                
                # Add 1-2 bridge connections between each pair of regions
                for connection in best_connections[:random.randint(1, 2)]:
                    routes.append({
                        'from': connection[0],
                        'to': connection[1],
                        'importance': 'medium', 
                        'distance': self._calculate_distance(connection[0], connection[1])
                    })
        
        return routes

    def _identify_spatial_regions(self, locations: List[Dict]) -> List[List[Dict]]:
        """Identify spatial regions in the galaxy for better connectivity planning"""
        if len(locations) <= 6:
            return [locations]  # Too few locations to regionalize
        
        # Simple clustering based on position
        regions = []
        used_locations = set()
        
        # Create regions of roughly 8-15 locations each
        target_region_size = max(6, len(locations) // 4)
        
        while len(used_locations) < len(locations):
            # Find an unused location as region center
            available = [loc for loc in locations if loc['id'] not in used_locations]
            if not available:
                break
                
            # Pick a central location (prefer stations/wealthy colonies)
            region_center = max(available, key=lambda loc: (
                loc['type'] == 'space_station',
                loc['wealth_level'],
                -len([l for l in available if self._calculate_distance(loc, l) < 30])
            ))
            
            # Build region around this center
            region = [region_center]
            used_locations.add(region_center['id'])
            
            # Add nearby locations to this region
            candidates = [loc for loc in available if loc['id'] != region_center['id']]
            candidates.sort(key=lambda loc: self._calculate_distance(region_center, loc))
            
            for candidate in candidates:
                if len(region) >= target_region_size:
                    break
                if candidate['id'] not in used_locations:
                    # Add if close enough to region center or any region member
                    min_distance_to_region = min(
                        self._calculate_distance(candidate, member) 
                        for member in region
                    )
                    if min_distance_to_region <= 40:
                        region.append(candidate)
                        used_locations.add(candidate['id'])
            
            regions.append(region)
        
        return regions

    def _find_best_inter_region_connections(self, region_a: List[Dict], region_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """Find the best connection points between two regions"""
        connections = []
        
        for loc_a in region_a:
            for loc_b in region_b:
                distance = self._calculate_distance(loc_a, loc_b)
                # Prefer stations and wealthy colonies as connection points
                priority = (
                    (loc_a['type'] == 'space_station') + (loc_b['type'] == 'space_station'),
                    (loc_a['wealth_level'] + loc_b['wealth_level']),
                    -distance  # Closer is better
                )
                connections.append(((loc_a, loc_b), distance, priority))
        
        # Sort by priority (stations first, then wealth, then distance)
        connections.sort(key=lambda x: x[2], reverse=True)
        
        return [conn[0] for conn in connections[:3]]  # Return top 3 candidates

    def _add_redundant_connections(self, all_locations: List[Dict], existing_routes: List[Dict]) -> List[Dict]:
        """Add redundant connections to prevent fragmentation"""
        routes = []
        
        # Calculate current connectivity for each location
        connectivity_map = {}
        for loc in all_locations:
            connectivity_map[loc['id']] = sum(1 for route in existing_routes 
                                            if route['from']['id'] == loc['id'] or route['to']['id'] == loc['id'])
        
        # Identify locations with low connectivity
        low_connectivity = [loc for loc in all_locations if connectivity_map[loc['id']] <= 2]
        
        for location in low_connectivity:
            # Find 1-2 additional connections for low-connectivity locations
            potential_targets = [loc for loc in all_locations if loc['id'] != location['id']]
            
            # Exclude already connected locations
            connected_ids = set()
            for route in existing_routes:
                if route['from']['id'] == location['id']:
                    connected_ids.add(route['to']['id'])
                elif route['to']['id'] == location['id']:
                    connected_ids.add(route['from']['id'])
            
            potential_targets = [loc for loc in potential_targets if loc['id'] not in connected_ids]
            
            if potential_targets:
                # Sort by distance and select 1-2 closest
                potential_targets.sort(key=lambda loc: self._calculate_distance(location, loc))
                
                for target in potential_targets[:random.randint(1, 2)]:
                    distance = self._calculate_distance(location, target)
                    if distance <= 80:  # Don't create extremely long connections
                        routes.append({
                            'from': location,
                            'to': target,
                            'importance': 'low',
                            'distance': distance
                        })
        
        return routes

    def _validate_and_fix_connectivity(self, all_locations: List[Dict], routes: List[Dict]) -> List[Dict]:
        """Validate overall connectivity and fix issues"""
        
        # Build adjacency list
        graph = {loc['id']: set() for loc in all_locations}
        for route in routes:
            from_id, to_id = route['from']['id'], route['to']['id']
            graph[from_id].add(to_id)
            graph[to_id].add(from_id)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        # If we have multiple components, connect them
        if len(components) > 1:
            print(f"🔧 Found {len(components)} disconnected components, fixing connectivity...")
            
            # Connect each component to the largest one
            largest_component = max(components, key=len)
            
            for component in components:
                if component == largest_component:
                    continue
                
                # Find best connection between this component and the largest
                best_connection = None
                best_distance = float('inf')
                
                for loc_id_a in component:
                    loc_a = next(loc for loc in all_locations if loc['id'] == loc_id_a)
                    for loc_id_b in largest_component:
                        loc_b = next(loc for loc in all_locations if loc['id'] == loc_id_b)
                        distance = self._calculate_distance(loc_a, loc_b)
                        
                        if distance < best_distance:
                            best_distance = distance
                            best_connection = (loc_a, loc_b)
                
                if best_connection:
                    routes.append({
                        'from': best_connection[0],
                        'to': best_connection[1],
                        'importance': 'medium',
                        'distance': best_distance
                    })
                    print(f"🌉 Added bridge connection: {best_connection[0]['name']} ↔ {best_connection[1]['name']}")
        
        return routes

    async def _create_dormant_corridors(self, conn, all_locations: List[Dict], active_routes: List[Dict]):
        """Creates dormant corridors with radical optimization using spatial binning and micro-transactions"""
        
        # Commit current transaction before starting dormant generation (only if conn exists)
        if conn is not None:
            self.db.commit_transaction(conn)
            conn = None  # Clear the connection reference
        
        active_pairs = {tuple(sorted([r['from']['id'], r['to']['id']])) for r in active_routes}
        num_locs = len(all_locations)
        
        # Calculate target dormant corridors to maintain ratio
        target_dormant_total = int(num_locs * 15)  # Maintain same ratio as before
        
        print(f"🌫️ Generating {target_dormant_total} dormant corridors for {num_locs} locations using spatial optimization...")
        
        # Create spatial bins for ultra-fast proximity lookups
        spatial_bins = self._create_spatial_bins(all_locations, bin_size=25)
        
        corridors_created = 0
        max_attempts = target_dormant_total * 3  # Prevent infinite loops
        attempts = 0
        
        # Process in very small independent transactions
        batch_size = 25  # Much smaller batches
        current_batch = []
        
        while corridors_created < target_dormant_total and attempts < max_attempts:
            attempts += 1
            
            # Pick a random location
            loc_a = random.choice(all_locations)
            
            # Get nearby locations using spatial binning (much faster than distance calc)
            nearby_candidates = self._get_nearby_from_bins(loc_a, spatial_bins, max_candidates=8)
            
            if not nearby_candidates:
                continue
                
            # Pick a random nearby candidate
            loc_b = random.choice(nearby_candidates)
            
            pair = tuple(sorted([loc_a['id'], loc_b['id']]))
            
            # Skip if already exists
            if pair in active_pairs:
                continue
                
            # Quick distance check (only now do we calculate distance)
            distance = self._calculate_distance(loc_a, loc_b)
            if distance > 60:  # Skip very long corridors
                continue
                
            # Create corridor data
            name = self._generate_corridor_name(loc_a, loc_b)
            fuel = max(10, int(distance * 0.8) + 5)
            danger = random.randint(2, 5)
            travel_time = self._calculate_ungated_route_time(distance)
            
            # Add to batch (bidirectional)
            current_batch.extend([
                (f"{name} (Dormant)", loc_a['id'], loc_b['id'], travel_time, fuel, danger),
                (f"{name} Return (Dormant)", loc_b['id'], loc_a['id'], travel_time, fuel, danger)
            ])
            
            active_pairs.add(pair)
            corridors_created += 2
            
            # Insert batch in micro-transaction when ready
            if len(current_batch) >= batch_size:
                await self._insert_dormant_batch(current_batch)
                current_batch = []
                
                # Progress and yield much more frequently
                if corridors_created % 100 == 0:
                    progress = (corridors_created / target_dormant_total) * 100
                    print(f"    🌫️ Dormant corridors: {progress:.0f}% ({corridors_created}/{target_dormant_total})")
                    
                # Yield control very frequently
                await asyncio.sleep(0.05)
        
        # Insert remaining batch
        if current_batch:
            await self._insert_dormant_batch(current_batch)
        
        print(f"🌫️ Created {corridors_created} dormant corridor segments in {attempts} attempts")

    def _create_spatial_bins(self, locations: List[Dict], bin_size: float = 25) -> Dict:
        """Create spatial bins for ultra-fast proximity lookups"""
        bins = {}
        
        for loc in locations:
            bin_x = int(loc['x_coord'] // bin_size)
            bin_y = int(loc['y_coord'] // bin_size)
            bin_key = (bin_x, bin_y)
            
            if bin_key not in bins:
                bins[bin_key] = []
            bins[bin_key].append(loc)
        
        return bins

    def _get_nearby_from_bins(self, location: Dict, spatial_bins: Dict, max_candidates: int = 8) -> List[Dict]:
        """Get nearby locations using spatial bins (much faster than distance calculations)"""
        bin_size = 25
        bin_x = int(location['x_coord'] // bin_size)
        bin_y = int(location['y_coord'] // bin_size)
        
        nearby = []
        
        # Check the location's bin and adjacent bins (3x3 grid)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_bin = (bin_x + dx, bin_y + dy)
                if check_bin in spatial_bins:
                    for candidate in spatial_bins[check_bin]:
                        if candidate['id'] != location['id']:
                            nearby.append(candidate)
                            
                            # Early exit when we have enough candidates
                            if len(nearby) >= max_candidates:
                                return nearby[:max_candidates]
        
        return nearby

    async def _insert_dormant_batch(self, batch_data: List[tuple]):
        """Insert dormant corridors in independent micro-transaction"""
        if not batch_data:
            return
            
        # Use completely independent transaction
        micro_conn = self.db.begin_transaction()
        try:
            query = '''INSERT INTO corridors 
                       (name, origin_location, destination_location, travel_time, fuel_cost, 
                        danger_level, is_active, is_generated)
                       VALUES (?, ?, ?, ?, ?, ?, 0, 1)'''
            self.db.executemany_in_transaction(micro_conn, query, batch_data)
            self.db.commit_transaction(micro_conn)
        except Exception as e:
            self.db.rollback_transaction(micro_conn)
            print(f"❌ Error inserting dormant batch: {e}")
        finally:
            micro_conn = None
        
    @galaxy_group.command(name="shift_corridors", description="Trigger corridor shifts to change galaxy connectivity")
    @app_commands.describe(
        intensity="Intensity of the shift (1-5, higher = more changes)",
        target_region="Focus shifts on a specific region (optional)"
    )
    async def shift_corridors(self, interaction: discord.Interaction, 
                             intensity: int = 2, target_region: str = None):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        if intensity < 1 or intensity > 5:
            await interaction.response.send_message("Intensity must be between 1 and 5.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            results = await self._execute_corridor_shifts(intensity, target_region)
            
            embed = discord.Embed(
                title="🌌 Corridor Shift Complete",
                description=f"Galactic infrastructure has undergone changes (Intensity {intensity})",
                color=0x4B0082
            )
            
            if results['activated']:
                embed.add_field(
                    name="🟢 New Corridors Activated",
                    value=f"{results['activated']} dormant routes opened",
                    inline=True
                )
            
            if results['deactivated']:
                embed.add_field(
                    name="🔴 Corridors Collapsed", 
                    value=f"{results['deactivated']} active routes closed",
                    inline=True
                )
            
            if results['new_dormant']:
                embed.add_field(
                    name="🌫️ New Potential Routes",
                    value=f"{results['new_dormant']} dormant corridors formed",
                    inline=True
                )
            
            connectivity_status = await self._analyze_connectivity_post_shift()
            embed.add_field(
                name="📊 Connectivity Status",
                value=connectivity_status,
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Advisory",
                value="Players in transit may experience route changes. Check `/travel routes` for updates.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
            # Notify active travelers
            await self._notify_travelers_of_shifts(results)
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                await news_cog.post_corridor_shift_news(results, intensity)  
            
        except Exception as e:
            await interaction.followup.send(f"Error during corridor shift: {str(e)}")

    async def _execute_corridor_shifts(self, intensity: int, target_region: str = None) -> Dict:
        """Execute corridor shifts based on intensity"""
        
        results = {
            'activated': 0,
            'deactivated': 0, 
            'new_dormant': 0,
            'affected_locations': set()
        }
        
        # Get all corridors
        active_corridors = self.db.execute_query(
            "SELECT corridor_id, name, origin_location, destination_location FROM corridors WHERE is_active = 1",
            fetch='all'
        )
        
        dormant_corridors = self.db.execute_query(
            "SELECT corridor_id, name, origin_location, destination_location FROM corridors WHERE is_active = 0",
            fetch='all'
        )
        
        # Calculate number of changes based on intensity
        max_deactivations = min(len(active_corridors) // (6 - intensity), len(active_corridors) // 3)
        max_activations = min(len(dormant_corridors) // (6 - intensity), len(dormant_corridors) // 2)
        
        # Deactivate some active corridors
        corridors_to_deactivate = random.sample(active_corridors, 
                                              min(max_deactivations, random.randint(0, max_deactivations)))
        
        for corridor in corridors_to_deactivate:
            # Don't deactivate if it would completely isolate a location
            if not self._would_isolate_location(corridor[0], corridor[2], corridor[3]):
                self.db.execute_query(
                    "UPDATE corridors SET is_active = 0 WHERE corridor_id = ?",
                    (corridor[0],)
                )
                results['deactivated'] += 1
                results['affected_locations'].add(corridor[2])
                results['affected_locations'].add(corridor[3])
                print(f"🔴 Deactivated corridor: {corridor[1]}")
        
        # Activate some dormant corridors
        corridors_to_activate = random.sample(dormant_corridors,
                                            min(max_activations, random.randint(0, max_activations)))
        
        for corridor in corridors_to_activate:
            self.db.execute_query(
                "UPDATE corridors SET is_active = 1 WHERE corridor_id = ?",
                (corridor[0],)
            )
            results['activated'] += 1
            results['affected_locations'].add(corridor[2])
            results['affected_locations'].add(corridor[3])
            print(f"🟢 Activated corridor: {corridor[1]}")
        # Simulate gate movements during shifts
        if intensity >= 3:  # Only move gates during significant shifts
            gate_results = await self._simulate_gate_movements(intensity)
            results.update(gate_results)
        # Create new dormant corridors to maintain potential
        await self._replenish_dormant_corridors(intensity)
        results['new_dormant'] = intensity * 5  # Approximate count
        
        return results

    def _would_isolate_location(self, corridor_id: int, origin_id: int, dest_id: int) -> bool:
        """Check if deactivating a corridor would completely isolate a location"""
        
        # Count active connections for both endpoints
        origin_connections = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE (origin_location = ? OR destination_location = ?) AND is_active = 1 AND corridor_id != ?",
            (origin_id, origin_id, corridor_id),
            fetch='one'
        )[0]
        
        dest_connections = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE (origin_location = ? OR destination_location = ?) AND is_active = 1 AND corridor_id != ?",
            (dest_id, dest_id, corridor_id),
            fetch='one'
        )[0]
        
        # Don't allow isolation
        return origin_connections <= 1 or dest_connections <= 1

    async def _replenish_dormant_corridors(self, intensity: int):
        """Create new dormant corridors to maintain future shift potential"""
        
        all_locations = self.db.execute_query(
            "SELECT location_id, name, location_type, x_coord, y_coord, wealth_level FROM locations",
            fetch='all'
        )
        
        # Convert to dict format
        locations = []
        for loc_id, name, loc_type, x, y, wealth in all_locations:
            locations.append({
                'id': loc_id,
                'name': name, 
                'type': loc_type,
                'x_coord': x,
                'y_coord': y,
                'wealth_level': wealth
            })
        
        # Create additional dormant corridors based on intensity
        target_new_dormant = intensity * random.randint(3, 8)
        created = 0
        
        for _ in range(target_new_dormant * 2):  # Try more attempts than needed
            if created >= target_new_dormant:
                break
                
            # Pick two random locations
            loc_a, loc_b = random.sample(locations, 2)
            
            # Check if they already have any corridor between them
            existing = self.db.execute_query(
                """SELECT COUNT(*) FROM corridors 
                   WHERE (origin_location = ? AND destination_location = ?) 
                      OR (origin_location = ? AND destination_location = ?)""",
                (loc_a['id'], loc_b['id'], loc_b['id'], loc_a['id']),
                fetch='one'
            )[0]
            
            if existing > 0:
                continue  # Already have corridor
            
            distance = self._calculate_distance(loc_a, loc_b)
            if distance > 120:  # Don't create extremely long dormant corridors
                continue
            
            # Create dormant corridor pair
            name = self._generate_corridor_name(loc_a, loc_b)
            fuel_cost = max(10, int(distance * 0.8) + 5)
            danger = random.randint(2, 5)
            travel_time = self._calculate_ungated_route_time(distance)
            
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, 
                    danger_level, is_active, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 1)''',
                (f"{name} (Dormant)", loc_a['id'], loc_b['id'], 
                 travel_time, fuel_cost, danger)
            )
            
            self.db.execute_query(
                '''INSERT INTO corridors 
                   (name, origin_location, destination_location, travel_time, fuel_cost, 
                    danger_level, is_active, is_generated)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 1)''',
                (f"{name} Return (Dormant)", loc_b['id'], loc_a['id'], 
                 travel_time, fuel_cost, danger)
            )
            
            created += 1

    async def _analyze_connectivity_post_shift(self) -> str:
        """Analyze connectivity after corridor shifts"""
        
        locations = self.db.execute_query(
            "SELECT location_id FROM locations",
            fetch='all'
        )
        
        if not locations:
            return "No locations found"
        
        # Build graph of active corridors
        graph = {loc[0]: set() for loc in locations}
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = 1",
            fetch='all'
        )
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        total_locations = len(locations)
        largest_component_size = max(len(comp) for comp in components) if components else 0
        connectivity_percent = (largest_component_size / total_locations) * 100 if total_locations > 0 else 0
        
        if len(components) == 1:
            return f"✅ Fully connected ({total_locations} locations)"
        else:
            return f"⚠️ {len(components)} clusters, largest: {largest_component_size}/{total_locations} ({connectivity_percent:.1f}%)"

    async def _notify_travelers_of_shifts(self, results: Dict):
        """Notify active travelers about corridor shifts"""
        
        if not results['affected_locations']:
            return
        
        # Find travelers who might be affected
        affected_travelers = self.db.execute_query(
            """SELECT DISTINCT ts.user_id, ts.temp_channel_id, c.name as corridor_name
               FROM travel_sessions ts
               JOIN corridors c ON ts.corridor_id = c.corridor_id
               WHERE ts.status = 'traveling' 
                 AND (ts.origin_location IN ({}) OR ts.destination_location IN ({}))""".format(
                     ','.join(map(str, results['affected_locations'])),
                     ','.join(map(str, results['affected_locations']))
                 ),
            fetch='all'
        )
        
        for user_id, channel_id, corridor_name in affected_travelers:
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🌌 Corridor Shift Detected",
                        description="Galactic infrastructure changes detected in nearby space.",
                        color=0x800080
                    )
                    embed.add_field(
                        name="Current Journey",
                        value=f"Your transit via {corridor_name} continues normally.",
                        inline=False
                    )
                    embed.add_field(
                        name="Advisory",
                        value="Route availability may have changed at your destination. Check `/travel routes` upon arrival.",
                        inline=False
                    )
                    
                    try:
                        await channel.send(embed=embed)
                    except:
                        pass  # Channel might be deleted or inaccessible
    @galaxy_group.command(name="analyze_connectivity", description="Analyze current galaxy connectivity")
    async def analyze_connectivity(self, interaction: discord.Interaction):
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            analysis = await self._perform_connectivity_analysis()
            
            embed = discord.Embed(
                title="📊 Galaxy Connectivity Analysis",
                description="Current state of galactic infrastructure",
                color=0x4169E1
            )
            
            embed.add_field(
                name="🗺️ Overall Connectivity",
                value=analysis['overall_status'],
                inline=False
            )
            
            embed.add_field(
                name="📈 Statistics",
                value=analysis['statistics'],
                inline=False
            )
            
            if analysis['isolated_locations']:
                embed.add_field(
                    name="⚠️ Isolated Locations",
                    value=analysis['isolated_locations'][:1000] + "..." if len(analysis['isolated_locations']) > 1000 else analysis['isolated_locations'],
                    inline=False
                )
            
            embed.add_field(
                name="🔮 Shift Potential",
                value=analysis['shift_potential'],
                inline=False
            )
            
            if analysis['recommendations']:
                embed.add_field(
                    name="💡 Recommendations",
                    value=analysis['recommendations'],
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error analyzing connectivity: {str(e)}")

    async def _perform_connectivity_analysis(self) -> Dict:
        """Perform detailed connectivity analysis"""
        
        # Get all locations and corridors
        locations = self.db.execute_query(
            "SELECT location_id, name, location_type FROM locations",
            fetch='all'
        )
        
        active_corridors = self.db.execute_query(
            "SELECT origin_location, destination_location FROM corridors WHERE is_active = 1",
            fetch='all'
        )
        
        dormant_corridors = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE is_active = 0",
            fetch='one'
        )[0]
        
        if not locations:
            return {"overall_status": "No locations found", "statistics": "", "isolated_locations": "", "shift_potential": "", "recommendations": ""}
        
        # Build connectivity graph
        graph = {loc[0]: set() for loc in locations}
        location_names = {loc[0]: f"{loc[1]} ({loc[2]})" for loc in locations}
        
        for origin, dest in active_corridors:
            graph[origin].add(dest)
            graph[dest].add(origin)
        
        # Find connected components
        visited = set()
        components = []
        
        for loc_id in graph:
            if loc_id not in visited:
                component = set()
                stack = [loc_id]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)
                        stack.extend(graph[current] - visited)
                
                components.append(component)
        
        # Analyze results
        total_locations = len(locations)
        largest_component = max(components, key=len) if components else set()
        connectivity_percent = (len(largest_component) / total_locations) * 100 if total_locations > 0 else 0
        
        # Overall status
        if len(components) == 1:
            overall_status = f"✅ **Fully Connected**\nAll {total_locations} locations are reachable from each other."
        else:
            overall_status = f"⚠️ **Fragmented Network**\n{len(components)} separate clusters detected.\nLargest cluster: {len(largest_component)}/{total_locations} locations ({connectivity_percent:.1f}%)"
        
        # Statistics
        connection_counts = [len(graph[loc_id]) for loc_id in graph]
        avg_connections = sum(connection_counts) / len(connection_counts) if connection_counts else 0
        
        statistics = f"""**Active Corridors:** {len(active_corridors)}
    **Dormant Corridors:** {dormant_corridors}
    **Average Connections per Location:** {avg_connections:.1f}
    **Most Connected:** {max(connection_counts) if connection_counts else 0} corridors
    **Least Connected:** {min(connection_counts) if connection_counts else 0} corridors"""
        
        # Isolated locations
        isolated_locations = ""
        if len(components) > 1:
            small_clusters = [comp for comp in components if len(comp) < len(largest_component)]
            if small_clusters:
                isolated_list = []
                for cluster in small_clusters:
                    cluster_names = [location_names[loc_id] for loc_id in cluster]
                    isolated_list.append(f"• Cluster of {len(cluster)}: {', '.join(cluster_names[:3])}" + ("..." if len(cluster) > 3 else ""))
                isolated_locations = "\n".join(isolated_list[:10])  # Limit to prevent spam
        
        if not isolated_locations:
            isolated_locations = "None - all locations are in the main network"
        
        # Shift potential
        shift_potential = f"""**Dormant Routes Available:** {dormant_corridors}
    **Potential for New Connections:** {'High' if dormant_corridors > total_locations else 'Moderate' if dormant_corridors > total_locations // 2 else 'Low'}
    **Risk Level:** {'Low' if len(components) == 1 else 'High'}"""
        
        # Recommendations
        recommendations = []
        if len(components) > 1:
            recommendations.append("• Use `/galaxy shift_corridors` to activate dormant routes")
            recommendations.append("• Consider manual route creation between isolated clusters")
        
        if avg_connections < 2.5:
            recommendations.append("• Overall connectivity is low - consider more corridor generation")
        
        if dormant_corridors < total_locations:
            recommendations.append("• Low dormant corridor count - future shifts may be limited")
        
        recommendations_text = "\n".join(recommendations) if recommendations else "Galaxy connectivity is healthy"
        
        return {
            "overall_status": overall_status,
            "statistics": statistics,
            "isolated_locations": isolated_locations,
            "shift_potential": shift_potential,
            "recommendations": recommendations_text
        }
    async def _generate_sub_locations_for_all_locations(self, conn, all_locations: List[Dict]) -> int:
        """Generates persistent sub-locations for all locations in bulk."""
        from utils.sub_locations import SubLocationManager
        
        sub_manager = SubLocationManager(self.bot)
        sub_locations_to_insert = []
        
        for location in all_locations:
            # The manager returns a list of sub-locations to be created
            generated_subs = sub_manager.get_persistent_sub_locations_data(
                location['id'], 
                location['type'], 
                location['wealth_level'],
                location.get('is_derelict', False)
            )
            sub_locations_to_insert.extend(generated_subs)
            
        if sub_locations_to_insert:
            query = '''INSERT INTO sub_locations 
                       (parent_location_id, name, sub_type, description) 
                       VALUES (?, ?, ?, ?)'''
            self.db.executemany_in_transaction(conn, query, sub_locations_to_insert)
            print(f"🏢 Generated {len(sub_locations_to_insert)} sub-locations in total.")
            
        return len(sub_locations_to_insert)
        
    async def _generate_gates_for_routes(self, conn, routes: List[Dict], major_locations: List[Dict]) -> List[Dict]:
        """Generate gates for routes with optimized batching and yielding"""
        if not routes:
            return []
        
        # Commit current transaction to avoid long locks
        if conn:
            self.db.commit_transaction(conn)
            conn = None
        
        print(f"🚪 Generating gates for {len(routes)} routes...")
        
        gates = []
        used_names = set()
        gates_to_create = []
        
        # First pass: determine which routes get gates and prepare gate data
        for i, route in enumerate(routes):
            gate_chance = 0.5
            if random.random() < gate_chance:
                # Pre-generate gate names to avoid conflicts
                origin_name = self._generate_unique_gate_name(route['from'], used_names)
                dest_name = self._generate_unique_gate_name(route['to'], used_names)
                
                used_names.add(origin_name)
                used_names.add(dest_name)
                
                gates_to_create.append({
                    'route_index': i,
                    'origin_data': self._create_gate_data(route['from'], origin_name),
                    'dest_data': self._create_gate_data(route['to'], dest_name)
                })
                
                route['has_gates'] = True
            else:
                route['has_gates'] = False
            
            # Yield every 20 routes in planning phase
            if i % 20 == 0:
                await asyncio.sleep(0.01)
        
        print(f"🚪 Creating {len(gates_to_create) * 2} gate locations...")
        
        # Second pass: create gates in small batches
        batch_size = 10  # Small batches to avoid long transactions
        
        for batch_start in range(0, len(gates_to_create), batch_size):
            batch_end = min(batch_start + batch_size, len(gates_to_create))
            batch = gates_to_create[batch_start:batch_end]
            
            # Create gates in independent micro-transaction
            batch_gates = await self._create_gate_batch(batch, routes)
            gates.extend(batch_gates)
            
            # Progress reporting
            progress = ((batch_end) / len(gates_to_create)) * 100
            if batch_start % 50 == 0:  # Report every 50 items processed
                print(f"    🚪 Gate creation progress: {progress:.0f}% ({batch_end}/{len(gates_to_create)} routes)")
            
            # Yield control after each batch
            await asyncio.sleep(0.05)
        
        print(f"✅ Created {len(gates)} gate locations")
        return gates

    def _generate_unique_gate_name(self, location: Dict, used_names: set) -> str:
        """Generate unique gate name more efficiently"""
        location_name = location['name']
        
        # Pre-generate several candidates to reduce conflicts
        candidates = [
            f"{location_name}-{random.choice(self.location_names)} {random.choice(self.gate_names)}",
            f"{location_name} {random.choice(self.gate_names)}",
            f"{random.choice(self.location_names)} {random.choice(self.gate_names)}",
            f"{location_name}-{random.choice(['Alpha', 'Beta', 'Gamma', 'Delta'])} {random.choice(self.gate_names)}"
        ]
        
        # Try candidates first
        for candidate in candidates:
            if candidate not in used_names:
                return candidate
        
        # Fallback with counter if all candidates taken
        base_name = f"{location_name} {random.choice(self.gate_names)}"
        counter = 1
        while f"{base_name} {counter}" in used_names:
            counter += 1
        
        return f"{base_name} {counter}"
    
    def _create_gate_data(self, location: Dict, gate_name: str) -> Dict:
        """Create gate data without database interaction"""
        import math
        
        # Position gate close to but not overlapping the location
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(3, 8)
        
        gate_x = location['x_coord'] + distance * math.cos(angle)
        gate_y = location['y_coord'] + distance * math.sin(angle)
        
        return {
            'name': gate_name,
            'type': 'gate',
            'x_coord': gate_x,
            'y_coord': gate_y,
            'system_name': location['system_name'],
            'description': f"Transit gate providing safe passage to and from {location['name']}. Features decontamination facilities and basic services.",
            'wealth_level': min(location['wealth_level'] + 1, 8),
            'population': random.randint(15, 40),
            'has_jobs': False,
            'has_shops': True,
            'has_medical': True,
            'has_repairs': True,
            'has_fuel': True,
            'has_upgrades': False,
            'is_generated': True,
            'parent_location': location['id']
        }
    async def _create_gate_batch(self, gate_batch: List[Dict], routes: List[Dict]) -> List[Dict]:
        """Create a batch of gates in independent transaction with retry logic"""
        created_gates = []
        
        # Retry logic for database lock issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait a bit if this is a retry
                if attempt > 0:
                    await asyncio.sleep(0.5 * attempt)
                
                # Use independent micro-transaction
                micro_conn = self.db.begin_transaction()
                break
            except RuntimeError as e:
                if "database lock" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database lock in gate creation, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    print(f"❌ Failed to acquire database lock for gate creation: {e}")
                    return []  # Return empty list instead of crashing
        try:
            for gate_info in gate_batch:
                route_index = gate_info['route_index']
                route = routes[route_index]
                
                # Create origin gate
                origin_data = gate_info['origin_data']
                origin_id = self._save_location_to_db(micro_conn, origin_data)
                origin_data['id'] = origin_id
                created_gates.append(origin_data)
                
                # Create destination gate
                dest_data = gate_info['dest_data']
                dest_id = self._save_location_to_db(micro_conn, dest_data)
                dest_data['id'] = dest_id
                created_gates.append(dest_data)
                
                # Update route with gate references
                route['origin_gate'] = origin_data
                route['destination_gate'] = dest_data
            
            self.db.commit_transaction(micro_conn)
            
        except Exception as e:
            self.db.rollback_transaction(micro_conn)
            print(f"❌ Error creating gate batch: {e}")
            # Return empty list for this batch
            return []
        finally:
            micro_conn = None
        
        return created_gates    
    def _create_gate_near_location(self, location: Dict, gate_type: str, used_names: set) -> Dict:
        """Create a gate near a major location"""
        
        # Position gate close to but not overlapping the location
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(3, 8)  # Close but separate
        
        gate_x = location['x_coord'] + distance * math.cos(angle)
        gate_y = location['y_coord'] + distance * math.sin(angle)
        
        name = ""
        attempts = 0
        while attempts < 50:
            # Randomly select a type name from your gate_names list (e.g., "Portal", "Junction")
            gate_type_name = random.choice(self.gate_names)
            # Randomly select a descriptor from your location_names list (e.g., "Hope", "Meridian")
            descriptor = random.choice(self.location_names)
            
            # Combine them for a unique name like "Earth-Hope Portal"
            name = f"{location['name']}-{descriptor} {gate_type_name}"
            
            if name not in used_names:
                break  # Found a unique name
            attempts += 1
        
        # A fallback for the very rare case of 50 failed attempts
        if attempts == 50:
            counter = 1
            while f"{name} {counter}" in used_names:
                counter += 1
            name = f"{name} {counter}"


        # Gates always have maintenance crews - ensure minimum population for NPCs
        gate_population = random.randint(15, 40)  # Small operational crew
        
        return {
            'name': name,
            'type': 'gate',
            'x_coord': gate_x,
            'y_coord': gate_y,
            'system_name': location['system_name'],
            'description': f"Transit gate providing safe passage to and from {location['name']}. Features decontamination facilities and basic services.",
            'wealth_level': min(location['wealth_level'] + 1, 8),  # Gates are well-maintained
            'population': gate_population,  # Ensure adequate population for NPCs
            'has_jobs': False,  # Gates don't have jobs
            'has_shops': True,   # Basic supplies
            'has_medical': True, # Decontamination 
            'has_repairs': True, # Ship maintenance
            'has_fuel': True,    # Always have fuel
            'has_upgrades': False, # No upgrades at gates
            'is_generated': True,
            'parent_location': location['id']  # Track which location this gate serves
        }
    
    async def _create_corridors(self, conn, routes: List[Dict], all_locations: List[Dict]) -> List[Dict]:
        """Create corridors with optimized batching and independent transaction management"""
        if not routes:
            return []
        
        # Handle transaction properly - commit if passed, otherwise start fresh
        if conn:
            self.db.commit_transaction(conn)
            conn = None
        
        print(f"🌉 Creating corridor network for {len(routes)} routes...")
        
        corridors_to_insert = []
        batch_size = 50  # Smaller batches
        corridors_created = 0
        
        for i, route in enumerate(routes):
            name = self._generate_corridor_name(route['from'], route['to'])
            loc1_id, loc2_id = route['from']['id'], route['to']['id']
            dist = route['distance']
            fuel = max(10, int(dist * 0.8) + 5)
            danger = max(1, min(5, 2 + random.randint(-1, 2)))

            if route.get('has_gates', False) and 'origin_gate' in route and 'destination_gate' in route:
                # Gated route with 6 segments
                og_id = route['origin_gate']['id']
                dg_id = route['destination_gate']['id']
                approach_time, main_time = self._calculate_gated_route_times(dist)
                gate_danger = max(1, danger - 1)
                
                corridors_to_insert.extend([
                    (f"{name} Approach", loc1_id, og_id, approach_time, int(fuel*0.2), gate_danger, 1, 1),
                    (name, og_id, dg_id, main_time, int(fuel*0.6), danger, 1, 1),
                    (f"{name} Arrival", dg_id, loc2_id, approach_time, int(fuel*0.2), gate_danger, 1, 1),
                    (f"{name} Return Departure", loc2_id, dg_id, approach_time, int(fuel*0.2), gate_danger, 1, 1),
                    (f"{name} Return", dg_id, og_id, main_time, int(fuel*0.6), danger, 1, 1),
                    (f"{name} Return Arrival", og_id, loc1_id, approach_time, int(fuel*0.2), gate_danger, 1, 1),
                ])
                corridors_created += 6
            else:
                # Ungated route with 2 segments
                ungated_time = self._calculate_ungated_route_time(dist)
                ungated_danger = min(5, danger + 2)
                ungated_fuel = int(fuel * 0.7)
                corridors_to_insert.extend([
                    (f"{name} (Ungated)", loc1_id, loc2_id, ungated_time, ungated_fuel, ungated_danger, 1, 1),
                    (f"{name} Return (Ungated)", loc2_id, loc1_id, ungated_time, ungated_fuel, ungated_danger, 1, 1),
                ])
                corridors_created += 2
            
            # Insert in batches with micro-transactions
            if len(corridors_to_insert) >= batch_size:
                await self._insert_corridor_batch(corridors_to_insert)
                corridors_to_insert = []
                
                # Progress reporting
                progress = ((i + 1) / len(routes)) * 100
                if i % 25 == 0:
                    print(f"    🌉 Corridor progress: {progress:.0f}% ({corridors_created} segments)")
                
                # Yield control
                await asyncio.sleep(0.05)
        
        # Insert remaining corridors
        if corridors_to_insert:
            await self._insert_corridor_batch(corridors_to_insert)

        print(f"✅ Created {corridors_created} corridor segments")
        return corridors_to_insert

    async def _insert_corridor_batch(self, batch_data: List[tuple]):
        """Insert corridor batch in independent micro-transaction with retry logic"""
        if not batch_data:
            return
        
        # Retry logic for database lock issues    
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait a bit if this is a retry
                if attempt > 0:
                    await asyncio.sleep(0.3 * attempt)
                
                micro_conn = self.db.begin_transaction()
                break
            except RuntimeError as e:
                if "database lock" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database lock in corridor creation, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    print(f"❌ Failed to acquire database lock for corridor creation: {e}")
                    return  # Skip this batch instead of crashing
        try:
            query = '''INSERT INTO corridors (name, origin_location, destination_location, 
                       travel_time, fuel_cost, danger_level, is_active, is_generated) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)'''
            self.db.executemany_in_transaction(micro_conn, query, batch_data)
            self.db.commit_transaction(micro_conn)
        except Exception as e:
            self.db.rollback_transaction(micro_conn)
            print(f"❌ Error inserting corridor batch: {e}")
        finally:
            micro_conn = None

    def _calculate_gated_route_times(self, distance: float) -> Tuple[int, int]:
        """Calculate travel times for gated routes (approach + main corridor) - 4-20 minute total limit"""
        
        # Total time budget: 4-20 minutes (240-1200 seconds)
        min_total_time = 7 * 60  # 5 minutes
        max_total_time = 20 * 60  # 20 minutes
        
        # Scale base time with distance but within constraints
        distance_factor = min(distance / 50.0, 2.0)  # Cap at 2x multiplier
        base_total_time = min_total_time + (max_total_time - min_total_time) * (distance_factor / 2.0)
        
        # Add randomization (±25%)
        variance = base_total_time * 0.15
        total_time = base_total_time + random.uniform(-variance, variance)
        
        # Clamp to 4-20 minute range
        total_time = max(min_total_time, min(max_total_time, int(total_time)))
        
        # Split into approach (30%) and main corridor (70%)
        approach_time = int(total_time * 0.3)
        main_time = total_time - approach_time
        
        # Ensure minimums
        approach_time = min(300, approach_time)  # At least 5 minutes
        main_time = min(480 , main_time)  # At least 8 minutes
        
        return approach_time, main_time

    def _calculate_ungated_route_time(self, distance: float) -> int:
        """Calculate travel time for ungated routes - 4-20 minute limit"""
        
        min_time = 6 * 60  # 4 minutes
        max_time = 18 * 60  # 18 minutes
        
        # Scale with distance
        distance_factor = min(distance / 50.0, 2.0)  # Cap at 2x multiplier
        base_time = min_time + (max_time - min_time) * (distance_factor / 2.0)
        
        # Add randomization (±30% for ungated danger)
        variance = base_time * 0.3
        ungated_time = base_time + random.uniform(-variance, variance)
        
        # Clamp to 4-20 minute range
        ungated_time = max(min_time, min(max_time, int(ungated_time)))
        
        return int(ungated_time)
    
    def _create_corridor_segment(self, name: str, origin_id: int, dest_id: int, 
                               travel_time: int, fuel_cost: int, danger_level: int, has_gate: bool = True) -> Dict:
        """Create a single corridor segment with gate status"""
        
        # Save to database
        self.db.execute_query(
            '''INSERT INTO corridors 
               (name, origin_location, destination_location, travel_time, fuel_cost, danger_level, is_generated)
               VALUES (?, ?, ?, ?, ?, ?, 1)''',
            (name, origin_id, dest_id, travel_time, fuel_cost, danger_level)
        )
        
        return {
            'name': name,
            'origin_id': origin_id,
            'destination_id': dest_id,
            'travel_time': travel_time,
            'fuel_cost': fuel_cost,
            'danger_level': danger_level,
            'has_gate': has_gate
        }
    
    def _generate_corridor_name(self, from_loc: Dict, to_loc: Dict) -> str:
        """Generate a lore-appropriate corridor name"""
        # Ensure we have the required fields
        from_name = from_loc.get('name', 'Unknown')
        to_name = to_loc.get('name', 'Unknown')
        from_system = from_loc.get('system_name', 'Unknown')
        to_system = to_loc.get('system_name', 'Unknown')
        
        # Generate shorter, more predictable names
        corridor_suffix = random.choice(self.corridor_names)
        
        base_names = [
            f"{from_name}-{to_name} {corridor_suffix}",
            f"{from_system} {corridor_suffix}",
            f"{to_system} {corridor_suffix}",
            f"{random.choice(['Trans', 'Inter', 'Cross'])}-{random.choice([from_system, to_system])} {corridor_suffix}"
        ]
        
        # Pick the shortest name that's still reasonable
        name = min(base_names, key=len)
        
        # Ensure name isn't too long
        if len(name) > 80:  # Leave room for "(Dormant)" suffix
            name = name[:77] + "..."
        
        return name
    
    def _save_location_to_db(self, conn, location: Dict[str, Any]) -> int:
        """Saves a single location within a transaction and returns its new ID."""
        query = '''INSERT INTO locations 
                   (name, location_type, description, wealth_level, population,
                    x_coord, y_coord, system_name, established_date, has_jobs, has_shops, has_medical, 
                    has_repairs, has_fuel, has_upgrades, has_black_market, is_generated, is_derelict, has_shipyard) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
        params = (
            location['name'], location['type'], location['description'], 
            location['wealth_level'], location['population'], location['x_coord'], 
            location['y_coord'], location['system_name'], location.get('established_date'),
            location['has_jobs'], location['has_shops'], location['has_medical'], 
            location['has_repairs'], location['has_fuel'], location['has_upgrades'],
            location.get('has_black_market', False), location['is_generated'], 
            location.get('is_derelict', False), location.get('has_shipyard', False)
        )
        return self.db.execute_in_transaction(conn, query, params, fetch='lastrowid')
    
    def _generate_unique_name(self, loc_type: str, used_names: set) -> str:
        """Generate a unique location name"""
        
        attempts = 0
        while attempts < 50:
            if loc_type == 'space_station':
                if random.random() < 0.7:
                    name = f"{random.choice(self.location_names)} Station"
                else:
                    name = f"{random.choice(self.location_prefixes)} {random.choice(self.location_names)}"
            elif loc_type == 'outpost':
                name = f"{random.choice(self.location_names)} Outpost"
            else:  # colony
                if random.random() < 0.5:
                    name = f"{random.choice(self.location_prefixes)} {random.choice(self.location_names)}"
                else:
                    name = random.choice(self.location_names)
            
            if name not in used_names:
                return name
            attempts += 1
        
        # Fallback with numbers
        base_name = random.choice(self.location_names)
        counter = 1
        while f"{base_name} {counter}" in used_names:
            counter += 1
        return f"{base_name} {counter}"
    
    def _generate_unique_system(self, used_systems: set) -> str:
        """Generate a unique system name"""
        
        available_systems = [s for s in self.system_names if s not in used_systems]
        if available_systems:
            return random.choice(available_systems)
        
        # Generate numbered systems if we run out
        counter = 1
        while f"System-{counter:03d}" in used_systems:
            counter += 1
        return f"System-{counter:03d}"
    
    def _find_nearby_locations(self, location: Dict, candidates: List[Dict], max_distance: float) -> List[Dict]:
        """Find locations within max_distance, sorted by proximity"""
        
        nearby = []
        for candidate in candidates:
            if candidate['id'] != location['id']:  # Don't include self
                distance = self._calculate_distance(location, candidate)
                if distance <= max_distance:
                    nearby.append(candidate)
        
        # Sort by distance
        nearby.sort(key=lambda loc: self._calculate_distance(location, loc))
        return nearby
    
    def _calculate_distance(self, loc1: Dict, loc2: Dict) -> float:
        """Calculate distance between two locations"""
        dx = loc1['x_coord'] - loc2['x_coord']
        dy = loc1['y_coord'] - loc2['y_coord']
        return math.sqrt(dx * dx + dy * dy)
    
    # Visual map generation with updated gate display
    @galaxy_group.command(name="visual_map", description="Generate a visual map of the galaxy")
    @app_commands.describe(
        map_style="Style of the visual map",
        show_labels="Whether to show location names",
        highlight_player="Highlight a specific player's location"
    )
    @app_commands.choices(map_style=[
        app_commands.Choice(name="Standard", value="standard"),
        app_commands.Choice(name="Infrastructure", value="infrastructure"), 
        app_commands.Choice(name="Wealth", value="wealth"),
        app_commands.Choice(name="Connections", value="connections"),
        app_commands.Choice(name="Danger", value="danger")
    ])
    async def visual_map(self, interaction: discord.Interaction, 
                        map_style: str = "standard", 
                        show_labels: bool = False,
                        highlight_player: discord.Member = None):
        
        await interaction.response.defer()
        
        try:
            map_buffer = await self._generate_visual_map(map_style, show_labels, highlight_player)
            
            if map_buffer is None:
                await interaction.followup.send("No locations found! Generate a galaxy first with `/galaxy generate`.")
                return
            
            map_file = discord.File(map_buffer, filename=f"galaxy_map_{map_style}.png")
            
            embed = discord.Embed(
                title=f"🌌 Galaxy Map - {map_style.title()} View",
                description=self._get_map_description(map_style),
                color=0x4169E1
            )
            
            legend_text = self._get_legend_text(map_style)
            if legend_text:
                embed.add_field(name="Legend", value=f"```\n{legend_text}\n```", inline=False)
            
            stats = await self._get_galaxy_stats()
            if stats:
                embed.add_field(name="Galaxy Statistics", value=stats, inline=True)
            
            embed.set_image(url="attachment://galaxy_map_{}.png".format(map_style))
            
            await interaction.followup.send(embed=embed, file=map_file)
            
        except Exception as e:
            import traceback
            print(f"Visual map generation error: {traceback.format_exc()}")
            await interaction.followup.send(f"Error generating visual map: {str(e)}\nPlease check that the galaxy has been generated and try again.")
    
    async def _generate_visual_map(self, map_style: str, show_labels: bool, highlight_player: discord.Member = None) -> io.BytesIO:
        """Generate visual map with enhanced zoom, focus, and readability"""
        
        # Fetch locations and corridors
        locations = self.db.execute_query(
            "SELECT location_id, name, location_type, x_coord, y_coord, wealth_level FROM locations",
            fetch='all'
        )
        if not locations:
            return None
        
        corridors = self.db.execute_query(
            '''SELECT c.origin_location, c.destination_location, c.danger_level,
                      ol.x_coord as ox, ol.y_coord as oy,
                      dl.x_coord as dx, dl.y_coord as dy, ol.location_type as origin_type
               FROM corridors c
               JOIN locations ol ON c.origin_location = ol.location_id
               JOIN locations dl ON c.destination_location = dl.location_id
               WHERE c.is_active = 1''',
            fetch='all'
        )
        
        # Look up the player's current location
        player_location = None
        player_coords = None
        if highlight_player:
            result = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (highlight_player.id,),
                fetch='one'
            )
            if result:
                player_location = result[0]
                for loc_id, name, loc_type, x, y, wealth in locations:
                    if loc_id == player_location:
                        player_coords = (x, y)
                        break
        
        # Determine zoom level and focus area
        zoom_level = "galaxy"  # Default to full galaxy view
        focus_center = None
        focus_radius = None
        
        if player_coords:
            zoom_level = "regional"
            focus_center = player_coords
            focus_radius = 40  # Regional view radius
        
        # Set up the figure with improved styling
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(20, 16), dpi=120)
        fig.patch.set_facecolor('#000011')
        ax.set_facecolor('#000011')
        
        # Filter locations and corridors based on zoom
        visible_locations = locations
        visible_corridors = corridors
        
        if zoom_level == "regional" and focus_center:
            # Filter to nearby locations for regional view
            fx, fy = focus_center
            visible_locations = []
            visible_location_ids = set()
            
            for loc in locations:
                loc_id, name, loc_type, x, y, wealth = loc
                distance = math.sqrt((x - fx)**2 + (y - fy)**2)
                if distance <= focus_radius or loc_id == player_location:
                    visible_locations.append(loc)
                    visible_location_ids.add(loc_id)
            
            # Filter corridors to only those connecting visible locations
            visible_corridors = []
            for corridor in corridors:
                origin_id, dest_id = corridor[0], corridor[1]
                if origin_id in visible_location_ids and dest_id in visible_location_ids:
                    visible_corridors.append(corridor)
        
        # Draw enhanced map elements
        await self._draw_space_background(ax, zoom_level, focus_center, focus_radius)
        await self._draw_corridors_enhanced(ax, visible_corridors, map_style, zoom_level)
        await self._draw_locations_enhanced(ax, visible_locations, map_style, player_location, zoom_level)
        
        if show_labels:
            await self._add_smart_labels(ax, visible_locations, map_style, zoom_level, player_location)
        
        # Add player context information
        if player_location and zoom_level == "regional":
            await self._add_player_context(ax, visible_locations, player_location, focus_center)
        
        # Style and set view
        await self._style_plot_enhanced(ax, map_style, highlight_player, zoom_level)
        
        # Set view bounds
        if zoom_level == "regional" and focus_center:
            fx, fy = focus_center
            margin = focus_radius * 1.2
            ax.set_xlim(fx - margin, fx + margin)
            ax.set_ylim(fy - margin, fy + margin)
        else:
            # Auto-fit to all locations with padding
            if visible_locations:
                x_coords = [loc[3] for loc in visible_locations]
                y_coords = [loc[4] for loc in visible_locations]
                x_range = max(x_coords) - min(x_coords)
                y_range = max(y_coords) - min(y_coords)
                padding = max(x_range, y_range) * 0.1
                
                ax.set_xlim(min(x_coords) - padding, max(x_coords) + padding)
                ax.set_ylim(min(y_coords) - padding, max(y_coords) + padding)
        
        # Add enhanced legend and info
        await self._add_enhanced_legend(ax, map_style, zoom_level, visible_locations, visible_corridors)
        
        # Save to buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='PNG', bbox_inches='tight',
                    facecolor='#000011', edgecolor='none', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        return buffer

    async def _draw_space_background(self, ax, zoom_level: str, focus_center: tuple = None, focus_radius: float = None):
        """Draw enhanced space background with context-aware details"""
        
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Determine star density based on zoom level
        if zoom_level == "regional":
            star_density = 200  # More stars for regional view
            nebula_count = 2
            nebula_size_range = (8, 20)
        else:
            star_density = 150  # Fewer stars for galaxy view
            nebula_count = 4
            nebula_size_range = (20, 50)
        
        # Enhanced star field
        star_x = np.random.uniform(xlim[0], xlim[1], star_density)
        star_y = np.random.uniform(ylim[0], ylim[1], star_density)
        
        # Variable star sizes and colors
        star_sizes = np.random.exponential(1.5, star_density)
        star_colors = np.random.choice(['white', '#ffffaa', '#aaaaff', '#ffaaaa'], star_density, p=[0.6, 0.2, 0.15, 0.05])
        star_alphas = np.random.uniform(0.2, 0.8, star_density)
        
        for i in range(star_density):
            ax.scatter(star_x[i], star_y[i], c=star_colors[i], s=star_sizes[i], 
                      alpha=star_alphas[i], zorder=0)
        
        # Enhanced nebulae with varied colors
        nebula_colors = ['#4B0082', '#483D8B', '#2F4F4F', '#8B4513', '#556B2F']
        
        for _ in range(nebula_count):
            center_x = random.uniform(xlim[0], xlim[1])
            center_y = random.uniform(ylim[0], ylim[1])
            width = random.uniform(*nebula_size_range)
            height = random.uniform(*nebula_size_range)
            
            nebula = patches.Ellipse((center_x, center_y), width, height,
                                   alpha=random.uniform(0.15, 0.25), 
                                   facecolor=random.choice(nebula_colors),
                                   zorder=0)
            ax.add_patch(nebula)
        
        # Add grid for regional view
        if zoom_level == "regional" and focus_center:
            ax.grid(True, alpha=0.15, color='cyan', linestyle=':', linewidth=0.5)
    async def _draw_locations_enhanced(self, ax, locations, map_style, player_location=None, zoom_level="galaxy"):
        """Draw locations with enhanced visibility and context-aware sizing"""
        
        # Enhanced location styles with zoom-aware sizing
        base_sizes = {
            'colony': 120 if zoom_level == "regional" else 100,
            'space_station': 160 if zoom_level == "regional" else 140,
            'outpost': 90 if zoom_level == "regional" else 70,
            'gate': 60 if zoom_level == "regional" else 40
        }
        
        location_styles = {
            'colony': {'marker': 'o', 'base_color': '#ff6600', 'size': base_sizes['colony']},
            'space_station': {'marker': 's', 'base_color': '#00aaff', 'size': base_sizes['space_station']},
            'outpost': {'marker': '^', 'base_color': '#888888', 'size': base_sizes['outpost']},
            'gate': {'marker': 'D', 'base_color': '#ffdd00', 'size': base_sizes['gate']}
        }
        
        # Separate locations by type for proper layering
        location_layers = {
            'major': [loc for loc in locations if loc[2] in ['colony', 'space_station']],
            'minor': [loc for loc in locations if loc[2] == 'outpost'],
            'infrastructure': [loc for loc in locations if loc[2] == 'gate']
        }
        
        # Draw in layers: infrastructure -> minor -> major -> player
        for layer_name, location_list in location_layers.items():
            for location in location_list:
                loc_id, name, loc_type, x, y, wealth = location
                style = location_styles.get(loc_type, location_styles['colony'])
                
                # Determine color and size based on map style
                color, size, alpha = await self._get_location_appearance(
                    loc_id, loc_type, wealth, map_style, style, zoom_level
                )
                
                # Enhanced glow effect for important locations
                if wealth >= 8 or loc_type == 'space_station':
                    glow_color = color if isinstance(color, str) else '#ffffff'
                    ax.scatter(x, y, c=glow_color, marker=style['marker'], 
                              s=size*1.5, alpha=0.3, zorder=2)
                
                # Main location marker
                ax.scatter(x, y, c=color, marker=style['marker'], s=size, 
                          edgecolors='white', linewidth=1.5, alpha=alpha, zorder=3)
                
                # Special indicators
                if wealth >= 9:
                    # Wealth indicator
                    ax.scatter(x, y+2, c='gold', marker='*', s=20, zorder=4)
                
                # Black market indicator (if applicable)
                has_black_market = self.db.execute_query(
                    "SELECT has_black_market FROM locations WHERE location_id = ?",
                    (loc_id,), fetch='one'
                )
                if has_black_market and has_black_market[0]:
                    ax.scatter(x-2, y-2, c='red', marker='o', s=15, alpha=0.7, zorder=4)
        
        # Draw player location with enhanced highlighting
        if player_location:
            for location in locations:
                loc_id, name, loc_type, x, y, wealth = location
                if loc_id == player_location:
                    # Multiple ring system for better visibility
                    rings = [
                        {'radius': 25, 'color': 'yellow', 'width': 4, 'alpha': 1.0},
                        {'radius': 20, 'color': 'white', 'width': 3, 'alpha': 0.9},
                        {'radius': 15, 'color': 'red', 'width': 2, 'alpha': 0.8}
                    ]
                    
                    for ring in rings:
                        circle = plt.Circle((x, y), ring['radius'], fill=False, 
                                          color=ring['color'], linewidth=ring['width'], 
                                          alpha=ring['alpha'], zorder=5)
                        ax.add_patch(circle)
                    
                    # Central star indicator
                    ax.scatter(x, y, c='yellow', marker='*', s=200, 
                              edgecolors='red', linewidth=2, alpha=1.0, zorder=6)
                    break

    async def _get_location_appearance(self, loc_id: int, loc_type: str, wealth: int, 
                                     map_style: str, style: dict, zoom_level: str):
        """Get enhanced appearance based on map style and context"""
        
        base_color = style['base_color']
        base_size = style['size']
        alpha = 1.0
        
        if map_style == 'wealth':
            # Enhanced wealth visualization
            wealth_ratio = wealth / 10.0
            color = plt.cm.RdYlGn(wealth_ratio)
            size = base_size + (wealth * 8)
            
        elif map_style == 'infrastructure':
            if loc_type == 'gate':
                color = '#ffff00'  # Bright yellow for gates
                size = base_size + 30
            elif loc_type == 'space_station':
                color = '#00ffff'  # Cyan for stations
                size = base_size + 20
            else:
                color = base_color
                size = base_size
                alpha = 0.7
                
        elif map_style == 'connections':
            # Color and size based on connectivity
            connections = self.db.execute_query(
                "SELECT COUNT(*) FROM corridors WHERE origin_location = ? OR destination_location = ?",
                (loc_id, loc_id), fetch='one'
            )[0]
            
            connection_ratio = min(connections / 8.0, 1.0)
            color = plt.cm.plasma(connection_ratio)
            size = base_size + (connections * 10)
            
        elif map_style == 'danger':
            # Color based on nearby corridor danger
            avg_danger = self.db.execute_query(
                "SELECT AVG(danger_level) FROM corridors WHERE origin_location = ?",
                (loc_id,), fetch='one'
            )[0] or 1
            
            danger_ratio = (avg_danger - 1) / 4.0  # Normalize 1-5 to 0-1
            color = plt.cm.Reds(0.3 + danger_ratio * 0.7)
            size = base_size
            
        else:  # standard
            color = base_color
            size = base_size
        
        return color, size, alpha
    
    async def _draw_corridors_enhanced(self, ax, corridors, map_style, zoom_level="galaxy"):
        """Draw corridors with enhanced visual distinction and clarity"""
        
        # Base styling
        line_width_base = 1.5 if zoom_level == "regional" else 1.0
        alpha_base = 0.6 if zoom_level == "regional" else 0.4
        
        # Group corridors by type for better layering
        corridor_groups = {
            'approach': [],
            'gated': [],
            'ungated': []
        }
        
        for corridor in corridors:
            origin_id, dest_id, danger, ox, oy, dx, dy, origin_type = corridor
            
            # Determine corridor type
            corridor_name = self.db.execute_query(
                "SELECT name FROM corridors WHERE origin_location = ? AND destination_location = ?",
                (origin_id, dest_id), fetch='one'
            )
            corridor_name = corridor_name[0] if corridor_name else ""
            
            if "Approach" in corridor_name:
                corridor_groups['approach'].append(corridor)
            elif "Ungated" in corridor_name:
                corridor_groups['ungated'].append(corridor)
            else:
                corridor_groups['gated'].append(corridor)
        
        # Draw corridors in order: approach -> gated -> ungated (most dangerous on top)
        for group_name, group_corridors in corridor_groups.items():
            for corridor in group_corridors:
                origin_id, dest_id, danger, ox, oy, dx, dy, origin_type = corridor
                
                # Get enhanced styling based on type and map style
                line_style = await self._get_corridor_style(
                    group_name, danger, map_style, line_width_base, alpha_base
                )
                
                # Draw main corridor line
                ax.plot([ox, dx], [oy, dy], 
                       color=line_style['color'],
                       alpha=line_style['alpha'],
                       linewidth=line_style['width'],
                       linestyle=line_style['linestyle'],
                       zorder=line_style['zorder'])
                
                # Add danger indicators for high-risk corridors
                if danger >= 4 and zoom_level == "regional":
                    await self._add_danger_indicators(ax, ox, oy, dx, dy, danger)
                
                # Add flow direction arrows for regional view
                if zoom_level == "regional" and map_style == "connections":
                    await self._add_flow_arrows(ax, ox, oy, dx, dy, line_style['color'])

    async def _get_corridor_style(self, corridor_type: str, danger: int, map_style: str, 
                                base_width: float, base_alpha: float) -> dict:
        """Get enhanced corridor styling based on type and map style"""
        
        style = {
            'width': base_width,
            'alpha': base_alpha,
            'linestyle': '-',
            'zorder': 1
        }
        
        if map_style == 'danger':
            # Danger-based coloring
            danger_colors = ['#00ff00', '#88ff00', '#ffff00', '#ff8800', '#ff0000']
            style['color'] = danger_colors[min(danger - 1, 4)]
            style['alpha'] = 0.4 + (danger * 0.1)
            style['width'] = base_width + (danger * 0.3)
            
        elif map_style == 'infrastructure':
            # Infrastructure-focused styling
            if corridor_type == 'approach':
                style['color'] = '#88ff88'  # Light green for local space
                style['alpha'] = 0.6
                style['width'] = base_width * 0.8
                style['linestyle'] = ':'
            elif corridor_type == 'gated':
                style['color'] = '#00ff88'  # Bright green for gated routes
                style['alpha'] = 0.8
                style['width'] = base_width * 1.2
            else:  # ungated
                style['color'] = '#ff6600'  # Orange for dangerous ungated
                style['alpha'] = 0.7
                style['width'] = base_width
                style['linestyle'] = '--'
                
        elif map_style == 'connections':
            # Connection flow styling
            style['color'] = '#00aaff'
            style['alpha'] = base_alpha + 0.2
            style['width'] = base_width * 1.1
            
        else:  # standard and wealth
            # Standard corridor colors
            if corridor_type == 'approach':
                style['color'] = '#666688'
            elif corridor_type == 'gated':
                style['color'] = '#4488aa'
            else:  # ungated
                style['color'] = '#aa6644'
        
        # Adjust zorder based on importance
        if corridor_type == 'ungated':
            style['zorder'] = 3  # Most dangerous on top
        elif corridor_type == 'gated':
            style['zorder'] = 2
        else:
            style['zorder'] = 1
        
        return style

    async def _add_danger_indicators(self, ax, ox: float, oy: float, dx: float, dy: float, danger: int):
        """Add visual danger indicators along high-risk corridors"""
        
        # Calculate midpoint and quarter points
        mid_x, mid_y = (ox + dx) / 2, (oy + dy) / 2
        q1_x, q1_y = (ox * 3 + dx) / 4, (oy * 3 + dy) / 4
        q3_x, q3_y = (ox + dx * 3) / 4, (oy + dy * 3) / 4
        
        danger_color = '#ff4444' if danger >= 5 else '#ff8844'
        
        # Add warning symbols using valid matplotlib markers
        warning_markers = ['^', 'v', 's']  # Triangle up, triangle down, square
        
        for i, (px, py) in enumerate([(q1_x, q1_y), (mid_x, mid_y), (q3_x, q3_y)]):
            marker = warning_markers[i % len(warning_markers)]
            ax.scatter(px, py, c=danger_color, marker=marker, s=30, alpha=0.8, zorder=4)
            
            # Add a subtle glow effect for high danger
            if danger >= 5:
                ax.scatter(px, py, c=danger_color, marker=marker, s=50, alpha=0.3, zorder=3)

    async def _add_flow_arrows(self, ax, ox: float, oy: float, dx: float, dy: float, color: str):
        """Add directional flow arrows for connection visualization"""
        
        # Calculate arrow position (1/3 along the line)
        arrow_x = ox + (dx - ox) * 0.33
        arrow_y = oy + (dy - oy) * 0.33
        
        # Calculate arrow direction
        arrow_dx = (dx - ox) * 0.1
        arrow_dy = (dy - oy) * 0.1
        
        ax.arrow(arrow_x, arrow_y, arrow_dx, arrow_dy,
                 head_width=2, head_length=2, fc=color, ec=color,
                 alpha=0.7, zorder=2)
    
    def _corridor_has_gate(self, origin_id: int, dest_id: int) -> bool:
        """Check if either endpoint of corridor is a gate"""
        gate_check = self.db.execute_query(
            '''SELECT COUNT(*) FROM locations 
               WHERE (location_id = ? OR location_id = ?) AND location_type = 'gate' ''',
            (origin_id, dest_id),
            fetch='one'
        )
        return gate_check[0] > 0
    
    async def _add_smart_labels(self, ax, locations, map_style, zoom_level, player_location=None):
        """Add smart labels with collision detection and priority-based display"""
        
        if zoom_level == "regional":
            max_labels = 15
            min_distance = 8
        else:
            max_labels = 25
            min_distance = 12
        
        # Calculate label priorities and data
        label_candidates = []
        
        for location in locations:
            loc_id, name, loc_type, x, y, wealth = location
            
            # Calculate priority
            priority = await self._calculate_label_priority(
                loc_id, loc_type, wealth, player_location, map_style
            )
            
            # Get connections for context
            connections = self.db.execute_query(
                "SELECT COUNT(*) FROM corridors WHERE origin_location = ? OR destination_location = ?",
                (loc_id, loc_id), fetch='one'
            )[0]
            
            label_candidates.append({
                'name': name,
                'x': x,
                'y': y,
                'type': loc_type,
                'wealth': wealth,
                'priority': priority,
                'connections': connections,
                'is_player': loc_id == player_location
            })
        
        # Sort by priority and apply collision detection
        label_candidates.sort(key=lambda x: x['priority'], reverse=True)
        placed_labels = []
        
        for candidate in label_candidates[:max_labels]:
            # Check for collisions with already placed labels
            collision = False
            for placed in placed_labels:
                distance = math.sqrt((candidate['x'] - placed['x'])**2 + 
                                   (candidate['y'] - placed['y'])**2)
                if distance < min_distance:
                    collision = True
                    break
            
            if not collision:
                placed_labels.append(candidate)
        
        # Draw labels with enhanced styling
        for label in placed_labels:
            await self._draw_enhanced_label(ax, label, zoom_level)

    async def _calculate_label_priority(self, loc_id: int, loc_type: str, wealth: int, 
                                      player_location: int, map_style: str) -> float:
        """Calculate label priority based on multiple factors"""
        
        priority = 0.0
        
        # Base priority by type
        type_priorities = {
            'space_station': 10.0,
            'colony': 7.0,
            'gate': 5.0,
            'outpost': 3.0
        }
        priority += type_priorities.get(loc_type, 1.0)
        
        # Wealth bonus
        priority += wealth * 0.5
        
        # Player location gets highest priority
        if loc_id == player_location:
            priority += 50.0
        
        # Connectivity bonus
        connections = self.db.execute_query(
            "SELECT COUNT(*) FROM corridors WHERE origin_location = ? OR destination_location = ?",
            (loc_id, loc_id), fetch='one'
        )[0]
        priority += connections * 0.8
        
        # Map style specific bonuses
        if map_style == 'infrastructure' and loc_type == 'gate':
            priority += 5.0
        elif map_style == 'wealth' and wealth >= 8:
            priority += 3.0
        elif map_style == 'connections' and connections >= 4:
            priority += 4.0
        
        return priority

    async def _draw_enhanced_label(self, ax, label: dict, zoom_level: str):
        """Draw enhanced label with context-aware styling"""
        
        x, y = label['x'], label['y']
        name = label['name']
        loc_type = label['type']
        wealth = label['wealth']
        is_player = label['is_player']
        
        # Font size based on zoom and importance
        if is_player:
            fontsize = 14 if zoom_level == "regional" else 12
            weight = 'bold'
        elif loc_type == 'space_station':
            fontsize = 12 if zoom_level == "regional" else 10
            weight = 'bold'
        elif wealth >= 8:
            fontsize = 11 if zoom_level == "regional" else 9
            weight = 'bold'
        else:
            fontsize = 10 if zoom_level == "regional" else 8
            weight = 'normal'
        
        # Color coding
        label_colors = {
            'colony': '#ffaa44',
            'space_station': '#44aaff',
            'outpost': '#aaaaaa',
            'gate': '#ffff44'
        }
        
        color = label_colors.get(loc_type, 'white')
        if is_player:
            color = '#ffff00'
        
        # Enhanced name formatting
        display_name = name
        if wealth >= 9:
            display_name = f"⭐ {name}"
        elif wealth >= 8:
            display_name = f"{name} ✦"
        
        # Smart offset calculation to avoid overlapping location marker
        offset_distance = 15 if zoom_level == "regional" else 12
        offset_x = random.uniform(-offset_distance, offset_distance)
        offset_y = random.uniform(-offset_distance, offset_distance)
        
        # Ensure offset doesn't put label too close to marker
        if abs(offset_x) < 8:
            offset_x = 8 if offset_x >= 0 else -8
        if abs(offset_y) < 8:
            offset_y = 8 if offset_y >= 0 else -8
        
        # Enhanced text box
        bbox_props = dict(
            boxstyle='round,pad=0.4',
            facecolor='black',
            edgecolor=color,
            alpha=0.8,
            linewidth=1.5 if is_player else 1.0
        )
        
        ax.annotate(display_name, (x, y), 
                   xytext=(offset_x, offset_y), 
                   textcoords='offset points',
                   fontsize=fontsize,
                   color=color,
                   weight=weight,
                   ha='center', va='center',
                   bbox=bbox_props,
                   zorder=10)
    async def _style_plot_enhanced(self, ax, map_style: str, highlight_player: discord.Member, zoom_level: str):
        """Enhanced plot styling with galaxy name and current time"""
        
        # Get galaxy info and current time
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = "Unknown Galaxy"
        current_ingame_time = None
        time_status = ""
        
        if galaxy_info:
            galaxy_name = galaxy_info[0] or "Unknown Galaxy"
            current_ingame_time = time_system.calculate_current_ingame_time()
            is_paused = galaxy_info[5] if len(galaxy_info) > 5 else False
            time_status = " (PAUSED)" if is_paused else ""
        
        # Enhanced titles with galaxy name
        titles = {
            'standard': 'Galaxy Overview',
            'infrastructure': 'Transit Infrastructure Network',
            'wealth': 'Economic Distribution Analysis',
            'connections': 'Trade Route Connectivity',
            'danger': 'Corridor Safety Assessment'
        }
        
        base_title = titles.get(map_style, 'Galaxy Map')
        
        if zoom_level == "regional":
            base_title = f"Regional View - {base_title}"
        
        if highlight_player:
            base_title += f" - {highlight_player.display_name}'s Location"
        
        # Add galaxy name to title
        full_title = f"{galaxy_name} - {base_title}"
        
        ax.set_title(full_title, color='white', fontsize=18, pad=25, weight='bold')
        
        # Enhanced axis labels
        if zoom_level == "regional":
            ax.set_xlabel('Local Coordinates (Tactical)', color='white', fontsize=12)
            ax.set_ylabel('Local Coordinates (Tactical)', color='white', fontsize=12)
        else:
            ax.set_xlabel('Galactic X Coordinate (Strategic)', color='white', fontsize=12)
            ax.set_ylabel('Galactic Y Coordinate (Strategic)', color='white', fontsize=12)
        
        # Enhanced grid
        if zoom_level == "regional":
            ax.grid(True, alpha=0.3, color='cyan', linestyle='-', linewidth=0.5)
        else:
            ax.grid(True, alpha=0.2, color='white', linestyle=':', linewidth=0.5)
        
        ax.tick_params(colors='white', labelsize=10)
        ax.set_aspect('equal', adjustable='box')
        
        # Add galaxy name and current time prominently at the top
        if current_ingame_time:
            formatted_time = time_system.format_ingame_datetime(current_ingame_time)
            # Remove the bold markdown formatting for the plot text
            clean_time = formatted_time.replace("**", "")
            galaxy_time_text = f"{galaxy_name}\nCurrent Time: {clean_time}{time_status}"
        else:
            galaxy_time_text = f"{galaxy_name}\nTime: Unknown{time_status}"
        
        # Position at top-left with background box
        ax.text(0.02, 0.98, galaxy_time_text,
               transform=ax.transAxes,
               fontsize=12, color='white',
               ha='left', va='top',
               weight='bold',
               bbox=dict(boxstyle='round,pad=0.8', facecolor='black', 
                        edgecolor='gold', alpha=0.9, linewidth=2),
               zorder=15)
        
        # Add generation timestamp and zoom indicator at bottom-right
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        info_text = f"Generated: {timestamp} | View: {zoom_level.title()}"
        if zoom_level == "regional":
            info_text += " | Scale: Tactical"
        else:
            info_text += " | Scale: Strategic"
        
        ax.text(0.99, 0.01, info_text,
               transform=ax.transAxes,
               fontsize=8, color='gray',
               ha='right', va='bottom',
               alpha=0.8)
    
    async def _add_space_decorations(self, ax):
        """Add decorative space elements"""
        
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Stars
        num_stars = 100
        star_x = np.random.uniform(xlim[0], xlim[1], num_stars)
        star_y = np.random.uniform(ylim[0], ylim[1], num_stars)
        star_sizes = np.random.uniform(0.5, 3.0, num_stars)
        
        ax.scatter(star_x, star_y, c='white', s=star_sizes, alpha=0.3, zorder=0)
        
        # Nebula patches
        for _ in range(3):
            center_x = random.uniform(xlim[0], xlim[1])
            center_y = random.uniform(ylim[0], ylim[1])
            width = random.uniform(20, 40)
            height = random.uniform(15, 30)
            
            nebula = patches.Ellipse((center_x, center_y), width, height,
                                   alpha=0.1, facecolor=random.choice(['purple', 'blue', 'green']),
                                   zorder=0)
            ax.add_patch(nebula)
    
    def _get_map_description(self, map_style: str) -> str:
        """Updated descriptions with galaxy context"""
        
        # Get galaxy name for context
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        galaxy_info = time_system.get_galaxy_info()
        galaxy_name = galaxy_info[0] if galaxy_info else "Unknown Galaxy"
        
        descriptions = {
            'standard': f'Overview of all locations and major corridor connections in {galaxy_name}.',
            'infrastructure': f'Transit infrastructure in {galaxy_name} showing gates (yellow diamonds) and route safety (green=gated, orange=ungated).',
            'wealth': f'Economic analysis of {galaxy_name} showing location prosperity and resource distribution.',
            'connections': f'Trade route network in {galaxy_name} displaying connectivity and traffic flow.',
            'danger': f'Corridor danger assessment for {galaxy_name} showing radiation levels and structural integrity.'
        }
        return descriptions.get(map_style, f'Visual representation of {galaxy_name}.')
    
    def _get_legend_text(self, map_style: str) -> str:
        """Updated legends with matplotlib-compatible symbols"""
        legends = {
            'standard': '●  Colonies\n■  Space Stations\n▲  Outposts\n◆  Transit Gates',
            'infrastructure': '──  Gated Corridors (Inter-system)\n┈┈  Local Space (Intra-system)\n◆  Yellow Gates: Transit Infrastructure',
            'wealth': 'Green: Wealthy (8-10)\nYellow: Moderate (5-7)\nRed: Poor (1-4)\nSize indicates economic power',
            'connections': 'Brighter/Larger = More Connected\nBlue lines show active corridors',
            'danger': 'Green: Safe (1-2)\nYellow: Moderate (3)\nOrange: Dangerous (4)\nRed: Extreme (5)'
        }
        return legends.get(map_style, '')
    async def _add_enhanced_legend(self, ax, map_style: str, zoom_level: str, 
                                 locations: list, corridors: list):
        """Add enhanced legend with matplotlib-compatible symbols"""
        
        # Position legend based on zoom level
        if zoom_level == "regional":
            legend_x = 0.02
            legend_y = 0.85  # Moved up slightly to avoid galaxy info box
            font_size = 10
        else:
            legend_x = 0.02
            legend_y = 0.82  # Moved up slightly to avoid galaxy info box
            font_size = 9
        
        legend_items = []
        
        # Map style specific legends with matplotlib-compatible symbols
        if map_style == 'infrastructure':
            legend_items = [
                "LOCATION TYPES:",
                "■  Space Stations", 
                "●  Colonies", 
                "▲  Outposts", 
                "◆  Transit Gates",
                "",
                "CORRIDOR TYPES:",
                "──  Gated Corridors (Safe)", 
                "┈┈  Local Space", 
                "╌╌  Ungated (Dangerous)"
            ]
        elif map_style == 'wealth':
            legend_items = [
                "ECONOMIC INDICATORS:",
                "Green   Wealthy (8-10)", 
                "Yellow  Moderate (5-7)", 
                "Red     Poor (1-4)", 
                "* Gold  Premium (9+)", 
                "",
                "Size = Economic Power"
            ]
        elif map_style == 'connections':
            legend_items = [
                "CONNECTIVITY ANALYSIS:",
                "Bright/Large = Well Connected",
                "→  Traffic Flow Direction", 
                "Blue Lines = Active Routes",
                "",
                "Size = Connection Count"
            ]
        elif map_style == 'danger':
            legend_items = [
                "CORRIDOR DANGER LEVELS:",
                "Green   Safe (1-2)", 
                "Yellow  Moderate (3)",
                "Orange  Dangerous (4)", 
                "Red     Extreme (5)", 
                "",
                "!  Hazard Warnings"
            ]
        else:  # standard
            legend_items = [
                "LOCATION TYPES:",
                "■  Space Stations", 
                "●  Colonies", 
                "▲  Outposts", 
                "◆  Gates",
                "",
                "OTHER:",
                "──  Corridor Routes", 
                "★  You Are Here", 
                "*  High Value Location"
            ]
        
        # Add statistical information for regional view
        if zoom_level == "regional":
            stats = await self._get_regional_stats(locations, corridors)
            legend_items.extend(["", "REGIONAL STATISTICS:"] + stats)
        
        # Add time scale information
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        galaxy_info = time_system.get_galaxy_info()
        
        if galaxy_info:
            time_scale = galaxy_info[2] if len(galaxy_info) > 2 else 4.0
            is_paused = galaxy_info[5] if len(galaxy_info) > 5 else False
            
            legend_items.extend([
                "",
                "TIME SYSTEM:",
                f"Scale: {time_scale}x speed",
                f"Status: {'PAUSED' if is_paused else 'RUNNING'}"
            ])
        
        # Draw legend box
        legend_text = "\n".join(legend_items)
        
        ax.text(legend_x, legend_y, legend_text,
               transform=ax.transAxes,
               fontsize=font_size,
               verticalalignment='top',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='black', 
                        edgecolor='white', alpha=0.9),
               color='white',
               family='monospace')    
    async def _add_player_context(self, ax, locations: list, player_location: int, focus_center: tuple):
        """Add contextual information around player location"""
        
        if not focus_center:
            return
        
        fx, fy = focus_center
        
        # Find player's location details
        player_loc_info = None
        for loc in locations:
            if loc[0] == player_location:
                player_loc_info = loc
                break
        
        if not player_loc_info:
            return
        
        loc_id, name, loc_type, x, y, wealth = player_loc_info
        
        # Add proximity rings around player
        proximity_rings = [
            {'radius': 10, 'color': 'yellow', 'alpha': 0.2, 'label': 'Local'},
            {'radius': 20, 'color': 'orange', 'alpha': 0.15, 'label': 'Regional'},
            {'radius': 35, 'color': 'red', 'alpha': 0.1, 'label': 'Extended'}
        ]
        
        for ring in proximity_rings:
            circle = plt.Circle((fx, fy), ring['radius'], fill=False,
                              color=ring['color'], alpha=ring['alpha'],
                              linewidth=1, linestyle='--', zorder=1)
            ax.add_patch(circle)
        
        # Add nearby location highlights
        nearby_locations = []
        for loc in locations:
            if loc[0] != player_location:
                loc_x, loc_y = loc[3], loc[4]
                distance = math.sqrt((loc_x - fx)**2 + (loc_y - fy)**2)
                if distance <= 15:  # Close proximity
                    nearby_locations.append((loc, distance))
        
        # Highlight closest 3 locations
        nearby_locations.sort(key=lambda x: x[1])
        for i, (loc, distance) in enumerate(nearby_locations[:3]):
            loc_x, loc_y = loc[3], loc[4]
            color_intensity = 1.0 - (i * 0.3)  # Fade for further locations
            
            # Draw connection line
            ax.plot([fx, loc_x], [fy, loc_y], 
                   color='cyan', alpha=color_intensity * 0.5, 
                   linewidth=1, linestyle=':', zorder=1)
            
            # Distance label
            ax.text((fx + loc_x) / 2, (fy + loc_y) / 2, f"{distance:.1f}",
                   fontsize=8, color='cyan', alpha=color_intensity,
                   ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))
    async def _get_regional_stats(self, locations: list, corridors: list) -> list:
        """Get statistical information for regional view"""
        
        stats = []
        
        # Location counts
        type_counts = {}
        total_wealth = 0
        
        for loc in locations:
            loc_type = loc[2]
            wealth = loc[5]
            type_counts[loc_type] = type_counts.get(loc_type, 0) + 1
            total_wealth += wealth
        
        # Format type counts
        for loc_type, count in type_counts.items():
            type_name = loc_type.replace('_', ' ').title()
            stats.append(f"{type_name}s: {count}")
        
        # Average wealth
        if locations:
            avg_wealth = total_wealth / len(locations)
            stats.append(f"Avg Wealth: {avg_wealth:.1f}")
        
        # Corridor information
        if corridors:
            stats.append(f"Routes: {len(corridors)}")
            
            # Danger analysis
            dangers = [c[2] for c in corridors]
            avg_danger = sum(dangers) / len(dangers)
            max_danger = max(dangers)
            stats.append(f"Avg Danger: {avg_danger:.1f}")
            stats.append(f"Max Danger: {max_danger}")
        
        return stats
    async def _get_galaxy_stats(self) -> str:
        """Get galaxy statistics"""
        total_locations = self.db.execute_query("SELECT COUNT(*) FROM locations", fetch='one')[0]
        total_corridors = self.db.execute_query("SELECT COUNT(DISTINCT name) FROM corridors", fetch='one')[0]
        gates = self.db.execute_query("SELECT COUNT(*) FROM locations WHERE location_type = 'gate'", fetch='one')[0]
        
        return f"Locations: {total_locations}\nTransit Gates: {gates}\nCorridors: {total_corridors}"
    
    # ... (keep existing map and info commands)
    async def _generate_built_in_repeaters(self, conn, all_locations: List[Dict]) -> int:
        """Generates built-in radio repeaters at major locations in bulk."""
        repeaters_to_insert = []
        
        for location in all_locations:
            repeater_chance = 0.0
            loc_type = location['type']
            wealth = location['wealth_level']

            if loc_type == 'space_station': repeater_chance = 0.4 if wealth >= 8 else 0.2
            elif loc_type == 'colony': repeater_chance = 0.15 if wealth >= 9 else 0.05
            elif loc_type == 'gate': repeater_chance = 0.3
            
            if random.random() < repeater_chance:
                if loc_type == 'space_station':
                    rec_range, trans_range = 12, 8
                elif loc_type == 'gate':
                    rec_range, trans_range = 10, 6
                else: # colony
                    rec_range, trans_range = 8, 5
                
                repeaters_to_insert.append((location['id'], rec_range, trans_range))

        if repeaters_to_insert:
            query = '''INSERT INTO repeaters 
                       (location_id, repeater_type, receive_range, transmit_range, is_active)
                       VALUES (?, 'built_in', ?, ?, 1)'''
            self.db.executemany_in_transaction(conn, query, repeaters_to_insert)
            print(f"📡 Created {len(repeaters_to_insert)} built-in repeaters.")
            
        return len(repeaters_to_insert)
    async def _ensure_galactic_news_setup(self, guild: discord.Guild, galaxy_name: str):
        """Ensure galactic news channel is configured and send connection announcement"""
        
        # Check if galactic updates channel is already configured
        updates_channel_id = self.db.execute_query(
            "SELECT galactic_updates_channel_id FROM server_config WHERE guild_id = ?",
            (guild.id,),
            fetch='one'
        )
        
        news_channel = None
        if updates_channel_id and updates_channel_id[0]:
            news_channel = guild.get_channel(updates_channel_id[0])
        
        # If no configured channel, try to find the galactic news channel
        if not news_channel:
            news_channel_name = "📡-galactic-news"
            for channel in guild.text_channels:
                if channel.name == news_channel_name:
                    news_channel = channel
                    # Update database configuration
                    existing_config = self.db.execute_query(
                        "SELECT guild_id FROM server_config WHERE guild_id = ?",
                        (guild.id,),
                        fetch='one'
                    )
                    
                    if existing_config:
                        self.db.execute_query(
                            "UPDATE server_config SET galactic_updates_channel_id = ? WHERE guild_id = ?",
                            (news_channel.id, guild.id)
                        )
                    else:
                        self.db.execute_query(
                            "INSERT INTO server_config (guild_id, galactic_updates_channel_id) VALUES (?, ?)",
                            (guild.id, news_channel.id)
                        )
                    
                    print(f"📰 Configured existing galactic news channel: {news_channel.id}")
                    break
        
        # Send connection announcement if we have a news channel
        if news_channel:
            news_cog = self.bot.get_cog('GalacticNewsCog')
            if news_cog:
                await news_cog.queue_news(
                    guild.id,
                    'admin_announcement',
                    'Galactic News Network Relay Established',
                    f'The Galactic News Network has successfully established a communication relay with {galaxy_name}. All major galactic events, infrastructure changes, and emergency broadcasts will now be transmitted to this sector with appropriate delays based on interstellar communication protocols. Welcome to the connected galaxy.',
                    None  # No specific location for this administrative message
                )
                print(f"📰 Queued galactic news connection announcement for {galaxy_name}")    
    async def _clear_existing_galaxy_data(self, conn):
        """Clear existing galaxy data in proper order to avoid foreign key constraints"""
        # Clear in reverse dependency order to avoid foreign key issues
        
        # First, clear tables that depend on locations
        self.db.execute_in_transaction(conn, "DELETE FROM home_activities")
        self.db.execute_in_transaction(conn, "DELETE FROM home_interiors")
        self.db.execute_in_transaction(conn, "DELETE FROM home_market_listings")
        self.db.execute_in_transaction(conn, "DELETE FROM home_invitations")
        self.db.execute_in_transaction(conn, "DELETE FROM location_homes")
        
        self.db.execute_in_transaction(conn, "DELETE FROM character_reputation")
        self.db.execute_in_transaction(conn, "DELETE FROM location_items")
        self.db.execute_in_transaction(conn, "DELETE FROM location_logs")
        self.db.execute_in_transaction(conn, "DELETE FROM shop_items")
        self.db.execute_in_transaction(conn, "DELETE FROM jobs")
        self.db.execute_in_transaction(conn, "DELETE FROM job_tracking")
        self.db.execute_in_transaction(conn, "DELETE FROM location_storage")
        self.db.execute_in_transaction(conn, "DELETE FROM location_income_log")
        self.db.execute_in_transaction(conn, "DELETE FROM location_access_control")
        self.db.execute_in_transaction(conn, "DELETE FROM location_upgrades")
        self.db.execute_in_transaction(conn, "DELETE FROM location_ownership")
        self.db.execute_in_transaction(conn, "DELETE FROM location_economy")
        self.db.execute_in_transaction(conn, "DELETE FROM economic_events")
        
        # Clear NPC related tables
        self.db.execute_in_transaction(conn, "DELETE FROM npc_respawn_queue")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_inventory")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_trade_inventory")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_jobs")
        self.db.execute_in_transaction(conn, "DELETE FROM npc_job_completions")
        self.db.execute_in_transaction(conn, "DELETE FROM static_npcs")
        self.db.execute_in_transaction(conn, "DELETE FROM dynamic_npcs")
        
        # Clear black market tables
        self.db.execute_in_transaction(conn, "DELETE FROM black_market_items")
        self.db.execute_in_transaction(conn, "DELETE FROM black_markets")
        
        # Clear sub-locations and repeaters
        self.db.execute_in_transaction(conn, "DELETE FROM sub_locations")
        self.db.execute_in_transaction(conn, "DELETE FROM repeaters")
        
        # Clear travel sessions that reference corridors/locations
        self.db.execute_in_transaction(conn, "DELETE FROM travel_sessions")
        self.db.execute_in_transaction(conn, "DELETE FROM corridor_events")
        
        # Finally clear corridors and locations
        self.db.execute_in_transaction(conn, "DELETE FROM corridors")
        self.db.execute_in_transaction(conn, "DELETE FROM locations")
        
        # Clear history and news
        self.db.execute_in_transaction(conn, "DELETE FROM galactic_history")
        self.db.execute_in_transaction(conn, "DELETE FROM news_queue")
        
        # Clear endgame config if exists
        self.db.execute_in_transaction(conn, "DELETE FROM endgame_config")
        self.db.execute_in_transaction(conn, "DELETE FROM endgame_evacuations")
        
        print("🗑️ Cleared existing galaxy data in proper order")
        
    async def _generate_initial_location_logs(self, conn, all_locations: List[Dict], start_date_obj) -> int:
        """Generate initial log books for locations with ultra-aggressive optimization for large galaxies"""
        from utils.npc_data import generate_npc_name, get_occupation
        
        # Commit the current transaction immediately to avoid long locks
        if conn:
            self.db.commit_transaction(conn)
            conn = None
        
        print(f"📜 Generating log books for {len(all_locations)} locations...")
        
        locations_with_logs = 0
        total_entries_created = 0
        
        # Ultra-small batch sizes for massive galaxies
        location_chunk_size = 3  # Process only 3 locations at a time
        batch_size = 15  # Very small batches for database inserts
        current_batch = []
        
        # Pre-filter locations to avoid processing derelicts
        valid_locations = [loc for loc in all_locations if not loc.get('is_derelict', False)]
        print(f"📜 Processing {len(valid_locations)} non-derelict locations for log books...")
        
        # Process locations in tiny chunks with frequent yielding
        for chunk_start in range(0, len(valid_locations), location_chunk_size):
            chunk_end = min(chunk_start + location_chunk_size, len(valid_locations))
            location_chunk = valid_locations[chunk_start:chunk_end]
            
            # Pre-generate all log data for this chunk without database calls
            chunk_log_entries = []
            
            for location in location_chunk:
                # 25% chance for each location to have a log book (same as original)
                if random.random() < 0.25:
                    locations_with_logs += 1
                    num_entries = random.randint(3, 5)  # Same range as original
                    
                    # Pre-generate all entries for this location
                    for _ in range(num_entries):
                        # Generate NPC author efficiently
                        first_name, last_name = generate_npc_name()
                        wealth_level = location.get('wealth_level', 5)
                        occupation = get_occupation(location['type'], wealth_level)
                        name_format = f"{first_name} {last_name}, {occupation}"
                        
                        # Get message using optimized selection
                        message = self._get_optimized_log_message(location['type'])
                        
                        # Generate historical date
                        days_ago = random.randint(1, 365)
                        hours_ago = random.randint(0, 23)
                        entry_time = start_date_obj - timedelta(days=days_ago, hours=hours_ago)
                        
                        # Add to chunk entries
                        chunk_log_entries.append(
                            (location['id'], 0, name_format, message, entry_time.isoformat(), 1)
                        )
            
            # Add chunk entries to current batch
            current_batch.extend(chunk_log_entries)
            total_entries_created += len(chunk_log_entries)
            
            # Insert when batch is ready, using micro-transactions
            if len(current_batch) >= batch_size:
                await self._insert_log_batch_micro_transaction(current_batch[:batch_size])
                current_batch = current_batch[batch_size:]
                
                # Aggressive yielding after each micro-transaction
                await asyncio.sleep(0.1)
            
            # Yield control after each chunk
            await asyncio.sleep(0.05)
            
            # Progress reporting every 25 locations
            if chunk_start % 25 == 0 and chunk_start > 0:
                progress = (chunk_start / len(valid_locations)) * 100
                print(f"    📜 Log generation progress: {progress:.0f}% ({chunk_start}/{len(valid_locations)}) - {total_entries_created} entries created")
                
                # Extra yield for progress reporting
                await asyncio.sleep(0.1)
        
        # Insert any remaining entries
        while current_batch:
            batch_to_insert = current_batch[:batch_size]
            current_batch = current_batch[batch_size:]
            await self._insert_log_batch_micro_transaction(batch_to_insert)
            await asyncio.sleep(0.05)
        
        print(f"📜 Generated log books for {locations_with_logs} locations with {total_entries_created} total entries")
        return locations_with_logs

    async def _insert_log_batch_micro_transaction(self, batch_data: List[tuple]):
        """Insert log entries in completely independent micro-transaction with retry logic"""
        if not batch_data:
            return
        
        # Retry logic for database lock issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait a bit if this is a retry
                if attempt > 0:
                    await asyncio.sleep(0.2 * attempt)
                
                # Use completely independent micro-transaction
                micro_conn = self.db.begin_transaction()
                
                query = '''INSERT INTO location_logs 
                           (location_id, author_id, author_name, message, posted_at, is_generated)
                           VALUES (?, ?, ?, ?, ?, ?)'''
                self.db.executemany_in_transaction(micro_conn, query, batch_data)
                self.db.commit_transaction(micro_conn)
                
                # Success - break out of retry loop
                break
                
            except Exception as e:
                if micro_conn:
                    try:
                        self.db.rollback_transaction(micro_conn)
                    except:
                        pass
                
                if "database lock" in str(e).lower() and attempt < max_retries - 1:
                    print(f"⚠️ Database lock in log generation, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    print(f"❌ Error inserting log batch: {e}")
                    if attempt == max_retries - 1:
                        print("⚠️ Skipping this log batch to continue generation")
                    break
            finally:
                micro_conn = None

    def _get_optimized_log_message(self, location_type: str) -> str:
        """Get a random log message using optimized selection without loading large arrays"""
        
        # Use smaller, focused message pools with weighted selection
        # 40% chance for location-specific, 60% for generic (same as original)
        if random.random() < 0.4:
            return self._get_location_specific_message(location_type)
        else:
            return self._get_generic_log_message()

    def _get_location_specific_message(self, location_type: str) -> str:
        """Get location-specific message using efficient selection"""
        
        # Smaller, curated pools for each type (maintaining variety but reducing memory)
        type_message_pools = {
            'colony': [
                "Agricultural output exceeding projections this quarter.",
                "Population growth steady. Housing expansion approved.", 
                "Mining operations proceeding on schedule.",
                "Trade relations with neighboring systems improving.",
                "Colonial infrastructure upgrade project initiated.",
                "Atmospheric processors maintaining optimal conditions.",
                "New settlers orientation program completed successfully.",
                "Terraforming efforts progressing as planned.",
                "Water recycling efficiency at 98%.",
                "Biodome experiencing minor issues, contained.",
                "Educational programs seeing increased enrollment.",
                "Defensive perimeter generators at full power.",
                "Medical facilities reporting low disease incidence.",
                "Energy grid experiencing peak demand fluctuations.",
                "Geological survey discovered new resources.",
                "Long-range probe returned with stellar data.",
                "Cultural exchange program approved.",
                "Resource extraction quotas met ahead of deadline.",
                "How much further to Earth?",
                "Another quiet day. Good for catching up on paperwork."
            ],
            'space_station': [
                "Docking bay efficiency improved with new protocols.",
                "Station rotation mechanics functioning normally.",
                "Merchant traffic up 15% compared to last cycle.",
                "Artificial gravity generators running smoothly.",
                "Recycling systems processing at maximum efficiency.",
                "Tourist accommodations at capacity.",
                "Station-wide maintenance inspection scheduled.",
                "Emergency response drill conducted successfully.",
                "Life support scrubbers cleaned and calibrated.",
                "Exterior hull integrity check passed.",
                "Research lab reporting deep space anomalies.",
                "Crew rotation completed without incident.",
                "Zero-G training for new recruits underway.",
                "Communications array received distress signal.",
                "Internal security patrol routes optimized.",
                "Cafeteria menu updated with hydroponic produce.",
                "Observatory windows cleaned, visibility excellent.",
                "Module atmospheric pressure stable.",
                "Power conduits showing minor thermal variations.",
                "How much further to Earth?"
            ],
            'outpost': [
                "Long-range communications restored after failure.",
                "Supply cache inventory updated and secured.",
                "Mineral survey detected promising ores.",
                "Perimeter sensors showing normal activity.",
                "Generator fuel reserves adequate for six months.",
                "Weather monitoring equipment calibrated.",
                "Emergency beacon tested and operational.",
                "Staff rotation schedule updated.",
                "Isolation protocols reviewed and updated.",
                "Automated drills reached target depth.",
                "Seismic activity within expected parameters.",
                "Wildlife deterrent system activated.",
                "Excavation team unearthed ancient artifacts.",
                "Solar array alignment optimized.",
                "Dust storm reduced visibility to zero.",
                "Water purification at peak capacity.",
                "Relay station signal strength improved.",
                "Drone reconnaissance returned with mapping data.",
                "Geothermal conduit sealed for repair.",
                "Another quiet shift on the frontier."
            ],
            'gate': [
                "Corridor stability within acceptable variance.",
                "Transit queue processing efficiently.",
                "Gate energy consumption optimized.",
                "Safety protocols updated per incidents.",
                "Decontamination procedures enhanced.",
                "Navigation beacon alignment verified.",
                "Traffic control systems upgraded.",
                "Emergency transit procedures drilled.",
                "Inter-system data packets flowing normally.",
                "Security checkpoint contraband seizure.",
                "Corridor stabilizer operating normally.",
                "Anomaly detection on standby.",
                "Personnel transit logs audited.",
                "Customs forms updated with new tariffs.",
                "Scheduled shutdown for power coupling replacement.",
                "Transit gate maintenance completed.",
                "Energy field fluctuations minimal.",
                "Gate synchronization nominal.",
                "Passenger manifest verification complete.",
                "How much further to Earth?"
            ]
        }
        
        pool = type_message_pools.get(location_type, type_message_pools['colony'])
        return random.choice(pool)

    def _get_generic_log_message(self) -> str:
        """Get generic message using efficient random selection"""
        
        # Create message categories for variety without huge arrays
        categories = [
            # System status messages
            [
                "All systems nominal. No incidents to report.",
                "Routine maintenance completed successfully.",
                "Equipment calibration finished, ready for operation.",
                "Environmental conditions stable.",
                "Security sweep complete. All clear.",
                "Communications array functioning normally.",
                "Power grid operating at optimal efficiency.",
                "Navigation systems updated and verified.",
                "Emergency systems tested and operational.",
                "Structural integrity checks passed."
            ],
            # Personal/crew messages  
            [
                "Another quiet day. Good for paperwork.",
                "Coffee supply running low again.",
                "Met interesting travelers today.",
                "Long shift, but someone has to keep things running.", 
                "Received message from family. Always nice.",
                "New arrival seemed nervous. First timer probably.",
                "Reminder to check backup generators tomorrow.",
                "Quiet night shift. Perfect for reading.",
                "Looking forward to next leave.",
                "The stars really make you feel small."
            ],
            # Technical/operational messages
            [
                "Diagnostic complete. Minor adjustments made.",
                "Software update installed successfully.",
                "Preventive maintenance on critical systems.",
                "Backup systems tested and functional.",
                "Network connectivity stable.",
                "Sensor array recalibrated.",
                "Performance metrics within parameters.",
                "System logs reviewed. No errors found.",
                "Component replacement scheduled.",
                "Energy consumption holding steady."
            ],
            # Trade/economic messages
            [
                "Cargo manifests reviewed and approved.",
                "Price negotiations concluded fairly.",
                "Supply shipment arrived on schedule.",
                "Market analysis complete. Prices steady.",
                "Trade agreement signed successfully.",
                "Customs inspection finished.",
                "Freight scheduling optimized.",
                "Quality assessment completed.",
                "Export permits processed.",
                "Trade route security briefing attended."
            ]
        ]
        
        # Select random category, then random message from that category
        category = random.choice(categories)
        return random.choice(category)
async def setup(bot):
    await bot.add_cog(GalaxyGeneratorCog(bot))