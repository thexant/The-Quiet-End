# utils/ship_activities.py
import discord
import random
from typing import List, Dict, Tuple
from datetime import datetime
from utils.leave_button import UniversalLeaveView

class ShipActivityManager:
    """Manages interactive activities available on player ships"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Define all possible ship activities
        self.activity_types = {
            'navigation_console': {
                'name': 'Navigation Console',
                'description': 'Plot courses and check star charts',
                'icon': '🗺️',
                'actions': ['check_charts', 'plot_course', 'scan_area']
            },
            'entertainment_system': {
                'name': 'Entertainment System',
                'description': 'Games, music, and holovids for relaxation',
                'icon': '🎮',
                'actions': ['play_game', 'watch_movie', 'listen_music']
            },
            'maintenance_bay': {
                'name': 'Maintenance Bay',
                'description': 'Keep your ship in top condition',
                'icon': '🔧',
                'actions': ['routine_maintenance', 'clean_ship', 'inspect_systems']
            },
            'observation_deck': {
                'name': 'Observation Deck',
                'description': 'View the cosmos through reinforced viewports',
                'icon': '🌌',
                'actions': ['stargaze', 'contemplate', 'take_photos']
            },
            'personal_quarters': {
                'name': 'Personal Quarters',
                'description': 'Your private living space',
                'icon': '🛏️',
                'actions': ['rest', 'personal_log', 'organize_belongings']
            },
            'galley': {
                'name': 'Ship Galley',
                'description': 'Prepare meals and beverages',
                'icon': '🍳',
                'actions': ['cook_meal', 'brew_coffee', 'check_supplies']
            },
            'cargo_hold': {
                'name': 'Cargo Hold',
                'description': 'Manage your stored goods and equipment',
                'icon': '📦',
                'actions': ['inspect_cargo', 'organize_hold', 'inventory_check']
            },
            'engineering_station': {
                'name': 'Engineering Station',
                'description': 'Monitor and adjust ship systems',
                'icon': '⚙️',
                'actions': ['system_diagnostics', 'tune_engines', 'power_management']
            },
            'comms_station': {
                'name': 'Communications Station',
                'description': 'Long-range communications and monitoring',
                'icon': '📡',
                'actions': ['scan_frequencies', 'send_transmission', 'monitor_chatter']
            },
            'recreation_area': {
                'name': 'Recreation Area',
                'description': 'Stay fit and pursue hobbies',
                'icon': '🏃',
                'actions': ['exercise', 'practice_skills', 'hobby_time']
            },
            'medical_station': {
                'name': 'Medical Station',
                'description': 'Basic medical and first aid facilities',
                'icon': '🏥',
                'actions': ['health_check', 'first_aid', 'medical_supplies']
            },
            'weapons_locker': {
                'name': 'Weapons Locker',
                'description': 'Secure storage for personal armaments',
                'icon': '🔫',
                'actions': ['inspect_weapons', 'practice_aim', 'inventory_weapons']
            }
        }
    
    def generate_ship_activities(self, ship_id: int, ship_type: str) -> List[str]:
        """Generate random activities for a new ship based on type"""
        # Different ship types have different activity probabilities
        type_preferences = {
            'Hauler': ['cargo_hold', 'maintenance_bay', 'galley', 'personal_quarters'],
            'Scout': ['navigation_console', 'observation_deck', 'comms_station', 'recreation_area'],
            'Courier': ['navigation_console', 'entertainment_system', 'personal_quarters', 'comms_station'],
            'Shuttle': ['personal_quarters', 'galley', 'entertainment_system', 'observation_deck'],
            'Heavy Freighter': ['cargo_hold', 'engineering_station', 'galley', 'recreation_area'],
            'Fast Courier': ['navigation_console', 'comms_station', 'personal_quarters', 'entertainment_system'],
            'Explorer': ['observation_deck', 'navigation_console', 'medical_station', 'recreation_area'],
            'Luxury Yacht': ['entertainment_system', 'observation_deck', 'galley', 'recreation_area', 'personal_quarters'],
            'Military Corvette': ['weapons_locker', 'navigation_console', 'engineering_station', 'medical_station'],
            'Research Vessel': ['observation_deck', 'medical_station', 'engineering_station', 'comms_station']
        }
        
        # Get preferred activities for ship type
        preferred = type_preferences.get(ship_type, list(self.activity_types.keys()))
        
        # Always include some basics
        guaranteed = ['personal_quarters']
        
        # Determine number of activities (3-6 based on ship size/type)
        if ship_type in ['Luxury Yacht', 'Military Corvette', 'Research Vessel', 'Heavy Freighter']:
            num_activities = random.randint(5, 6)
        elif ship_type in ['Scout', 'Explorer']:
            num_activities = random.randint(4, 5)
        else:
            num_activities = random.randint(3, 4)
        
        # Build activity list
        selected_activities = set(guaranteed)
        
        # Add preferred activities
        for activity in preferred:
            if len(selected_activities) < num_activities and activity in self.activity_types:
                selected_activities.add(activity)
        
        # Fill remaining slots with random activities
        all_activities = list(self.activity_types.keys())
        random.shuffle(all_activities)
        
        for activity in all_activities:
            if len(selected_activities) >= num_activities:
                break
            if activity not in selected_activities:
                selected_activities.add(activity)
        
        # Store in database
        for activity_type in selected_activities:
            activity_data = self.activity_types[activity_type]
            self.db.execute_query(
                '''INSERT INTO ship_activities (ship_id, activity_type, activity_name)
                   VALUES (%s, %s, %s)''',
                (ship_id, activity_type, activity_data['name'])
            )
        
        return list(selected_activities)
    
    def get_ship_activities(self, ship_id: int) -> List[Dict]:
        """Get all activities for a ship"""
        activities = self.db.execute_query(
            '''SELECT activity_type, activity_name FROM ship_activities
               WHERE ship_id = %s AND is_active = true''',
            (ship_id,),
            fetch='all'
        )
        
        result = []
        for activity_type, activity_name in activities:
            if activity_type in self.activity_types:
                activity_data = self.activity_types[activity_type].copy()
                result.append({
                    'type': activity_type,
                    'name': activity_name,
                    'icon': activity_data['icon'],
                    'description': activity_data['description'],
                    'actions': activity_data['actions']
                })
        
        return result


class ShipActivityView(discord.ui.View):
    """Interactive view for ship activities"""
    
    def __init__(self, bot, ship_id: int, ship_name: str, char_name: str, location_name: str = None, is_transit: bool = False):
        super().__init__(timeout=1800)  # 30 minute timeout
        self.bot = bot
        self.db = bot.db
        self.ship_id = ship_id
        self.ship_name = ship_name
        self.char_name = char_name
        self.location_name = location_name  # For transit context
        
        # Get ship activities and create buttons
        manager = ShipActivityManager(bot)
        activities = manager.get_ship_activities(ship_id)
        
        for activity in activities:
            button = ShipActivityButton(
                activity_type=activity['type'],
                label=activity['name'],
                emoji=activity['icon'],
                style=discord.ButtonStyle.secondary
            )
            self.add_item(button)
        
        # Add universal leave button only if not in transit
        if not is_transit:
            leave_view = UniversalLeaveView(bot)
            for item in leave_view.children:
                self.add_item(item)
    
    async def handle_activity(self, interaction: discord.Interaction, activity_type: str):
        """Handle activity interactions"""
        # Get activity data
        manager = ShipActivityManager(self.bot)
        activity_data = manager.activity_types.get(activity_type)
        
        if not activity_data:
            await interaction.response.send_message(
                "Activity not found!",
                ephemeral=True
            )
            return
        
        # Choose random action from available actions
        action = random.choice(activity_data['actions'])
        
        # Route to appropriate handler
        handler_method = getattr(self, f"_handle_{action}", None)
        if handler_method:
            await handler_method(interaction, activity_data)
        else:
            await self._handle_generic_activity(interaction, activity_data, action)
    
    # Activity handlers
    async def _handle_check_charts(self, interaction, activity_data):
        """Handle checking navigation charts"""
        location_info = ""
        if self.location_name:
            location_info = f"\n📍 Currently transiting to: **{self.location_name}**"
        
        responses = [
            "studies the holographic star charts, plotting potential routes",
            "reviews corridor stability data for nearby systems",
            "examines trade route information and traffic patterns",
            "analyzes navigation hazards marked on the charts",
            "updates the ship's navigation database with recent discoveries"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Navigation Console",
            description=f"*{self.char_name} {random.choice(responses)}.*{location_info}",
            color=0x0080ff
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_play_game(self, interaction, activity_data):
        """Handle playing games"""
        games = [
            ("Zero-G Racing Simulator", "sets a new personal best lap time"),
            ("Corridor Pilot VR", "successfully navigates through a simulated static fog"),
            ("Colony Builder 2751", "expands their virtual colony to 10,000 citizens"),
            ("Pirate Hunter", "defeats the boss on level 15"),
            ("Quantum Chess", "loses to the AI on difficulty 7")
        ]
        
        game, result = random.choice(games)
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Entertainment System",
            description=f"*{self.char_name} loads up **{game}** and {result}.*",
            color=0xff00ff
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_routine_maintenance(self, interaction, activity_data):
        """Handle ship maintenance"""
        tasks = [
            "checks and tightens all hull panel connections",
            "runs diagnostics on the life support systems",
            "cleans the air filtration units",
            "inspects the fuel injection systems",
            "lubricates the cargo bay door mechanisms",
            "calibrates the artificial gravity generators"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Maintenance Bay",
            description=f"*{self.char_name} {random.choice(tasks)}. The {self.ship_name} is well-maintained.*",
            color=0xffa500
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_stargaze(self, interaction, activity_data):
        """Handle stargazing"""
        observations = [
            "watches the distant stars shimmer through the viewport",
            "observes a nebula's colorful gases swirling in the distance",
            "spots a convoy of ships traveling to a nearby system",
            "notices the faint glow of a distant space station",
            "admires the way corridor energy dances across the hull shields",
            "contemplates the vast emptiness between the stars"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Observation Deck",
            description=f"*{self.char_name} {random.choice(observations)}.*",
            color=0x191970
        )
        
        if self.location_name:
            embed.add_field(
                name="Current View",
                value=f"The corridor to {self.location_name} stretches out ahead",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_rest(self, interaction, activity_data):
        """Handle resting in quarters"""
        rest_actions = [
            "settles into their bunk for a quick nap",
            "meditates quietly in their personal space",
            "reads a few chapters from a digital book",
            "listens to calming music while relaxing",
            "does some light stretching exercises"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Personal Quarters",
            description=f"*{self.char_name} {random.choice(rest_actions)}.*",
            color=0x9370db
        )
        
        # Small chance to restore 1-5 HP
        if random.random() < 0.3:
            hp_restored = random.randint(1, 5)
            char_hp = self.db.execute_query(
                "SELECT hp, max_hp FROM characters WHERE name = %s",
                (self.char_name,),
                fetch='one'
            )
            
            if char_hp and char_hp[0] < char_hp[1]:
                actual_restored = min(hp_restored, char_hp[1] - char_hp[0])
                self.db.execute_query(
                    "UPDATE characters SET hp = hp + %s WHERE name = %s",
                    (actual_restored, self.char_name)
                )
                embed.add_field(
                    name="💚 Refreshed",
                    value=f"The rest restored {actual_restored} HP",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_cook_meal(self, interaction, activity_data):
        """Handle cooking in the galley"""
        meals = [
            ("protein paste stir-fry", "surprisingly tasty"),
            ("recycled water soup", "nutritious but bland"),
            ("freeze-dried vegetable medley", "colorful and healthy"),
            ("synthetic meat substitute", "almost like the real thing"),
            ("emergency ration casserole", "creative use of limited ingredients")
        ]
        
        meal, quality = random.choice(meals)
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Ship Galley",
            description=f"*{self.char_name} prepares {meal}. It's {quality}.*",
            color=0xffd700
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_system_diagnostics(self, interaction, activity_data):
        """Handle engineering diagnostics"""
        systems = [
            ("Primary Power Grid", random.randint(87, 99)),
            ("Life Support", random.randint(91, 100)),
            ("Navigation Systems", random.randint(85, 98)),
            ("Hull Integrity", random.randint(82, 100)),
            ("Engine Efficiency", random.randint(79, 95))
        ]
        
        system, efficiency = random.choice(systems)
        
        status = "Optimal" if efficiency > 95 else "Good" if efficiency > 85 else "Acceptable"
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Engineering Station",
            description=f"*{self.char_name} runs a diagnostic check on the {system}.*",
            color=0x00ff00 if efficiency > 95 else 0xffff00 if efficiency > 85 else 0xff9900
        )
        
        embed.add_field(
            name="System Status",
            value=f"{system}: **{efficiency}%** - {status}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_scan_frequencies(self, interaction, activity_data):
        """Handle communications scanning"""
        signals = [
            "picks up distant emergency beacon signals",
            "intercepts fragments of a trade negotiation",
            "detects automated navigation warnings",
            "hears static-filled music from a colony broadcast",
            "monitors routine traffic control chatter",
            "catches part of a news broadcast about corridor shifts"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Communications Station",
            description=f"*{self.char_name} {random.choice(signals)}.*",
            color=0x4682b4
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_exercise(self, interaction, activity_data):
        """Handle exercise activities"""
        exercises = [
            "completes a zero-gravity workout routine",
            "runs on the magnetic treadmill for 20 minutes",
            "practices combat maneuvers in the small space",
            "does resistance training with elastic bands",
            "performs yoga poses adapted for spacecraft"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Recreation Area",
            description=f"*{self.char_name} {random.choice(exercises)}.*",
            color=0x32cd32
        )
        
        embed.add_field(
            name="💪 Fitness",
            value="Staying in shape is important for space travelers",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_inspect_cargo(self, interaction, activity_data):
        """Handle cargo inspection"""
        inspections = [
            "checks the cargo restraints and finds everything secure",
            "takes inventory of supplies and updates the manifest",
            "reorganizes some containers for better weight distribution",
            "inspects the environmental controls in the cargo bay",
            "ensures all hazardous materials are properly labeled"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Cargo Hold",
            description=f"*{self.char_name} {random.choice(inspections)}.*",
            color=0x8b4513
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_personal_log(self, interaction, activity_data):
        """Handle personal log entries"""
        log_topics = [
            "records thoughts about recent events",
            "updates their personal journal with today's activities",
            "reviews old log entries from past adventures",
            "documents interesting observations from their travels",
            "writes a letter to family back home"
        ]
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} Personal Log",
            description=f"*{self.char_name} {random.choice(log_topics)}.*",
            color=0x708090
        )
        
        if self.location_name:
            embed.add_field(
                name="📝 Log Entry",
                value=f"*'Currently in transit to {self.location_name}. All systems normal.'*",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_generic_activity(self, interaction, activity_data, action):
        """Generic handler for activities without specific implementations"""
        action_descriptions = {
            'plot_course': "plots potential routes to distant systems",
            'scan_area': "scans the surrounding space for anomalies",
            'watch_movie': "watches an old Earth classic on the entertainment system",
            'listen_music': "plays some music throughout the ship",
            'clean_ship': "tidies up the living areas",
            'inspect_systems': "checks various ship systems",
            'contemplate': "quietly contemplates the journey ahead",
            'take_photos': "captures images of the cosmic scenery",
            'organize_belongings': "reorganizes personal items",
            'brew_coffee': "brews a cup of synthetic coffee",
            'check_supplies': "takes inventory of food supplies",
            'organize_hold': "rearranges items in storage",
            'inventory_check': "updates the cargo manifest",
            'tune_engines': "makes minor adjustments to engine parameters",
            'power_management': "optimizes power distribution",
            'send_transmission': "sends a routine status update",
            'monitor_chatter': "listens to local communications",
            'practice_skills': "practices various skills",
            'hobby_time': "spends time on a personal hobby",
            'health_check': "runs a basic health diagnostic",
            'first_aid': "checks the first aid supplies",
            'medical_supplies': "inventories medical equipment",
            'inspect_weapons': "checks personal weapons",
            'practice_aim': "practices marksmanship in VR",
            'inventory_weapons': "counts ammunition and supplies"
        }
        
        description = action_descriptions.get(action, "interacts with the ship's systems")
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} {activity_data['name']}",
            description=f"*{self.char_name} {description}.*",
            color=0x808080
        )
        
        await interaction.response.send_message(embed=embed)


class ShipActivityButton(discord.ui.Button):
    """Individual activity button for ships"""
    
    def __init__(self, activity_type: str, **kwargs):
        super().__init__(**kwargs)
        self.activity_type = activity_type
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        await view.handle_activity(interaction, self.activity_type)