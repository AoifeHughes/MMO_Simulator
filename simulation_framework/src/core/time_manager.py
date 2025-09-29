from __future__ import annotations
from typing import Dict, Any
from datetime import datetime, timedelta


class TimeManager:
    """Manages simulation time and tick progression"""

    def __init__(self):
        self.current_tick = 0
        self.start_time = datetime.now()

        # Game time configuration
        # 1 tick = 1 game minute by default
        # 1 game day = 1440 ticks (24 * 60)
        # 1 game hour = 60 ticks
        self.ticks_per_game_hour = 60
        self.ticks_per_game_day = 1440

    def tick(self) -> None:
        """Advance time by one tick"""
        self.current_tick += 1

    def reset(self) -> None:
        """Reset the time manager to initial state"""
        self.current_tick = 0
        self.start_time = datetime.now()

    def get_game_time(self) -> Dict[str, Any]:
        """Get current game time representation"""
        total_minutes = self.current_tick

        days = total_minutes // self.ticks_per_game_day
        remaining_minutes = total_minutes % self.ticks_per_game_day

        hours = remaining_minutes // self.ticks_per_game_hour
        minutes = remaining_minutes % self.ticks_per_game_hour

        return {
            'tick': self.current_tick,
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'time_string': f"Day {days}, {hours:02d}:{minutes:02d}"
        }

    def get_elapsed_real_time(self) -> timedelta:
        """Get elapsed real-world time since simulation start"""
        return datetime.now() - self.start_time

    def ticks_since(self, past_tick: int) -> int:
        """Get number of ticks since a past tick"""
        return max(0, self.current_tick - past_tick)

    def is_day_time(self) -> bool:
        """Check if it's day time in the game world"""
        game_time = self.get_game_time()
        hour = game_time['hours']
        return 6 <= hour < 18  # Day time is 6 AM to 6 PM

    def is_night_time(self) -> bool:
        """Check if it's night time in the game world"""
        return not self.is_day_time()

    def get_time_of_day_modifier(self) -> float:
        """Get time of day modifier for various activities"""
        game_time = self.get_game_time()
        hour = game_time['hours']

        # Activities are easier during day time
        if 8 <= hour < 16:  # Prime day time
            return 1.0
        elif 6 <= hour < 8 or 16 <= hour < 18:  # Early morning / late afternoon
            return 0.9
        elif 18 <= hour < 22:  # Evening
            return 0.8
        else:  # Night time
            return 0.7

    def __str__(self) -> str:
        """String representation of current time"""
        game_time = self.get_game_time()
        elapsed = self.get_elapsed_real_time()

        return (f"Tick {self.current_tick} ({game_time['time_string']}) "
                f"- Real time elapsed: {elapsed}")

    def __repr__(self) -> str:
        return f"TimeManager(tick={self.current_tick})"