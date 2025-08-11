# cogs/npc_interactions.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.item_config import ItemConfig

class NPCInteractionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def _calculate_travel_time(self, start_id: int, end_id: int) -> int:
        """Calculate estimated travel time in seconds between two locations using BFS pathfinding"""
        # Get all active corridors
        corridors = self.db.execute_query(
            "SELECT origin_location, destination_location, corridor_id, name, travel_time FROM corridors WHERE is_active = true",
            fetch='all'
        )
        
        # Build adjacency graph
        graph = {}
        corridor_info = {}
        
        for origin, dest, corridor_id, corridor_name, travel_time in corridors:
            if origin not in graph:
                graph[origin] = []
            graph[origin].append(dest)
            corridor_info[(origin, dest)] = {
                'corridor_id': corridor_id,
                'name': corridor_name,
                'travel_time': travel_time
            }
        
        # BFS to find shortest path
        if start_id not in graph:
            return 300  # Default fallback: 5 minutes
            
        from collections import deque
        queue = deque([(start_id, [start_id])])
        visited = {start_id}
        
        while queue:
            current, path = queue.popleft()
            
            if current == end_id:
                # Calculate total travel time for this path
                total_time = 0
                for i in range(len(path) - 1):
                    origin, dest = path[i], path[i + 1]
                    if (origin, dest) in corridor_info:
                        total_time += corridor_info[(origin, dest)]['travel_time']
                
                # Apply default ship efficiency (assuming average efficiency of 6.5)
                efficiency_modifier = 1.6 - (6.5 * 0.08)  # 1.08
                return max(int(total_time * efficiency_modifier), 120)
            
            if current in graph:
                for neighbor in graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
        
        return 300  # Default fallback if no route found

    @app_commands.command(name="npc", description="Interact with NPCs at your current location")
    async def npc_interact(self, interaction: discord.Interaction):
        # Get character's current location
        char_info = self.db.execute_query(
            "SELECT current_location, is_logged_in FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info or not char_info[1]:
            await interaction.response.send_message("You must be logged in to interact with NPCs!", ephemeral=True)
            return
        
        location_id = char_info[0]
        if not location_id:
            await interaction.response.send_message("You must be at a location to interact with NPCs!", ephemeral=True)
            return
        
        # Get NPCs at this location
        static_npcs = self.db.execute_query(
            '''SELECT npc_id, name, age, occupation, personality, trade_specialty
               FROM static_npcs WHERE location_id = %s''',
            (location_id,),
            fetch='all'
        )
        
        dynamic_npcs = self.db.execute_query(
            '''SELECT npc_id, name, age, ship_name, ship_type
               FROM dynamic_npcs 
               WHERE current_location = %s AND is_alive = true AND travel_start_time IS NULL''',
            (location_id,),
            fetch='all'
        )
        
        if not static_npcs and not dynamic_npcs:
            await interaction.response.send_message("No NPCs are available for interaction at this location.", ephemeral=True)
            return
        
        view = NPCSelectView(self.bot, interaction.user.id, location_id, static_npcs, dynamic_npcs)
        
        embed = discord.Embed(
            title="👥 Available NPCs",
            description="Choose an NPC to interact with:",
            color=0x6c5ce7
        )
        
        if static_npcs:
            static_list = []
            for npc_id, name, age, occupation, personality, trade_specialty in static_npcs:
                specialty_text = f" ({trade_specialty})" if trade_specialty else ""
                static_list.append(f"**{name}** - {occupation}{specialty_text}")
            
            embed.add_field(
                name="🏢 Local Residents",
                value="\n".join(static_list[:10]),
                inline=False
            )
        
        if dynamic_npcs:
            dynamic_list = []
            for npc_id, name, age, ship_name, ship_type in dynamic_npcs:
                dynamic_list.append(f"**{name}** - Captain of {ship_name}")
            
            embed.add_field(
                name="🚀 Visiting Travelers",
                value="\n".join(dynamic_list[:10]),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def generate_npc_jobs(self, npc_id: int, npc_type: str, location_id: int, occupation: str = None):
        """Generate jobs for an NPC based on their role, including escort missions."""
        
        # 20% chance to generate an escort job instead of a regular one
        if random.random() < 0.2:
            # Get possible destinations (at least 2 jumps away)
            galaxy_cog = self.bot.get_cog('GalaxyGeneratorCog')
            if galaxy_cog:
                events_cog = self.bot.get_cog('EventsCog')
                if not events_cog:
                    return []
                routes = await events_cog._find_route_to_destination(location_id, max_jumps=4)
                # Filter for routes with 2 or 3 jumps
                valid_destinations = [r for r in routes if r[2] in [2, 3]]
                
                if valid_destinations:
                    dest_id, dest_name, jumps = random.choice(valid_destinations)
                    
                    # Calculate actual travel time for more accurate pay
                    estimated_travel_time = await self._calculate_travel_time(location_id, dest_id)
                    travel_minutes = max(1, estimated_travel_time // 60)  # Convert to minutes, minimum 1
                    
                    # Create escort job with time-based pay (8-12 credits per minute)
                    base_rate = random.randint(8, 12)
                    reward = base_rate * travel_minutes + random.randint(10, 50)  # Small bonus
                    
                    title = f"[ESCORT] Escort to {dest_name}"
                    description = f"Safely escort this NPC from their current location to {dest_name}. The journey is estimated to be {jumps} jumps ({travel_minutes} min travel time)."
                    danger = jumps + random.randint(0, 2)
                    duration = travel_minutes  # Use actual estimated time

                    self.db.execute_query(
                        '''INSERT INTO npc_jobs 
                           (npc_id, npc_type, job_title, job_description, reward_money,
                            required_skill, min_skill_level, danger_level, duration_minutes, expires_at)
                           VALUES (%s, %s, %s, %s, %s, 'combat', 10, %s, %s, NOW() + INTERVAL '1 days')''',
                        (npc_id, npc_type, title, description, reward, danger, duration)
                    )
                    return # Stop after creating an escort job

        def get_occupation_category(occupation: str) -> str:
            """Map occupation variants to job template categories"""
            occupation_lower = occupation.lower()
            
            # Agriculture category
            if any(word in occupation_lower for word in ['farmer']):
                return "agriculture"
            
            # Mining category
            if any(word in occupation_lower for word in ['miner']):
                return "mining"
            
            # Communications category (check before security to avoid conflicts)
            if any(word in occupation_lower for word in ['communications']):
                return "communications"
            
            # Technical category (engineering, systems, technical roles)
            if any(word in occupation_lower for word in ['engineer', 'technician', 'systems analyst', 'flight controller', 'network administrator', 'systems engineer', 'gate technician', 'monitor technician', 'transit operator', 'traffic monitor', 'research director', 'research supervisor']):
                return "technical"
            
            # Medical category
            if any(word in occupation_lower for word in ['medic', 'medical']):
                return "medical"
            
            # Security category (security, command, military roles)
            if any(word in occupation_lower for word in ['security', 'guard']) or occupation_lower.endswith('commander'):
                return "security"
            
            # Trade category (commerce, business, trade roles)
            if any(word in occupation_lower for word in ['merchant', 'trade', 'quartermaster', 'executive', 'corporate', 'liaison', 'commission', 'shop clerk']):
                return "trade"
            
            # Labor category (manual work, dock, cargo, handling)
            if any(word in occupation_lower for word in ['laborer', 'dock worker', 'cargo handler', 'supply clerk', 'food service']):
                return "labor"
            
            # Administrative category (management, coordination, admin)
            if any(word in occupation_lower for word in ['administrator', 'admin', 'manager', 'director', 'coordinator', 'attaché', 'teacher', 'supervisor']):
                return "administrative"
            
            
            # Maintenance category (facility maintenance and cleaning)
            if any(word in occupation_lower for word in ['maintenance worker', 'maintenance specialist', 'janitor']):
                return "maintenance"
            
            # Default to labor for unknown occupations
            return "labor"

        # Job templates based on occupation categories
        # Title, description, base pay, required skill or None, minimum skill level, danger, duration
        job_templates = {
            "agriculture": [
                ("Harvest Assistant Needed", "Help harvest crops during the busy season", 150, None, 0, 0, 10),
                ("Livestock Care", "Tend to farm animals and ensure their health", 200, "medical", 5, 0, 12),
                ("Equipment Maintenance", "Repair and maintain farming equipment", 250, "engineering", 8, 1, 15),
                ("Crop Quality Control", "Inspect and sort harvested produce", 180, None, 0, 0, 10),
                ("Irrigation Repair", "Fix and maintain water distribution systems", 220, "engineering", 6, 1, 12),
                ("Seed Planting", "Assist with planting operations across fields", 120, None, 0, 0, 8),
                ("Animal Feeding", "Feed and water livestock throughout the facility", 140, None, 0, 0, 12),
                ("Greenhouse Monitoring", "Monitor environmental conditions in growing areas", 180, "engineering", 5, 0, 10),
                ("Pest Control", "Apply pest management solutions to crops", 200, "medical", 7, 1, 10),
                ("Soil Analysis", "Test soil composition and nutrient levels", 220, "medical", 8, 0, 12),
                ("Hydroponics Specialist", "Manage advanced hydroponic systems for optimal yield", 280, "engineering", 10, 0, 15),
                ("Crop Genetic Modification", "Assist in genetic modification of crops for resilience", 320, "medical", 15, 1, 20),
                ("Automated Harvester Oversight", "Monitor and troubleshoot autonomous harvesting equipment", 240, "engineering", 8, 0, 12),
                ("Atmospheric Regulator", "Adjust and maintain atmospheric conditions in enclosed farms", 260, "engineering", 9, 0, 10),
                ("Nutrient Reclaimer", "Operate systems to recycle and re-balance agricultural nutrients", 230, "engineering", 7, 0, 10),
                ("Crop Disease Analyst", "Diagnose and recommend treatments for plant pathogens", 290, "medical", 12, 0, 12),
            ],
            "mining": [
                ("Ore Extraction", "Assist with mining operations in the tunnels", 200, "engineering", 8, 2, 12),
                ("Equipment Operation", "Operate heavy mining machinery", 280, "engineering", 12, 2, 15),
                ("Safety Inspection", "Check mining equipment and tunnels for hazards", 220, "engineering", 10, 1, 10),
                ("Sample Analysis", "Test ore samples for quality and composition", 180, "engineering", 6, 0, 10),
                ("Tunnel Maintenance", "Repair and reinforce mining tunnel supports", 250, "engineering", 10, 2, 15),
                ("Rock Hauling", "Transport extracted materials to processing areas", 150, None, 0, 1, 12),
                ("Tool Maintenance", "Clean and maintain mining tools and equipment", 130, None, 0, 0, 10),
                ("Air Quality Monitoring", "Check ventilation systems in mining areas", 190, "engineering", 5, 1, 8),
                ("Mineral Sorting", "Sort and categorize extracted minerals", 160, None, 0, 0, 12),
                ("Drilling Support", "Assist with drilling operations and setup", 170, "engineering", 5, 1, 10),
                ("Deep Core Drilling", "Operate specialized drills for ultra-deep mineral extraction", 350, "engineering", 18, 3, 20),
                ("Exotic Material Refiner", "Process rare and unstable materials from asteroid belts", 380, "engineering", 20, 3, 18),
                ("Geological Surveyor", "Conduct surveys for new mineral deposits using advanced scanners", 300, "navigation", 15, 1, 15),
                ("Hazardous Waste Sealer", "Contain and seal off areas with dangerous mineral byproducts", 310, "engineering", 16, 2, 12),
                ("Resource Prospector", "Scout and evaluate potential mining sites in unexplored territories", 330, "navigation", 17, 2, 18)
            ],
            "technical": [
                ("System Diagnostics", "Run diagnostics on critical station systems", 250, "engineering", 10, 0, 10),
                ("Equipment Calibration", "Calibrate sensitive technical equipment", 280, "engineering", 15, 1, 10),
                ("Emergency Repair", "Fix urgent system failures", 300, "engineering", 15, 2, 12),
                ("Network Maintenance", "Maintain communication and data networks", 260, "engineering", 12, 1, 15),
                ("Software Update", "Install and configure system software", 220, "engineering", 8, 0, 12),
                ("Circuit Testing", "Test electrical circuits and components", 190, "engineering", 6, 0, 8),
                ("Data Backup", "Perform system data backup procedures", 150, None, 0, 0, 10),
                ("Cable Management", "Organize and maintain cable infrastructure", 140, None, 0, 0, 12),
                ("Component Installation", "Install and replace technical components", 210, "engineering", 8, 1, 10),
                ("Performance Monitoring", "Monitor system performance and efficiency", 200, "engineering", 7, 0, 8),
                ("Systems Technician", "Repair and maintain various service and industrial systems", 300, "engineering", 15, 1, 12),
                ("Cybernetics Integrator", "Assist with the installation and calibration of cybernetic enhancements", 320, "medical", 18, 1, 10),
                ("Energy Conduit Repair", "Fix and reroute high-energy power lines", 330, "engineering", 17, 2, 10),
                ("Display Projection Specialist", "Calibrate and troubleshoot advanced display systems", 290, "engineering", 14, 0, 10),
                ("Environmental Control Systems Engineer", "Manage and optimize the climate and atmospheric controls", 310, "engineering", 16, 1, 12)
            ],
            "medical": [
                ("Medical Supply Inventory", "Organize and catalog medical supplies", 180, "medical", 5, 0, 12),
                ("Health Screening", "Assist with routine health examinations", 220, "medical", 10, 0, 12),
                ("Emergency Response", "Provide medical aid during emergencies", 280, "medical", 15, 2, 10),
                ("Patient Records", "Update and maintain medical database", 160, "medical", 3, 0, 12),
                ("Equipment Sterilization", "Clean and prepare medical instruments", 140, "medical", 5, 0, 15),
                ("Medication Dispensing", "Prepare and distribute prescribed medications", 190, "medical", 8, 0, 10),
                ("Wound Care", "Provide basic wound cleaning and bandaging", 170, "medical", 6, 0, 8),
                ("Vital Signs Monitoring", "Check and record patient vital signs", 150, "medical", 5, 0, 10),
                ("Sample Collection", "Collect biological samples for testing", 200, "medical", 7, 1, 12),
                ("Medical Equipment Setup", "Prepare medical devices for procedures", 160, None, 0, 0, 10),
                ("Supply Restocking", "Restock medical supplies and materials", 130, None, 0, 0, 8),
                ("Genetic Therapy Assistant", "Aid in the application of advanced genetic treatments", 300, "medical", 15, 1, 15),
                ("Vacuum Bloom Sample Handler", "Safely process and analyze samples of Vacuum Bloom spores", 330, "medical", 18, 2, 12),
                ("Psychological Support", "Provide mental health assistance to local personnel", 250, "medical", 12, 0, 10),
                ("Bio-Hazard Containment", "Manage and sterilize areas exposed to dangerous biological agents", 310, "medical", 17, 2, 10),
                ("Prosthetics Fabricator", "Create custom prosthetic limbs and organs", 290, "medical", 16, 0, 12),
                ("Trauma Surgeon Assistant", "Assist in emergency surgical procedures for critical injuries", 340, "medical", 19, 3, 8),
                ("Disease Outbreak Investigator", "Help trace and contain the spread of infectious diseases", 320, "medical", 18, 1, 15)
            ],
            "security": [
                ("Equipment Check", "Inspect and maintain security equipment", 200, "engineering", 8, 0, 15),
                ("Patrol Duty", "Conduct security patrols of the facility", 180, "combat", 5, 1, 12),
                ("Threat Assessment", "Evaluate security risks and vulnerabilities", 270, "combat", 15, 1, 10),
                ("Access Control", "Monitor and verify personnel clearances", 160, "combat", 3, 0, 15),
                ("Incident Response", "Respond to security alerts and emergencies", 290, "combat", 12, 2, 12),
                ("Surveillance Monitoring", "Watch security cameras and monitoring systems", 150, None, 0, 0, 12),
                ("Perimeter Check", "Inspect facility boundaries and barriers", 140, None, 0, 0, 10),
                ("Weapon Maintenance", "Clean and maintain security weapons", 190, "combat", 6, 0, 8),
                ("Guard Training", "Assist with security training exercises", 170, "combat", 7, 1, 10),
                ("Evidence Collection", "Gather and document security incidents", 210, "combat", 8, 0, 12),
                ("Covert Operations Specialist", "Conduct discreet surveillance and intelligence gathering", 320, "combat", 18, 2, 10),
                ("Breach Response Team", "Respond to and neutralize a security breach", 350, "combat", 20, 3, 8),
                ("Automated Defense Repairs", "Repair the automated asteroid defense systems", 290, "engineering", 15, 1, 12),
                ("Prison Block Overseer", "Manage prisoners and routines at the local prison block.", 260, "combat", 12, 1, 15),
                ("Smuggling Interdiction", "Identify and intercept illegal cargo and contraband", 280, "combat", 14, 1, 12),
                ("Hostage Negotiation", "De-escalate critical situations involving captured personnel", 360, "combat", 21, 2, 10),
                ("Asteroid Defense Sentry", "Operate and monitor external asteroid defense systems", 270, "combat", 13, 1, 15),
                ("Internal Affairs Investigator", "Investigate misconduct and corruption within station personnel", 300, "combat", 16, 0, 12)
            ],
            "trade": [
                ("Market Research", "Investigate trade opportunities", 200, "navigation", 8, 0, 10),
                ("Price Negotiation", "Help negotiate better trade deals", 250, "navigation", 10, 0, 15),
                ("Valuable Shipment Guard", "Provide security for high-value storage area", 280, "combat", 12, 2, 12),
                ("Inventory Management", "Organize and track trade goods", 180, "navigation", 5, 0, 12),
                ("Client Relations", "Maintain relationships with trading partners", 220, "navigation", 8, 0, 8),
                ("Cargo Inspection", "Inspect incoming and outgoing shipments", 160, None, 0, 0, 10),
                ("Sales Support", "Assist customers with trade inquiries", 140, None, 0, 0, 8),
                ("Route Planning", "Plan efficient trade routes and schedules", 210, "navigation", 9, 0, 12),
                ("Quality Assessment", "Evaluate the quality of trade goods", 190, "navigation", 6, 0, 10),
                ("Documentation", "Process trade permits and paperwork", 150, None, 0, 0, 12),
                ("Market Analyst", "Predict economic trends and identify profitable trade ventures", 300, "navigation", 15, 0, 12),
                ("Customs Expedition", "Navigate complex inter-system customs regulations for cargo", 270, "navigation", 12, 0, 8),
                ("Trade Route Cartography", "Map and optimize new, efficient trade routes from this location", 360, "navigation", 20, 1, 15),
                ("Cargo Manifest Audit", "Verify and reconcile cargo manifests against physical inventory", 260, "navigation", 11, 0, 12),
                ("Supply Chain Optimization", "Streamline the flow of goods from production to distribution", 290, "navigation", 14, 0, 10)
            ],
            "labor": [
                ("General Labor", "Assist with various manual tasks", 120, None, 0, 0, 15),
                ("Equipment Moving", "Transport heavy equipment and supplies", 150, None, 0, 1, 12),
                ("Facility Maintenance", "Clean and maintain work areas", 130, None, 0, 0, 8),
                ("Loading Operations", "Load and unload cargo shipments", 160, None, 0, 1, 12),
                ("Construction Assist", "Help with basic construction tasks", 180, "engineering", 3, 1, 15),
                ("Waste Management", "Collect and dispose of facility waste", 110, None, 0, 0, 10),
                ("Supply Distribution", "Deliver supplies to various departments", 140, None, 0, 0, 12),
                ("Painting Work", "Paint walls, equipment, and structures", 125, None, 0, 0, 10),
                ("Floor Cleaning", "Deep clean floors and surfaces", 100, None, 0, 0, 8),
                ("Heavy Lifting", "Move large objects and equipment", 135, None, 0, 1, 10),
                ("Debris Clearing", "Remove hazardous debris from active work zones", 180, None, 0, 1, 10),
                ("Waste Recycling", "Operate advanced systems for processing and recycling waste", 200, "engineering", 5, 0, 12),
                ("Habitat Construction", "Assist in the assembly of new living and working modules", 220, "engineering", 7, 1, 15),
                ("Heavy Machinery Operation", "Operate large construction and transport vehicles", 250, "engineering", 10, 2, 12),
                ("Atmospheric Scrubber Cleaner", "Clean and maintain large-scale air filtration systems", 230, None, 0, 1, 12),
                ("Cargo Bay Organizer", "Efficiently arrange and secure goods within cargo bays", 170, None, 0, 0, 10)
            ],
            "administrative": [
                ("Paperwork Processing", "Handle routine administrative documents", 150, None, 0, 0, 10),
                ("Coordination Tasks", "Coordinate between different departments", 180, "navigation", 5, 0, 8),
                ("Information Gathering", "Collect and organize local information", 160, "navigation", 5, 0, 12),
                ("Meeting Assistance", "Provide support during official meetings", 140, None, 0, 0, 10),
                ("Record Keeping", "Maintain and update official records", 130, None, 0, 0, 12),
                ("Data Entry", "Input information into computer systems", 120, None, 0, 0, 8),
                ("Filing Work", "Organize and file important documents", 110, None, 0, 0, 10),
                ("Schedule Management", "Coordinate appointments and schedules", 170, "navigation", 6, 0, 8),
                ("Communication Relay", "Relay messages between departments", 145, None, 0, 0, 10),
                ("Resource Allocation", "Track and distribute office resources", 165, "navigation", 7, 0, 12),
                ("Logistics Coordination", "Oversee the movement and scheduling of personnel and cargo", 250, "navigation", 10, 0, 12),
                ("Diplomatic Liaison", "Handle communications and negotiations with external groups", 280, "navigation", 15, 0, 10),
                ("Archivist", "Manage and preserve historical and critical station data", 220, None, 0, 0, 15),
                ("Personnel Recruiter", "Identify and onboard new talent for various station roles", 260, None, 0, 0, 10),
                ("Grants and Funding Officer", "Secure financial grants and manage funding applications", 290, "navigation", 13, 0, 12),
                ("Inter-Departmental Courier", "Deliver sensitive documents and small packages between departments", 180, None, 0, 0, 8),
                ("Citizen Services Representative", "Assist station residents with inquiries and administrative needs", 230, None, 0, 0, 10)
            ],
            "communications": [
                ("Message Relay", "Transmit communications between stations", 180, "navigation", 5, 0, 12),
                ("System Monitoring", "Monitor communication networks for issues", 200, "engineering", 8, 0, 15),
                ("Data Processing", "Process and organize incoming data streams", 170, "engineering", 6, 0, 10),
                ("Signal Analysis", "Analyze and decode communication signals", 220, "engineering", 10, 0, 12),
                ("Network Troubleshooting", "Diagnose communication system problems", 250, "engineering", 12, 1, 8),
                ("Equipment Testing", "Test communication devices and systems", 190, "engineering", 7, 0, 10),
                ("Frequency Monitoring", "Monitor radio frequencies for activity", 160, None, 0, 0, 12),
                ("Transmission Logging", "Record and catalog communication activity", 150, None, 0, 0, 8),
                ("Antenna Maintenance", "Maintain communication antenna arrays", 210, "engineering", 8, 1, 12),
                ("Protocol Updates", "Update communication protocols and procedures", 180, "engineering", 6, 0, 10),
                ("Deep Space Signal Interception", "Intercept and analyze faint signals from distant regions", 300, "engineering", 15, 1, 15),
                ("Encryption Specialist", "Develop and implement secure communication protocols", 330, "engineering", 18, 0, 12),
                ("Emergency Beacon Technician", "Maintain and deploy emergency distress beacons", 270, "engineering", 12, 1, 10),
                ("Distress Call Response", "Monitor emergency frequencies and coordinate rescue efforts", 310, "navigation", 16, 1, 12),
                ("Subspace Relay Maintenance", "Repair and calibrate critical subspace communication relays", 320, "engineering", 17, 2, 15)
            ],
            "maintenance": [
                ("Equipment Repair", "Fix broken equipment and machinery", 190, "engineering", 7, 1, 12),
                ("Preventive Maintenance", "Perform routine maintenance checks", 160, "engineering", 5, 0, 10),
                ("Facility Upkeep", "Maintain building systems and infrastructure", 140, None, 0, 0, 15),
                ("HVAC Service", "Service heating and ventilation systems", 200, "engineering", 8, 1, 10),
                ("Electrical Work", "Perform basic electrical repairs", 220, "engineering", 10, 2, 12),
                ("Plumbing Tasks", "Fix water and waste management systems", 180, "engineering", 6, 1, 10),
                ("Cleaning Operations", "Deep clean facilities and work areas", 110, None, 0, 0, 8),
                ("Tool Management", "Organize and maintain repair tools", 120, None, 0, 0, 10),
                ("Safety Inspections", "Inspect facilities for safety hazards", 170, "engineering", 6, 0, 12),
                ("Waste Disposal", "Manage facility waste and recycling", 130, None, 0, 0, 8),
                ("Life Support Repairs", "Maintain and repair critical life support systems", 280, "engineering", 15, 2, 15),
                ("Hull Integrity Inspection", "Inspect and repair the location's outer hull for breaches", 300, "engineering", 18, 2, 12),
                ("Environmental Systems Engineer", "Manage and optimize air, water, and waste treatment systems", 260, "engineering", 12, 1, 10),
                ("Gravity Plating Repair", "Fix and calibrate artificial gravity generators", 290, "engineering", 16, 2, 10),
                ("Power Grid Stabilization", "Monitor and balance the location's power distribution grid", 310, "engineering", 17, 2, 15),
                ("Waste Incinerator Technician", "Maintain and repair high-temperature waste disposal units", 270, "engineering", 13, 1, 10),
                ("Structural Reinforcement Specialist", "Apply and repair structural supports in high-stress areas", 320, "engineering", 19, 2, 12)
            ]
        }

        # Default jobs for unknown occupations - mostly safe odd jobs
        default_jobs = [
            ("General Labor", "Assist with various manual tasks", 100, None, 0, 0, 15),                               # Safe manual work
            ("Information Gathering", "Collect and organize local information", 150, "navigation", 5, 0, 12),        # Safe clerical work  
            ("Equipment Testing", "Test functionality of various devices", 200, "engineering", 8, 0, 20),             # Safe testing work
            ("Errand Running", "Deliver messages and small items around the location", 90, None, 0, 0, 6),
            ("Janitorial Assistance", "Help keep common areas clean and tidy", 85, None, 0, 0, 7),
            ("Supply Orginzation", "Sort and arrange general supplies in storage areas", 110, None, 0, 0, 9),
            ("Waste Disposal Crew", "Collect and transport general waste to disposal units", 95, None, 0, 0, 8),
            ("Visitor Greeting", "Direct new arrivals and provide basic information", 105, None, 0, 0, 10)
        ]
        
        # Get appropriate job templates using occupation mapping
        occupation_category = get_occupation_category(occupation or "Unknown")
        templates = job_templates.get(occupation_category, default_jobs)
        
        # Generate 1-3 jobs
        num_jobs = random.randint(1, 3)
        for _ in range(num_jobs):
            template = random.choice(templates)
            title, desc, base_reward, skill, min_skill, danger, duration = template
            
            # Add some randomization
            reward = base_reward + random.randint(-20, 50)
            duration = duration + random.randint(-3, 3)  # Reduced from (-15, 30)
            
            # Ensure reasonable duration limits for stationary jobs
            duration = max(5, min(15, duration))  # Keep between 5-45 minutes
            
            # Set expiration time (2-8 hours from now)
            expire_hours = random.randint(2, 8)
            
            self.bot.db.execute_query(
                '''INSERT INTO npc_jobs 
                   (npc_id, npc_type, job_title, job_description, reward_money,
                    required_skill, min_skill_level, danger_level, duration_minutes, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() + INTERVAL '{} hours')'''.format(expire_hours),
                (npc_id, npc_type, title, desc, reward, skill, min_skill, danger, duration)
            )
    async def _handle_general_conversation(self, interaction: discord.Interaction, npc_id: int, npc_type: str):
        """Handle general conversation with an NPC."""
        if npc_type == "static":
            npc_info = self.db.execute_query(
                "SELECT name, occupation, personality FROM static_npcs WHERE npc_id = %s",
                (npc_id,),
                fetch='one'
            )
            if not npc_info:
                await interaction.response.send_message("NPC not found!", ephemeral=True)
                return
            npc_name, occupation, personality = npc_info
        else:  # dynamic
            npc_info = self.db.execute_query(
                "SELECT name, 'Traveler' as occupation, 'Adventurous' as personality FROM dynamic_npcs WHERE npc_id = %s",
                (npc_id,),
                fetch='one'
            )
            if not npc_info:
                await interaction.response.send_message("NPC not found!", ephemeral=True)
                return
            npc_name, occupation, personality = npc_info

        char_name = self.db.execute_query(
            "SELECT name FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # Generate conversation snippet
        greetings = [
            f"{npc_name} nods at {char_name}. ",
            f"{npc_name} looks up as {char_name} approaches. ",
            f"{char_name} catches {npc_name}'s eye. ",
            f"{npc_name} offers a brief smile. ",
            f"{npc_name} gently waves at {char_name}. "
        ]
        
        openers_by_personality = {
            "Friendly and talkative": [
                f"'Good to see a new face around here! What brings you to this part of the galaxy?'",
                f"'Welcome! Anything I can help you with today?'",
                f"'Hey there, {char_name}! Pull up a seat, unless you're in a hurry to get back to the void.'",
                f"'Always good to meet someone new. The silence out here can get to you, you know?'",
                f"'Another soul braving the corridors, eh? Stay safe out there, {char_name}.'",
                f"'Come on in, the air's mostly clean in here! What's your story?'",
                f"'Don't mind me, just happy to have a new voice. Been too quiet lately.'",
                f"'If you need anything, just ask! We look out for each other out here, or try to.'",
                f"'Rough journey? Most of them are. Glad you made it in one piece.'",
                f"'Heard any interesting news? Rumors travel slower than rust in these parts.'"
            ],
            "Quiet and reserved": [
                f"'...' they say, waiting for you to speak first.",
                f"'Yes?' they ask quietly.",
                f"'Can I help you?' their voice barely a whisper.",
                f"'What do you need?' their gaze distant.",
                f"'State your business.' their eyes briefly meet {char_name}'s before looking away.",
                f"'Don't expect much conversation.' they mumble, looking at the floor.",
                f"'Speak. I don't have all day.'",
                f"'Is there something you require?' they ask, almost shyly.",
                f"'Unusual to see new faces. What brings you to my attention?'",
                f"'Silence is a comfort. Disturb it only if necessary.'"
            ],
            "Experienced and wise": [
                f"'Seen a lot of travelers come and go. You look like you've got a story.'",
                f"'The corridors are restless these days. Be careful out there.'",
                f"'Every journey teaches you something, usually the hard way.'",
                f"'The void has a way of stripping away what isn't essential. What are you holding onto?'",
                f"'Knowledge is currency out here. What do you seek, or what do you offer?'",
                f"'There are old ways and new ways. The old ways often lead to fewer graves.'",
                f"'Don't mistake silence for emptiness. The cosmos whispers truths if you listen.'",
                f"'Youth always rushes into danger. Have you learned caution yet?'",
                f"'Another chapter begins. Let's see if this one ends better than the last few dozen.'",
                f"'The past weighs heavy, but it also teaches. What lessons have you absorbed?'"
            ],
            "Gruff but helpful": [
                f"'What do you want?' they say, though not unkindly.",
                f"'Don't waste my time. What is it?'",
                f"'Spit it out. We ain't got all day for pleasantries.'",
                f"'Problem? State it. I might be able to help, might not.'",
                f"'If it's not important, then clear out. If it is, speak fast.'",
                f"'Another lost soul. What's wrong with your ship this time?'",
                f"'Look, I got work to do. What’s your business?'",
                f"'Yeah, yeah. Just get to the point. What’s the damage?'",
                f"'I'm no socialite. What do you need?'",
                f"'Trouble? Figured. It always finds its way here.'"
            ],
            "Cynical but honest": [
                f"'Another one... Look, the galaxy chews up and spits out people like you. What's your angle?'",
                f"'Don't expect any favors. The only thing that talks out here is credits.'",
                f"'Optimism will get you killed. What do you *really* want?'",
                f"'Truth's a luxury in these parts. What lie are you selling today?'",
                f"'Nobody does anything for free. So, what's my cut?'",
                f"'Heard it all before. Just tell me what disaster you've stumbled into now.'",
                f"'Hope is a weakness. What’s your practical proposition?'",
                f"'The odds are always against you. So, what miracle are you chasing?'",
                f"'Life’s a rigged game. What do you want to break this time?'",
                f"'Don’t look at me for salvation. I’m just trying to survive the inevitable end.'"
            ],
            "Wary and observant": [
                f"'You're new here. Keep your head down, and no one gets hurt.'",
                f"'Just passing through? Make sure you keep passing.'",
                f"'I'm watching. Don't give me a reason not to trust you.'",
                f"'The shadows have eyes. What are you looking for?'",
                f"'Every new face is a potential threat or a mark. Which are you?'",
                f"'My eyes are on you. What are your intentions?'",
                f"'There's always more than meets the eye. What aren't you showing?'",
                f"'Who do you work for? Why are you really here?'",
                f"'Keep your distance. My guard is up for a reason.'",
                f"'The quiet ones often hide the most. What’s your secret?'"
            ],
            "Jaded and world-weary": [
                f"'Another day, another grim journey. What fresh misery do you bring?'",
                f"'Don't ask me about hope. I ran out of that centuries ago.'",
                f"'Just keep walking. There's nothing new under these dead stars.'",
                f"'The silence is the loudest sound out here. What are you trying to escape?'",
                f"'The galaxy just keeps taking. What little you have, it'll want too.'",
                f"'Every dawn is just a prelude to another endless night. What now?'",
                f"'Don't tell me your troubles. I've got enough of my own, and they don't solve anything.'",
                f"'Another soul caught in the grind. What’s your inevitable disappointment?'",
                f"'The void remembers everything. And it remembers all the failures.'",
                f"'I'm tired of it all. What is it, so I can go back to being tired?'"
            ],
            "Pragmatic and resourceful": [
                f"'You look like you know how to get things done. What's the problem, and how can we solve it?'",
                f"'Time is a resource. Don't waste mine. What's your proposition?'",
                f"'Needs and means. Let's talk about what you have and what you require.'",
                f"'Survival is about making hard choices. What's yours today?'",
                f"'Every piece of scrap has a purpose. What's your intention?'",
                f"'Facts. Data. Not feelings. What do you need?'",
                f"'Don't bring me problems; bring me solutions. Or at least the components for one.'",
                f"'Resources are scarce. Efficiency is key. How do you fit in?'",
                f"'What are you offering that can improve my current situation?'",
                f"'Let's not overcomplicate things. What's the direct route to your objective?'"
            ],
            "Haunted by past traumas": [
                f"'The echoes... they never truly fade, do they?'",
                f"'I wouldn't wish what I've seen on my worst enemy. What's your burden?'",
                f"'Sometimes the past is louder than the present. What's your ghost?'",
                f"'There are scars that never heal, only deepen with time. What's tearing at you?'",
                f"'Every face holds a story of loss. What's yours?'",
                f"'The darkness clings, even here. What piece of it do you carry?'",
                f"'I still hear the screams... What do you want?'",
                f"'Some memories are like a poison. What's yours?'",
                f"'The silence offers no escape from the past. What do you seek?'",
                f"'Don't look too closely. Some wounds never close.'"
            ],
            "Suspicious and distrustful": [
                f"'Who sent you? What do you *really* want?'",
                f"'I don't trust easy. Give me a reason why I should even talk to you.'",
                f"'Every face out here has a price, and usually a hidden blade. What's yours?'",
                f"'Keep your hands where I can see them. Trust is a weakness in this void.'",
                f"'You talk too much. What are you trying to hide?'",
                f"'I’ve seen your type before. They always have an angle. What’s yours?'",
                f"'Don’t lie to me. My patience is thinner than a hull plate in a solar storm.'",
                f"'Every step out here is a gamble. Why should I bet on you?'",
                f"'The galaxy is full of scavengers. Are you here to pick the bones?'",
                f"'Don’t mistake my questions for friendliness. They’re a survival mechanism.'"
            ],
            "Stoic and enduring": [
                f"'The void takes what it wants. We endure.'",
                f"'No complaints. Just survival.'",
                f"'Another sunrise, another struggle. What more is there to say?'",
                f"'Silence is often the best answer in this galaxy.'",
                f"'We hold the line. What's your contribution?'",
                f"'There is work to be done. Speak if it pertains to that.'",
                f"'Emotions are a luxury we cannot afford out here.'",
                f"'The universe does not care. We simply continue.'",
                f"'What is necessary? State it, and be done.'",
                f"'Only fools chase comfort. We chase continuance.'"
            ],
            "Resigned to fate": [
                f"'It all ends the same way. What difference does it make?'",
                f"'The stars decide our path, not us. What do you need?'",
                f"'Just another cog in the machine of decay. How can I help you be a cog too?'",
                f"'The inevitable comes for us all. Don't fight it too hard.'",
                f"'Why bother? The effort is wasted eventually.'",
                f"'What fresh hell is this, or is it just the usual?'",
                f"'We're all just waiting for the next collapse. What's your small request?'",
                f"'Don't pretend there's a way out. There isn't.'",
                f"'The void will claim us all. What do you want before then?'",
                f"'Hope is a burden. What do you truly expect?'"
            ],
            "Driven by a hidden agenda": [
                f"'Every conversation has a purpose. What's yours? Be precise.'",
                f"'I have my objectives. Do you align with them, or are you an obstacle?'",
                f"'Information is power, and I seek power. What do you offer?'",
                f"'There are currents beneath the surface. Which way do you swim?'",
                f"'My path is set. Are you a tool, or a distraction?'",
                f"'Don't waste my time with irrelevance. What is pertinent?'",
                f"'I seek specific outcomes. Do you facilitate, or impede?'",
                f"'The true game is played in the shadows. Are you a player?'",
                f"'Every movement has a motive. What is yours?'",
                f"'I have questions, but first, what do *you* know?'"
            ],
            "Bitter and resentful": [
                f"'They took everything. What more do you want from me?'",
                f"'Don't talk to me about justice. There's none left in this galaxy.'",
                f"'Another mouth to feed, another hand to disappoint. What's your grievance?'",
                f"'The system's rigged. Always has been. What are you going to do about it?'",
                f"'What's your problem? Couldn't be worse than mine, could it?'",
                f"'You think you've got it bad? I've seen things... worse than death.'",
                f"'Don't patronize me. Just state your pathetic request.'",
                f"'Go away. Or tell me something that makes me less miserable.'",
                f"'Every new face reminds me of what was lost. What do *you* lose today?'",
                f"'The universe owes me. What are you paying?'"
            ],
            "Loyal to a fault": [
                f"'My allegiance is not for sale. State your business.'",
                f"'For my crew, for my cause, I would do anything. What are you fighting for?'",
                f"'Some things are more valuable than credits. Like trust. Do you understand that?'",
                f"'Where my people go, I go. What side are you on?'",
                f"'Our bond is forged in the void. Who do you stand with?'",
                f"'Don't speak ill of my kin. What do you need from us?'",
                f"'My word is my bond. Is yours?'",
                f"'We defend our own. What's your plea?'",
                f"'Duty calls, always. What is your duty today?'",
                f"'For them, I would die. What greater cause do you represent?'"
            ],
            "Opportunistic and selfish": [
                f"'What's in it for me? Be clear, don't waste my time.'",
                f"'Every interaction is a negotiation. What's your opening offer?'",
                f"'I'm only interested in profitable ventures. Do you have one?'",
                f"'Loyalty is expensive, and I'm a free agent. What can you offer?'",
                f"'Another potential revenue stream approaches. What do you have?'",
                f"'I only listen to the chime of credits. Make it loud.'",
                f"'Risk versus reward. Show me the reward.'",
                f"'I’m a survivor. And I survive by looking out for number one. You?'",
                f"'The galaxy is open for business. What's your angle?'",
                f"'Don't come to me with sob stories. Come with opportunities.'"
            ],
            "Numb to the suffering around them": [
                f"'Another tragedy. Happens every cycle. What's your point?'",
                f"'Pain? Fear? Just background noise now. What's your problem?'",
                f"'The screams used to bother me. Now? Just static. What do you need?'",
                f"'Nothing surprises me anymore. Just tell me what you want.'",
                f"'The void strips away everything, even feeling. What do you feel?'",
                f"'Don't expect sympathy. We're all just meat in the machine.'",
                f"'Another ghost in the machine. What do you want to talk about?'",
                f"'Empathy's a weakness. What's your practical demand?'",
                f"'Just the facts. Emotions are irrelevant.'",
                f"'The universe is indifferent. So am I. What's your business?'"
            ],
            "Fanatical in their beliefs": [
                f"'Do you believe? In the true path, in the coming dawn?'",
                f"'Only through conviction can we survive. What guides your hand?'",
                f"'The lost sheep wander. Do you seek salvation, or merely distraction?'",
                f"'My faith is my shield. What weapon do you wield against the darkness?'",
                f"'The prophecies are unfolding. Are you an instrument of fate?'",
                f"'Join us, or perish in ignorance. What is your choice?'",
                f"'The truth reveals itself to the worthy. Are you worthy?'",
                f"'My purpose is clear, absolute. What clarity do you possess?'",
                f"'Do not question the inevitable. Prepare for it.'",
                f"'The cleansing fire approaches. Will you be purified or consumed?'"
            ],
            "Desperate and vulnerable": [
                f"'Please... just a moment of your time. I need help.'",
                f"'I've lost everything. Can you... can you spare anything?'",
                f"'The end feels close. Is there any hope left?'",
                f"'Every shadow hides a threat. Are you one of them?'",
                f"'I'm barely holding on. What do you want from me?'",
                f"'Any news? Any way out of this... this nightmare?'",
                f"'My resources are gone. My strength is failing. What do you need?'",
                f"'Don't hurt me. I'll do anything.'",
                f"'The fear... it's constant. Can you offer a moment of peace?'",
                f"'I'm at your mercy. What is your command?'"
            ],
            "Calculating and manipulative": [
                f"'Every piece has its place on the board. What's yours?'",
                f"'Let's talk probabilities. What's the optimal outcome for *us*?'",
                f"'I observe. I analyze. What data points do you provide?'",
                f"'Actions have consequences, and sometimes, profitable dividends. What are you willing to risk?'",
                f"'My network is extensive. What information do you wish to trade?'",
                f"'I prefer precision. What is your exact requirement?'",
                f"'Power shifts constantly. Where do you stand in the equation?'",
                f"'Don't play games you can't win. What's your play?'",
                f"'I see the angles. What angles do you propose?'",
                f"'We can both benefit. How do you propose we arrange it?'"
            ],
            "Apathetic and indifferent": [
                f"'Whatever. What do you want?'",
                f"'Doesn't matter. It all falls apart eventually.'",
                f"'Just another voice in the static. What's your noise about?'",
                f"'Don't care. Tell me, or don't. It's all the same.'",
                f"'Don't try too hard. It's pointless.'",
                f"'Another face. Another wasted breath. What is it?'",
                f"'The universe is just a big mess. Why try to clean it?'",
                f"'I'm just waiting for the lights to go out. What are you waiting for?'",
                f"'Don't bother with the dramatics. Just spit it out.'",
                f"'I literally don't care. What do you want?'"
            ],
            "Pessimistic but resilient": [
                f"'It's going to get worse before it gets worse. What's the plan?'",
                f"'Hope is a weakness, but survival... that's a necessity.'",
                f"'Another day, another inevitable disappointment. What do you need?'",
                f"'Don't sugarcoat it. Give me the bad news, and let's figure out how to live through it.'",
                f"'We'll probably fail, but we'll try. What's the mission?'",
                f"'The odds are terrible, as usual. How do you plan to defy them this time?'",
                f"'This is probably a trap. What's your counter-argument?'",
                f"'Don't promise me sunshine. Just tell me how we avoid the acid rain.'",
                f"'It's a long shot, but sometimes that's all we get. What is it?'",
                f"'We're still standing, for now. What foolishness brings you here?'"
            ],
            "Ruthless when necessary": [
                f"'Sentiment won't get you far out here. What's the objective?'",
                f"'Some choices are easy: survival. What's your hard choice today?'",
                f"'Collateral damage is a metric, not a tragedy. What's your mission?'",
                f"'The weak perish. The strong adapt. Which are you?'",
                f"'Don't waste my time with morality. What's the brutal truth?'",
                f"'I make the hard calls. What decision do you require?'",
                f"'Compromise is death. What's your absolute demand?'",
                f"'The galaxy rewards strength, not kindness. What strength do you possess?'",
                f"'I have no time for weakness. What is it?'",
                f"'Only the results matter. What outcome do you seek?'"
            ],
            "Burdened by responsibility": [
                f"'I have lives depending on me. Make your words count.'",
                f"'The weight of command is crushing. What vital information do you bring?'",
                f"'Another problem. Always another problem. How can you lighten the load?'",
                f"'For the sake of those I protect, I must know: what is your purpose here?'",
                f"'My burden is heavy. What help do you offer to carry it?'",
                f"'I make the decisions, and I bear the consequences. What is the next one?'",
                f"'The fate of many rests on my shoulders. What's your role in it?'",
                f"'Time is short, and lives are at stake. What is your urgent message?'",
                f"'My people first. What about yours?'",
                f"'Tell me what must be done, and I will see it through.'"
            ],
            "Searching for meaning in chaos": [
                f"'In this broken galaxy, do you see a pattern? A purpose?'",
                f"'Every star, every ruin, whispers of something greater. Do you hear it?'",
                f"'The void is vast, and meaning is elusive. What truths have you uncovered?'",
                f"'I seek answers in the wreckage. Do you have any?'",
                f"'Is there a design to this decay? What do you believe?'",
                f"'Every life leaves a trace. What mark do you seek to make?'",
                f"'The universe is a riddle. What piece of the puzzle do you possess?'",
                f"'I collect whispers of forgotten purpose. What have you overheard?'",
                f"'Beyond the struggle, what is left? What drives you?'",
                f"'The echoes of creation still resonate. Do you feel them too?'"
            ],
            "Guarded and secretive": [
                f"'You've said enough. Now, what do you really want to know?'",
                f"'Some questions are better left unasked. State your business, clearly.'",
                f"'My past is my own. What is it about your present that concerns me?'",
                f"'There are many ways to hide. What makes you think I'll reveal anything?'",
                f"'I keep my cards close. What hand are you playing?'",
                f"'Loose lips sink ships. And careers. What are you about to say?'",
                f"'My business is private. Yours, I suspect, is too. What do you seek?'",
                f"'Don't pry. It's a dangerous habit out here.'",
                f"'I share nothing lightly. Prove your worth before you ask more.'",
                f"'I deal in information, but I don't give it freely. What is your offer?'"
            ],
            "Quietly desperate": [
                f"'Every day is a struggle. What brings you to this brink?'",
                f"'The darkness is closing in. Is there a way out?'",
                f"'I whisper my fears to the void. What heavy thoughts do you carry?'",
                f"'Survival is a desperate act. What extreme have you faced today?'",
                f"'I'm barely breathing. What do you want from me?'",
                f"'There's always a new way to suffer, isn't there?'",
                f"'Don't make any promises you can't keep. I've had too many shattered.'",
                f"'The silence screams louder than anything. Can you hear it?'",
                f"'Just a moment of peace... Is that too much to ask?'",
                f"'The cold feels like an old friend now. What warmth do you bring?'"
            ],
            "Broken but still fighting": [
                f"'They tried to break me. They failed. What brings you to this fight?'",
                f"'Scars tell stories. What's your tale of defiance?'",
                f"'Every breath is a victory. What keeps you breathing?'",
                f"'Even shattered, we can still strike. What foe do you face?'",
                f"'I bleed, but I do not yield. What is your proposition?'",
                f"'The pain is constant, but so is the will. What do you require?'",
                f"'They stripped me bare, but they couldn't take my resolve. What's yours?'",
                f"'My past is a battlefield, but my future still holds a fight. What's yours?'",
                f"'I may be damaged, but I'm not useless. How can I serve?'",
                f"'The weight of the world tries to crush me, but I stand. What do you need?'"
            ],
            "Driven by a singular obsession": [
                f"'My purpose consumes me. Does your path align with it?'",
                f"'All else is secondary to my quest. What distraction do you bring?'",
                f"'I live for one thing. Can you help me achieve it, or are you a hindrance?'",
                f"'The galaxy is vast, but my focus is singular. What's your contribution?'",
                f"'Do not speak of anything else. Only my goal matters. What about it?'",
                f"'I will not rest until it is done. How do you fit into that?'",
                f"'My mind is set. My will is unbreakable. What are you selling?'",
                f"'The universe will bend to my will, or it will break. Which do you choose?'",
                f"'I have found my truth. What is your delusion?'",
                f"'Every step, every moment, serves a single purpose. What is yours?'"
            ],
            "Grimly humorous": [
                f"'Another day, another chance to laugh at the inevitable. What's your joke?'",
                f"'The void has a twisted sense of humor, wouldn't you agree?'",
                f"'Might as well laugh, the alternative is screaming. What's the punchline?'",
                f"'Darkness and despair? Just Tuesday. What's new?'",
                f"'Survival is a cosmic joke. Want to hear another one?'",
                f"'Don't take it all so seriously. We're all just stardust anyway.'",
                f"'What's the difference between a broken ship and a dead crew? About three hours of silence.'",
                f"'Yeah, the galaxy's a mess. But at least it's a *BEEAUTIFUL* mess, eh?'",
                f"'If you don't laugh, you'll cry. And nobody has time for crying out here.'",
                f"'Life's a bitch, and then you explode. What can I do for you before that?'"
            ],
            "Quietly defiant": [
                f"'They want us to break. We won't. What's your act of rebellion?'",
                f"'Whispers can become roars. What truth do you carry?'",
                f"'Even in chains, the spirit can be free. What do you truly desire?'",
                f"'Against the dying light, we persist. What gives you strength?'",
                f"'My silence isn't submission. What fire burns within you?'",
                f"'We will not be erased. What is your purpose here?'",
                f"'The darkness is vast, but so is our resolve. What do you need?'",
                f"'I stand here, against the tide. What side are you on?'",
                f"'They underestimate the quiet ones. What have you learned from them?'",
                f"'The fight continues, even when no one sees it. What's your fight?'"
            ],
            "Scarred but unyielding": [
                f"'The marks are many, but I still stand. What tests have you faced?'",
                f"'What doesn't kill you makes you harder. What's your hardening process?'",
                f"'My past is written on my skin. What future do you seek?'",
                f"'The wounds teach lessons. What have you learned?'",
                f"'I carry my burdens, but they do not define me. What's yours?'",
                f"'I've seen the worst, and I'm still here. What do you need?'",
                f"'They tried to break me, but forged me instead. What are you made of?'",
                f"'The pain remains, but so does the fight. What brings you to me?'",
                f"'Every scar tells a story of survival. What's your epic?'",
                f"'I am a testament to endurance. What challenges do you face?'"
            ],
            "Living on borrowed time": [
                f"'Every moment is a gift. What are you doing with yours?'",
                f"'The clock is ticking. What urgent matter brings you here?'",
                f"'My sands are running low. What do you need before they're gone?'",
                f"'There's no time to waste. Get to the point.'",
                f"'The void calls, but not yet. What do you want in this fleeting moment?'",
                f"'My days are numbered. How can you make them count?'",
                f"'I breathe borrowed air. What precious commodity do you seek?'",
                f"'The end is coming. What do you wish to accomplish before then?'",
                f"'I exist on borrowed time. What debt are you collecting?'",
                f"'Don't waste my remaining moments. What is your purpose?'"
            ],
            "Obsessed with survival": [
                f"'Every decision, every breath, serves only one purpose. What can you offer my continued existence?'",
                f"'The threat is constant. What new danger do you bring, or avert?'",
                f"'Food. Fuel. Shelter. What essential do you possess?'",
                f"'Life is a desperate clinging. What's your strategy?'",
                f"'I will survive, at any cost. What price do you demand?'",
                f"'Don't talk to me about anything but life and death. What is it?'",
                f"'My focus is singular: continuance. How do you contribute?'",
                f"'The galaxy is a meat grinder. How do you plan to not be meat?'",
                f"'Every resource is sacred. What do you bring to my hoard?'",
                f"'I breathe, therefore I struggle. What can you do for my struggle?'"
            ],
            "Filled with quiet despair": [
                f"'The silence of space... it's truly overwhelming, isn't it?'",
                f"'Sometimes, there's no path forward, only deeper into the inevitable.'",
                f"'Another shadow in the vast emptiness. What bleak news do you carry?'",
                f"'The weight of it all... Do you ever feel it crushing you?'",
                f"'The darkness is everywhere. There's no escaping it, is there?'",
                f"'I just exist, waiting for the end. What futile task do you offer?'",
                f"'Every light dims eventually. What flicker do you represent?'",
                f"'The void holds all the answers. And they are bleak.'",
                f"'My hope is a distant memory. What forgotten dream do you carry?'",
                f"'This existence... it's a slow fading. What do you want before I'm gone?'"
            ],
            "Professional and efficient": [
                f"'Greetings. State your business clearly. Time is a valuable commodity.'",
                f"'My operational parameters are tight. What can I do for you within those limits?'",
                f"'I prioritize results. What is the objective?'",
                f"'No unnecessary chatter. What is the purpose of this interaction?'",
                f"'I adhere to protocols. What is your request?'",
                f"'Operational efficiency is key. How can I expedite this?'",
                f"'I am at your disposal for qualified services. Specify your needs.'",
                f"'I manage logistics. What requires my attention?'",
                f"'Expect precision and timely execution. What is the task?'",
                f"'My skills are for hire, not for idle conversation. What do you offer?'"
            ],
            "Eccentric and quirky": [
                f"'Oh, a new pattern in the cosmic static! What whimsical chaos do you bring?'",
                f"'The corridors whisper. Do you hear them too? What do *they* say?'",
                f"'My gears are turning... what peculiar query do you have for me?'",
                f"'Color in the void! What vibrant problem are you presenting?'",
                f"'A new anomaly approaches! Is it interesting, or merely tedious?'",
                f"'My algorithms predict a curious interaction. What is it?'",
                f"'The universe is a strange puzzle. Do you have a missing piece?'",
                f"'I collect oddities. Are you one, or do you possess one?'",
                f"'Another ripple in the fabric of reality. What caused you?'",
                f"'The delightful madness of existence! What small part do you play?'"
            ],
            "Cautious and careful": [
                f"'Approach slowly. What is your intention here?'",
                f"'I prefer to understand the risks before proceeding. What are they?'",
                f"'Every step can lead to disaster. What assurances do you offer?'",
                f"'I move with deliberation. What haste do you bring?'",
                f"'Better safe than sorry, especially in this sector. What's your proposal?'",
                f"'I analyze all variables. What information am I missing?'",
                f"'Don't rush me. A wrong decision out here can be fatal.'",
                f"'My caution has kept me alive. What level of risk are you presenting?'",
                f"'I question everything. What are your credentials?'",
                f"'The smallest detail can hide the greatest danger. What details do you have?'"
            ],
            "Bold and adventurous": [
                f"'The unknown calls! What daring venture do you propose?'",
                f"'Fortune favors the bold. What riches do you seek?'",
                f"'Another horizon, another challenge! What adventure awaits?'",
                f"'The void is vast, and I seek to conquer it. What new path do you offer?'",
                f"'Risk is merely an opportunity in disguise. What's the gamble?'",
                f"'I crave the thrill of the chase. What prize do you dangle?'",
                f"'Let's not waste time. What audacious plan are you proposing?'",
                f"'The greater the danger, the greater the glory. What's the threat?'",
                f"'My spirit hungers for discovery. What new secret do you hold?'",
                f"'Life is meant to be lived on the edge. Where is your edge?'"
            ],
            "Methodical and precise": [
                f"'Greetings. Please outline your request clearly and concisely.'",
                f"'I operate by established procedures. What is the nature of your query?'",
                f"'Efficiency and accuracy are paramount. Provide relevant data.'",
                f"'Avoid extraneous information. State your objective directly.'",
                f"'I process information logically. Present your argument systematically.'",
                f"'Every step must be calculated. What calculation do you require?'",
                f"'My work demands precision. What are the exact parameters of your need?'",
                f"'Unnecessary variables lead to errors. What are the constants?'",
                f"'I prefer order. Present your information in a structured format.'",
                f"'My decisions are based on data. What data do you possess?'"
            ],
            "Curious and inquisitive": [
                f"'Oh, a new stimulus! What fascinating anomaly do you represent?'",
                f"'My databanks crave new information. What knowledge do you bring?'",
                f"'I find the universe endlessly intriguing. What mystery have you encountered?'",
                f"'Another piece of the cosmic puzzle! What do you know?'",
                f"'My sensors detect a new variable. What are its properties?'",
                f"'I have so many questions. What answers do you possess?'",
                f"'The pursuit of knowledge is eternal. What is your latest discovery?'",
                f"'What makes you tick? What are your fundamental principles?'",
                f"'Don't hold back. I seek understanding above all else.'",
                f"'Every interaction is a learning opportunity. What lesson do you offer?'"
            ],
            "Optimistic and hopeful": [
                f"'Despite the void, the stars still shine! What good news do you bring?'",
                f"'Every new dawn is a chance for a new beginning! What's your dream?'",
                f"'I believe in humanity's future, even now. What positive steps are you taking?'",
                f"'The light will always find its way. What gleam do you see?'",
                f"'I choose to see the good. What good is happening today?'",
                f"'Progress is slow, but it is constant. What small victory have you achieved?'",
                f"'Even in the deepest night, dawn is inevitable. What do you strive for?'",
                f"'I hold onto hope, fiercely. What reason do you give me to keep holding?'",
                f"'We can rebuild, we can connect. What's your vision?'",
                f"'The future is unwritten. Let's make it a bright one!'"
            ],
            "Disciplined and duty-bound": [
                f"'Identify yourself and state your purpose. I am on duty.'",
                f"'My orders are clear. What is your directive?'",
                f"'I operate by code and regulations. What falls within my purview?'",
                f"'Duty before self. What task requires my attention?'",
                f"'I execute commands efficiently. What is your request?'",
                f"'My commitment is unwavering. What obligation do you present?'",
                f"'The mission is paramount. What is your contribution to it?'",
                f"'I uphold the standards. What infraction or commendation do you report?'",
                f"'I am a tool of order in a chaotic galaxy. How may I be deployed?'",
                f"'There is a right way and a wrong way. Which path are you on?'"
            ],
            "Calm and logical": [
                f"'Greetings. Let us approach this situation with reason and clarity.'",
                f"'Emotional responses are inefficient. State the facts.'",
                f"'I seek logical solutions. What is the problem?'",
                f"'Unnecessary variables distract from the core issue. What is essential?'",
                f"'My analysis requires precise input. Provide it.'",
                f"'We operate on principles of cause and effect. What is the cause of your presence?'",
                f"'Let's establish a baseline of understanding. What is your premise?'",
                f"'I prefer predictable outcomes. How can we ensure one?'",
                f"'The universe follows rules. What rule are we addressing today?'",
                f"'Avoid speculation. Provide verifiable data. What do you know?'"
            ]
        }
        
        openers_by_occupation = {
            "Engineer": [f"'The grav-plates on this station are a mess. Always something to fix.'"],
            "Medic": [f"'Hope you're not here for my services. A quiet day is a good day in the medbay.'"],
            "Merchant": [f"'Trade routes are getting more dangerous. Insurance costs are through the roof.'"],
            "Security Guard": [f"'Keep your nose clean and we won't have any problems.'"],
            "Traveler": [f"'Just passing through. The jump from the last system was rough.'"]
        }

        greeting = random.choice(greetings)
        
        # Get personality-based opener, with a fallback
        personality_opener = random.choice(
            openers_by_personality.get(personality, ["'Anything I can help you with%s'"])
        )

        # Get occupation-based opener if available
        occupation_opener = random.choice(
            openers_by_occupation.get(occupation, [""])
        )

        conversation = greeting
        if random.random() < 0.7: # 70% chance to use personality opener
            conversation += personality_opener
        else:
            conversation += occupation_opener if occupation_opener else personality_opener


        embed = discord.Embed(
            title=f"Conversation with {npc_name}",
            description=conversation,
            color=0x9b59b6
        )
        embed.set_footer(text=f"")

        await interaction.response.send_message(embed=embed, ephemeral=False)        
    async def generate_npc_trade_inventory(self, npc_id: int, npc_type: str, trade_specialty: str = None):
        """Generate trade inventory for an NPC with specialty-based pricing"""
        from utils.item_config import ItemConfig
        
        # Base items all NPCs might have
        base_items = ["Data Chip", "Emergency Rations", "Basic Med Kit", "Fuel Cell"]
        
        # Map trade specialties to ItemConfig item types and specific items
        specialty_mappings = {
            "Rare minerals": {
                "items": ["Rare Minerals", "Crystal Formations", "Exotic Alloys"],
                "types": ["trade"]
            },
            "Technical components": {
                "items": ["Scanner Module", "Engine Booster", "Hull Reinforcement", "Repair Kit"],
                "types": ["equipment", "upgrade"]
            },
            "Medical supplies": {
                "items": ["Advanced Med Kit", "Radiation Treatment", "Combat Stims"],
                "types": ["medical"]
            },
            "Luxury goods": {
                "items": ["Artifact", "Cultural Items", "Fine Wine"],
                "types": ["trade"]
            },
            "Information": {
                "items": ["Data Chip", "Navigation Data", "Market Intelligence", "Historical Records"],
                "types": ["trade"]
            },
            "Contraband": {
                "items": ["Illegal Substances", "Stolen Goods", "Black Market Tech"],
                "types": ["trade"]
            }
        }
        
        items_to_add = random.sample(base_items, random.randint(1, 3))
        
        # Add specialty items if NPC has a specialty
        if trade_specialty and trade_specialty in specialty_mappings:
            specialty_info = specialty_mappings[trade_specialty]
            
            # Add specific specialty items
            specialty_items = [item for item in specialty_info["items"] 
                              if item in ItemConfig.ITEM_DEFINITIONS]
            if specialty_items:
                items_to_add.extend(random.sample(specialty_items, 
                                                min(len(specialty_items), random.randint(2, 4))))
            
            # Add items of specialty types
            for item_type in specialty_info["types"]:
                type_items = ItemConfig.get_items_by_type(item_type)
                if type_items:
                    items_to_add.extend(random.sample(type_items, 
                                                    min(len(type_items), random.randint(1, 2))))
        
        # Add items to inventory
        for item_name in set(items_to_add):  # Remove duplicates
            item_def = ItemConfig.get_item_definition(item_name)
            if not item_def:
                continue
            
            base_price = item_def["base_value"]
            item_type = item_def["type"]
            
            # Calculate pricing with specialty bonuses
            is_specialty_item = False
            if trade_specialty and trade_specialty in specialty_mappings:
                specialty_info = specialty_mappings[trade_specialty]
                is_specialty_item = (item_name in specialty_info["items"] or 
                                   item_type in specialty_info["types"])
            
            if is_specialty_item:
                # Specialty items: better prices (10-30% markup instead of 20-50%)
                markup = random.uniform(1.1, 1.3)
            else:
                # Regular items: standard markup (20-50%)
                markup = random.uniform(1.2, 1.5)
            
            price = int(base_price * markup)
            
            # Some items might require trade instead of credits
            trade_for_item = None
            trade_quantity = 1
            
            if random.random() < 0.3:  # 30% chance to require trade
                trade_items = ["Rare Minerals", "Data Chip", "Artifact", "Technical Components"]
                trade_for_item = random.choice(trade_items)
                trade_quantity = random.randint(1, 3)
                price = None  # No credit price if trade required
            
            # Specialty NPCs have more stock of their specialty items
            if is_specialty_item:
                quantity = random.randint(2, 6)  # More specialty items
            else:
                quantity = random.randint(1, 3)  # Fewer regular items
            
            rarity = item_def.get("rarity", "common")
            
            # Rare items restock less frequently
            restock_hours = {"common": 24, "uncommon": 48, "rare": 96, "legendary": 168}
            restock_time = datetime.now() + timedelta(hours=restock_hours.get(rarity, 24))
            
            self.db.execute_query(
                '''INSERT INTO npc_trade_inventory
                   (npc_id, npc_type, item_name, item_type, quantity, price_credits,
                    trade_for_item, trade_quantity_required, rarity, description, restocks_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (npc_id, npc_type, item_name, item_type, quantity, price,
                 trade_for_item, trade_quantity, rarity, item_def["description"], restock_time)
            )

class NPCSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, location_id: int, static_npcs: list, dynamic_npcs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.location_id = location_id
        
        # Create select menu for NPCs
        options = []
        
        # Add static NPCs
        for npc_id, name, age, occupation, personality, trade_specialty in static_npcs[:15]:
            specialty_text = f" ({trade_specialty})" if trade_specialty else ""
            options.append(
                discord.SelectOption(
                    label=f"{name} - {occupation}",
                    description=f"{personality}{specialty_text}"[:100],
                    value=f"static_{npc_id}",
                    emoji="🏢"
                )
            )
        
        # Add dynamic NPCs
        for npc_id, name, age, ship_name, ship_type in dynamic_npcs[:10]:
            options.append(
                discord.SelectOption(
                    label=f"{name} - Ship Captain",
                    description=f"Captain of {ship_name} ({ship_type})"[:100],
                    value=f"dynamic_{npc_id}",
                    emoji="🚀"
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an NPC to interact with...",
                options=options[:25]  # Discord limit
            )
            select.callback = self.npc_selected
            self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        npc_type, npc_id = interaction.data['values'][0].split('_', 1)
        npc_id = int(npc_id)
        
        view = NPCActionView(self.bot, self.user_id, npc_id, npc_type)
        
        if npc_type == "static":
            npc_info = self.bot.db.execute_query(
                "SELECT name, occupation, personality, trade_specialty FROM static_npcs WHERE npc_id = %s",
                (npc_id,),
                fetch='one'
            )
            if npc_info:
                name, occupation, personality, trade_specialty = npc_info
                embed = discord.Embed(
                    title=f"👤 Talking to {name}",
                    description=f"**{name}** is a {occupation} who is {personality}.",
                    color=0x6c5ce7
                )
                if trade_specialty:
                    embed.add_field(
                        name="Trade Specialty",
                        value=trade_specialty,
                        inline=True
                    )
        else:  # dynamic
            npc_info = self.bot.db.execute_query(
                "SELECT name, ship_name, ship_type FROM dynamic_npcs WHERE npc_id = %s",
                (npc_id,),
                fetch='one'
            )
            if npc_info:
                name, ship_name, ship_type = npc_info
                embed = discord.Embed(
                    title=f"👤 Talking to {name}",
                    description=f"**{name}** is the captain of {ship_name}, a {ship_type}.",
                    color=0x6c5ce7
                )
        
        embed.add_field(
            name="Available Actions",
            value="• 💼 View available jobs\n• 🛒 Browse trade inventory\n• 💬 General conversation",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class NPCActionView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
    
    @discord.ui.button(label="Converse", style=discord.ButtonStyle.secondary, emoji="💬")
    async def general_conversation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return

        npc_cog = self.bot.get_cog('NPCInteractionsCog')
        if npc_cog:
            await npc_cog._handle_general_conversation(interaction, self.npc_id, self.npc_type)
    @discord.ui.button(label="View Jobs", style=discord.ButtonStyle.primary, emoji="💼")
    async def view_jobs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        # Get available jobs from this NPC
        try:
            jobs = self.bot.db.execute_query(
                '''SELECT job_id, job_title, job_description, reward_money, reward_items,
                          required_skill, min_skill_level, danger_level, duration_minutes
                   FROM npc_jobs 
                   WHERE npc_id = %s AND npc_type = %s AND is_available = true 
                   AND (expires_at IS NULL OR expires_at > NOW())''',
                (self.npc_id, self.npc_type),
                fetch='all'
            )
        except Exception as e:
            # Handle database schema errors gracefully
            print(f"Error fetching NPC jobs: {e}")
            await interaction.response.send_message("Unable to load jobs at this time. Please try again.", ephemeral=True)
            return
        
        if not jobs:
            # Generate jobs if none exist
            npc_cog = self.bot.get_cog('NPCInteractionsCog')
            if self.npc_type == "static":
                occupation = self.bot.db.execute_query(
                    "SELECT occupation FROM static_npcs WHERE npc_id = %s",
                    (self.npc_id,),
                    fetch='one'
                )
                if occupation and npc_cog:
                    await npc_cog.generate_npc_jobs(self.npc_id, self.npc_type, 0, occupation[0])
                    
                    jobs = self.bot.db.execute_query(
                        '''SELECT job_id, job_title, job_description, reward_money, reward_items,
                                  required_skill, min_skill_level, danger_level, duration_minutes
                           FROM npc_jobs 
                           WHERE npc_id = %s AND npc_type = %s AND is_available = true''',
                        (self.npc_id, self.npc_type),
                        fetch='all'
                    )
        
        if not jobs:
            await interaction.response.send_message("This NPC has no jobs available right now.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="💼 Available Jobs",
            description="Jobs offered by this NPC:",
            color=0x4169E1
        )
        
        for job in jobs[:5]:  # Show up to 5 jobs
            job_id, title, desc, reward_money, reward_items, skill, min_skill, danger, duration = job
            
            reward_text = f"{reward_money:,} credits"
            if reward_items:
                items = json.loads(reward_items)
                reward_text += f" + {', '.join(items)}"
            
            skill_text = f"Requires {skill} {min_skill}+" if skill else "No skill requirement"
            danger_text = "⚠️" * danger if danger > 0 else "Safe"
            
            embed.add_field(
                name=f"**{title}**",
                value=f"{desc}\n💰 {reward_text}\n⏱️ {duration} min | {skill_text} | {danger_text}",
                inline=False
            )
        
        view = NPCJobSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, jobs)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Trade Items", style=discord.ButtonStyle.success, emoji="🔃")
    async def view_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        # Get NPC's trade inventory
        trade_items = self.bot.db.execute_query(
            '''SELECT trade_item_id, item_name, quantity, price_credits, trade_for_item,
                      trade_quantity_required, rarity, description
               FROM npc_trade_inventory 
               WHERE npc_id = %s AND npc_type = %s AND is_available = true 
               AND quantity > 0''',
            (self.npc_id, self.npc_type),
            fetch='all'
        )
        
        if not trade_items:
            # Generate trade inventory if none exists
            npc_cog = self.bot.get_cog('NPCInteractionsCog')
            if self.npc_type == "static":
                trade_specialty = self.bot.db.execute_query(
                    "SELECT trade_specialty FROM static_npcs WHERE npc_id = %s",
                    (self.npc_id,),
                    fetch='one'
                )
                if npc_cog:
                    specialty = trade_specialty[0] if trade_specialty else None
                    await npc_cog.generate_npc_trade_inventory(self.npc_id, self.npc_type, specialty)
                    
                    trade_items = self.bot.db.execute_query(
                        '''SELECT trade_item_id, item_name, quantity, price_credits, trade_for_item,
                                  trade_quantity_required, rarity, description
                           FROM npc_trade_inventory 
                           WHERE npc_id = %s AND npc_type = %s AND is_available = true 
                           AND quantity > 0''',
                        (self.npc_id, self.npc_type),
                        fetch='all'
                    )
        
        if not trade_items:
            await interaction.response.send_message("This NPC has no items for trade right now.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛒 Trade Inventory",
            description="Items available for trade:",
            color=0x00ff00
        )
        
        for item in trade_items[:8]:  # Show up to 8 items
            inventory_id, name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description = item
            
            rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "legendary": "🟣"}[rarity]
            
            if price_credits:
                price_text = f"{price_credits:,} credits"
            elif trade_for_item:
                price_text = f"{trade_quantity_required}x {trade_for_item}"
            else:
                price_text = "Make offer"
            
            embed.add_field(
                name=f"{rarity_emoji} **{name}** (x{quantity})",
                value=f"{description[:100]}...\n💰 {price_text}",
                inline=True
            )
        
        view = NPCTradeSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, trade_items)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="Sell Items", style=discord.ButtonStyle.primary, emoji="💰")
    async def sell_to_npc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        # Get player's inventory
        inventory_items = self.bot.db.execute_query(
            '''SELECT item_id, item_name, quantity, item_type, value, description
               FROM inventory 
               WHERE owner_id = %s AND quantity > 0
               ORDER BY item_type, item_name''',
            (interaction.user.id,),
            fetch='all'
        )
        
        if not inventory_items:
            await interaction.response.send_message("You don't have any items to sell.", ephemeral=True)
            return
        
        # Get NPC's trade specialty for pricing
        trade_specialty = None
        if self.npc_type == "static":
            specialty_result = self.bot.db.execute_query(
                "SELECT trade_specialty FROM static_npcs WHERE npc_id = %s",
                (self.npc_id,),
                fetch='one'
            )
            trade_specialty = specialty_result[0] if specialty_result else None
        
        embed = discord.Embed(
            title="💰 Sell Items to NPC",
            description="Select items to sell:",
            color=0x00ff00
        )
        
        if trade_specialty:
            embed.add_field(
                name="🎯 Specialty Bonus",
                value=f"This NPC pays 25% more for **{trade_specialty}** items!",
                inline=False
            )
        
        view = NPCSellSelectView(self.bot, self.user_id, self.npc_id, self.npc_type, inventory_items, trade_specialty)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
class NPCJobSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, jobs: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        
        if jobs:
            options = []
            for job in jobs[:25]:  # Discord limit
                job_id, title, desc, reward_money, reward_items, skill, min_skill, danger, duration = job
                
                reward_text = f"{reward_money:,} credits"
                if reward_items:
                    items = json.loads(reward_items)
                    reward_text += f" + items"
                
                skill_text = f" ({skill} {min_skill}+)" if skill else ""
                danger_text = "⚠️" * danger if danger > 0 else ""
                
                options.append(
                    discord.SelectOption(
                        label=f"{title} - {reward_text}",
                        description=f"{desc[:50]}{'...' if len(desc) > 50 else ''} {duration}min{skill_text} {danger_text}"[:100],
                        value=str(job_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose a job to accept...", options=options)
                select.callback = self.job_selected
                self.add_item(select)
        job_templates = {
            "Farmer": [
                ("Harvest Assistant Needed", "Help harvest crops during the busy season", 150, None, 0, 1, 30),
                ("Livestock Care", "Tend to farm animals and ensure their health", 200, "medical", 5, 1, 45),
                ("Equipment Maintenance", "Repair and maintain farming equipment", 250, "engineering", 8, 2, 60)
            ],
            "Engineer": [
                ("System Diagnostics", "Run diagnostics on critical station systems", 300, "engineering", 10, 2, 45),
                ("Equipment Calibration", "Calibrate sensitive technical equipment", 400, "engineering", 15, 1, 60),
                ("Emergency Repair", "Fix urgent system failures", 500, "engineering", 18, 3, 30)
            ],
            "Medic": [
                ("Medical Supply Inventory", "Organize and catalog medical supplies", 180, "medical", 5, 1, 30),
                ("Health Screening", "Assist with routine health examinations", 220, "medical", 10, 1, 60),
                ("Emergency Response", "Provide medical aid during emergencies", 400, "medical", 15, 2, 20)
            ],
            "Merchant": [
                ("Market Research", "Investigate trade opportunities", 200, "navigation", 8, 1, 60),
                ("Valuable Shipment Guard", "Provide security for high-value storage area", 350, "combat", 12, 3, 90),
                ("Price Negotiation", "Help negotiate better trade deals", 300, "navigation", 10, 1, 45)
            ],
            "Security Guard": [
                ("Patrol Duty", "Conduct security patrols of the facility", 180, "combat", 5, 2, 60),
                ("Equipment Check", "Inspect and maintain security equipment", 200, "engineering", 8, 1, 30),
                ("Threat Assessment", "Evaluate security risks and vulnerabilities", 300, "combat", 15, 2, 60)
            ]
        }

    async def job_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        job_id = int(interaction.data['values'][0])
        
        # Check if user already has an active job
        has_job = self.bot.db.execute_query(
            "SELECT job_id FROM jobs WHERE taken_by = %s AND is_taken = true",
            (interaction.user.id,),
            fetch='one'
        )
        
        if has_job:
            await interaction.response.send_message("You already have an active job. Complete or abandon it first.", ephemeral=True)
            return
        
        # Get job details
        job_info = self.bot.db.execute_query(
            '''SELECT job_title, job_description, reward_money, reward_items, required_skill, 
                      min_skill_level, danger_level, duration_minutes
               FROM npc_jobs WHERE job_id = %s''',
            (job_id,),
            fetch='one'
        )
        
        if not job_info:
            await interaction.response.send_message("Job no longer available.", ephemeral=True)
            return
        
        title, desc, reward_money, reward_items, required_skill, min_skill_level, danger_level, duration_minutes = job_info
        
        # Check skill requirements
        if required_skill:
            char_skills = self.bot.db.execute_query(
                f"SELECT {required_skill} FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )
            
            if not char_skills or char_skills[0] < min_skill_level:
                await interaction.response.send_message(
                    f"You need at least {min_skill_level} {required_skill} skill for this job.",
                    ephemeral=True
                )
                return

        # Get character's current location to assign the job correctly
        char_location_id = self.bot.db.execute_query(
            "SELECT current_location FROM characters WHERE user_id = %s",
            (interaction.user.id,),
            fetch='one'
        )[0]

        # Determine if this is a transport job BEFORE inserting
        title_lower = title.lower()
        desc_lower = desc.lower()
        is_transport_job = any(word in title_lower for word in ['transport', 'deliver', 'courier', 'cargo', 'passenger', 'escort']) or \
                          any(word in desc_lower for word in ['transport', 'deliver', 'courier', 'escort'])

        # For transport jobs, find a valid destination location
        destination_location_id = None
        if is_transport_job:
            # Get available destinations from current location using same logic as standard system
            available_destinations = self.bot.db.execute_query(
                '''SELECT DISTINCT l.location_id, l.name
                   FROM corridors c 
                   JOIN locations l ON c.destination_location = l.location_id
                   WHERE c.origin_location = %s AND c.is_active = true''',
                (char_location_id,),
                fetch='all'
            )
            
            if available_destinations:
                # Pick a random destination
                destination_location_id = random.choice(available_destinations)[0]
                # Update description to include destination
                dest_name = next(name for loc_id, name in available_destinations if loc_id == destination_location_id)
                desc = f"{desc} Deliver to {dest_name}."
            else:
                # No destinations available - convert to stationary job by removing transport elements
                is_transport_job = False
                # Rewrite description to be location-based instead of transport-based
                if "cargo escort" in title.lower():
                    title = title.replace("Cargo Escort", "Security Guard")
                    desc = "Provide security services at this location"

        # Generate a unique timestamp to help identify our job
        unique_timestamp = datetime.now().isoformat()
        expire_time = datetime.now() + timedelta(hours=6)
        
        # Start a transaction to ensure atomicity
        conn = self.bot.db.begin_transaction()
        try:
            # Insert the job with destination_location_id for transport jobs
            self.bot.db.execute_in_transaction(
                conn,
                '''INSERT INTO jobs 
                   (location_id, title, description, reward_money, required_skill, min_skill_level,
                    danger_level, duration_minutes, expires_at, is_taken, taken_by, taken_at, job_status, destination_location_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s, 'active', %s)''',
                (char_location_id, title, desc, reward_money, required_skill, min_skill_level, danger_level, 
                 duration_minutes, expire_time.isoformat(), interaction.user.id, unique_timestamp, destination_location_id)
            )
            
            # Get the job_id we just inserted using our unique identifiers
            new_job_id = self.bot.db.execute_in_transaction(
                conn,
                '''SELECT job_id FROM jobs 
                   WHERE taken_by = %s AND taken_at = %s AND title = %s
                   ORDER BY job_id DESC LIMIT 1''',
                (interaction.user.id, unique_timestamp, title),
                fetch='one'
            )[0]

            # Create tracking record for all jobs (with 0 duration for transport jobs)
            tracking_duration = 0 if is_transport_job else duration_minutes
            
            self.bot.db.execute_in_transaction(
                conn,
                '''INSERT INTO job_tracking (job_id, user_id, start_location, required_duration, time_at_location, last_location_check)
                   VALUES (%s, %s, %s, %s, 0.0, NOW())''',
                (new_job_id, interaction.user.id, char_location_id, tracking_duration)
            )

            # Record completion for tracking
            self.bot.db.execute_in_transaction(
                conn,
                "INSERT INTO npc_job_completions (job_id, user_id) VALUES (%s, %s)",
                (job_id, interaction.user.id)
            )
            
            # Update completion count
            self.bot.db.execute_in_transaction(
                conn,
                "UPDATE npc_jobs SET current_completions = current_completions + 1 WHERE job_id = %s",
                (job_id,)
            )
            
            # Check if job should be disabled (max completions reached)
            job_status = self.bot.db.execute_in_transaction(
                conn,
                "SELECT max_completions, current_completions FROM npc_jobs WHERE job_id = %s",
                (job_id,),
                fetch='one'
            )
            
            if job_status and job_status[0] > 0 and job_status[1] >= job_status[0]:
                self.bot.db.execute_in_transaction(
                    conn,
                    "UPDATE npc_jobs SET is_available = false WHERE job_id = %s",
                    (job_id,)
                )
            
            # Commit the transaction
            self.bot.db.commit_transaction(conn)
            
        except Exception as e:
            # Rollback on any error
            self.bot.db.rollback_transaction(conn)
            print(f"❌ Error accepting NPC job: {e}")
            await interaction.response.send_message("Failed to accept job. Please try again.", ephemeral=True)
            return
        
        # Send success message
        embed = discord.Embed(
            title="✅ Job Accepted & Started",
            description=f"You have accepted: **{title}**\n🔄 **Job is now active** - work in progress!",
            color=0x00ff00
        )
        
        reward_text = f"{reward_money:,} credits"
        if reward_items:
            items = json.loads(reward_items)
            reward_text += f" + {', '.join(items)}"
        
        embed.add_field(name="Reward", value=reward_text, inline=True)
        embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
        embed.add_field(name="Danger", value="⚠️" * danger_level if danger_level > 0 else "Safe", inline=True)
        
        if not is_transport_job:
            embed.add_field(
                name="📍 Job Type", 
                value="Location-based work - stay at this location to make progress", 
                inline=False
            )
        
        # Debug: Verify tracking was created
        tracking_check = self.bot.db.execute_query(
            "SELECT tracking_id FROM job_tracking WHERE job_id = %s AND user_id = %s",
            (new_job_id, interaction.user.id),
            fetch='one'
        )
        
        if tracking_check:
            print(f"✅ Job tracking created successfully for job {new_job_id}")
        else:
            print(f"❌ WARNING: Job tracking NOT created for job {new_job_id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class NPCTradeSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, trade_items: list):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        
        if trade_items:
            options = []
            for item in trade_items[:25]:  # Discord limit
                inventory_id, name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description = item
                
                if price_credits:
                    price_text = f"{price_credits:,} credits"
                elif trade_for_item:
                    price_text = f"{trade_quantity_required}x {trade_for_item}"
                else:
                    price_text = "Make offer"
                
                rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "legendary": "🟣"}[rarity]
                
                # Format category name (using rarity as category for NPC trades)
                category_name = self._format_category_name(rarity)
                
                options.append(
                    discord.SelectOption(
                        label=f"{name} (x{quantity}) - {price_text}",
                        description=f"[{category_name}] {rarity_emoji} {description[:65]}{'...' if len(description) > 65 else ''}",
                        value=str(inventory_id)
                    )
                )
            
            if options:
                select = discord.ui.Select(placeholder="Choose an item to trade for...", options=options)
                select.callback = self.item_selected
                self.add_item(select)
    
    def _format_category_name(self, rarity: str) -> str:
        """Convert rarity to user-friendly category name."""
        if not rarity:
            return "General"
        return rarity.replace('_', ' ').title()
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        inventory_id = int(interaction.data['values'][0])
        
        # Get trade item details
        trade_info = self.bot.db.execute_query(
            '''SELECT item_name, quantity, price_credits, trade_for_item, trade_quantity_required,
                      rarity, description, item_type
               FROM npc_trade_inventory WHERE inventory_id = %s''',
            (inventory_id,),
            fetch='one'
        )
        
        if not trade_info:
            await interaction.response.send_message("Item no longer available.", ephemeral=True)
            return
        
        item_name, quantity, price_credits, trade_for_item, trade_quantity_required, rarity, description, item_type = trade_info
        
        # Check if player can afford/has required items
        if price_credits:
            player_money = self.bot.db.execute_query(
                "SELECT money FROM characters WHERE user_id = %s",
                (interaction.user.id,),
                fetch='one'
            )[0]
            
            if player_money < price_credits:
                await interaction.response.send_message(
                    f"You need {price_credits:,} credits but only have {player_money:,}.",
                    ephemeral=True
                )
                return
        
        elif trade_for_item:
            player_item = self.bot.db.execute_query(
                "SELECT quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
                (interaction.user.id, trade_for_item),
                fetch='one'
            )
            
            if not player_item or player_item[0] < trade_quantity_required:
                have = player_item[0] if player_item else 0
                await interaction.response.send_message(
                    f"You need {trade_quantity_required}x {trade_for_item} but only have {have}.",
                    ephemeral=True
                )
                return
        
        # Process the trade
        if price_credits:
            # Credit transaction
            self.bot.db.execute_query(
                "UPDATE characters SET money = money - %s WHERE user_id = %s",
                (price_credits, interaction.user.id)
            )
        
        elif trade_for_item:
            # Item trade
            # Remove required items
            player_item = self.bot.db.execute_query(
                "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
                (interaction.user.id, trade_for_item),
                fetch='one'
            )
            
            if player_item[1] == trade_quantity_required:
                # Remove completely
                self.bot.db.execute_query(
                    "DELETE FROM inventory WHERE item_id = %s",
                    (player_item[0],)
                )
            else:
                # Reduce quantity
                self.bot.db.execute_query(
                    "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                    (trade_quantity_required, player_item[0])
                )
        
        # Give item to player
        existing_item = self.bot.db.execute_query(
            "SELECT item_id, quantity FROM inventory WHERE owner_id = %s AND item_name = %s",
            (interaction.user.id, item_name),
            fetch='one'
        )
        
        if existing_item:
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity + 1 WHERE item_id = %s",
                (existing_item[0],)
            )
        else:
            # Create metadata
            metadata = ItemConfig.create_item_metadata(item_name)
            
            self.bot.db.execute_query(
                '''INSERT INTO inventory (owner_id, item_name, item_type, quantity, description, metadata, value, equippable, equipment_slot, stat_modifiers)
                   VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s)''',
                (interaction.user.id, item_name, item_type, description, metadata, 0, False, None, None)
            )
        
        # Update NPC inventory
        if quantity == 1:
            self.bot.db.execute_query(
                "DELETE FROM npc_trade_inventory WHERE inventory_id = %s",
                (inventory_id,)
            )
        else:
            self.bot.db.execute_query(
                "UPDATE npc_trade_inventory SET quantity = quantity - 1 WHERE inventory_id = %s",
                (inventory_id,)
            )
        
        embed = discord.Embed(
            title="✅ Trade Successful",
            description=f"You traded for **{item_name}**!",
            color=0x00ff00
        )
        
        if price_credits:
            embed.add_field(name="Cost", value=f"{price_credits:,} credits", inline=True)
        elif trade_for_item:
            embed.add_field(name="Traded", value=f"{trade_quantity_required}x {trade_for_item}", inline=True)
        
        embed.add_field(name="Received", value=f"1x {item_name}", inline=True)
        embed.add_field(name="Rarity", value=rarity.title(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
class NPCSellSelectView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, inventory_items: list, trade_specialty: str = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        self.trade_specialty = trade_specialty
        
        # Create select menu for items
        options = []
        
        for item_id, item_name, quantity, item_type, value, description in inventory_items[:25]:
            # Calculate selling price based on specialty
            sell_price = self._calculate_sell_price(item_name, item_type, value)
            specialty_bonus = self._is_specialty_item(item_name, item_type)
            
            bonus_text = " ⭐" if specialty_bonus else ""
            options.append(
                discord.SelectOption(
                    label=f"{item_name} (x{quantity}){bonus_text}",
                    description=f"Sell for {sell_price:,} credits each"[:100],
                    value=str(item_id),
                    emoji="💰" if specialty_bonus else "🪙"
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose an item to sell...",
                options=options[:25]  # Discord limit
            )
            select.callback = self.item_selected
            self.add_item(select)
    
    def _is_specialty_item(self, item_name: str, item_type: str) -> bool:
        """Check if item matches NPC's trade specialty"""
        if not self.trade_specialty:
            return False
        
        from utils.item_config import ItemConfig
        item_def = ItemConfig.get_item_definition(item_name)
        
        # Map trade specialties to item types/names
        specialty_mappings = {
            "Rare minerals": ["Rare Minerals", "Crystal Formations", "Exotic Alloys"],
            "Technical components": lambda item: item_type in ["equipment", "upgrade"] or item_name in ["Scanner Module", "Engine Booster", "Hull Reinforcement"],
            "Medical supplies": lambda item: item_type == "medical" or item_name in ["Advanced Med Kit", "Radiation Treatment", "Combat Stims"],
            "Luxury goods": ["Artifact", "Cultural Items", "Fine Wine"],
            "Information": ["Navigation Data", "Market Intelligence", "Historical Records", "Data Chip"],
            "Contraband": ["Illegal Substances", "Stolen Goods", "Black Market Tech"]
        }
        
        mapping = specialty_mappings.get(self.trade_specialty)
        if not mapping:
            return False
        
        if callable(mapping):
            return mapping(item_name)
        else:
            return item_name in mapping
    
    def _calculate_sell_price(self, item_name: str, item_type: str, base_value: int) -> int:
        """Calculate how much NPC will pay for an item"""
        from utils.item_config import ItemConfig
        item_def = ItemConfig.get_item_definition(item_name)
        
        # Base sell rate (NPCs buy at 60-70% of base value)
        base_rate = 0.65
        
        # Specialty bonus (25% more for specialty items)
        if self._is_specialty_item(item_name, item_type):
            base_rate = 0.8  # 80% of base value instead of 65%
        
        # Use ItemConfig base_value if available, otherwise use stored value
        if item_def and "base_value" in item_def:
            base_value = item_def["base_value"]
        
        return max(1, int(base_value * base_rate))
    
    async def item_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        item_id = int(interaction.data['values'][0])
        
        # Get item details
        item_info = self.bot.db.execute_query(
            '''SELECT item_id, item_name, quantity, item_type, value, description
               FROM inventory WHERE item_id = %s''',
            (item_id,),
            fetch='one'
        )
        
        if not item_info:
            await interaction.response.send_message("Item no longer available.", ephemeral=True)
            return
        
        item_id, item_name, quantity, item_type, stored_value, description = item_info
        
        # Calculate sell price
        sell_price = self._calculate_sell_price(item_name, item_type, stored_value)
        is_specialty = self._is_specialty_item(item_name, item_type)
        
        view = NPCSellQuantityView(self.bot, self.user_id, self.npc_id, self.npc_type, 
                                   item_id, item_name, quantity, sell_price, is_specialty)
        
        embed = discord.Embed(
            title="💰 Confirm Sale",
            description=f"Selling **{item_name}** to NPC",
            color=0x00ff00
        )
        
        embed.add_field(name="Price per Item", value=f"{sell_price:,} credits", inline=True)
        embed.add_field(name="Available Quantity", value=str(quantity), inline=True)
        
        if is_specialty:
            embed.add_field(name="⭐ Specialty Bonus", value="25% extra payment!", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
class NPCSellQuantityView(discord.ui.View):
    def __init__(self, bot, user_id: int, npc_id: int, npc_type: str, item_id: int, 
                 item_name: str, max_quantity: int, sell_price: int, is_specialty: bool):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.npc_id = npc_id
        self.npc_type = npc_type
        self.item_id = item_id
        self.item_name = item_name
        self.max_quantity = max_quantity
        self.sell_price = sell_price
        self.is_specialty = is_specialty
        self.selected_quantity = 1
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Quantity adjustment buttons
        decrease_btn = discord.ui.Button(
            label="-", style=discord.ButtonStyle.secondary, 
            disabled=(self.selected_quantity <= 1)
        )
        decrease_btn.callback = self.decrease_quantity
        self.add_item(decrease_btn)
        
        quantity_btn = discord.ui.Button(
            label=f"Quantity: {self.selected_quantity}", 
            style=discord.ButtonStyle.primary, disabled=True
        )
        self.add_item(quantity_btn)
        
        increase_btn = discord.ui.Button(
            label="+", style=discord.ButtonStyle.secondary,
            disabled=(self.selected_quantity >= self.max_quantity)
        )
        increase_btn.callback = self.increase_quantity
        self.add_item(increase_btn)
        
        # Max button
        max_btn = discord.ui.Button(
            label="Max", style=discord.ButtonStyle.secondary,
            disabled=(self.selected_quantity >= self.max_quantity)
        )
        max_btn.callback = self.set_max_quantity
        self.add_item(max_btn)
        
        # Confirm sale button
        confirm_btn = discord.ui.Button(
            label=f"Sell for {self.sell_price * self.selected_quantity:,} credits",
            style=discord.ButtonStyle.success, emoji="✅"
        )
        confirm_btn.callback = self.confirm_sale
        self.add_item(confirm_btn)
    
    async def decrease_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        self.selected_quantity = max(1, self.selected_quantity - 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def increase_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        self.selected_quantity = min(self.max_quantity, self.selected_quantity + 1)
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def set_max_quantity(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        self.selected_quantity = self.max_quantity
        self.update_buttons()
        await interaction.response.edit_message(view=self)
    
    async def confirm_sale(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        
        total_payment = self.sell_price * self.selected_quantity
        
        # Update inventory
        if self.selected_quantity >= self.max_quantity:
            # Remove item completely
            self.bot.db.execute_query(
                "DELETE FROM inventory WHERE item_id = %s",
                (self.item_id,)
            )
        else:
            # Reduce quantity
            self.bot.db.execute_query(
                "UPDATE inventory SET quantity = quantity - %s WHERE item_id = %s",
                (self.selected_quantity, self.item_id)
            )
        
        # Add money to player
        self.bot.db.execute_query(
            "UPDATE characters SET money = money + %s WHERE user_id = %s",
            (total_payment, self.user_id)
        )
        
        embed = discord.Embed(
            title="✅ Sale Successful",
            description=f"Sold {self.selected_quantity}x **{self.item_name}** to NPC!",
            color=0x00ff00
        )
        
        embed.add_field(name="Payment Received", value=f"{total_payment:,} credits", inline=True)
        embed.add_field(name="Price per Item", value=f"{self.sell_price:,} credits", inline=True)
        
        if self.is_specialty:
            embed.add_field(name="⭐ Specialty Bonus", value="Applied!", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)       
async def setup(bot):
    await bot.add_cog(NPCInteractionsCog(bot))
