# utils/activity_tracker.py - Fixed version with missing methods
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
        self.monitoring_task = None  # Track the main monitoring task
            
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
            
            # Mark the warning as inactive in the database
            self.db.execute_query(
                "UPDATE afk_warnings SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            
            # Send confirmation that timer was cancelled
            asyncio.create_task(self._send_timer_cancelled_message(user_id))
        
        # Cancel any existing AFK logout task
        if user_id in self.afk_tasks:
            self.afk_tasks[user_id].cancel()
            del self.afk_tasks[user_id]
        
    def start_activity_monitoring(self):
        """Start the activity monitoring background task"""
        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self.monitor_activity())
            print("✅ Activity monitoring task started")
        return self.monitoring_task
    
    def cancel_all_tasks(self):
        """Cancel all activity tracker tasks"""
        print("🔄 Cancelling activity tracker tasks...")
        
        # Cancel the main monitoring task
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            self.monitoring_task = None
        
        # Cancel all AFK warning tasks
        for user_id, task in list(self.warning_tasks.items()):
            if not task.done():
                task.cancel()
        self.warning_tasks.clear()
        
        # Cancel all AFK logout tasks
        for user_id, task in list(self.afk_tasks.items()):
            if not task.done():
                task.cancel()
        self.afk_tasks.clear()
        
        print("✅ All activity tracker tasks cancelled")
    
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
        await self.bot.wait_until_ready()  # Wait for bot to be ready first
        print("👁️ Activity monitoring started")
        
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Find users who have been inactive for 2 hours
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
                    
            except asyncio.CancelledError:
                print("👁️ Activity monitoring cancelled")
                break
            except Exception as e:
                print(f"Error in activity monitor: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def resume_afk_warnings_on_startup(self):
        """Resume any AFK warnings that were active before bot restart"""
        try:
            # Find any active warnings that haven't expired
            current_time = datetime.utcnow()
            active_warnings = self.db.execute_query(
                "SELECT user_id, expires_at FROM afk_warnings WHERE is_active = 1 AND datetime(expires_at) > datetime(?)",
                (current_time.isoformat(),),
                fetch='all'
            )
            
            for user_id, expires_at_str in active_warnings:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    time_remaining = (expires_at - current_time).total_seconds()
                    
                    if time_remaining > 0:
                        # Create task to handle the remaining time
                        warning_task = asyncio.create_task(self._resume_afk_warning(user_id, time_remaining))
                        self.warning_tasks[user_id] = warning_task
                        print(f"⏰ Resumed AFK warning for user {user_id} with {time_remaining:.0f}s remaining")
                    else:
                        # Warning has expired, mark as inactive
                        self.db.execute_query(
                            "UPDATE afk_warnings SET is_active = 0 WHERE user_id = ?",
                            (user_id,)
                        )
                except Exception as e:
                    print(f"Error resuming warning for user {user_id}: {e}")
                    
        except Exception as e:
            print(f"Error resuming AFK warnings: {e}")
    
    async def _resume_afk_warning(self, user_id: int, time_remaining: float):
        """Resume an AFK warning task with remaining time"""
        try:
            # Wait for the remaining time
            await asyncio.sleep(time_remaining)
            
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
                
        except asyncio.CancelledError:
            print(f"⏰ Resumed AFK warning cancelled for user {user_id}")
        except Exception as e:
            print(f"Error in resumed AFK warning for user {user_id}: {e}")
    
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
                
        except asyncio.CancelledError:
            print(f"⚠️ AFK warning cancelled for user {user_id}")
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