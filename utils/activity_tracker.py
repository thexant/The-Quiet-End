# utils/activity_tracker.py
import asyncio
import discord
from datetime import datetime, timedelta
from typing import Dict, Set

class ActivityTracker:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.afk_tasks: Dict[int, asyncio.Task] = {}
        self.warning_tasks: Dict[int, asyncio.Task] = {}
            
    def update_activity(self, user_id: int):
        """Update user's last activity timestamp"""
        self.db.execute_query(
            "UPDATE characters SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ? AND is_logged_in = 1",
            (user_id,)
        )
        
        # Cancel any existing AFK warning for this user
        if user_id in self.warning_tasks:
            self.warning_tasks[user_id].cancel()
            del self.warning_tasks[user_id]
            
            # Send confirmation that timer was cancelled
            asyncio.create_task(self._send_timer_cancelled_message(user_id))
        
        # Cancel any existing AFK logout task
        if user_id in self.afk_tasks:
            self.afk_tasks[user_id].cancel()
            del self.afk_tasks[user_id]
    
    async def _send_timer_cancelled_message(self, user_id: int):
        """Send ephemeral message that inactivity timer was cancelled"""
        user = self.bot.get_user(user_id)
        if user:
            try:
                embed = discord.Embed(
                    title="⏰ Inactivity Timer Cancelled",
                    description="You're still logged in.",
                    color=0x00ff00
                )
                await user.send(embed=embed)
            except:
                pass  # Failed to DM user
    
    async def monitor_activity(self):
        """Background task to monitor user activity and trigger AFK warnings"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Find users who have been inactive for 2 hours
                # Use datetime.utcnow() to match SQLite's CURRENT_TIMESTAMP (which is UTC)
                two_hours_ago = datetime.utcnow() - timedelta(hours=2)
                inactive_users = self.db.execute_query(
                    '''SELECT user_id, name FROM characters 
                       WHERE is_logged_in = 1 
                       AND datetime(last_activity) < datetime(?) 
                       AND user_id NOT IN (SELECT user_id FROM afk_warnings WHERE is_active = 1)''',
                    (two_hours_ago.isoformat(),),
                    fetch='all'
                )
                
                for user_id, char_name in inactive_users:
                    # Skip if already has warning task
                    if user_id in self.warning_tasks:
                        continue
                    
                    # Start AFK warning process
                    warning_task = asyncio.create_task(self._start_afk_warning(user_id, char_name))
                    self.warning_tasks[user_id] = warning_task
                
            except Exception as e:
                print(f"Error in activity monitor: {e}")
                await asyncio.sleep(60)
    
    async def _start_afk_warning(self, user_id: int, char_name: str):
        """Start the AFK warning process for a user"""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            # Create warning record using UTC time
            expires_at = datetime.utcnow() + timedelta(minutes=10)
            self.db.execute_query(
                "INSERT INTO afk_warnings (user_id, expires_at) VALUES (?, ?)",
                (user_id, expires_at.isoformat())
            )
            
            # Send warning message
            embed = discord.Embed(
                title="⚠️ Inactivity Warning",
                description=f"You've been inactive for 2 hours. You will be automatically logged out in **10 minutes** and any active jobs will be cancelled.",
                color=0xff9900
            )
            embed.add_field(
                name="How to Stay Logged In",
                value="Interact with anything in the server (send a message, use a command, click a button) to cancel this timer.",
                inline=False
            )
            
            try:
                await user.send(embed=embed)
            except:
                pass  # Failed to DM user
            
            # Wait 10 minutes, then check if user is still inactive
            await asyncio.sleep(600)
            
            # Check if warning is still active (user didn't interact)
            active_warning = self.db.execute_query(
                "SELECT warning_id FROM afk_warnings WHERE user_id = ? AND is_active = 1",
                (user_id,),
                fetch='one'
            )
            
            if active_warning:
                # User didn't interact, auto-logout
                char_cog = self.bot.get_cog('CharacterCog')
                if char_cog:
                    await char_cog._execute_auto_logout(user_id, "AFK timeout")
                
                # Clean up warning
                self.db.execute_query(
                    "UPDATE afk_warnings SET is_active = 0 WHERE user_id = ?",
                    (user_id,)
                )
            
            # Clean up task
            if user_id in self.warning_tasks:
                del self.warning_tasks[user_id]
                
        except Exception as e:
            print(f"Error in AFK warning for user {user_id}: {e}")
    
    def cleanup_user_tasks(self, user_id: int):
        """Clean up any pending tasks for a user"""
        if user_id in self.warning_tasks:
            self.warning_tasks[user_id].cancel()
            del self.warning_tasks[user_id]
        
        if user_id in self.afk_tasks:
            self.afk_tasks[user_id].cancel()
            del self.afk_tasks[user_id]
        
        # Mark any active warnings as inactive
        self.db.execute_query(
            "UPDATE afk_warnings SET is_active = 0 WHERE user_id = ?",
            (user_id,)
        )