# cogs/quests.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from utils.item_config import ItemConfig

class QuestObjectiveModal(discord.ui.Modal):
    """Modal for creating quest objectives"""
    def __init__(self, quest_cog, quest_data: dict, objective_order: int):
        super().__init__(title=f"Quest Objective #{objective_order}")
        self.quest_cog = quest_cog
        self.quest_data = quest_data
        self.objective_order = objective_order
        
        # Objective type selection would be done via a separate view
        # This modal gets the details for a specific objective type
        
        self.description = discord.ui.TextInput(
            label="Objective Description",
            placeholder="Describe what the player needs to do...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.description)
        
        self.target_item = discord.ui.TextInput(
            label="Target Item (if applicable)",
            placeholder="Item name for obtain/deliver objectives",
            required=False,
            max_length=100
        )
        self.add_item(self.target_item)
        
        self.target_quantity = discord.ui.TextInput(
            label="Quantity/Amount",
            placeholder="Quantity for items, amount for money",
            required=False,
            default="1",
            max_length=10
        )
        self.add_item(self.target_quantity)
        
        self.target_location = discord.ui.TextInput(
            label="Target Location Name",
            placeholder="Location name for travel/visit objectives",
            required=False,
            max_length=100
        )
        self.add_item(self.target_location)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs based on objective type
            objective_type = self.quest_data.get('current_objective_type', 'visit_location')
            
            # Parse quantity/amount
            try:
                quantity = int(self.target_quantity.value) if self.target_quantity.value else 1
            except ValueError:
                quantity = 1
            
            # Parse location name to get ID
            location_id = None
            if self.target_location.value and self.target_location.value.strip():
                location_id = self.quest_cog._get_location_id_by_name(self.target_location.value)
                if location_id is None and self.target_location.value.strip():
                    await interaction.response.send_message(f"Location '{self.target_location.value}' not found. Please check the spelling and try again.", ephemeral=True)
                    return
            
            # Create objective data
            objective_data = {
                'order': self.objective_order,
                'type': objective_type,
                'description': self.description.value,
                'target_item': self.target_item.value or None,
                'target_quantity': quantity,
                'target_location_id': location_id,
                'is_optional': False
            }
            
            # Add to quest data
            if 'objectives' not in self.quest_data:
                self.quest_data['objectives'] = []
            
            self.quest_data['objectives'].append(objective_data)
            
            # Continue with quest creation flow
            await self.quest_cog._continue_quest_creation(interaction, self.quest_data)
            
        except Exception as e:
            await interaction.response.send_message(f"Error creating objective: {e}", ephemeral=True)

class QuestCreationModal(discord.ui.Modal):
    """Modal for basic quest creation"""
    def __init__(self, quest_cog, start_location_id: int):
        super().__init__(title="Create New Quest")
        self.quest_cog = quest_cog
        self.start_location_id = start_location_id
        
        self.quest_title = discord.ui.TextInput(
            label="Quest Title",
            placeholder="Enter a compelling quest title...",
            required=True,
            max_length=100
        )
        self.add_item(self.quest_title)
        
        self.description = discord.ui.TextInput(
            label="Quest Description",
            placeholder="Describe the quest background and goals...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.description)
        
        self.reward_money = discord.ui.TextInput(
            label="Money Reward",
            placeholder="Credits reward (default: 0)",
            required=False,
            default="0",
            max_length=10
        )
        self.add_item(self.reward_money)
        
        self.estimated_duration = discord.ui.TextInput(
            label="Estimated Duration",
            placeholder="e.g. '30 minutes', '2 hours'",
            required=False,
            max_length=50
        )
        self.add_item(self.estimated_duration)
        
        self.danger_level = discord.ui.TextInput(
            label="Danger Level (1-10)",
            placeholder="1 = Safe, 10 = Extremely Dangerous",
            required=False,
            default="3",
            max_length=2
        )
        self.add_item(self.danger_level)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate money reward
            try:
                money_reward = int(self.reward_money.value) if self.reward_money.value else 0
            except ValueError:
                money_reward = 0
            
            # Validate danger level
            try:
                danger = max(1, min(10, int(self.danger_level.value))) if self.danger_level.value else 3
            except ValueError:
                danger = 3
            
            quest_data = {
                'title': self.quest_title.value,
                'description': self.description.value,
                'start_location_id': self.start_location_id,
                'reward_money': money_reward,
                'estimated_duration': self.estimated_duration.value or None,
                'danger_level': danger,
                'created_by': interaction.user.id,
                'objectives': []
            }
            
            # Show objective creation interface
            await self.quest_cog._show_objective_creation(interaction, quest_data)
            
        except Exception as e:
            await interaction.response.send_message(f"Error creating quest: {e}", ephemeral=True)

class ObjectiveTypeView(discord.ui.View):
    """View for selecting objective types"""
    def __init__(self, quest_cog, quest_data: dict):
        super().__init__(timeout=300)
        self.quest_cog = quest_cog
        self.quest_data = quest_data
        
        # Objective type dropdown
        options = [
            discord.SelectOption(label="Travel to Location", value="travel", description="Player must travel to a specific location"),
            discord.SelectOption(label="Obtain Item", value="obtain_item", description="Player must acquire a specific item"),
            discord.SelectOption(label="Deliver Item", value="deliver_item", description="Player must deliver an item to a location"),
            discord.SelectOption(label="Sell Item", value="sell_item", description="Player must sell a specific item"),
            discord.SelectOption(label="Earn Money", value="earn_money", description="Player must earn a specific amount of credits"),
            discord.SelectOption(label="Visit Location", value="visit_location", description="Player must visit a location (no travel required)"),
        ]
        
        select_menu = discord.ui.Select(
            placeholder="Choose objective type...",
            options=options
        )
        select_menu.callback = self.objective_type_selected
        self.add_item(select_menu)
    
    async def objective_type_selected(self, interaction: discord.Interaction):
        objective_type = interaction.data['values'][0]
        self.quest_data['current_objective_type'] = objective_type
        
        # Show objective creation modal
        objective_order = len(self.quest_data.get('objectives', [])) + 1
        modal = QuestObjectiveModal(self.quest_cog, self.quest_data, objective_order)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Finish Quest", style=discord.ButtonStyle.success)
    async def finish_quest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.quest_data.get('objectives'):
            await interaction.response.send_message("Quest must have at least one objective!", ephemeral=True)
            return
        
        # Save quest to database
        await self.quest_cog._save_quest(interaction, self.quest_data)

class QuestsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.progress_task = None

    quest_group = app_commands.Group(name="quest", description="Quest management (admin only)")
    
    async def cog_load(self):
        """Start quest progress monitoring when cog loads"""
        print("🏆 Quest system loaded, starting progress monitoring...")
        await asyncio.sleep(2)  # Wait for other systems to be ready
        self.progress_task = self.bot.loop.create_task(self.quest_progress_monitor())
    
    async def cog_unload(self):
        """Stop quest progress monitoring when cog unloads"""
        if self.progress_task and not self.progress_task.done():
            self.progress_task.cancel()
            try:
                await self.progress_task
            except asyncio.CancelledError:
                pass
            print("🏆 Quest progress monitoring stopped")
    
    async def quest_progress_monitor(self):
        """Background task to monitor quest progress"""
        await self.bot.wait_until_ready()
        print("🔄 Quest progress monitoring started")
        
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Get all active quests
                active_quests = self.db.execute_query(
                    '''SELECT qp.quest_id, qp.user_id, qp.current_objective,
                              qp.objectives_completed
                       FROM quest_progress qp
                       WHERE qp.quest_status = 'active' ''',
                    fetch='all'
                )
                
                if not active_quests:
                    continue
                
                for quest_id, user_id, current_objective, completed_obj_json in active_quests:
                    try:
                        await self._check_quest_progress(quest_id, user_id, current_objective, completed_obj_json)
                    except Exception as e:
                        print(f"Error checking progress for quest {quest_id}, user {user_id}: {e}")
                        continue
                        
            except asyncio.CancelledError:
                print("🏆 Quest progress monitoring cancelled")
                break
            except Exception as e:
                print(f"Error in quest progress monitor: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_quest_progress(self, quest_id: int, user_id: int, current_objective: int, completed_obj_json: str):
        """Check if a specific quest's current objective is completed"""
        # Get the current objective details
        objective = self.db.execute_query(
            '''SELECT objective_type, target_location_id, target_item, target_quantity,
                      target_amount, description
               FROM quest_objectives
               WHERE quest_id = ? AND objective_order = ?''',
            (quest_id, current_objective),
            fetch='one'
        )
        
        if not objective:
            return
        
        obj_type, target_location, target_item, target_quantity, target_amount, description = objective
        
        # Get player's current status
        player_status = self.db.execute_query(
            "SELECT current_location, money FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        if not player_status:
            return
        
        current_location, money = player_status
        completed = False
        
        # Check different objective types
        if obj_type == 'travel' or obj_type == 'visit_location':
            if current_location == target_location:
                completed = True
        
        elif obj_type == 'obtain_item':
            # Check if player has the required item quantity
            item_count = self.db.execute_query(
                "SELECT SUM(quantity) FROM inventory WHERE owner_id = ? AND item_name = ?",
                (user_id, target_item),
                fetch='one'
            )
            
            if item_count and item_count[0] and item_count[0] >= target_quantity:
                completed = True
        
        elif obj_type == 'earn_money':
            if money >= target_amount:
                completed = True
        
        elif obj_type == 'sell_item':
            # This would require more complex tracking - for now skip
            pass
        
        elif obj_type == 'deliver_item':
            # Check if player is at target location and has item
            if current_location == target_location:
                item_count = self.db.execute_query(
                    "SELECT SUM(quantity) FROM inventory WHERE owner_id = ? AND item_name = ?",
                    (user_id, target_item),
                    fetch='one'
                )
                
                if item_count and item_count[0] and item_count[0] >= target_quantity:
                    # Remove the items for delivery
                    self.db.execute_query(
                        "UPDATE inventory SET quantity = quantity - ? WHERE owner_id = ? AND item_name = ?",
                        (target_quantity, user_id, target_item)
                    )
                    # Remove items with 0 quantity
                    self.db.execute_query(
                        "DELETE FROM inventory WHERE owner_id = ? AND quantity <= 0",
                        (user_id,)
                    )
                    completed = True
        
        # If objective is completed, update progress
        if completed:
            await self._complete_objective(quest_id, user_id, current_objective, completed_obj_json)
    
    async def _complete_objective(self, quest_id: int, user_id: int, current_objective: int, completed_obj_json: str):
        """Mark an objective as completed and advance quest progress"""
        try:
            # Parse completed objectives
            completed_objectives = []
            if completed_obj_json:
                try:
                    completed_objectives = json.loads(completed_obj_json)
                except:
                    completed_objectives = []
            
            # Add current objective to completed list
            if current_objective not in completed_objectives:
                completed_objectives.append(current_objective)
            
            # Get total objectives for this quest
            total_objectives = self.db.execute_query(
                "SELECT COUNT(*) FROM quest_objectives WHERE quest_id = ?",
                (quest_id,),
                fetch='one'
            )[0]
            
            # Check if quest is complete
            if len(completed_objectives) >= total_objectives:
                # Complete the quest
                await self._complete_quest(quest_id, user_id)
            else:
                # Advance to next objective
                next_objective = current_objective + 1
                self.db.execute_query(
                    '''UPDATE quest_progress 
                       SET current_objective = ?, objectives_completed = ?
                       WHERE quest_id = ? AND user_id = ?''',
                    (next_objective, json.dumps(completed_objectives), quest_id, user_id)
                )
                
                # Notify player of progress
                await self._notify_objective_completed(user_id, quest_id, current_objective)
                
        except Exception as e:
            print(f"Error completing objective for quest {quest_id}, user {user_id}: {e}")
    
    async def _complete_quest(self, quest_id: int, user_id: int):
        """Complete a quest and give rewards"""
        try:
            # Get quest details
            quest_data = self.db.execute_query(
                "SELECT title, reward_money, reward_experience FROM quests WHERE quest_id = ?",
                (quest_id,),
                fetch='one'
            )
            
            if not quest_data:
                return
            
            title, reward_money, reward_exp = quest_data
            
            # Mark quest as completed
            self.db.execute_query(
                "UPDATE quest_progress SET quest_status = 'completed' WHERE quest_id = ? AND user_id = ?",
                (quest_id, user_id)
            )
            
            # Give rewards
            if reward_money > 0:
                self.db.execute_query(
                    "UPDATE characters SET money = money + ? WHERE user_id = ?",
                    (reward_money, user_id)
                )
            
            if reward_exp > 0:
                self.db.execute_query(
                    "UPDATE characters SET experience = experience + ? WHERE user_id = ?",
                    (reward_exp, user_id)
                )
            
            # Increment quest completion count
            self.db.execute_query(
                "UPDATE quests SET current_completions = current_completions + 1 WHERE quest_id = ?",
                (quest_id,)
            )
            
            # Record completion
            completion_time = self.db.execute_query(
                "SELECT (julianday('now') - julianday(started_at)) * 24 * 60 FROM quest_progress WHERE quest_id = ? AND user_id = ?",
                (quest_id, user_id),
                fetch='one'
            )
            
            completion_minutes = int(completion_time[0]) if completion_time and completion_time[0] else 0
            
            self.db.execute_query(
                '''INSERT INTO quest_completions 
                   (quest_id, user_id, completion_time_minutes, reward_received)
                   VALUES (?, ?, ?, ?)''',
                (quest_id, user_id, completion_minutes, json.dumps({'money': reward_money, 'experience': reward_exp}))
            )
            
            # Notify player
            await self._notify_quest_completed(user_id, title, reward_money, reward_exp)
            
        except Exception as e:
            print(f"Error completing quest {quest_id} for user {user_id}: {e}")
    
    async def _notify_objective_completed(self, user_id: int, quest_id: int, objective_order: int):
        """Notify player that an objective was completed"""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            # Get objective description
            objective = self.db.execute_query(
                "SELECT description FROM quest_objectives WHERE quest_id = ? AND objective_order = ?",
                (quest_id, objective_order),
                fetch='one'
            )
            
            if objective:
                embed = discord.Embed(
                    title="✅ Objective Completed!",
                    description=f"**{objective[0]}**",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Progress",
                    value="Moving to next objective. Use `/tqe` to check your progress.",
                    inline=False
                )
                
                try:
                    await user.send(embed=embed)
                except:
                    pass  # User might have DMs disabled
                    
        except Exception as e:
            print(f"Error notifying objective completion: {e}")
    
    async def _notify_quest_completed(self, user_id: int, quest_title: str, reward_money: int, reward_exp: int):
        """Notify player that a quest was completed"""
        try:
            # Get user's current location channel
            user_location = self.db.execute_query(
                "SELECT current_location FROM characters WHERE user_id = ?",
                (user_id,),
                fetch='one'
            )
            
            if not user_location:
                return
            
            location_id = user_location[0]
            
            # Get location channel
            location_data = self.db.execute_query(
                "SELECT channel_id, name FROM locations WHERE location_id = ?",
                (location_id,),
                fetch='one'
            )
            
            if not location_data:
                return
            
            channel_id, location_name = location_data
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                return
            
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            embed = discord.Embed(
                title="🏆 Quest Completed!",
                description=f"**{quest_title}**\n\n{user.mention} has completed their quest!",
                color=0x9b59b6
            )
            
            rewards = []
            if reward_money > 0:
                rewards.append(f"{reward_money:,} credits")
            if reward_exp > 0:
                rewards.append(f"{reward_exp} experience")
            
            if rewards:
                embed.add_field(
                    name="🎁 Rewards Received",
                    value=" + ".join(rewards),
                    inline=False
                )
            
            embed.add_field(
                name="What's Next?",
                value="Look for new quests at job boards throughout the galaxy!",
                inline=False
            )
            
            embed.set_footer(text=f"Completed at {location_name}")
            
            try:
                # Send ephemeral message that only the user can see
                await channel.send(f"{user.mention}", embed=embed, delete_after=30)
            except:
                pass  # Channel might not be accessible
                
        except Exception as e:
            print(f"Error notifying quest completion: {e}")

    @quest_group.command(name="create", description="Create a new quest (admin only)")
    @app_commands.describe(start_location_name="Location name where quest will be available")
    async def quest_create(self, interaction: discord.Interaction, start_location_name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can create quests.", ephemeral=True)
            return
        
        # Verify location exists and get its ID
        start_location_id = self._get_location_id_by_name(start_location_name)
        
        if start_location_id is None:
            await interaction.response.send_message(f"Location '{start_location_name}' not found. Please check the spelling and try again.", ephemeral=True)
            return
        
        # Show quest creation modal
        modal = QuestCreationModal(self, start_location_id)
        await interaction.response.send_modal(modal)
    
    async def _show_objective_creation(self, interaction: discord.Interaction, quest_data: dict):
        """Show the objective creation interface"""
        embed = discord.Embed(
            title="Create Quest Objectives",
            description=f"**Quest:** {quest_data['title']}\n\nAdd objectives that players must complete in order.",
            color=0x6c5ce7
        )
        
        if quest_data.get('objectives'):
            objectives_text = []
            for i, obj in enumerate(quest_data['objectives'], 1):
                objectives_text.append(f"{i}. {obj['description']}")
            embed.add_field(
                name="Current Objectives",
                value="\n".join(objectives_text[:10]),
                inline=False
            )
        
        view = ObjectiveTypeView(self, quest_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _continue_quest_creation(self, interaction: discord.Interaction, quest_data: dict):
        """Continue quest creation after adding an objective"""
        embed = discord.Embed(
            title="Quest Objective Added",
            description=f"Objective #{len(quest_data['objectives'])} added successfully!",
            color=0x00ff00
        )
        
        objectives_text = []
        for i, obj in enumerate(quest_data['objectives'], 1):
            objectives_text.append(f"{i}. {obj['description']}")
        
        embed.add_field(
            name="Current Objectives",
            value="\n".join(objectives_text),
            inline=False
        )
        
        view = ObjectiveTypeView(self, quest_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _get_location_id_by_name(self, location_name: str) -> Optional[int]:
        """Helper function to get location ID by name"""
        if not location_name or not location_name.strip():
            return None
        
        location = self.db.execute_query(
            "SELECT location_id FROM locations WHERE LOWER(name) = LOWER(?)",
            (location_name.strip(),),
            fetch='one'
        )
        
        return location[0] if location else None

    async def _save_quest(self, interaction: discord.Interaction, quest_data: dict):
        """Save the completed quest to database"""
        try:
            # Insert quest
            quest_id = self.db.execute_query(
                '''INSERT INTO quests 
                   (title, description, start_location_id, reward_money, created_by, 
                    estimated_duration, danger_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (quest_data['title'], quest_data['description'], quest_data['start_location_id'],
                 quest_data['reward_money'], quest_data['created_by'],
                 quest_data['estimated_duration'], quest_data['danger_level']),
                fetch='lastrowid'
            )
            
            # Insert objectives
            for obj in quest_data['objectives']:
                self.db.execute_query(
                    '''INSERT INTO quest_objectives 
                       (quest_id, objective_order, objective_type, target_location_id,
                        target_item, target_quantity, target_amount, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (quest_id, obj['order'], obj['type'], obj['target_location_id'],
                     obj['target_item'], obj['target_quantity'], 
                     obj.get('target_amount', 0), obj['description'])
                )
            
            embed = discord.Embed(
                title="✅ Quest Created Successfully",
                description=f"**{quest_data['title']}** has been created with {len(quest_data['objectives'])} objectives.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="Quest ID",
                value=str(quest_id),
                inline=True
            )
            
            location_name = self.db.execute_query(
                "SELECT name FROM locations WHERE location_id = ?",
                (quest_data['start_location_id'],),
                fetch='one'
            )[0]
            
            embed.add_field(
                name="Available At",
                value=location_name,
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error saving quest: {e}", ephemeral=True)

    @quest_group.command(name="list", description="List all quests (admin only)")
    async def quest_list(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can list quests.", ephemeral=True)
            return
        
        quests = self.db.execute_query(
            '''SELECT q.quest_id, q.title, q.is_active, l.name as location_name,
                      q.current_completions, q.max_completions
               FROM quests q
               JOIN locations l ON q.start_location_id = l.location_id
               ORDER BY q.created_at DESC''',
            fetch='all'
        )
        
        if not quests:
            await interaction.response.send_message("No quests found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 All Quests",
            color=0x6c5ce7
        )
        
        quest_list = []
        for quest_id, title, is_active, location_name, completions, max_completions in quests:
            status = "🟢 Active" if is_active else "🔴 Inactive"
            completion_text = f"{completions}"
            if max_completions > 0:
                completion_text += f"/{max_completions}"
            
            quest_list.append(f"**{quest_id}.** {title}\n└ {status} | {location_name} | Completions: {completion_text}")
        
        # Split into chunks if too many quests
        for i in range(0, len(quest_list), 10):
            chunk = quest_list[i:i+10]
            embed.add_field(
                name=f"Quests {i+1}-{min(i+10, len(quest_list))}",
                value="\n\n".join(chunk),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @quest_group.command(name="toggle", description="Enable/disable a quest (admin only)")
    @app_commands.describe(quest_id="ID of the quest to toggle")
    async def quest_toggle(self, interaction: discord.Interaction, quest_id: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can manage quests.", ephemeral=True)
            return
        
        quest = self.db.execute_query(
            "SELECT title, is_active FROM quests WHERE quest_id = ?",
            (quest_id,),
            fetch='one'
        )
        
        if not quest:
            await interaction.response.send_message(f"Quest {quest_id} not found.", ephemeral=True)
            return
        
        title, is_active = quest
        new_status = not is_active
        
        self.db.execute_query(
            "UPDATE quests SET is_active = ? WHERE quest_id = ?",
            (new_status, quest_id)
        )
        
        status_text = "enabled" if new_status else "disabled"
        embed = discord.Embed(
            title=f"Quest {status_text.title()}",
            description=f"**{title}** has been {status_text}.",
            color=0x00ff00 if new_status else 0xff0000
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def get_available_quests(self, location_id: int) -> List[Dict[str, Any]]:
        """Get available quests at a specific location for job board integration"""
        quests = self.db.execute_query(
            '''SELECT q.quest_id, q.title, q.description, q.reward_money,
                      q.estimated_duration, q.danger_level, q.required_level,
                      q.max_completions, q.current_completions
               FROM quests q
               WHERE q.start_location_id = ? AND q.is_active = 1
               AND (q.max_completions = -1 OR q.current_completions < q.max_completions)
               ORDER BY q.created_at DESC''',
            (location_id,),
            fetch='all'
        )
        
        quest_list = []
        for quest_data in quests:
            quest_id, title, description, reward_money, duration, danger, required_level, max_comp, current_comp = quest_data
            
            quest_list.append({
                'quest_id': quest_id,
                'title': f"QUEST: {title}",
                'description': description,
                'reward_money': reward_money,
                'estimated_duration': duration,
                'danger_level': danger,
                'required_level': required_level,
                'type': 'quest'
            })
        
        return quest_list

    def can_accept_quest(self, user_id: int, quest_id: int) -> tuple[bool, str]:
        """Check if user can accept a quest"""
        # Check if user already has this quest
        existing = self.db.execute_query(
            "SELECT quest_status FROM quest_progress WHERE user_id = ? AND quest_id = ?",
            (user_id, quest_id),
            fetch='one'
        )
        
        if existing:
            status = existing[0]
            if status == 'active':
                return False, "You already have this quest active!"
            elif status == 'completed':
                return False, "You have already completed this quest!"
        
        # Check if user has any other active quest
        active_quest = self.db.execute_query(
            "SELECT COUNT(*) FROM quest_progress WHERE user_id = ? AND quest_status = 'active'",
            (user_id,),
            fetch='one'
        )[0]
        
        if active_quest > 0:
            return False, "You can only have one active quest at a time!"
        
        # Check level requirement
        char_level = self.db.execute_query(
            "SELECT level FROM characters WHERE user_id = ?",
            (user_id,),
            fetch='one'
        )
        
        quest_required_level = self.db.execute_query(
            "SELECT required_level FROM quests WHERE quest_id = ?",
            (quest_id,),
            fetch='one'
        )
        
        if char_level and quest_required_level:
            if char_level[0] < quest_required_level[0]:
                return False, f"You need to be level {quest_required_level[0]} to accept this quest!"
        
        return True, ""

    def accept_quest(self, user_id: int, quest_id: int) -> bool:
        """Accept a quest and start tracking progress"""
        try:
            # Create quest progress record
            self.db.execute_query(
                '''INSERT INTO quest_progress 
                   (quest_id, user_id, current_objective, quest_status)
                   VALUES (?, ?, 1, 'active')''',
                (quest_id, user_id)
            )
            return True
        except Exception as e:
            print(f"Error accepting quest {quest_id} for user {user_id}: {e}")
            return False

    @quest_group.command(name="status", description="Check your current quest progress")
    async def quest_status(self, interaction: discord.Interaction):
        # Get user's active quest
        active_quest = self.db.execute_query(
            '''SELECT qp.quest_id, q.title, q.description, qp.current_objective,
                      qp.started_at, q.reward_money
               FROM quest_progress qp
               JOIN quests q ON qp.quest_id = q.quest_id
               WHERE qp.user_id = ? AND qp.quest_status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not active_quest:
            await interaction.response.send_message("You don't have any active quests.", ephemeral=True)
            return
        
        quest_id, title, description, current_obj, started_at, reward = active_quest
        
        # Get all objectives for this quest
        objectives = self.db.execute_query(
            '''SELECT objective_order, objective_type, description, target_location_id,
                      target_item, target_quantity, target_amount
               FROM quest_objectives
               WHERE quest_id = ?
               ORDER BY objective_order''',
            (quest_id,),
            fetch='all'
        )
        
        # Get completed objectives
        progress_data = self.db.execute_query(
            "SELECT objectives_completed FROM quest_progress WHERE quest_id = ? AND user_id = ?",
            (quest_id, interaction.user.id),
            fetch='one'
        )
        
        completed_objectives = []
        if progress_data and progress_data[0]:
            try:
                completed_objectives = json.loads(progress_data[0])
            except:
                completed_objectives = []
        
        embed = discord.Embed(
            title=f"🏆 Quest Progress: {title}",
            description=description,
            color=0x9b59b6
        )
        
        embed.add_field(name="💰 Reward", value=f"{reward:,} credits", inline=True)
        
        if started_at:
            try:
                started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                timestamp = int(started_dt.timestamp())
                embed.add_field(name="📅 Started", value=f"<t:{timestamp}:R>", inline=True)
            except:
                embed.add_field(name="📅 Started", value="Recently", inline=True)
        
        # Show objectives with progress
        if objectives:
            obj_text = []
            for order, obj_type, desc, location_id, item, quantity, amount in objectives:
                if order in completed_objectives:
                    obj_text.append(f"✅ **{order}.** {desc}")
                elif order == current_obj:
                    obj_text.append(f"🔄 **{order}.** {desc} **(CURRENT)**")
                else:
                    obj_text.append(f"⏳ **{order}.** {desc}")
            
            embed.add_field(
                name="📋 Objectives Progress",
                value="\n".join(obj_text[:10]),
                inline=False
            )
        
        progress_percent = (len(completed_objectives) / len(objectives)) * 100 if objectives else 0
        embed.add_field(
            name="📊 Overall Progress",
            value=f"{len(completed_objectives)}/{len(objectives)} objectives ({progress_percent:.0f}%)",
            inline=False
        )
        
        embed.set_footer(text=f"Quest ID: {quest_id}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @quest_group.command(name="abandon", description="Abandon your current quest")
    async def quest_abandon(self, interaction: discord.Interaction):
        """Allow players to abandon their current quest"""
        active_quest = self.db.execute_query(
            '''SELECT qp.quest_id, q.title
               FROM quest_progress qp
               JOIN quests q ON qp.quest_id = q.quest_id
               WHERE qp.user_id = ? AND qp.quest_status = 'active' ''',
            (interaction.user.id,),
            fetch='one'
        )
        
        if not active_quest:
            await interaction.response.send_message("You don't have any active quests to abandon.", ephemeral=True)
            return
        
        quest_id, title = active_quest
        
        # Update quest status to abandoned
        self.db.execute_query(
            "UPDATE quest_progress SET quest_status = 'abandoned' WHERE quest_id = ? AND user_id = ?",
            (quest_id, interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🚫 Quest Abandoned",
            description=f"You have abandoned the quest: **{title}**",
            color=0xff9500
        )
        
        embed.add_field(
            name="Notice",
            value="You can accept new quests from job boards at various locations.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(QuestsCog(bot))