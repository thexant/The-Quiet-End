# utils/time_system.py
from datetime import datetime, timedelta
from typing import Optional, Tuple
import re

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
                      is_time_paused, time_paused_at, current_ingame_time
               FROM galaxy_info WHERE galaxy_id = 1""",
            fetch='one'
        )
    
    def calculate_current_ingame_time(self) -> Optional[datetime]:
        """Calculate current in-game date and time"""
        galaxy_info = self.get_galaxy_info()
        if not galaxy_info:
            return None
            
        name, start_date_str, time_scale, time_started_at, created_at, is_paused, paused_at, current_ingame = galaxy_info
        
        # Parse start date
        start_date = self.parse_date_string(start_date_str)
        if not start_date:
            return None
        
        # If time is paused, return the stored current time
        if is_paused and current_ingame:
            return datetime.fromisoformat(current_ingame)
        
        # Use time_started_at if available, otherwise use created_at
        real_start_time = datetime.fromisoformat(time_started_at) if time_started_at else datetime.fromisoformat(created_at)
        
        # Calculate elapsed real time since galaxy creation (or since unpause)
        current_real_time = datetime.now()
        
        # If we were paused, we need to account for the pause time
        if paused_at and current_ingame:
            # Start from where we paused
            base_ingame_time = datetime.fromisoformat(current_ingame)
            # Add time since unpause
            elapsed_since_unpause = current_real_time - datetime.fromisoformat(paused_at)
            time_scale_factor = time_scale if time_scale else 4.0
            scaled_elapsed = elapsed_since_unpause * time_scale_factor
            current_ingame_datetime = base_ingame_time + scaled_elapsed
        else:
            # Normal calculation from start
            elapsed_real_time = current_real_time - real_start_time
            time_scale_factor = time_scale if time_scale else 4.0
            elapsed_ingame_time = elapsed_real_time * time_scale_factor
            current_ingame_datetime = start_date + elapsed_ingame_time
        
        return current_ingame_datetime
    
    def format_ingame_datetime(self, dt: datetime) -> str:
        """Format in-game date and time for display with ISST timezone"""
        date_str = dt.strftime("%d-%m-%Y")
        time_str = dt.strftime("%H:%M")
        
        return f"**{date_str}** at **{time_str} ISST**"
    
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
    
    def pause_time(self) -> bool:
        """Pause the time system"""
        current_ingame = self.calculate_current_ingame_time()
        if not current_ingame:
            return False
        
        current_real = datetime.now()
        self.db.execute_query(
            """UPDATE galaxy_info SET 
               is_time_paused = 1, 
               time_paused_at = ?,
               current_ingame_time = ?
               WHERE galaxy_id = 1""",
            (current_real.isoformat(), current_ingame.isoformat())
        )
        return True
    
    def resume_time(self) -> bool:
        """Resume the time system"""
        current_real = datetime.now()
        self.db.execute_query(
            """UPDATE galaxy_info SET 
               is_time_paused = 0,
               time_paused_at = ?
               WHERE galaxy_id = 1""",
            (current_real.isoformat(),)
        )
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
               current_ingame_time = ?,
               time_paused_at = ?,
               is_time_paused = 0
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