# utils/home_activities.py
import discord
import random
from typing import List, Dict, Tuple
from datetime import datetime

class HomeActivityManager:
    """Manages interactive activities available in player homes"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Define all possible home activities
        self.activity_types = {
            'kitchen': {
                'name': 'Kitchen',
                'description': 'Prepare meals and experiment with recipes',
                'icon': '🍳',
                'actions': ['cook_meal', 'brew_coffee', 'check_supplies']
            },
            'entertainment': {
                'name': 'Entertainment Center',
                'description': 'Relax with games, movies, and music',
                'icon': '📺',
                'actions': ['watch_holovid', 'play_game', 'listen_music']
            },
            'bedroom': {
                'name': 'Bedroom',
                'description': 'Rest and personal space',
                'icon': '🛏️',
                'actions': ['rest', 'change_outfit', 'check_messages']
            },
            'study': {
                'name': 'Study',
                'description': 'Read, research, and work on personal projects',
                'icon': '📚',
                'actions': ['read_book', 'research_topic', 'write_journal']
            },
            'garden': {
                'name': 'Garden Area',
                'description': 'Tend to plants and enjoy nature',
                'icon': '🌱',
                'actions': ['water_plants', 'harvest_herbs', 'relax_outdoors']
            },
            'workshop': {
                'name': 'Workshop',
                'description': 'Tinker with gadgets and repairs',
                'icon': '🔧',
                'actions': ['repair_item', 'craft_gadget', 'organize_tools']
            },
            'gym': {
                'name': 'Exercise Area',
                'description': 'Stay fit with personal training equipment',
                'icon': '💪',
                'actions': ['workout', 'meditate', 'practice_martial_arts']
            },
            'balcony': {
                'name': 'Balcony/Viewport',
                'description': 'Enjoy views of the location',
                'icon': '🌆',
                'actions': ['enjoy_view', 'have_drink', 'stargaze']
            }
        }
    
    def generate_random_activities(self, count: int) -> List[str]:
        """Generate random activities for a home"""
        available_types = list(self.activity_types.keys())
        selected = random.sample(available_types, min(count, len(available_types)))
        return selected
    
    def get_home_activities(self, home_id: int) -> List[Dict]:
        """Get all activities for a home"""
        activities = self.db.execute_query(
            '''SELECT activity_type, activity_name FROM home_activities
               WHERE home_id = ? AND is_active = 1''',
            (home_id,),
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


class HomeActivityView(discord.ui.View):
    """Interactive view for home activities"""
    
    def __init__(self, bot, home_id: int, home_name: str, char_name: str):
        super().__init__(timeout=1800)  # 30 minute timeout
        self.bot = bot
        self.db = bot.db
        self.home_id = home_id
        self.home_name = home_name
        self.char_name = char_name
        
        # Get home activities and create buttons
        manager = HomeActivityManager(bot)
        activities = manager.get_home_activities(home_id)
        
        for activity in activities[:25]:  # Discord limit
            button = HomeActivityButton(
                activity_type=activity['type'],
                label=activity['name'],
                emoji=activity['icon'],
                style=discord.ButtonStyle.secondary
            )
            self.add_item(button)
    
    async def handle_activity(self, interaction: discord.Interaction, activity_type: str):
        """Handle activity interactions"""
        manager = HomeActivityManager(self.bot)
        activity_data = manager.activity_types.get(activity_type)
        
        if not activity_data:
            await interaction.response.send_message("Activity not found!", ephemeral=True)
            return
        
        # Select random action
        action = random.choice(activity_data['actions'])
        
        # Generate response based on activity type
        responses = {
            'kitchen': {
                'cook_meal': f"*{self.char_name} prepares a delicious meal in their kitchen.*",
                'brew_coffee': f"*{self.char_name} brews a fresh cup of coffee, the aroma filling the home.*",
                'check_supplies': f"*{self.char_name} checks their food supplies and makes a shopping list.*"
            },
            'entertainment': {
                'watch_holovid': f"*{self.char_name} settles in to watch a holovid on the entertainment system.*",
                'play_game': f"*{self.char_name} loads up their favorite game for some relaxation.*",
                'listen_music': f"*{self.char_name} puts on some music and relaxes.*"
            },
            'bedroom': {
                'rest': f"*{self.char_name} takes a refreshing nap in their comfortable bed.*",
                'change_outfit': f"*{self.char_name} changes into a fresh outfit from their wardrobe.*",
                'check_messages': f"*{self.char_name} checks their personal messages and communications.*"
            },
            'study': {
                'read_book': f"*{self.char_name} picks up a book and loses themselves in reading.*",
                'research_topic': f"*{self.char_name} researches an interesting topic on their terminal.*",
                'write_journal': f"*{self.char_name} writes in their personal journal.*"
            },
            'garden': {
                'water_plants': f"*{self.char_name} waters their plants, watching them thrive.*",
                'harvest_herbs': f"*{self.char_name} harvests some fresh herbs from their garden.*",
                'relax_outdoors': f"*{self.char_name} relaxes in their garden area, enjoying the greenery.*"
            },
            'workshop': {
                'repair_item': f"*{self.char_name} repairs a broken item in their workshop.*",
                'craft_gadget': f"*{self.char_name} tinkers with parts to create a useful gadget.*",
                'organize_tools': f"*{self.char_name} organizes their tools and workspace.*"
            },
            'gym': {
                'workout': f"*{self.char_name} completes an intense workout session.*",
                'meditate': f"*{self.char_name} meditates peacefully, clearing their mind.*",
                'practice_martial_arts': f"*{self.char_name} practices martial arts techniques.*"
            },
            'balcony': {
                'enjoy_view': f"*{self.char_name} enjoys the view from their balcony.*",
                'have_drink': f"*{self.char_name} relaxes with a drink on the balcony.*",
                'stargaze': f"*{self.char_name} gazes at the stars through the viewport.*"
            }
        }
        
        response_text = responses.get(activity_type, {}).get(action, f"*{self.char_name} uses the {activity_data['name']}.*")
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} {activity_data['name']}",
            description=response_text,
            color=0x2F4F4F
        )
        
        await interaction.response.send_message(embed=embed)


class HomeActivityButton(discord.ui.Button):
    """Button for home activities"""
    
    def __init__(self, activity_type: str, **kwargs):
        super().__init__(**kwargs)
        self.activity_type = activity_type
    
    async def callback(self, interaction: discord.Interaction):
        view: HomeActivityView = self.view
        await view.handle_activity(interaction, self.activity_type)