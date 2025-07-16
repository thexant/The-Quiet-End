# cogs/location_logs.py
import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta
from utils.npc_data import generate_npc_name, get_occupation

class LocationLogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    logs_group = app_commands.Group(name="logs", description="Location logs and guestbooks")
    
    @logs_group.command(name="view", description="View the location's log/guestbook")
    async def view_logs(self, interaction: discord.Interaction):
        # Get current location
        char_location = self.db.execute_query(
            '''SELECT c.current_location, l.name, l.location_type, l.is_derelict
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )

        if not char_location:
            await interaction.response.send_message("Location not found!", ephemeral=True)
            return

        location_id, location_name, location_type, is_derelict = char_location

        # Check if location is derelict
        if is_derelict:
            await interaction.response.send_message(
                f"📜 The abandoned {location_name} has no functioning log systems.",
                ephemeral=True
            )
            return
        # Check if this location has a log (25% chance if none exists)
        has_log = self.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0] > 0
        
        if not has_log:
            # 25% chance to generate log
            if random.random() < 0.45:
                await self._generate_initial_log(location_id, location_name, location_type)
                has_log = True
        
        if not has_log:
            await interaction.response.send_message(
                f"📜 No log or guestbook found at {location_name}.",
                ephemeral=True
            )
            return
        
        # Get log entries (most recent first)
        entries = self.db.execute_query(
            '''SELECT author_name, message, posted_at, is_generated
               FROM location_logs
               WHERE location_id = ?
               ORDER BY posted_at DESC
               LIMIT 10''',
            (location_id,),
            fetch='all'
        )
        
        embed = discord.Embed(
            title=f"📜 {location_name} - Location Log",
            description=f"Messages and records from visitors to this {location_type.replace('_', ' ')}",
            color=0x8b4513
        )
        
        if entries:
            log_text = []
            for author, message, posted_at, is_generated in entries:
                # Format timestamp
                posted_time = datetime.fromisoformat(posted_at)
                time_str = posted_time.strftime("%Y-%m-%d")
                
                # Different formatting for generated vs player entries
                if is_generated:
                    log_text.append(f"**[{time_str}] {author}**")
                    log_text.append(f"*{message}*")
                else:
                    log_text.append(f"**[{time_str}] {author}**")
                    log_text.append(f'"{message}"')
                log_text.append("")
            
            # Split into multiple fields if too long
            full_text = "\n".join(log_text)
            if len(full_text) > 1024:
                # Split into chunks
                chunks = []
                current_chunk = ""
                for line in log_text:
                    if len(current_chunk + line + "\n") > 1000:
                        chunks.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                if current_chunk:
                    chunks.append(current_chunk)
                
                for i, chunk in enumerate(chunks[:3]):  # Max 3 fields
                    field_name = "📖 Log Entries" if i == 0 else f"📖 Log Entries (cont. {i+1})"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            else:
                embed.add_field(name="📖 Log Entries", value=full_text, inline=False)
        else:
            embed.add_field(name="📖 Empty Log", value="No entries found.", inline=False)
        
        embed.add_field(
            name="✍️ Add Entry",
            value="Use `/logs add <message>` to add your own entry to this log.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @logs_group.command(name="add", description="Add an entry to the location's log")
    @app_commands.describe(message="Your message to add to the log")
    async def add_log_entry(self, interaction: discord.Interaction, message: str):
        if len(message) > 500:
            await interaction.response.send_message("Log entries must be 500 characters or less.", ephemeral=True)
            return
        
        # Get character and location info
        char_info = self.db.execute_query(
            '''SELECT c.name, c.current_location, l.name as location_name
               FROM characters c
               JOIN locations l ON c.current_location = l.location_id
               WHERE c.user_id = ?''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not char_info:
            await interaction.response.send_message("Character or location not found!", ephemeral=True)
            return
        
        char_name, location_id, location_name = char_info
        
        # Check if location has a log
        has_log = self.db.execute_query(
            "SELECT COUNT(*) FROM location_logs WHERE location_id = ?",
            (location_id,),
            fetch='one'
        )[0] > 0
        
        if not has_log:
            await interaction.response.send_message(
                "This location doesn't have a log or guestbook. Check back later!",
                ephemeral=True
            )
            return
        
        # Add entry
        self.db.execute_query(
            '''INSERT INTO location_logs (location_id, author_id, author_name, message)
               VALUES (?, ?, ?, ?)''',
            (location_id, interaction.user.id, char_name, message)
        )
        
        embed = discord.Embed(
            title="✍️ Log Entry Added",
            description=f"Your entry has been added to the {location_name} log.",
            color=0x00ff00
        )
        
        embed.add_field(name="Your Entry", value=f'"{message}"', inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _generate_initial_log(self, location_id: int, location_name: str, location_type: str):
        """Generate initial log entries for a location using dynamic NPCs with location-specific content"""
        

            # Get current in-game time
        from utils.time_system import TimeSystem
        time_system = TimeSystem(self.bot)
        current_ingame_time = time_system.calculate_current_ingame_time()
        
        if not current_ingame_time:
            # Fallback to real time if time system isn't initialized
            current_ingame_time = datetime.now()
        
        # Generate 3-7 initial entries
        num_entries = random.randint(3, 7)
        # Location-specific message templates
        location_messages = {
            'colony': [
                "Agricultural output exceeding projections this quarter.",
                "Population growth steady. Housing expansion approved.",
                "Mining operations proceeding on schedule.",
                "Trade relations with neighboring systems improving.",
                "Colonial infrastructure upgrade project initiated.",
                "Atmospheric processors maintaining optimal conditions.",
                "New settlers orientation program completed successfully.",
                "Local star radiation levels fluctuated today.",
                "Large planetary storm hit the colony.",
                "Resource extraction quotas met ahead of deadline.",
                "Terraforming efforts progressing as planned.",
                "Water recycling efficiency at 98%.",
                "Biodome 3 experiencing minor fungal bloom, contained.",
                "Educational programs seeing increased enrollment.",
                "Defensive perimeter generators at full power.",
                "Long-range probe returned with new stellar cartography data.",
                "Medical facilities reporting low incidence of new diseases.",
                "Energy grid experiencing peak demand fluctuations.",
                "Cultural exchange program with Sector Gamma approved.",
                "Geological survey team discovered new geothermal vents."
            ],
            'space_station': [
                "Docking bay efficiency improved with new traffic protocols.",
                "Station rotation mechanics functioning within normal parameters.",
                "Merchant traffic up 15% compared to last cycle.",
                "Artificial gravity generators running smoothly.",
                "Recycling systems processing waste at maximum efficiency.",
                "How much further to Earth?",
                "Tourist accommodation bookings at capacity.",
                "Station-wide maintenance inspection scheduled for next week.",
                "Emergency response drill conducted successfully.",
                "Module 7 atmospheric pressure stable.",
                "Life support environmental scrubbers cleaned.",
                "Exterior hull plating integrity check passed.",
                "Research lab reporting anomalous energy readings from deep space.",
                "Crew rotation completed without incident.",
                "Power conduits 4 and 5 showing minor thermal variations.",
                "Observation deck windows cleaned, visibility excellent.",
                "Zero-G training simulations for new recruits underway.",
                "Communications array received faint distress signal from unknown vessel.",
                "Cafeteria menu updated with fresh hydroponic produce.",
                "Internal security patrol routes optimized for coverage."
            ],
            'outpost': [
                "Long-range communications restored after equipment failure.",
                "Supply cache inventory updated and secured.",
                "Mineral survey scan detected ores.",
                "Perimeter sensors detecting normal background activity only.",
                "Generator fuel reserves adequate for six months operation.",
                "Weather monitoring equipment requires minor calibration.",
                "Emergency beacon tested and confirmed operational.",
                "Staff rotation schedule updated for next assignment period.",
                "Isolation protocols reviewed and updated.",
                "Automated drills reached target depth.",
                "Seismic activity within expected parameters.",
                "Atmospheric processing unit 2 showing slight pressure drop.",
                "Wildlife deterrent system activated after local fauna approached perimeter.",
                "Excavation team unearthed ancient artifacts.",
                "Solar array alignment adjusted for optimal energy capture.",
                "Dust storm visibility zero for past 12 hours.",
                "Water purification units operating at peak capacity.",
                "Geothermal power conduit A-7 sealed for repair.",
                "Relay station 4 signal strength improved after antenna adjustment.",
                "Drone reconnaissance mission returned with mapping data."
            ],
            'gate': [
                "Corridor stability measurements within acceptable variance.",
                "Transit queue processing efficiently during peak hours.",
                "Gate energy consumption optimized for cost savings.",
                "Safety protocols updated following recent navigation incidents.",
                "Decontamination procedures enhanced per Federal directives.",
                "Navigation beacon alignment verified and corrected.",
                "Traffic control systems upgraded to latest specification.",
                "Emergency transit procedures drilled with all staff.",
                "Inter-system data packets flowing normally.",
                "Security checkpoint 3 reported minor contraband seizure.",
                "Corridor stabilizer operating within expected tolerances.",
                "Anomaly detection systems on standby, no readings.",
                "Personnel transit logs audited for compliance.",
                "Customs declaration forms updated, new tariff rates applied.",
                "Scheduled shutdown for primary power coupling replacement."
            ]
        }

        # Generic messages that work for any location
        generic_messages = [
            "Completed daily inspection rounds. All systems nominal.",
            "Shift report: No incidents to report. Operations running smoothly.",
            "Updated safety protocols as per latest regulations.",
            "Monthly evaluation complete. Performance metrics within acceptable range.",
            "Routine maintenance scheduled for next cycle.",
            "Quality control checks passed. Standards maintained.",
            "Staff briefing conducted. New procedures implemented.",
            "Equipment calibration complete. Ready for continued operations.",
            "Inventory audit finished. Supplies adequate for current needs.",
            "Training session completed for new personnel.",
            "All systems green. No anomalies detected.",
            "Environmental conditions stable.",
            "Security sweep complete. Perimeter secure.",
            "Communications array functioning normally.",
            "Power grid operating at optimal efficiency.",
            "Life support systems within normal parameters.",
            "Navigation beacons updated and verified.",
            "Emergency systems tested and confirmed operational.",
            "Radiation levels remain within safe limits.",
            "Structural integrity checks completed successfully.",
            "Another quiet day. Good for getting caught up on paperwork.",
            "Coffee supply running low. Need to add that to the next order.",
            "Met some interesting travelers today. Always enjoy hearing their stories.",
            "Long shift, but someone has to keep things running.",
            "Received a message from family today. Always brightens the mood.",
            "Weather patterns have been unusual lately. Hope it doesn't affect operations.",
            "New arrival seemed nervous. First time this far from home, I'd guess.",
            "Reminder to self: check the backup generators tomorrow.",
            "Quiet night shift. Perfect time for reading technical manuals.",
            "Looking forward to my next leave. Could use a change of scenery.",
            "Cargo manifests reviewed and approved for processing.",
            "Price negotiations concluded. Fair deal reached.",
            "Supply shipment arrived on schedule. Quality goods as usual.",
            "Market analysis complete. Prices holding steady.",
            "New trade agreement signed. Should improve local economy.",
            "Customs inspection finished. All documentation in order.",
            "Freight scheduling updated. Traffic flow optimized.",
            "Quality assessment of incoming goods complete. Standards met.",
            "Export permits processed. Shipments cleared for departure.",
            "Trade route security briefing attended. Safety first.",
            "Diagnostic complete. Minor adjustments made to improve efficiency.",
            "Software update installed. No compatibility issues detected.",
            "Preventive maintenance performed on critical systems.",
            "Backup systems tested. Failsafes functioning properly.",
            "Network connectivity stable. Data transmission normal.",
            "Sensor array recalibrated for optimal performance.",
            "Firmware update applied successfully. System restart completed.",
            "Performance metrics analyzed. Operating within design parameters.",
            "Component replacement scheduled for next maintenance window.",
            "System logs reviewed. No error conditions found.",
            "Energy consumption holding steady.",
            "Waste disposal systems operating at capacity.",
            "Air filtration systems cleaned and re-calibrated.",
            "Hydraulics checked. Pressure levels optimal.",
            "Coolant levels within acceptable range.",
            "Structural stress tests performed, no anomalies.",
            "Vibration dampeners adjusted.",
            "Power conduits inspected for wear.",
            "Data core integrity verified.",
            "Auxiliary power unit on standby.",
            "Automated repair drones deployed for minor hull abrasions.",
            "Environmental controls stable across all zones.",
            "Routine software patch deployed system-wide.",
            "Emergency lighting systems tested and confirmed.",
            "Life support nutrient re-supply completed.",
            "Maintenance crew reported no critical issues.",
            "Internal pressure differentials normalized.",
            "Atmospheric composition analyzed, optimal.",
            "Waste heat exchangers functioning efficiently.",
            "Generator coolant lines purged.",
            "Plasma conduits inspected for energy leaks.",
            "Shield emitters recalibrated.",
            "Weapon systems on standby, no threats detected.",
            "Crew quarters sanitation levels verified.",
            "Recreational facilities maintenance completed.",
            "Medical bay inventory updated.",
            "Laboratory samples secured for transport.",
            "Command center displays updated with latest intel.",
            "Communications relays checked for interference.",
            "Telemetry data streams nominal.",
            "Navigation charts updated with recent discoveries.",
            "Astrogation calculations verified.",
            "Engine output efficiency within parameters.",
            "Fuel cells operating at optimal temperature.",
            "Thrust vectoring systems tested.",
            "Landing gear cycles performed, no issues.",
            "Flight control surfaces checked for responsiveness.",
            "Warp core diagnostic run completed.",
            "Jump drive capacitor charge holding steady.",
            "Hyperdrive calibrations verified.",
            "Pilot flight hours logged and approved.",
            "Cargo hold pressurized, secure for transit.",
            "Manifest discrepancies resolved.",
            "Loading bay activity nominal.",
            "Unloading operations proceeding efficiently.",
            "Freight containers secured for departure.",
            "Supply chain logistics reviewed and optimized.",
            "Inventory tracking system updated.",
            "Material requisitions approved.",
            "Shipment manifests cross-referenced.",
            "Trade agreements reviewed for compliance.",
            "Economic projections holding steady.",
            "Market fluctuations monitored, no significant shifts.",
            "Revenue reports submitted for analysis.",
            "Budget allocations reviewed.",
            "Financial projections updated.",
            "Investment portfolio performing as expected.",
            "Audit completed, all accounts balanced.",
            "Resource allocation strategy refined.",
            "Operational expenses within budget.",
            "Profit margins stable this quarter.",
            "Contract negotiations progressing well.",
            "Legal compliance checks completed.",
            "Data privacy protocols reinforced.",
            "Information security audit passed.",
            "Network firewall updated.",
            "System access logs reviewed.",
            "Personnel records updated.",
            "Training modules completed by all staff.",
            "Performance reviews scheduled for next cycle.",
            "Inter-departmental communication flow optimized.",
            "Project timelines adjusted for efficiency.",
            "Team morale holding strong.",
            "New initiatives launched successfully.",
            "Feedback mechanisms implemented.",
            "Suggestions box reviewed, actionable items noted.",
            "Work-life balance initiatives promoting well-being.",
            "Community outreach program showing positive results.",
            "Public relations messages approved.",
            "Crisis communication protocols on standby.",
            "Media monitoring active, no negative reports.",
            "Brand reputation holding strong.",
            "Stakeholder engagement meeting concluded.",
            "Partnership discussions initiated.",
            "Regulatory compliance documents filed.",
            "Certification renewals processed.",
            "Quality assurance checks consistently high.",
            "Innovation pipeline developing new concepts.",
            "Research and development showing promise.",
            "Prototype testing underway.",
            "Design specifications finalized for new project.",
            "Technical documentation updated and distributed.",
            "User interface feedback incorporated into next revision.",
            "Software architecture reviewed for scalability.",
            "Database optimization completed.",
            "Cloud infrastructure capacity increased.",
            "Cybersecurity threat level remains low.",
            "Automated defense systems active.",
            "Intrusion detection systems on high alert.",
            "Forensics team reviewing past anomalies.",
            "Encryption protocols updated to latest standards.",
            "Network traffic flow analyzed for irregularities.",
            "Secure communication channels verified.",
            "Disaster recovery plan reviewed and updated.",
            "Data backup procedures confirmed.",
            "Archived data integrity checks passed.",
            "System restore points created.",
            "Contingency plans in place for all scenarios.",
            "Supply chain resilience assessment completed.",
            "Critical resource stockpiles verified.",
            "Emergency supply routes mapped.",
            "Logistics network efficiency analyzed.",
            "Transportation schedules optimized.",
            "Fleet maintenance logs reviewed.",
            "Vehicle diagnostics running smoothly.",
            "Crew readiness drills performed.",
            "Medical personnel on standby.",
            "First aid stations resupplied.",
            "Sanitation crews performed deep clean.",
            "Waste management systems running without issue.",
            "Recycling rates up this cycle.",
            "Environmental impact assessments completed.",
            "Conservation efforts showing progress.",
            "Resource management policies reinforced.",
            "Water consumption within targets.",
            "Energy conservation initiatives underway.",
            "Waste heat capture systems online.",
            "Air quality sensors showing optimal readings.",
            "Hydroponics bay yield exceeding expectations.",
            "Food processing units operating at capacity.",
            "Nutritional supplements inventory full.",
            "Recreational activities participation increased.",
            "Fitness center equipment serviced.",
            "Educational resources updated.",
            "Library archives cataloged.",
            "Entertainment schedules posted.",
            "Visitor log updated.",
            "Guest services feedback positive.",
            "Concierge desk reports no unusual requests.",
            "Gift shop inventory refreshed.",
            "Observation deck popularity high.",
            "Public announcement system tested.",
            "Internal comms channels clear.",
            "Security camera feeds reviewed.",
            "Access control systems verified.",
            "Perimeter alarm systems armed.",
            "Patrol drone battery levels optimal.",
            "Response teams on alert.",
            "Evacuation routes marked and clear.",
            "Emergency shelters stocked.",
            "Medical emergency protocols drilled.",
            "Fire suppression systems tested.",
            "Hazardous materials containment procedures reviewed.",
            "Structural diagnostics running.",
            "Hull stress levels nominal.",
            "Internal bracing inspected for integrity.",
            "External sensors cleaned.",
            "Navigation lights functioning.",
            "Comm dish alignment confirmed.",
            "Power transfer conduits checked.",
            "Auxiliary battery array charged.",
            "Gravitational plating calibration complete.",
            "Sub-systems all reporting green.",
            "Core temperature stable.",
            "Main reactor output steady.",
            "Energy shields at optimal strength.",
            "Weapon system arming sequence verified.",
            "Targeting arrays locked and ready.",
            "Missile tubes reloaded.",
            "Laser cannons charged.",
            "Defensive countermeasures deployed for testing.",
            "Attack patterns simulated.",
            "Tactical displays updated.",
            "Strategic planning session completed.",
            "Fleet movements logged.",
            "Scout reports analyzed.",
            "Intelligence briefing conducted.",
            "Diplomatic communications established.",
            "Treaty negotiations ongoing.",
            "Ambassadorial reports submitted.",
            "Trade embargos maintained.",
            "Alliance protocols reviewed.",
            "Non-aggression pacts confirmed.",
            "Interstellar law briefings attended.",
            "Legal disputes mediated.",
            "Justice department caseload reviewed.",
            "Criminal activity reported low.",
            "Security forces on high alert.",
            "Civilian unrest reported minimal.",
            "Public services operating efficiently.",
            "Infrastructure development projects on schedule.",
            "Urban planning initiatives progressing.",
            "Housing sector expanding.",
            "Agricultural yields projected strong.",
            "Mining operations meeting quotas.",
            "Manufacturing output increasing.",
            "Supply chain efficiency improved.",
            "Distribution networks optimized.",
            "Retail sector reporting healthy sales.",
            "Service industry expanding.",
            "Tourism sector showing growth.",
            "Financial markets stable.",
            "Banking services operating normally.",
            "Credit ratings maintained.",
            "Tax revenues collected.",
            "Budget surplus reported.",
            "Investment opportunities identified.",
            "Philanthropic initiatives supported.",
            "Charitable donations processed.",
            "Volunteer efforts lauded.",
            "Community events well-attended.",
            "Art and culture programs flourishing.",
            "Historical archives updated.",
            "Scientific research grants awarded.",
            "Technological advancements reported.",
            "Education system reforms implemented.",
            "Healthcare access expanded.",
            "Public health initiatives successful.",
            "Emergency medical services on standby.",
            "Disease outbreak protocols reviewed.",
            "Mental health support services available.",
            "Social welfare programs benefiting many.",
            "Infrastructure integrity check completed.",
            "Power conduit junction box maintenance.",
            "HVAC system diagnostics run.",
            "Automated janitorial units deployed.",
            "Replicator output calibrated.",
            "Food synthesis unit filter replacement.",
            "Cargo lift mechanism inspected.",
            "Habitat module pressure verified.",
            "Waste heat recovery system optimized.",
            "Airlock seals tested.",
            "Magnetic containment field stable.",
            "Cryogenic storage units at optimal temperature.",
            "Antigrav platform stability confirmed.",
            "Bio-containment protocols enforced.",
            "Genetics lab data encrypted.",
            "Robotics division completed new prototype.",
            "AI core diagnostics nominal.",
            "Virtual reality training simulations updated.",
            "Holographic display projectors serviced.",
            "Quantum entanglement communicators online.",
            "Psionic inhibitor field operating.",
            "Warp field generator coolant levels nominal.",
            "Ion cannon capacitor banks charged.",
            "Plasma rifle maintenance complete.",
            "Energy shield modulator recalibrated.",
            "Anti-gravity lift systems checked.",
            "Medical drone calibration complete.",
            "Surgical bay sterilization cycle finished.",
            "Rehabilitation unit patient logs updated.",
            "Pharmacology lab inventory refreshed.",
            "Contamination showers tested.",
            "Environmental suit integrity checked.",
            "Personal comms device signal strength strong.",
            "Recreational drone flight paths mapped.",
            "Zero-g sports arena scheduled for deep clean.",
            "Library access terminals updated.",
            "Theatre projection systems tested.",
            "Art gallery environmental controls stable.",
            "Marketplace vendor licenses renewed.",
            "Security presence increased in commercial districts.",
            "Banking terminal network secure.",
            "Data center cooling systems optimal.",
            "Server farm power draw stable.",
            "Network security protocols updated.",
            "Fire suppression system pressure checked.",
            "Emergency exits clear and lit.",
            "Backup power cells fully charged.",
            "Structural integrity sensors green.",
            "Shield emitters cycling normally.",
            "Life support primary filters replaced.",
            "Atmospheric composition stable.",
            "Water reclamation systems efficient.",
            "Power grid load balanced.",
            "Waste disposal schedule maintained.",
            "Medical bay equipped and ready.",
            "Security team on regular patrol.",
            "Communications satellite link strong.",
            "Navigation computer updated.",
            "Thruster array responsive.",
            "Fuel cells at optimum levels.",
            "Environmental control systems fully operational.",
            "Routine systems check completed.",
            "All indicators show normal activity.",
            "No anomalies reported on any watch.",
            "Day's operations concluded without incident.",
            "Handover brief given to next shift.",
            "Personnel accounted for.",
            "Sleep cycle protocols initiated.",
            "Quiet hours observed throughout facility.",
            "Thinking about home today. Miss the open skies of Earth.",
            "Wish they had real rain here, not fire sprinklers.",
            "Heard some new music on the radio. Might have to track that artist down.",
            "Almost forgot my lunch today. Good thing the emergency rations are, uh... edible.",
            "My plant is actually thriving in the hydroponics bay. Little victories.",
            "Got stuck in a queue for the public transit, even in space!",
            "Someone left a really weird message in the last log entry. Hope they're okay.",
            "The new synthetic coffee isn't half bad, for synthetic coffee.",
            "Spotted a derelict freighter on the long-range scanners. Spooky.",
            "Wishing I could just step outside and feel the sun on my face.",
            "The comms were down for a bit. Always unsettling.",
            "My back is killing me. Guess endless console sitting isn't good for you.",
            "Someone keeps leaving their dirty dishes in the communal sink. Ugh.",
            "Found a forgotten data drive with some old music. Nostalgic.",
            "The stars really make you feel small, don't they?",
            "Another day, another credit earned. Living the dream.",
            "Trying to remember what day of the week it is. Feels like all of them.",
            "My plant died. Guess I'm not a natural botanist.",
            "The new uniforms are surprisingly comfortable.",
            "Finally got a response from that long-lost relative. Good to hear from them.",
            "The recycled water tastes a bit metallic today. Or maybe I'm just paranoid.",
            "Wish I had brought more snacks.",
            "The humming of the life support system is surprisingly soothing.",
            "Decided to try a new recipe in the mess hall. Didn't burn anything this time.",
            "Got a promotion today! All those late nights paid off.",
            "The stars are truly beautiful...",
            "Saw some impressive acrobatics on broadcast today.",
            "My radio unit kept bugging out. Think I need a new one.",
            "Almost forgot my duty shift. Time flies when you're procrastinating.",
            "Got a call from a friend in another system. Good to catch up.",
            "Feeling philosophical tonight. What really is 'home'?",
            "My sleep's all over the place with these varying shifts.",
            "Someone drew a smiley face on the comms console. Made me smile.",
            "The new art exhibit is actually pretty good.",
            "Trying to figure out where all the dust comes from in a sealed environment.",
            "Managed to get my laundry done before the machines broke down again.",
            "The new filtration system is making the air smell oddly fresh."
        ]

        
        # Combine location-specific and generic messages
        specific_messages = location_messages.get(location_type, [])
        all_messages = specific_messages + generic_messages
        
        # Generate entries with random NPCs
        for _ in range(num_entries):
            # Generate NPC
            first_name, last_name = generate_npc_name()
            full_name = f"{first_name} {last_name}"
            
            # Determine wealth level (weighted toward middle values for more variety)
            wealth_level = random.choices(
                range(1, 11), 
                weights=[1, 2, 3, 4, 5, 5, 4, 3, 2, 1]  # Bell curve distribution
            )[0]
            
            # Get occupation based on location type and wealth
            occupation = get_occupation(location_type, wealth_level)
            
            # Create author name format variety
            name_format = random.choice([
                f"{full_name}, {occupation}",  # Full formal
                f"{first_name} {last_name}",   # Just name
                f"{occupation} {last_name}",   # Title + surname
                f"{first_name}, {occupation}"  # First name + title
            ])
            
            # Select message (favor location-specific if available)
            if specific_messages and random.random() < 0.35:  # 60% chance for location-specific
                message = random.choice(specific_messages)
            else:
                message = random.choice(generic_messages)
            
            # Random time in past 90 days
            days_ago = random.randint(1, 90)
            hours_ago = random.randint(0, 23)
            entry_time = current_ingame_time - timedelta(days=days_ago, hours=hours_ago)
            
            self.db.execute_query(
                '''INSERT INTO location_logs 
                   (location_id, author_id, author_name, message, posted_at, is_generated)
                   VALUES (?, ?, ?, ?, ?, 1)''',
                (location_id, 0, name_format, message, entry_time.isoformat())
            )

async def setup(bot):
    await bot.add_cog(LocationLogsCog(bot))