# utils/time_system.py
from datetime import datetime, timedelta
from typing import Optional, Tuple
import re
from utils.datetime_utils import safe_datetime_parse

class TimeSystem:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
    def parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse DD-MM-YYYY format date string"""
        try:
            # Support both DD-MM-YYYY and YYYY formats for backward compatibility
            if re.match(r'^\d{4}$', date_str):
                # Old YYYY format
                return datetime.strptime(f"{date_str}-01-01", "%Y-%m-%d")
            elif re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', date_str):
                # New DD-MM-YYYY format
                return datetime.strptime(date_str, "%d-%m-%Y")
            else:
                return None
        except ValueError:
            return None
    def get_current_shift(self) -> tuple:
        """Get current shift name and period info"""
        current_time = self.calculate_current_ingame_time()
        if not current_time:
            return None, None
        
        hour = current_time.hour
        if 6 <= hour < 12:
            return "Morning Shift", "morning"
        elif 12 <= hour < 18:
            return "Day Shift", "day"
        elif 18 <= hour < 24:
            return "Evening Shift", "evening"
        else:
            return "Night Shift", "night"

    def get_shift_description(self, shift_period: str) -> str:
        """Get description for shift period"""
        descriptions = {
            "morning": "Colony work shifts are beginning across human space.",
            "day": "Peak operational hours - maximum traffic on all corridors.",
            "evening": "Systems transitioning to night operations.",
            "night": "Minimal activity - most colonies on standby operations."
        }
        return descriptions.get(shift_period, "Standard operations in effect.")

    def detect_shift_change(self, last_check_time: datetime) -> tuple:
        """Detect if a shift change occurred since last check"""
        if not last_check_time:
            return False, None, None
        
        # Get shift at last check
        last_hour = last_check_time.hour
        if 6 <= last_hour < 12:
            last_shift = "morning"
        elif 12 <= last_hour < 18:
            last_shift = "day"
        elif 18 <= last_hour < 24:
            last_shift = "evening"
        else:
            last_shift = "night"
        
        # Get current shift
        current_shift_name, current_shift = self.get_current_shift()
        
        if current_shift != last_shift:
            return True, last_shift, current_shift
        
        return False, None, None
    def parse_datetime_string(self, datetime_str: str) -> Optional[datetime]:
        """Parse DD-MM-YYYY HH:MM format datetime string"""
        try:
            if re.match(r'^\d{1,2}-\d{1,2}-\d{4} \d{1,2}:\d{2}$', datetime_str):
                return datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")
            else:
                return None
        except ValueError:
            return None
    
    def get_galaxy_info(self) -> Optional[Tuple]:
        """Get galaxy information including start date and time scale"""
        return self.db.execute_query(
            """SELECT name, start_date, time_scale_factor, time_started_at, created_at,
                      is_time_paused, time_paused_at, current_ingame_time, is_manually_paused
               FROM galaxy_info WHERE galaxy_id = 1""",
            fetch='one'
        )
    
    def calculate_current_ingame_time(self) -> Optional[datetime]:
        """Calculate current in-game date and time"""
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info:
            return None
            
        name, start_date_str, time_scale, time_started_at, created_at, is_paused, time_paused_at, current_ingame, is_manually_paused = galaxy_info
        
        # Parse start date
        start_date = self.parse_date_string(start_date_str)
        if not start_date:
            return None
        
        # If time is paused, return the stored current time
        if is_paused and current_ingame:
            return safe_datetime_parse(current_ingame)
        
        # Use time_started_at if available, otherwise use created_at
        real_start_time = safe_datetime_parse(time_started_at) if time_started_at else safe_datetime_parse(created_at)
        current_real_time = datetime.now()
        time_scale_factor = time_scale if time_scale else 4.0
        
        # Check if we're resuming from a pause (only if we're not currently paused)
        if not is_paused and time_paused_at and current_ingame:
            # We're resuming from a pause - calculate from the pause point
            base_ingame_time = safe_datetime_parse(current_ingame)
            pause_time = safe_datetime_parse(time_paused_at)
            
            # Add time since resume with current time scale
            elapsed_since_resume = current_real_time - pause_time
            scaled_elapsed = elapsed_since_resume * time_scale_factor
            current_ingame_datetime = base_ingame_time + scaled_elapsed
        else:
            # Normal calculation from start
            elapsed_real_time = current_real_time - real_start_time
            elapsed_ingame_time = elapsed_real_time * time_scale_factor
            current_ingame_datetime = start_date + elapsed_ingame_time
        
        return current_ingame_datetime
    def set_time_scale(self, new_scale: float) -> bool:
        """Set time scale factor and properly rebase the time calculation"""
        # Get current time before changing scale
        current_time = self.calculate_current_ingame_time()
        if not current_time:
            return False
        
        # Update the scale and rebase the calculation
        current_real = datetime.now()
        self.db.execute_query(
            """UPDATE galaxy_info SET 
               time_scale_factor = %s,
               current_ingame_time = %s,
               time_paused_at = %s,
               is_time_paused = false,
               is_manually_paused = false
               WHERE galaxy_id = 1""",
            (new_scale, current_time.isoformat(), current_real.isoformat())
        )
        return True
    def format_ingame_datetime(self, dt: datetime) -> str:
        """Format in-game date and time for display with ISST timezone"""
        date_str = dt.strftime("%d-%m-%Y")
        time_str = dt.strftime("%H:%M")
        
        return f"{date_str} at {time_str} ISST"
    
    def get_days_elapsed(self) -> Optional[int]:
        """Get number of in-game days elapsed since galaxy start"""
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info:
            return None
            
        name, start_date_str, *_ = galaxy_info
        
        start_date = self.parse_date_string(start_date_str)
        if not start_date:
            return None
            
        current_time = self.calculate_current_ingame_time()
        if not current_time:
            return None
            
        return (current_time - start_date).days
    
    def pause_time(self, manual: bool = True) -> bool:
        """Pause the time system"""
        current_ingame = self.calculate_current_ingame_time()
        if not current_ingame:
            return False
        
        current_real = datetime.now()
        self.db.execute_query(
            """UPDATE galaxy_info SET 
               is_time_paused = true, 
               time_paused_at = %s,
               current_ingame_time = %s,
               is_manually_paused = %s
               WHERE galaxy_id = 1""",
            (current_real.isoformat(), current_ingame.isoformat(), manual)
        )
        
        if manual:
            formatted_time = self.format_ingame_datetime(current_ingame)
            print(f"⏸️ MANUAL-PAUSE: Time system manually paused by admin at {formatted_time}")
        
        return True
    
    def resume_time(self) -> bool:
        """Resume the time system (manually by admin)"""
        # Get the current paused time before resuming
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info or not galaxy_info[5]:  # not paused
            return False
        
        current_ingame = galaxy_info[7]  # current_ingame_time
        if not current_ingame:
            return False
        
        current_real = datetime.now()
        self.db.execute_query(
            """UPDATE galaxy_info SET 
               is_time_paused = false,
               time_paused_at = %s,
               current_ingame_time = %s,
               is_manually_paused = false
               WHERE galaxy_id = 1""",
            (current_real.isoformat(), current_ingame)
        )
        
        # Get time scale for logging
        time_scale = galaxy_info[2] if galaxy_info else 4.0
        resume_time_dt = safe_datetime_parse(current_ingame)
        formatted_time = self.format_ingame_datetime(resume_time_dt)
        player_count = self.get_logged_in_player_count()
        
        print(f"▶️ MANUAL-RESUME: Time system manually resumed by admin from {formatted_time}")
        print(f"▶️ MANUAL-RESUME: Time flowing at {time_scale}x speed - {player_count} players online")
        
        return True
    
    def set_current_time(self, new_datetime: datetime) -> bool:
        """Set the current in-game time (must be after start date)"""
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info:
            return False
        
        name, start_date_str, *_ = galaxy_info
        start_date = self.parse_date_string(start_date_str)
        if not start_date:
            return False
        
        # Validate that new time is not before start
        if new_datetime < start_date:
            return False
        
        current_real = datetime.now()
        self.db.execute_query(
            """UPDATE galaxy_info SET 
               current_ingame_time = %s,
               time_paused_at = %s,
               is_time_paused = false,
               is_manually_paused = false
               WHERE galaxy_id = 1""",
            (new_datetime.isoformat(), current_real.isoformat())
        )
        return True
    
    def is_paused(self) -> bool:
        """Check if time system is paused"""
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info:
            return False
        return bool(galaxy_info[5])  # is_time_paused
    
    def is_manually_paused(self) -> bool:
        """Check if time system was manually paused by admin"""
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info:
            return False
        return bool(galaxy_info[8])  # is_manually_paused
    
    def get_logged_in_player_count(self) -> int:
        """Get count of currently logged in players"""
        result = self.db.execute_query(
            "SELECT COUNT(*) FROM characters WHERE is_logged_in = true",
            fetch='one'
        )
        return result[0] if result else 0
    
    def auto_pause_time(self) -> bool:
        """Automatically pause the time system when no players are online"""
        try:
            # Check if already paused
            if self.is_paused():
                print("⏸️ AUTO-PAUSE: Time system already paused, skipping auto-pause")
                return True
            
            # Get current player count
            player_count = self.get_logged_in_player_count()
            print(f"⏸️ AUTO-PAUSE: Checking player count - {player_count} players online")
            
            # If players are still online, don't auto-pause
            if player_count > 0:
                print(f"⏸️ AUTO-PAUSE: Skipping auto-pause - {player_count} players still online")
                return False
            
            # Perform the pause
            current_ingame = self.calculate_current_ingame_time()
            if not current_ingame:
                print("❌ AUTO-PAUSE: Failed to calculate current time for auto-pause")
                return False
            
            current_real = datetime.now()
            self.db.execute_query(
                """UPDATE galaxy_info SET 
                   is_time_paused = true, 
                   time_paused_at = %s,
                   current_ingame_time = %s,
                   is_manually_paused = false
                   WHERE galaxy_id = 1""",
                (current_real.isoformat(), current_ingame.isoformat())
            )
            
            formatted_time = self.format_ingame_datetime(current_ingame)
            print(f"⏸️ AUTO-PAUSE: Time system automatically paused at {formatted_time}")
            print(f"⏸️ AUTO-PAUSE: No players online - time flow suspended to save resources")
            return True
            
        except Exception as e:
            print(f"❌ AUTO-PAUSE: Failed to auto-pause time system: {e}")
            return False
    
    def auto_resume_time(self) -> bool:
        """Automatically resume the time system when players log in"""
        try:
            # Check if manually paused by admin
            if self.is_manually_paused():
                print("▶️ AUTO-RESUME: Time system manually paused by admin - skipping auto-resume")
                return False
            
            # Check if already running
            if not self.is_paused():
                print("▶️ AUTO-RESUME: Time system already running, skipping auto-resume")
                return True
            
            # Get current player count
            player_count = self.get_logged_in_player_count()
            print(f"▶️ AUTO-RESUME: Player logged in - {player_count} players now online")
            
            # Get the current paused time before resuming
            galaxy_info = self.get_galaxy_info()
            if not galaxy_info or not galaxy_info[5]:  # not paused
                print("▶️ AUTO-RESUME: Time system not paused, no resume needed")
                return False
            
            current_ingame = galaxy_info[7]  # current_ingame_time
            if not current_ingame:
                print("❌ AUTO-RESUME: No stored pause time found for auto-resume")
                return False
            
            current_real = datetime.now()
            self.db.execute_query(
                """UPDATE galaxy_info SET 
                   is_time_paused = false,
                   time_paused_at = %s,
                   current_ingame_time = %s,
                   is_manually_paused = false
                   WHERE galaxy_id = 1""",
                (current_real.isoformat(), current_ingame)
            )
            
            # Get time scale for logging
            time_scale = galaxy_info[2] if galaxy_info else 4.0
            resume_time = safe_datetime_parse(current_ingame)
            formatted_time = self.format_ingame_datetime(resume_time)
            
            print(f"▶️ AUTO-RESUME: Time system automatically resumed from {formatted_time}")
            print(f"▶️ AUTO-RESUME: Time flowing at {time_scale}x speed - {player_count} players online")
            return True
            
        except Exception as e:
            print(f"❌ AUTO-RESUME: Failed to auto-resume time system: {e}")
            return False