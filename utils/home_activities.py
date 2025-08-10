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
            },
            'storage': {
                'name': 'Storage Room',
                'description': 'Access your home storage',
                'icon': '📦',
                'actions': ['check_storage', 'organize_items', 'inventory_review']
            },
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
               WHERE home_id = %s AND is_active = true''',
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
        self.add_item(StorageButton())
        self.add_item(IncomeButton())
        
        for activity in activities[:25]:  # Discord limit
            button = HomeActivityButton(
                activity_type=activity['type'],
                label=activity['name'],
                emoji=activity['icon'],
                style=discord.ButtonStyle.secondary
            )
            self.add_item(button)
        
        # Add UniversalLeaveView components
        from utils.leave_button import UniversalLeaveView
        universal_leave_view = UniversalLeaveView(bot)
        for item in universal_leave_view.children:
            self.add_item(item)
    
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
            },
            'storage': {
                'check_storage': f"*{self.char_name} checks their storage room inventory.*",
                'organize_items': f"*{self.char_name} spends time organizing their stored items.*",
                'inventory_review': f"*{self.char_name} reviews what they have in storage.*"
            },
        }
        
        response_text = responses.get(activity_type, {}).get(action, f"*{self.char_name} uses the {activity_data['name']}.*")
        
        embed = discord.Embed(
            title=f"{activity_data['icon']} {activity_data['name']}",
            description=response_text,
            color=0x2F4F4F
        )
        if activity_type == 'storage':
            # Show storage summary
            storage_info = self.db.execute_query(
                '''SELECT COUNT(DISTINCT item_name), COALESCE(SUM(quantity), 0), h.storage_capacity
                   FROM location_homes h
                   LEFT JOIN home_storage s ON h.home_id = s.home_id
                   WHERE h.home_id = %s
                   GROUP BY h.storage_capacity''',
                (self.home_id,),
                fetch='one'
            )
            
            if storage_info:
                unique_items, total_items, capacity = storage_info
                response_text += f"\n\n📊 **Storage Status:** {total_items}/{capacity} items ({unique_items} unique types)"
                response_text += "\n💡 *Use `/storage view` to see details*"

        await interaction.response.send_message(embed=embed)

class StorageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Storage",
            emoji="📦",
            style=discord.ButtonStyle.primary
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "**Storage Commands:**\n"
            "• `/storage view` - View your storage\n"
            "• `/storage store` - Store items\n"
            "• `/storage retrieve` - Get items back",
            ephemeral=True
        )

class IncomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Income",
            emoji="💰",
            style=discord.ButtonStyle.success
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Check if home has income
        home_id = self.view.home_id
        income_data = interaction.client.db.execute_query(
            '''SELECT SUM(hu.daily_income), hi.accumulated_income
               FROM home_upgrades hu
               LEFT JOIN home_income hi ON hu.home_id = hi.home_id
               WHERE hu.home_id = %s
               GROUP BY hi.accumulated_income''',
            (home_id,),
            fetch='one'
        )
        
        if income_data and income_data[0]:
            daily, accumulated = income_data
            await interaction.response.send_message(
                f"**💰 Income Status**\n"
                f"Daily Rate: {daily} credits/day\n"
                f"Available to Collect: {accumulated or 0} credits\n\n"
                f"Use `/tqe` and access the 'Extras > Homes' menu to collect!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Your home doesn't generate income yet!\n"
                "Use `/tqe` and access the 'Extras > Homes' menu to purchase income-generating upgrades.",
                ephemeral=True
            )
            
class HomeActivityButton(discord.ui.Button):
    """Button for home activities"""
    
    def __init__(self, activity_type: str, **kwargs):
        super().__init__(**kwargs)
        self.activity_type = activity_type
    
    async def callback(self, interaction: discord.Interaction):
        view: HomeActivityView = self.view
        await view.handle_activity(interaction, self.activity_type)