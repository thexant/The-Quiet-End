# utils/home_income_calculator.py
import asyncio
from datetime import datetime
from typing import Optional

class HomeIncomeCalculator:
    """Handles passive income calculation for homes"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.running = False
    
    async def start(self):
        """Start the income calculation loop"""
        self.running = True
        self.bot.loop.create_task(self._income_loop())
    
    async def stop(self):
        """Stop the income calculation loop"""
        self.running = False
    
    async def _income_loop(self):
        """Main loop that calculates income every hour"""
        await self.bot.wait_until_ready()
        
        while self.running:
            try:
                await self._calculate_all_income()
            except Exception as e:
                print(f"Error in income calculation: {e}")
            
            # Wait 1 hour before next calculation
            await asyncio.sleep(3600)
    
    async def _calculate_all_income(self):
        """Calculate income for all homes with upgrades"""
        from utils.time_system import TimeSystem
        from utils.datetime_utils import safe_datetime_parse
        time_system = TimeSystem(self.bot)
        
        # Get all homes with income-generating upgrades
        homes_with_income = self.db.execute_query(
            '''SELECT DISTINCT h.home_id, i.last_calculated, i.accumulated_income
               FROM home_upgrades h
               LEFT JOIN home_income i ON h.home_id = i.home_id
               WHERE h.daily_income > 0''',
            fetch='all'
        )
        
        current_time = time_system.calculate_current_ingame_time()
        if not current_time:
            return
        
        for home_id, last_calculated_str, current_accumulated in homes_with_income:
            # Get total daily income for this home
            total_daily = self.db.execute_query(
                "SELECT SUM(daily_income) FROM home_upgrades WHERE home_id = %s",
                (home_id,),
                fetch='one'
            )[0]
            
            if not total_daily:
                continue
            
            # Calculate time passed
            if last_calculated_str:
                last_calculated = safe_datetime_parse(last_calculated_str)
                days_passed = (current_time - last_calculated).total_seconds() / 86400
            else:
                days_passed = 0
                current_accumulated = 0
            
            # Calculate new income (cap total accumulation at 7 days)
            new_income = int(total_daily * days_passed)
            total_accumulated = current_accumulated + new_income
            
            # Cap at 7 days worth
            max_income = total_daily * 7
            if total_accumulated > max_income:
                total_accumulated = max_income
            
            # Update or insert income record
            self.db.execute_query(
                '''INSERT INTO home_income 
                   (home_id, accumulated_income, last_collected, last_calculated)
                   VALUES (%s, %s, NOW(), %s)
                   ON CONFLICT (home_id) DO UPDATE SET 
                   accumulated_income = EXCLUDED.accumulated_income,
                   last_calculated = EXCLUDED.last_calculated''',
                (home_id, total_accumulated, current_time.isoformat())
            )

